# Hulk_Gateway_Verify 使用指南

概述
- 本脚本用于验证 Hulk LLM Gateway 的常用 API（对话 / 续写 / 嵌入）并生成测试结果与分析报告。
- 生成结果包括：CSV（原始记录，含 HTTP 元数据）、HTML 分析报告、以及基于 CSV 导出的 XLSX（Summary 与失败用例明细）。

运行前准备
- Python 3.7+ 环境；已安装依赖：requests、openpyxl。
- 确保在脚本顶部配置 `base_url` 与 `api_key`（或通过其他方式传入）。
- 可选：在 `docs/test_contents.json` 中准备 contents 配置（示例已提供）。

主要命令行参数
- 不带参数：运行内置 DEFAULT_CONTENTS 所有内容。
  - 示例：python Hulk_Gateway_Verify.py

- --contents-file <path>
  - 说明：指定一个 JSON 文件路径，从中读取 chat_completion/completion/embedding 的 contents 配置。
  - 格式示例（docs/test_contents.json）：
	{
	  "chat_completion": ["介绍一下Python", "你能做些什么"],
	  "completion": ["春天来了，万物复苏"],
	  "embedding": ["我喜欢AI"]
	}
  - 示例：python Hulk_Gateway_Verify.py --contents-file docs/test_contents.json

- --single-content "<text>"
  - 说明：仅运行某个具体内容项。脚本会在三类 contents 中查找该文本并仅对匹配到的类别保留该文本，其他类别将被置空并跳过。
  - 注意：--single-content 的匹配是精确匹配，文本必须与配置中的某项完全一致。
  - 示例：python Hulk_Gateway_Verify.py --single-content "介绍一下Python"

- 组合示例（推荐）
  - 指定配置文件并只跑单项：
	python Hulk_Gateway_Verify.py --contents-file docs/test_contents.json --single-content "介绍一下Python"

其它保留功能
- 启动多结果合并分析网页：
  python Hulk_Gateway_Verify.py --merge-report-ui
- 直接合并多个结果文件并生成分析报告：
  python Hulk_Gateway_Verify.py merge-files path/to/result1.csv path/to/result2.csv
- 使用 API 用例 CSV 运行（独立模块）：
  python Hulk_Gateway_Verify.py api-case-run path/to/case.csv
  或
  python Hulk_Gateway_Verify.py --api-case-file path/to/case.csv

输出说明
- CSV（原始记录）
  - 路径：log/hulk_gateway_verify_result_YYYYMMDD_HHMMSS.csv
  - 包含列（主要）：timestamp, status, model_name, compliance_check, input_content, api_name, expected_http_status, actual_http_status, request_payload, response_headers, response_body, result_or_error

- XLSX（基于 CSV 导出）
  - 同名文件：log/hulk_gateway_verify_result_YYYYMMDD_HHMMSS.xlsx
  - 包含：Summary（总数/成功/失败）与失败用例明细表（包含上面列及调试所需的请求/响应细节）。

常见问题
- Q: 我运行 --single-content 仍看到其它内容被执行。为什么？
  A: 请确认是否在命令中指定了 --contents-file。如果未指定脚本会使用内置 DEFAULT_CONTENTS；若要用 docs/test_contents.json，请加 --contents-file docs/test_contents.json。CLI 操作会在启动前设置 DEFAULT_CONTENTS，main() 不再自动覆盖它。

- Q: 我想把期望的 HTTP 状态码配置到每条内容上。
  A: 当前默认 expected_http_status 为 200。可以扩展 docs/test_contents.json 为每项对象形式（例如 {"text":"...","expected_http_status":200}），我可以帮助你实现该扩展。

后续增强建议（可选）
- 将 CSV 导出增强为带更多汇总表的 XLSX（按模型/按 API 分类）并增加首行冻结与自动换行。 
- 支持 --single-content 的模糊或正则匹配。 
- 支持为每条 content 配置 expected_http_status。
