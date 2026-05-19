import requests

# 1. 基础配置
base_url = "http://hulk.cmit.local:18080/v1"  # 你的LLM Gateway地址
api_key = "eyJhbGciOiJIUzUxMiIsImlhdCI6MTc3OTA5MDczOSwiZXhwIjoxNzg2ODY2NzM5fQ.eyJpZCI6NzE2LCJuYW1lIjoid2FuZ3hmIiwic291cmNlIjoibGRhcCIsImV4dGVybmFsX2lkIjoie2VjYWE5ZGVkLWI2MzMtNGNmOC05Y2Q5LWQxZGE4MTYyYWFhYn0iLCJyb2xlIjoiVXNlciJ9.M_lPymDGllUI0BaMULupNQ8HaWa9G0zYfRgm5AGz8KBaBuBTcru472vOZilgULdROivMsRJmCxVlNkL81nvlfw"  # 从POST /v1/api-keys拿到的Key

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
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": user_message}],
        "stream": stream,
        "compliance_check":cmp_ck
    }

    response = requests.post(url, json=payload, headers=headers)
    result = response.json()
    return result["choices"][0]["message"]["content"]


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
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "compliance_check":cmp_ck
    }

    response = requests.post(url, json=payload, headers=headers)
    result = response.json()
    return result["choices"][0]["text"]


# -------------------- 3. 向量嵌入接口 ----------------------
def embedding(text: str, model_name: str,cmp_ck=0):
    """
    文本转向量（Embedding）
    :param text: 需要转向量的文本
    :param model_name: 向量模型名称（必填）
    :return: 向量数组
    """
    url = f"{base_url}/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "input": text,
        "compliance_check":cmp_ck
    }

    response = requests.post(url, json=payload, headers=headers)
    result = response.json()
    return result["data"][0]["embedding"]

def test_chat_completion(models):
    # 1. 调用对话
    print("-------------开始验证调用对话--------------")
    compliance_checks = [0,1]
    for compliance_check in compliance_checks:
        id=1
        for model in models.get("data", []):
            try:
                print(f"模型ID: {id} - 模型描述: {model}")
                ans = chat_completion("介绍一下Python", model_name = model['id'])
                print("对话结果：", ans)
                print("-"*60)
                id+=1
            except Exception as err:
                print(err)

def test_completion(models):
    # 2. 调用续写
    print("-------------开始验证调用续写---------------")
    compliance_checks = [0,1]
    for compliance_check in compliance_checks:
        id=1
        for model in models.get("data", []):
            print(f"模型ID: {id} - 模型描述: {model}")
            text = completion("春天来了，万物", model_name = model['id'])
            print("续写结果：", text)
            print("-"*60)
            id+=1

def main():
    models = get_models(base_url, api_key)
    # 假设你从 /v1/models 查到的模型是：
    print("*"*20)


    # 3. 调用向量
    #vec = embedding("我喜欢AI", model_name=EMBED_MODEL)
    #print("向量长度：", len(vec))


if __name__ == "__main__":
    main()
