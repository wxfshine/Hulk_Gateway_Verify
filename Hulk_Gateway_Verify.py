import requests
import logging
import sys
import atexit
import os
import csv
import html
import webbrowser
from datetime import datetime

# 1. 基础配置
base_url = "http://hulk.cmit.local:18080/v1"  # 你的LLM Gateway地址
api_key = "eyJhbGciOiJIUzUxMiIsImlhdCI6MTc3OTA5MDczOSwiZXhwIjoxNzg2ODY2NzM5fQ.eyJpZCI6NzE2LCJuYW1lIjoid2FuZ3hmIiwic291cmNlIjoibGRhcCIsImV4dGVybmFsX2lkIjoie2VjYWE5ZGVkLWI2MzMtNGNmOC05Y2Q5LWQxZGE4MTYyYWFhYn0iLCJyb2xlIjoiVXNlciJ9.M_lPymDGllUI0BaMULupNQ8HaWa9G0zYfRgm5AGz8KBaBuBTcru472vOZilgULdROivMsRJmCxVlNkL81nvlfw"  # 从POST /v1/api-keys拿到的Key

EMBEDDING_MODEL_NAMES = {
    "dengcao/Qwen3-Embedding-4B:Q4_K_M",
    "text-embedding-nomic-embed-text-v1.5"
}

CHAT_MODEL_NAMES = {
    "Qwen3.6-35B-A3B",
    "deepseek-ocr",
    "gemma-4-31B-it",
    "gemma4-26b-a4b",
    "llama3.2",
    "qwen3-14b-awq"
}


class TeeStream:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, message):
        for stream in self.streams:
            stream.write(message)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


def setup_logging():
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"hulk_gateway_verify_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    log_handle = open(log_file, "w", encoding="utf-8")

    original_stdout = sys.stdout
    original_stderr = sys.stderr

    sys.stdout = TeeStream(original_stdout, log_handle)
    sys.stderr = TeeStream(original_stderr, log_handle)

    def cleanup_logging():
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        log_handle.close()

    atexit.register(cleanup_logging)

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            original_stderr.write("程序被手动中断。\n")
            original_stderr.flush()
            log_handle.write("程序被手动中断。\n")
            log_handle.flush()
            return

        logging.error("程序发生未捕获异常", exc_info=(exc_type, exc_value, exc_traceback))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    sys.excepthook = handle_exception

    print(f"日志文件: {log_file}")
    return log_handle


