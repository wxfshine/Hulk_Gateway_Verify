# `chat/completions` Excel 用例列设计

该文档对应模板文件：

- 旧版：`docs/chat_completions_api_test_case_template.csv`
- 强化版：`docs/chat_completions_api_test_case_template_v2.csv`

建议优先使用强化版模板。原模板如果正在被 Excel 打开，可能无法直接覆盖。

模板文件可直接用 Excel 打开、编辑、另存为 `xlsx`。

## 列说明

| 列名 | 含义 | 说明 |
| --- | --- | --- |
| `case_id` | 用例编号 | 唯一编号，建议如 `CHAT-001` |
| `enabled` | 是否启用 | `Y` / `N` |
| `case_name` | 用例名称 | 简洁描述测试目标 |
| `case_category` | 用例分类 | 如 `happy_path`、`required_validation`、`type_validation`、`enum_validation`、`response_schema` |
| `priority` | 优先级 | 如 `P0`、`P1`、`P2` |
| `api_name` | 接口名称 | 当前建议固定为 `chat_completions` |
| `method` | 请求方法 | 当前接口为 `POST` |
| `path` | 请求路径 | 当前接口为 `/v1/chat/completions` |
| `request_content_type` | 请求内容类型 | 当前一般为 `application/json` |
| `request_payload` | 请求体 JSON | 完整请求 JSON 字符串，支持标准字段和自定义扩展字段 |
| `expected_http_status` | 预期状态码 | 如 `200`、`422` |
| `expected_result_type` | 预期结果类型 | 建议取值：`success`、`validation_error` |
| `expected_required_fields` | 预期必须存在的字段 | 用 `|` 分隔，支持点路径，如 `choices.0.message` |
| `expected_field_types` | 预期字段类型 | 用 `字段路径:类型` 表示，多个值用 `|` 分隔 |
| `expected_field_values` | 预期字段值 | 用 `字段路径=值` 表示，多个值用 `|` 分隔 |
| `expected_array_non_empty_fields` | 预期非空数组字段 | 用 `|` 分隔，如 `choices` |
| `expected_error_loc` | 预期错误定位 | 对校验失败场景使用，如 `body.model`、`body.messages.0.role`。支持用 `|` 填多个可接受值。 |
| `expected_error_type` | 预期错误类型 | 对校验失败场景使用。支持用 `|` 填多个可接受值，例如 `int_type|literal_error`。 |
| `expected_error_msg_contains` | 预期错误消息关键字 | 对校验失败场景使用，建议做包含匹配。支持用 `|` 填多个可接受关键字。 |
| `expected_error_input` | 预期错误输入值 | 对校验失败场景使用。支持用 `|` 填多个可接受值。 |
| `notes` | 备注 | 补充说明 |

## 设计原则

### 1. 请求侧尽量整包透传
`request_payload` 建议直接存完整 JSON，而不是拆成很多列。

原因：
- 便于测试任意扩展字段
- 便于测试嵌套结构
- 更贴近真实 API 请求
- 后续兼容其他 OpenAI 风格字段更容易

### 2. 断言列尽量结构化
建议把断言分成：
- 状态码断言
- 成功响应结构断言
- 失败响应结构断言
- 错误定位断言
- 错误类型断言
- 错误消息关键字断言

这样便于程序自动执行，也方便后续做报告分析。

### 3. 成功与失败用例共用一套表头
区别主要靠：
- `expected_http_status`
- `expected_result_type`
- `expected_error_loc`
- `expected_error_type`
- `expected_error_msg_contains`

### 4. 对不稳定错误文案使用“多可接受值”
不同网关实现、不同 FastAPI / Pydantic 版本，错误类型和错误文案可能略有差异。

因此建议：
- `expected_error_type` 用较稳定的类型名
- `expected_error_msg_contains` 用关键字包含匹配
- 如果存在版本差异，可用 `|` 填多个可接受值

例如：
- `int_type|literal_error`
- `valid integer|Input should be`
- `model|body.model`

## 当前强化版模板覆盖的主要测试点

- 最小合法请求
- `compliance_check` 取值 `0/1/2/3`
- `compliance_check` 默认值
- `compliance_check=null`
- 自定义扩展字段兼容
- 缺少 `model`
- 缺少 `messages`
- `messages` 为空数组
- `messages` 类型错误
- `messages[].role` / `messages[].content` 缺失
- `model` / `role` / `content` 类型错误
- `compliance_check` 类型错误
- `compliance_check` 越界
- 成功响应 schema 校验
- 失败响应 schema 校验

## 后续可继续扩展的列
如果后面你想增强接口测试能力，可以继续新增：

- `pre_step`
- `post_check`
- `extract_fields`
- `depends_on_case_id`
- `timeout_seconds`
- `headers_json`
- `query_params_json`
- `expected_json_path_rules`

当前这版先以“够用、清晰、便于 Excel 维护”为主。