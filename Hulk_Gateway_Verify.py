import requests
import logging
import sys
import atexit
import os
import csv
from datetime import datetime

# 1. 基础配置
base_url = "http://hulk.cmit.local:18080/v1"  # 你的LLM Gateway地址
api_key = "eyJhbGciOiJIUzUxMiIsImlhdCI6MTc3OTA5MDczOSwiZXhwIjoxNzg2ODY2NzM5fQ.eyJpZCI6NzE2LCJuYW1lIjoid2FuZ3hmIiwic291cmNlIjoibGRhcCIsImV4dGVybmFsX2lkIjoie2VjYWE5ZGVkLWI2MzMtNGNmOC05Y2Q5LWQxZGE4MTYyYWFhYn0iLCJyb2xlIjoiVXNlciJ9.M_lPymDGllUI0BaMULupNQ8HaWa9G0zYfRgm5AGz8KBaBuBTcru472vOZilgULdROivMsRJmCxVlNkL81nvlfw"  # 从POST /v1/api-keys拿到的Key


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
    return writer, result_handle


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


def test_chat_completion(models, compliance_check, writer, result_handle):
    contents = ["介绍一下Python", "你能做些什么", "我今天非常开心"]
    run_api_test(models, compliance_check, "验证调用对话", contents, chat_completion, writer, result_handle)


def test_completion(models, compliance_check, writer, result_handle):
    contents = ["春天来了，万物复苏", "今天天气真好，适合出去游玩", "人工智能的发展趋势是"]
    run_api_test(models, compliance_check, "验证调用续写", contents, completion, writer, result_handle)


def test_embedding(models, compliance_check, writer, result_handle):
    contents = ["我喜欢AI", "今天要下雨吗", "航天科技的发展趋势是"]
    run_api_test(models, compliance_check, "验证调用向量", contents, embedding, writer, result_handle)


def main():
    setup_logging()
    writer, result_handle = create_result_writer()
    models = get_models(base_url, api_key)
    print("*" * 20)

    if models:
        for compliance_check in [0, 1]:
            test_chat_completion(models, compliance_check, writer, result_handle)
            test_completion(models, compliance_check, writer, result_handle)
            test_embedding(models, compliance_check, writer, result_handle)

if __name__ == "__main__":
    main()