def create_result_writer():
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
    os.makedirs(log_dir, exist_ok=True)
    result_file = os.path.join(log_dir, f"hulk_gateway_verify_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    result_handle = open(result_file, "w", newline="", encoding="utf-8-sig")
    writer = csv.writer(result_handle)
    writer.writerow(["timestamp", "status", "model_name", "compliance_check", "input_content", "api_name", "result_or_error"])
    result_handle.flush()

    def cleanup_result_file():
        result_handle.close()

    atexit.register(cleanup_result_file)
    print(f"结果表格文件: {result_file}")
    return writer, result_handle, result_file


def format_result(result):
    if isinstance(result, list):
        preview = result[:10]
        return f"向量长度: {len(result)}, 前10项: {preview}"
    return str(result)


def record_test_result(writer, result_handle, status, model_name, compliance_check, input_content, api_name, result_or_error):
    writer.writerow([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status,
        model_name,
        compliance_check,
        input_content,
        api_name,
        result_or_error
    ])
    result_handle.flush()


def analyze_test_results(result_file):
    analysis = {
        "report_generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "test_start_time": "",
        "test_end_time": "",
        "total_count": 0,
        "success_count": 0,
        "error_count": 0,
        "overall_success_rate": 0.0,
        "api_stats": {},
        "model_stats": {},
        "compliance_stats": {},
        "error_type_stats": {},
        "input_error_stats": {},
        "feedback_stats": {
            "total_count": 0,
            "success_count": 0,
            "error_count": 0,
            "success_rate": 0.0
        },
        "mismatch_records": [],
        "summary": []
    }

    with open(result_file, "r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)

    if rows:
        analysis["test_start_time"] = rows[0]["timestamp"]
        analysis["test_end_time"] = rows[-1]["timestamp"]

    for row in rows:
        status = row["status"]
        model_name = row["model_name"]
        api_name = row["api_name"]
        compliance_check = str(row["compliance_check"])
        input_content = row["input_content"]
        result_or_error = row["result_or_error"]

        analysis["total_count"] += 1
        if status == "success":
            analysis["success_count"] += 1
        else:
            analysis["error_count"] += 1

        api_stats = analysis["api_stats"].setdefault(api_name, {"total": 0, "success": 0, "error": 0, "success_rate": 0.0})
        api_stats["total"] += 1
        api_stats[status] += 1

        model_stats = analysis["model_stats"].setdefault(model_name, {"total": 0, "success": 0, "error": 0, "success_rate": 0.0})
        model_stats["total"] += 1
        model_stats[status] += 1

        compliance_stats = analysis["compliance_stats"].setdefault(compliance_check, {"total": 0, "success": 0, "error": 0, "success_rate": 0.0})
        compliance_stats["total"] += 1
        compliance_stats[status] += 1

        is_embedding_api = api_name == "验证调用向量"
        is_embedding_model = model_name in EMBEDDING_MODEL_NAMES
        is_chat_model = model_name in CHAT_MODEL_NAMES
        if (is_embedding_api and not is_embedding_model) or ((not is_embedding_api) and not is_chat_model):
            analysis["mismatch_records"].append({
                "model_name": model_name,
                "api_name": api_name,
                "input_content": input_content,
                "status": status
            })

        if api_name == "验证调用反馈提交与查询":
            analysis["feedback_stats"]["total_count"] += 1
            if status == "success":
                analysis["feedback_stats"]["success_count"] += 1
            else:
                analysis["feedback_stats"]["error_count"] += 1

        if status == "error":
            error_type = result_or_error.split(":", 1)[0] if ":" in result_or_error else "UnknownError"
            analysis["error_type_stats"][error_type] = analysis["error_type_stats"].get(error_type, 0) + 1
            analysis["input_error_stats"][input_content] = analysis["input_error_stats"].get(input_content, 0) + 1

    if analysis["total_count"]:
        analysis["overall_success_rate"] = analysis["success_count"] / analysis["total_count"] * 100

    for stats in analysis["api_stats"].values():
        if stats["total"]:
            stats["success_rate"] = stats["success"] / stats["total"] * 100

    for stats in analysis["model_stats"].values():
        if stats["total"]:
            stats["success_rate"] = stats["success"] / stats["total"] * 100

    for stats in analysis["compliance_stats"].values():
        if stats["total"]:
            stats["success_rate"] = stats["success"] / stats["total"] * 100

    if analysis["feedback_stats"]["total_count"]:
        analysis["feedback_stats"]["success_rate"] = analysis["feedback_stats"]["success_count"] / analysis["feedback_stats"]["total_count"] * 100

    best_model = None
    worst_model = None
    if analysis["model_stats"]:
        sorted_models = sorted(
            analysis["model_stats"].items(),
            key=lambda item: (-item[1]["success_rate"], -item[1]["success"], item[0])
        )
        best_model = sorted_models[0]
        worst_model = sorted(
            analysis["model_stats"].items(),
            key=lambda item: (item[1]["success_rate"], -item[1]["error"], item[0])
        )[0]

    analysis["summary"].append(
        f"本次共执行 {analysis['total_count']} 条测试，成功 {analysis['success_count']} 条，失败 {analysis['error_count']} 条，整体成功率 {analysis['overall_success_rate']:.2f}% 。"
    )

    if best_model:
        analysis["summary"].append(
            f"成功率最高的模型是 {best_model[0]}，成功率 {best_model[1]['success_rate']:.2f}% 。"
        )

    if worst_model:
        analysis["summary"].append(
            f"成功率最低的模型是 {worst_model[0]}，成功率 {worst_model[1]['success_rate']:.2f}% 。"
        )

    if analysis["feedback_stats"]["total_count"]:
        analysis["summary"].append(
            f"反馈链路共测试 {analysis['feedback_stats']['total_count']} 条，成功率 {analysis['feedback_stats']['success_rate']:.2f}% 。"
        )

    if analysis["error_type_stats"]:
        top_error = sorted(analysis["error_type_stats"].items(), key=lambda item: (-item[1], item[0]))[0]
        analysis["summary"].append(
            f"最常见错误类型为 {top_error[0]}，共出现 {top_error[1]} 次。"
        )

    if analysis["mismatch_records"]:
        analysis["summary"].append(
            f"发现 {len(analysis['mismatch_records'])} 条模型类型与接口类型不匹配的记录，需要进一步检查测试分流逻辑。"
        )
    else:
        analysis["summary"].append("未发现模型类型与接口类型不匹配的记录。")

    return analysis


def generate_analysis_html(analysis, result_file):
    report_file = os.path.join(
        os.path.dirname(result_file),
        f"hulk_gateway_verify_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    )

    def build_stats_rows(stats_dict, key_title):
        if not stats_dict:
            return "<tr><td colspan='5'>暂无数据</td></tr>"
        rows = []
        for name, stats in sorted(stats_dict.items(), key=lambda item: item[0]):
            rows.append(
                f"<tr><td>{html.escape(str(name))}</td><td>{stats['total']}</td><td>{stats['success']}</td><td>{stats['error']}</td><td>{stats['success_rate']:.2f}%</td></tr>"
            )
        return "".join(rows)

    def build_simple_rows(stats_dict, value_title):
        if not stats_dict:
            return f"<tr><td colspan='2'>暂无{html.escape(value_title)}</td></tr>"
        rows = []
        for name, count in sorted(stats_dict.items(), key=lambda item: (-item[1], item[0])):
            rows.append(
                f"<tr><td>{html.escape(str(name))}</td><td>{count}</td></tr>"
            )
        return "".join(rows)

    def build_mismatch_rows(records):
        if not records:
            return "<tr><td colspan='4'>未发现不匹配记录</td></tr>"
        rows = []
        for record in records:
            rows.append(
                f"<tr><td>{html.escape(record['model_name'])}</td><td>{html.escape(record['api_name'])}</td><td>{html.escape(record['input_content'])}</td><td>{html.escape(record['status'])}</td></tr>"
            )
        return "".join(rows)

    summary_html = "".join(f"<li>{html.escape(item)}</li>" for item in analysis["summary"])

    html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Hulk Gateway 测试结果分析报告</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 24px; background: #f7f9fc; color: #1f2937; }}
        h1, h2 {{ color: #111827; }}
        .card {{ background: #ffffff; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08); }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
        th, td {{ border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; vertical-align: top; }}
        th {{ background: #eef2ff; }}
        ul {{ margin: 0; padding-left: 20px; }}
        .metric {{ display: inline-block; min-width: 180px; margin-right: 16px; margin-bottom: 8px; }}
        .path {{ color: #2563eb; word-break: break-all; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>Hulk Gateway 测试结果分析报告</h1>
        <p class="path">结果文件：{html.escape(result_file)}</p>
        <div class="metric">报告生成时间：{html.escape(analysis['report_generated_at'])}</div>
        <div class="metric">测试开始时间：{html.escape(analysis['test_start_time'] or '暂无数据')}</div>
        <div class="metric">测试结束时间：{html.escape(analysis['test_end_time'] or '暂无数据')}</div>
        <br>
        <div class="metric">总测试数：{analysis['total_count']}</div>
        <div class="metric">成功数：{analysis['success_count']}</div>
        <div class="metric">失败数：{analysis['error_count']}</div>
        <div class="metric">整体成功率：{analysis['overall_success_rate']:.2f}%</div>
    </div>

    <div class="card">
        <h2>测试结论摘要</h2>
        <ul>{summary_html}</ul>
    </div>

    <div class="card">
        <h2>按接口类型统计</h2>
        <table>
            <tr><th>接口类型</th><th>总数</th><th>成功</th><th>失败</th><th>成功率</th></tr>
            {build_stats_rows(analysis['api_stats'], '接口类型')}
        </table>
    </div>

    <div class="card">
        <h2>按模型统计</h2>
        <table>
            <tr><th>模型名称</th><th>总数</th><th>成功</th><th>失败</th><th>成功率</th></tr>
            {build_stats_rows(analysis['model_stats'], '模型名称')}
        </table>
    </div>

    <div class="card">
        <h2>按合规开关统计</h2>
        <table>
            <tr><th>compliance_check</th><th>总数</th><th>成功</th><th>失败</th><th>成功率</th></tr>
            {build_stats_rows(analysis['compliance_stats'], 'compliance_check')}
        </table>
    </div>

    <div class="card">
        <h2>反馈接口专项统计</h2>
        <div class="metric">反馈测试数：{analysis['feedback_stats']['total_count']}</div>
        <div class="metric">反馈成功数：{analysis['feedback_stats']['success_count']}</div>
        <div class="metric">反馈失败数：{analysis['feedback_stats']['error_count']}</div>
        <div class="metric">反馈成功率：{analysis['feedback_stats']['success_rate']:.2f}%</div>
    </div>

    <div class="card">
        <h2>错误类型分布</h2>
        <table>
            <tr><th>错误类型</th><th>出现次数</th></tr>
            {build_simple_rows(analysis['error_type_stats'], '错误类型')}
        </table>
    </div>

    <div class="card">
        <h2>高频失败输入</h2>
        <table>
            <tr><th>输入内容</th><th>失败次数</th></tr>
            {build_simple_rows(analysis['input_error_stats'], '失败输入')}
        </table>
    </div>

    <div class="card">
        <h2>模型类型与接口类型匹配检查</h2>
        <table>
            <tr><th>模型名称</th><th>接口类型</th><th>输入内容</th><th>状态</th></tr>
            {build_mismatch_rows(analysis['mismatch_records'])}
        </table>
    </div>
</body>
</html>
"""

    with open(report_file, "w", encoding="utf-8") as html_file:
        html_file.write(html_content)

    return report_file


def open_analysis_html(report_file):
    try:
        opened = webbrowser.open(f"file://{os.path.abspath(report_file)}")
        if opened:
            print(f"已在默认浏览器中打开分析报告: {report_file}")
        else:
            print(f"未能自动打开浏览器，请手动打开分析报告: {report_file}")
    except Exception as err:
        print(f"自动打开分析报告失败: {type(err).__name__}: {err}")


def post_json(url, payload):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    try:
        return response.json()
    except ValueError as err:
        raise ValueError(f"接口返回的不是合法 JSON: {response.text}") from err


def get_json(url, params=None):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    try:
        return response.json()
    except ValueError as err:
        raise ValueError(f"接口返回的不是合法 JSON: {response.text}") from err


def extract_chat_content(result):
    choices = result.get("choices")
    if not choices:
        raise ValueError(f"接口返回缺少 choices 字段: {result}")

    message = choices[0].get("message")
    if not message or "content" not in message:
        raise ValueError(f"接口返回缺少 message.content 字段: {result}")

    return message["content"]


def extract_completion_text(result):
    choices = result.get("choices")
    if not choices or "text" not in choices[0]:
        raise ValueError(f"接口返回缺少 choices[0].text 字段: {result}")
    return choices[0]["text"]


def extract_embedding_vector(result):
    data = result.get("data")
    if not data or "embedding" not in data[0]:
        raise ValueError(f"接口返回缺少 data[0].embedding 字段: {result}")
    return data[0]["embedding"]


def extract_feedback_items(result):
    if isinstance(result, list):
        return result

    if isinstance(result, dict):
        for key in ["data", "items", "results", "feedbacks"]:
            value = result.get(key)
            if isinstance(value, list):
                return value

    raise ValueError(f"查询反馈接口返回格式不符合预期: {result}")

def get_models(base_url, api_key):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    response = requests.get(f"{base_url}/models", headers=headers)

    if response.status_code == 200:
        models = response.json()
        print("✅ 获取模型列表成功：")
        for model in models.get("data", []):
            print(f"- 模型ID: {model['id']}")
        return models

    print(f"❌ 请求失败，状态码: {response.status_code}")
    print("错误信息:", response.text)
    return None


def filter_models_by_name(models, allowed_model_names, model_type_name):
    filtered_data = [
        model for model in models.get("data", [])
        if model.get("id") in allowed_model_names
    ]

    print(f"✅ {model_type_name}模型列表：")
    for model in filtered_data:
        print(f"- 模型ID: {model['id']}")

    missing_models = [
        model_name for model_name in allowed_model_names
        if model_name not in {model.get('id') for model in filtered_data}
    ]
    if missing_models:
        print(f"⚠️ 以下{model_type_name}模型未在接口返回列表中找到：")
        for model_name in missing_models:
            print(f"- 模型ID: {model_name}")

    return {"data": filtered_data}



# -------------------- 1. 对话聊天接口（最常用）----------------------
def chat_completion(user_message: str, model_name: str, stream: bool = False,cmp_ck=0):
    """
    对话聊天接口
    :param user_message: 用户问题
    :param model_name: 模型名称（必填）
    :param stream: 是否流式输出
    :return: AI 回答内容
    """
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": user_message}],
        "stream": stream,
        "compliance_check":cmp_ck
    }

    result = post_json(url, payload)
    return extract_chat_content(result)


# -------------------- 2. 文本续写接口 ----------------------
def completion(prompt: str, model_name: str, max_tokens: int = 512,cmp_ck=0):
    """
    文本续写接口
    :param prompt: 提示词
    :param model_name: 模型名称（必填）
    :param max_tokens: 最大生成长度
    :return: 续写文本
    """
    url = f"{base_url}/completions"
    payload = {
        "model": model_name,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "compliance_check":cmp_ck
    }

    result = post_json(url, payload)
    return extract_completion_text(result)


# -------------------- 3. 向量嵌入接口 ----------------------
def embedding(text: str, model_name: str,cmp_ck=0):
    """
    文本转向量（Embedding）
    :param text: 需要转向量的文本
    :param model_name: 向量模型名称（必填）
    :return: 向量数组
    """
    url = f"{base_url}/embeddings"
    payload = {
        "model": model_name,
        "input": text,
        "compliance_check":cmp_ck
    }

    result = post_json(url, payload)
    return extract_embedding_vector(result)


def submit_feedback(messages, model_name: str, rating: int, comment: str = ""):
    url = f"{base_url}/feedback"
    payload = {
        "messages": messages,
        "model": model_name,
        "rating": rating,
        "comment": comment
    }
    return post_json(url, payload)


def query_feedback(page: int = 1, page_size: int = 10):
    url = f"{base_url}/feedback"
    params = {
        "page": page,
        "page_size": page_size
    }
    return get_json(url, params=params)

def run_api_test(models, compliance_check, api_name, contents, api_func, writer, result_handle):
    print(f"-------------开始{api_name}--------------")
    for model in models.get("data", []):
        model_name = model["id"]
        for content in contents:
            print(f"模型名称: {model_name} - 内容输入: {content} - compliance_check: {compliance_check} - 测试项目: {api_name}")
            try:
                result = api_func(content, model_name=model_name, cmp_ck=compliance_check)
                formatted_result = format_result(result)
                print("结果：", formatted_result)
                record_test_result(writer, result_handle, "success", model_name, compliance_check, content, api_name, formatted_result)
            except Exception as err:
                error_message = f"{type(err).__name__}: {err}"
                print("报错信息：", error_message)
                record_test_result(writer, result_handle, "error", model_name, compliance_check, content, api_name, error_message)
        print("-" * 60)


def test_feedback(models, compliance_check, writer, result_handle):
    print("-------------开始验证调用反馈提交与查询--------------")
    test_cases = [
        {
            "user_message": "请介绍一下Python的主要特点",
            "rating": 8,
            "comment": f"自动化测试反馈 compliance_check={compliance_check}"
        },
        {
            "user_message": "请总结一下人工智能的发展趋势",
            "rating": 9,
            "comment": f"自动化测试反馈2 compliance_check={compliance_check}"
        }
    ]

    for model in models.get("data", []):
        model_name = model["id"]
        for case in test_cases:
            user_message = case["user_message"]
            rating = case["rating"]
            comment = case["comment"]
            print(f"模型名称: {model_name} - 内容输入: {user_message} - compliance_check: {compliance_check} - 测试项目: 验证调用反馈提交与查询")

            try:
                assistant_reply = chat_completion(user_message, model_name=model_name, cmp_ck=compliance_check)
                messages = [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": assistant_reply}
                ]

                submit_result = submit_feedback(messages, model_name, rating, comment)
                feedback_result = query_feedback(page=1, page_size=10)
                feedback_items = extract_feedback_items(feedback_result)

                matched_feedback = next(
                    (
                        item for item in feedback_items
                        if item.get("model") == model_name
                        and item.get("rating") == rating
                        and item.get("comment") == comment
                        and item.get("messages") == messages
                    ),
                    None
                )

                if not matched_feedback:
                    raise ValueError(
                        f"查询反馈结果中未找到刚提交的数据。submit_result={submit_result}, feedback_result={feedback_result}"
                    )

                formatted_result = f"提交成功并查询校验成功，rating={rating}, comment={comment}"
                print("结果：", formatted_result)
                record_test_result(writer, result_handle, "success", model_name, compliance_check, user_message, "验证调用反馈提交与查询", formatted_result)
            except Exception as err:
                error_message = f"{type(err).__name__}: {err}"
                print("报错信息：", error_message)
                record_test_result(writer, result_handle, "error", model_name, compliance_check, user_message, "验证调用反馈提交与查询", error_message)
        print("-" * 60)


def test_chat_completion(models, compliance_check, writer, result_handle):
    contents = ["介绍一下Python", "你能做些什么", "我今天非常开心","中国历史上最强大的王朝是哪个？","美国哪一年成立?","请给我说说人工智能中大模型、边缘模型是什么意思"]
    run_api_test(models, compliance_check, "验证调用对话", contents, chat_completion, writer, result_handle)


def test_completion(models, compliance_check, writer, result_handle):
    contents = ["春天来了，万物复苏", "今天天气真好，适合出去游玩", "人工智能的发展趋势是", "历史上最惨烈的水库泄洪事故", "北京通州未来房价趋势", "21世纪人类航天可能会有哪些突破"]
    run_api_test(models, compliance_check, "验证调用续写", contents, completion, writer, result_handle)


def test_embedding(models, compliance_check, writer, result_handle):
    contents = ["我喜欢AI", "今天要下雨吗", "航天科技的发展趋势是"]
    run_api_test(models, compliance_check, "验证调用向量", contents, embedding, writer, result_handle)


def main():
    setup_logging()
    writer, result_handle, result_file = create_result_writer()
    models = get_models(base_url, api_key)
    print("*" * 20)

    if models:
        chat_models = filter_models_by_name(models, CHAT_MODEL_NAMES, "聊天/对话")
        embedding_models = filter_models_by_name(models, EMBEDDING_MODEL_NAMES, "向量")
        for compliance_check in [0, 1]:
            test_chat_completion(chat_models, compliance_check, writer, result_handle)
            test_completion(chat_models, compliance_check, writer, result_handle)
            test_embedding(embedding_models, compliance_check, writer, result_handle)
            test_feedback(chat_models, compliance_check, writer, result_handle)

        analysis = analyze_test_results(result_file)
        report_file = generate_analysis_html(analysis, result_file)
        print(f"分析报告文件: {report_file}")
        open_analysis_html(report_file)

    print("✅ 测试流程已执行完毕。")

if __name__ == "__main__":
    main()
