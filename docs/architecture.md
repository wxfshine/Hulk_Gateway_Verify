# Hulk_Gateway_Verify 架构概览

本文档说明当前仓库中 `Hulk_Gateway_Verify.py` 的模块划分、数据流与关键实现点（基于当前代码）。

主要模块与职责
- Hulk_Gateway_Verify.py
  - 程序入口与 CLI 调度（解析命令行并触发不同流程）。
  - 测试流程控制：获取模型列表 -> 过滤模型 -> 对每个模型与每条 contents 执行测试 -> 记录结果 -> 生成分析报告与 Excel。 
  - 提供三个主要 API 封装：chat_completion / completion / embedding，均支持 `capture=True` 一次请求返回解析值与 HTTP 元数据（status、headers、raw_text、parsed_json、request_payload）。
  - run_api_test：统一执行单个 API 类型在一组模型上的所有 contents，使用 capture 模式获得元数据并写入结果 CSV。
  - 结果输出：CSV（log 目录）、HTML 分析报告（log 目录）、以及基于 CSV 导出的 XLSX（包含 Summary 与“失败用例明细”表）。

- api_case_testing.py
  - 独立的 API 用例执行模块（读取用例 CSV、执行断言、输出结果和 HTML 报表）。
  - 保留为独立子流程，通过 CLI 的 `api-case-run` 触发。

关键数据流
1. 启动脚本并解析 CLI 参数（--contents-file / --single-content 等）。
2. 根据 CLI 对内置 DEFAULT_CONTENTS 进行替换或过滤（CLI 优先级高）。
3. 获取模型列表并按白名单过滤为 chat/embedding 模型集。
4. 对每个 API 类型（对话/续写/向量）调用 run_api_test：
   - 对每个模型与每个 content 调用对应 api_func(..., capture=True)。
   - api_func 返回解析值与 meta（包含 status_code、headers、raw_text、parsed_json、request_payload）。
   - 将解析值用于展示与记录，将 meta 写入 CSV 的额外列（expected_http_status、actual_http_status、request_payload、response_headers、response_body）。
5. 所有测试完成后：
   - 生成 CSV（位于 log 目录），并基于 CSV 生成 HTML 分析报告与 XLSX（Summary + 失败明细）。

设计与实现要点
- capture 模式：一次请求即可得到业务解析结果与原始 HTTP 元数据，避免重复请求与信息丢失。
- 结果记录：CSV 包含每条记录的 HTTP 元信息（5 列），方便在 Excel 中快速定位问题。
- 配置优先级：CLI（--contents-file / --single-content）优先于内置 DEFAULT_CONTENTS；main 不会自动覆盖 CLI 设置。
- 可扩展性：导出 XLSX 逻辑使用 openpyxl，便于未来增强格式化与统计表。

文件与输出位置
- 源码：`Hulk_Gateway_Verify.py`、`api_case_testing.py`。
- 配置示例：`docs/test_contents.json`。
- 输出文件：`log/hulk_gateway_verify_result_YYYYMMDD_HHMMSS.csv`，以及同名的 `.xlsx` 与 HTML 报告。
