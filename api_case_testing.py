import csv
import html
import json
import logging
import os
import webbrowser
from datetime import datetime
from urllib.parse import urlsplit

import requests


API_CASE_RESULT_HEADERS = [
    "timestamp",
    "case_id",
    "case_name",
    "case_category",
    "priority",
    "api_name",
    "method",
    "path",
    "status",
    "expected_http_status",
    "actual_http_status",
    "expected_result_type",
    "actual_result_type",
    "request_payload",
    "response_headers",
    "blocked_by_link",
    "rfc_7725_check",
    "response_body",
    "assertion_summary",
    "error_message"
]


class ApiCaseTestError(Exception):
    pass


class ApiCaseRunner:
    def __init__(self, base_url, api_key, log_dir):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.log_dir = log_dir
        self.api_registry = {
            "chat_completions": self._execute_chat_completions
        }

    def run_case_file(self, case_file):
        os.makedirs(self.log_dir, exist_ok=True)
        case_rows = self._load_case_rows(case_file)
        result_file = self._create_result_file()
        results = []

        with open(result_file, "w", newline="", encoding="utf-8-sig") as result_handle:
            writer = csv.DictWriter(result_handle, fieldnames=API_CASE_RESULT_HEADERS)
            writer.writeheader()

            for case in case_rows:
                result = self._run_single_case(case)
                writer.writerow(result)
                result_handle.flush()
                results.append(result)

        analysis = self._analyze_case_results(results)
        report_file = self._generate_case_report_html(analysis, result_file, case_file)
        return result_file, report_file, analysis

    def _load_case_rows(self, case_file):
        with open(case_file, "r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            required_headers = [
                "case_id",
                "enabled",
                "case_name",
                "api_name",
                "method",
                "path",
                "request_payload",
                "expected_http_status",
                "expected_result_type"
            ]
            if not reader.fieldnames:
                raise ApiCaseTestError(f"用例文件缺少表头: {case_file}")
            missing_headers = [header for header in required_headers if header not in reader.fieldnames]
            if missing_headers:
                raise ApiCaseTestError(f"用例文件缺少字段 {missing_headers}: {case_file}")

            rows = []
            for row in reader:
                if str(row.get("enabled", "")).strip().upper() != "Y":
                    continue
                rows.append(row)

        if not rows:
            raise ApiCaseTestError(f"未在用例文件中读取到启用的测试用例: {case_file}")
        return rows

    def _create_result_file(self):
        return os.path.join(
            self.log_dir,
            f"hulk_gateway_api_case_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

    def _run_single_case(self, case):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        case_id = case.get("case_id", "")
        case_name = case.get("case_name", "")
        case_category = case.get("case_category", "")
        priority = case.get("priority", "")
        api_name = case.get("api_name", "")
        method = case.get("method", "POST")
        path = case.get("path", "")
        expected_http_status = self._safe_int(case.get("expected_http_status"))
        expected_result_type = (case.get("expected_result_type") or "").strip()
        request_payload_text = case.get("request_payload", "")

        actual_http_status = ""
        response_headers_text = ""
        blocked_by_link = ""
        rfc_7725_check = ""
        response_body_text = ""
        actual_result_type = ""
        assertion_summary = []
        error_message = ""
        status = "success"

        try:
            payload = json.loads(request_payload_text) if request_payload_text else {}
            response = self._dispatch_api_request(api_name, method, path, payload, case)
            actual_http_status = response.status_code
            response_headers_text = json.dumps(dict(response.headers), ensure_ascii=False)
            response_json = self._safe_response_json(response)
            response_body_text = json.dumps(response_json, ensure_ascii=False)
            actual_result_type = self._detect_result_type(response_json, actual_http_status)

            blocked_by_link = self._extract_blocked_by_link(response.headers)
            if actual_http_status == 451:
                rfc_7725_check = self._check_451_requirements(response.headers, response_json)
                assertion_summary.append(f"451专项检查: {rfc_7725_check}")

            self._assert_equal(expected_http_status, actual_http_status, "HTTP 状态码")
            self._assert_equal(expected_result_type, actual_result_type, "结果类型")
            self._assert_required_fields(response_json, case.get("expected_required_fields", ""))
            self._assert_field_types(response_json, case.get("expected_field_types", ""))
            self._assert_field_values(response_json, case.get("expected_field_values", ""))
            self._assert_non_empty_arrays(response_json, case.get("expected_array_non_empty_fields", ""))
            self._assert_validation_error_fields(
                response_json,
                case.get("expected_error_loc", ""),
                case.get("expected_error_type", ""),
                case.get("expected_error_msg_contains", ""),
                case.get("expected_error_input", "")
            )
            assertion_summary.append("全部断言通过")
        except Exception as err:
            status = "error"
            error_message = f"{type(err).__name__}: {err}"
            logging.exception("API 用例执行失败: %s - %s", case_id, case_name)
            if not response_body_text:
                response_body_text = ""
            if not actual_result_type:
                actual_result_type = "request_error"
            if not assertion_summary:
                assertion_summary.append("执行或断言失败")

        return {
            "timestamp": timestamp,
            "case_id": case_id,
            "case_name": case_name,
            "case_category": case_category,
            "priority": priority,
            "api_name": api_name,
            "method": method,
            "path": path,
            "status": status,
            "expected_http_status": expected_http_status,
            "actual_http_status": actual_http_status,
            "expected_result_type": expected_result_type,
            "actual_result_type": actual_result_type,
            "request_payload": request_payload_text,
            "response_headers": response_headers_text,
            "blocked_by_link": blocked_by_link,
            "rfc_7725_check": rfc_7725_check,
            "response_body": response_body_text,
            "assertion_summary": " | ".join(assertion_summary),
            "error_message": error_message
        }

    def _dispatch_api_request(self, api_name, method, path, payload, case):
        if api_name not in self.api_registry:
            raise ApiCaseTestError(f"未注册的 API 名称: {api_name}")
        return self.api_registry[api_name](method, path, payload, case)

    def _execute_chat_completions(self, method, path, payload, case):
        return self._request_json(method, path, payload)

    def _request_json(self, method, path, payload):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        url = self._build_request_url(path)
        response = requests.request(method.upper(), url, headers=headers, json=payload)
        return response

    def _build_request_url(self, path):
        normalized_path = "/" + str(path or "").lstrip("/")
        base_parts = urlsplit(self.base_url)
        base_path = (base_parts.path or "").rstrip("/")

        if base_path and normalized_path == base_path:
            final_path = base_path
        elif base_path and normalized_path.startswith(base_path + "/"):
            final_path = normalized_path
        else:
            final_path = f"{base_path}{normalized_path}" if base_path else normalized_path

        return f"{base_parts.scheme}://{base_parts.netloc}{final_path}"

    def _safe_response_json(self, response):
        try:
            return response.json()
        except ValueError:
            return {"raw_text": response.text}

    def _detect_result_type(self, response_json, actual_http_status):
        if isinstance(response_json, dict) and "detail" in response_json:
            return "validation_error"
        if isinstance(actual_http_status, int) and 200 <= actual_http_status < 300:
            return "success"
        if actual_http_status == 451:
            return "blocked_by_law"
        return "error"

    def _extract_blocked_by_link(self, response_headers):
        link_header = response_headers.get("Link", "")
        if not link_header:
            return ""

        for link_item in [item.strip() for item in link_header.split(",") if item.strip()]:
            if 'rel="blocked-by"' in link_item or "rel=blocked-by" in link_item:
                start_index = link_item.find("<")
                end_index = link_item.find(">", start_index + 1)
                if start_index != -1 and end_index != -1:
                    return link_item[start_index + 1:end_index]
                return link_item
        return ""

    def _check_451_requirements(self, response_headers, response_json):
        issues = []

        blocked_by_link = self._extract_blocked_by_link(response_headers)
        if not blocked_by_link:
            issues.append("缺少 Link 响应头或未包含 rel=blocked-by")

        response_text = json.dumps(response_json, ensure_ascii=False) if not isinstance(response_json, str) else response_json
        required_keywords_groups = [
            ["原因", "屏蔽", "拒绝", "blocked"],
            ["法律", "合规", "政策", "law", "policy"],
            ["申诉", "渠道", "appeal", "contact"]
        ]

        group_names = ["核心原因", "法律依据/合规政策", "申诉渠道"]
        for index, keywords in enumerate(required_keywords_groups):
            if not any(keyword in response_text for keyword in keywords):
                issues.append(f"响应体缺少{group_names[index]}说明")

        if issues:
            return "不符合 RFC 7725: " + "；".join(issues)
        return "符合 RFC 7725"

    def _assert_required_fields(self, response_json, required_fields_text):
        for field_path in self._split_values(required_fields_text):
            value = self._get_value_by_path(response_json, field_path)
            if value is None:
                raise AssertionError(f"缺少必需字段: {field_path}")

    def _assert_field_types(self, response_json, field_types_text):
        type_mapping = {
            "string": str,
            "integer": int,
            "array": list,
            "object": dict,
            "number": (int, float),
            "boolean": bool
        }
        for item in self._split_values(field_types_text):
            if ":" not in item:
                continue
            field_path, expected_type_name = item.split(":", 1)
            field_path = field_path.strip()
            expected_type_name = expected_type_name.strip()
            value = self._get_value_by_path(response_json, field_path)
            if value is None:
                raise AssertionError(f"字段不存在，无法校验类型: {field_path}")
            expected_type = type_mapping.get(expected_type_name)
            if expected_type is None:
                raise AssertionError(f"不支持的类型断言: {expected_type_name}")
            if expected_type_name == "integer" and isinstance(value, bool):
                raise AssertionError(f"字段类型不匹配: {field_path} 期望 {expected_type_name}，实际 bool")
            if not isinstance(value, expected_type):
                raise AssertionError(f"字段类型不匹配: {field_path} 期望 {expected_type_name}，实际 {type(value).__name__}")

    def _assert_field_values(self, response_json, field_values_text):
        for item in self._split_values(field_values_text):
            if "=" not in item:
                continue
            field_path, expected_value = item.split("=", 1)
            field_path = field_path.strip()
            expected_value = expected_value.strip()
            actual_value = self._get_value_by_path(response_json, field_path)
            if str(actual_value) != expected_value:
                raise AssertionError(f"字段值不匹配: {field_path} 期望 {expected_value}，实际 {actual_value}")

    def _assert_non_empty_arrays(self, response_json, array_fields_text):
        for field_path in self._split_values(array_fields_text):
            value = self._get_value_by_path(response_json, field_path)
            if not isinstance(value, list) or not value:
                raise AssertionError(f"字段不是非空数组: {field_path}")

    def _assert_validation_error_fields(self, response_json, expected_error_loc, expected_error_type, expected_error_msg_contains, expected_error_input):
        if not any([expected_error_loc, expected_error_type, expected_error_msg_contains, expected_error_input]):
            return

        detail = self._get_value_by_path(response_json, "detail")
        if not isinstance(detail, list) or not detail:
            raise AssertionError("失败响应缺少 detail 数组")

        first_error = detail[0]
        if expected_error_loc:
            actual_loc = self._get_value_by_path(response_json, "detail.0.loc")
            normalized_loc = self._normalize_loc(actual_loc)
            expected_locs = self._split_values(expected_error_loc)
            if expected_locs and normalized_loc not in expected_locs:
                raise AssertionError(f"错误定位不匹配: 期望 {expected_error_loc}，实际 {normalized_loc}")

        if expected_error_type:
            actual_type = str(first_error.get("type"))
            expected_types = self._split_values(expected_error_type)
            if expected_types and actual_type not in expected_types:
                raise AssertionError(f"错误类型不匹配: 期望 {expected_error_type}，实际 {actual_type}")

        if expected_error_msg_contains:
            actual_msg = str(first_error.get("msg", ""))
            expected_messages = self._split_values(expected_error_msg_contains)
            if expected_messages and not any(message in actual_msg for message in expected_messages):
                raise AssertionError(f"错误消息不包含预期关键字: {expected_error_msg_contains}")

        if expected_error_input:
            actual_input = first_error.get("input")
            expected_inputs = self._split_values(expected_error_input)
            if expected_inputs and str(actual_input) not in expected_inputs:
                raise AssertionError(f"错误输入值不匹配: 期望 {expected_error_input}，实际 {actual_input}")

    def _normalize_loc(self, loc_value):
        if isinstance(loc_value, list):
            if loc_value and str(loc_value[0]) == "body":
                loc_value = loc_value[1:]
            return ".".join(str(item) for item in loc_value)
        return str(loc_value)

    def _get_value_by_path(self, data, field_path):
        if field_path == "":
            return None
        current = data
        for part in field_path.split("."):
            if isinstance(current, list):
                if not part.isdigit():
                    return None
                index = int(part)
                if index >= len(current):
                    return None
                current = current[index]
            elif isinstance(current, dict):
                if part not in current:
                    return None
                current = current[part]
            else:
                return None
        return current

    def _split_values(self, text):
        if not text:
            return []
        return [item.strip() for item in str(text).split("|") if item.strip()]

    def _safe_int(self, value):
        if value in [None, ""]:
            return ""
        return int(value)

    def _assert_equal(self, expected, actual, field_name):
        if expected == "":
            return
        if expected != actual:
            raise AssertionError(f"{field_name}不匹配: 期望 {expected}，实际 {actual}")

    def _analyze_case_results(self, results):
        analysis = {
            "report_generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "test_start_time": results[0]["timestamp"] if results else "",
            "test_end_time": results[-1]["timestamp"] if results else "",
            "total_count": len(results),
            "success_count": 0,
            "error_count": 0,
            "overall_success_rate": 0.0,
            "api_stats": {},
            "category_stats": {},
            "error_stats": {},
            "failed_cases": [],
            "status_code_stats": {},
            "http_451_cases": [],
            "summary": []
        }

        for result in results:
            status = result["status"]
            api_name = result["api_name"]
            category = result["case_category"] or (result["case_id"].split("-", 1)[0] if result["case_id"] else "UNKNOWN")
            status_code = str(result.get("actual_http_status", ""))

            if status_code:
                analysis["status_code_stats"][status_code] = analysis["status_code_stats"].get(status_code, 0) + 1
            if status_code == "451":
                analysis["http_451_cases"].append(result)

            if status == "success":
                analysis["success_count"] += 1
            else:
                analysis["error_count"] += 1
                error_key = result["error_message"].split(":", 1)[0] if result["error_message"] else "UnknownError"
                analysis["error_stats"][error_key] = analysis["error_stats"].get(error_key, 0) + 1
                analysis["failed_cases"].append(result)

            api_stats = analysis["api_stats"].setdefault(api_name, {"total": 0, "success": 0, "error": 0, "success_rate": 0.0})
            api_stats["total"] += 1
            api_stats[status] += 1

            category_stats = analysis["category_stats"].setdefault(category, {"total": 0, "success": 0, "error": 0, "success_rate": 0.0})
            category_stats["total"] += 1
            category_stats[status] += 1

        if analysis["total_count"]:
            analysis["overall_success_rate"] = analysis["success_count"] / analysis["total_count"] * 100

        for stats in list(analysis["api_stats"].values()) + list(analysis["category_stats"].values()):
            if stats["total"]:
                stats["success_rate"] = stats["success"] / stats["total"] * 100

        analysis["summary"].append(
            f"本次共执行 {analysis['total_count']} 条 API 用例，成功 {analysis['success_count']} 条，失败 {analysis['error_count']} 条，整体成功率 {analysis['overall_success_rate']:.2f}% 。"
        )
        if analysis["error_stats"]:
            top_error = sorted(analysis["error_stats"].items(), key=lambda item: (-item[1], item[0]))[0]
            analysis["summary"].append(f"最常见错误类型为 {top_error[0]}，共出现 {top_error[1]} 次。")
        else:
            analysis["summary"].append("所有 API 用例均执行成功。")

        if analysis["http_451_cases"]:
            compliant_count = sum(1 for case in analysis["http_451_cases"] if case.get("rfc_7725_check") == "符合 RFC 7725")
            analysis["summary"].append(
                f"检测到 {len(analysis['http_451_cases'])} 条 451 响应，其中 {compliant_count} 条符合 RFC 7725，{len(analysis['http_451_cases']) - compliant_count} 条需要进一步检查 Link 头或响应体说明。"
            )

        return analysis

    def _generate_case_report_html(self, analysis, result_file, case_file):
        report_file = os.path.join(
            self.log_dir,
            f"hulk_gateway_api_case_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        )

        def build_stats_rows(stats_dict):
            if not stats_dict:
                return "<tr><td colspan='5'>暂无数据</td></tr>"
            rows = []
            for name, stats in sorted(stats_dict.items(), key=lambda item: item[0]):
                rows.append(
                    f"<tr><td>{html.escape(str(name))}</td><td>{stats['total']}</td><td>{stats['success']}</td><td>{stats['error']}</td><td>{stats['success_rate']:.2f}%</td></tr>"
                )
            return "".join(rows)

        def build_simple_rows(stats_dict):
            if not stats_dict:
                return "<tr><td colspan='2'>暂无数据</td></tr>"
            rows = []
            for name, count in sorted(stats_dict.items(), key=lambda item: (-item[1], item[0])):
                rows.append(f"<tr><td>{html.escape(str(name))}</td><td>{count}</td></tr>")
            return "".join(rows)

        def build_451_rows(cases):
            if not cases:
                return "<tr><td colspan='6'>未检测到 451 响应</td></tr>"
            rows = []
            for case in cases:
                rows.append(
                    "<tr>"
                    f"<td>{html.escape(str(case.get('case_id', '')))}</td>"
                    f"<td>{html.escape(str(case.get('case_name', '')))}</td>"
                    f"<td>{html.escape(str(case.get('actual_http_status', '')))}</td>"
                    f"<td>{html.escape(str(case.get('blocked_by_link', '')))}</td>"
                    f"<td>{html.escape(str(case.get('rfc_7725_check', '')))}</td>"
                    f"<td><pre>{html.escape(str(case.get('response_body', '')))}</pre></td>"
                    "</tr>"
                )
            return "".join(rows)

        def build_failed_case_rows(failed_cases):
            if not failed_cases:
                return "<tr><td colspan='13'>没有失败用例</td></tr>"

            rows = []
            for case in failed_cases:
                rows.append(
                    "<tr>"
                    f"<td>{html.escape(str(case.get('case_id', '')))}</td>"
                    f"<td>{html.escape(str(case.get('case_name', '')))}</td>"
                    f"<td>{html.escape(str(case.get('api_name', '')))}</td>"
                    f"<td>{html.escape(str(case.get('status', '')))}</td>"
                    f"<td>{html.escape(str(case.get('expected_http_status', '')))}</td>"
                    f"<td>{html.escape(str(case.get('actual_http_status', '')))}</td>"
                    f"<td>{html.escape(str(case.get('blocked_by_link', '')))}</td>"
                    f"<td>{html.escape(str(case.get('rfc_7725_check', '')))}</td>"
                    f"<td><pre>{html.escape(str(case.get('request_payload', '')))}</pre></td>"
                    f"<td><pre>{html.escape(str(case.get('response_headers', '')))}</pre></td>"
                    f"<td><pre>{html.escape(str(case.get('response_body', '')))}</pre></td>"
                    f"<td>{html.escape(str(case.get('assertion_summary', '')))}</td>"
                    f"<td>{html.escape(str(case.get('error_message', '')))}</td>"
                    "</tr>"
                )
            return "".join(rows)

        summary_html = "".join(f"<li>{html.escape(item)}</li>" for item in analysis["summary"])

        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Hulk Gateway API 用例测试分析报告</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 24px; background: #f7f9fc; color: #1f2937; }}
        h1, h2 {{ color: #111827; }}
        .card {{ background: #ffffff; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08); }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
        th, td {{ border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; vertical-align: top; }}
        th {{ background: #eef2ff; }}
        .metric {{ display: inline-block; min-width: 220px; margin-right: 16px; margin-bottom: 8px; }}
        .path {{ color: #2563eb; word-break: break-all; }}
        pre {{ white-space: pre-wrap; word-break: break-word; margin: 0; font-family: Consolas, monospace; max-width: 420px; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>Hulk Gateway API 用例测试分析报告</h1>
        <p class="path">用例文件：{html.escape(case_file)}</p>
        <p class="path">结果文件：{html.escape(result_file)}</p>
        <div class="metric">报告生成时间：{html.escape(analysis['report_generated_at'])}</div>
        <div class="metric">测试开始时间：{html.escape(analysis['test_start_time'] or '暂无数据')}</div>
        <div class="metric">测试结束时间：{html.escape(analysis['test_end_time'] or '暂无数据')}</div>
        <br>
        <div class="metric">总用例数：{analysis['total_count']}</div>
        <div class="metric">成功数：{analysis['success_count']}</div>
        <div class="metric">失败数：{analysis['error_count']}</div>
        <div class="metric">整体成功率：{analysis['overall_success_rate']:.2f}%</div>
    </div>

    <div class="card">
        <h2>测试结论摘要</h2>
        <ul>{summary_html}</ul>
    </div>

    <div class="card">
        <h2>按 API 统计</h2>
        <table>
            <tr><th>API 名称</th><th>总数</th><th>成功</th><th>失败</th><th>成功率</th></tr>
            {build_stats_rows(analysis['api_stats'])}
        </table>
    </div>

    <div class="card">
        <h2>按用例前缀统计</h2>
        <table>
            <tr><th>分类</th><th>总数</th><th>成功</th><th>失败</th><th>成功率</th></tr>
            {build_stats_rows(analysis['category_stats'])}
        </table>
    </div>

    <div class="card">
        <h2>错误类型分布</h2>
        <table>
            <tr><th>错误类型</th><th>出现次数</th></tr>
            {build_simple_rows(analysis['error_stats'])}
        </table>
    </div>

    <div class="card">
        <h2>HTTP 状态码分布</h2>
        <table>
            <tr><th>状态码</th><th>出现次数</th></tr>
            {build_simple_rows(analysis['status_code_stats'])}
        </table>
    </div>

    <div class="card">
        <h2>451 响应专项检查</h2>
        <table>
            <tr>
                <th>用例编号</th>
                <th>用例名称</th>
                <th>实际状态码</th>
                <th>blocked-by Link</th>
                <th>RFC 7725 检查结果</th>
                <th>响应体</th>
            </tr>
            {build_451_rows(analysis['http_451_cases'])}
        </table>
    </div>

    <div class="card">
        <h2>失败用例明细</h2>
        <table>
            <tr>
                <th>用例编号</th>
                <th>用例名称</th>
                <th>API 名称</th>
                <th>状态</th>
                <th>预期状态码</th>
                <th>实际状态码</th>
                <th>blocked-by Link</th>
                <th>RFC 7725 检查</th>
                <th>请求体</th>
                <th>响应头</th>
                <th>响应体</th>
                <th>断言摘要</th>
                <th>错误信息</th>
            </tr>
            {build_failed_case_rows(analysis['failed_cases'])}
        </table>
    </div>
</body>
</html>
"""

        with open(report_file, "w", encoding="utf-8") as html_file:
            html_file.write(html_content)
        return report_file


def run_api_case_testing(base_url, api_key, case_file, log_dir):
    runner = ApiCaseRunner(base_url=base_url, api_key=api_key, log_dir=log_dir)
    result_file, report_file, analysis = runner.run_case_file(case_file)
    print(f"API 用例结果文件: {result_file}")
    print(f"API 用例分析报告: {report_file}")
    try:
        opened = webbrowser.open(f"file://{os.path.abspath(report_file)}")
        if opened:
            print(f"已在默认浏览器中打开 API 用例分析报告: {report_file}")
        else:
            print(f"未能自动打开浏览器，请手动打开 API 用例分析报告: {report_file}")
    except Exception as err:
        print(f"自动打开 API 用例分析报告失败: {type(err).__name__}: {err}")
    return result_file, report_file, analysis
