# coding=utf-8
"""OpenAI 兼容协议的大模型调用封装

模型配置读取自项目统一的配置文件 feishu-config.json 的 ai 段：
  {
    "app_id": "cli_xxx",
    "app_secret": "xxx",
    "ai": {"base_url": "https://api.deepseek.com", "api_key": "sk-xxx", "model": "deepseek-chat"}
  }

调用失败会重试（最多 3 次，等待时间递增），仍失败则抛 RuntimeError，由调用方决定如何提示。
"""
import json
import os
import sys
import time

import requests

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feishu-config.json")

# 失败重试：最多 RETRY_TIMES 次，第 n 次失败后等待 RETRY_DELAY * n 秒
RETRY_TIMES = 3
RETRY_DELAY = 5

CONFIG_EXAMPLE = """{
  "app_id": "cli_xxx",
  "app_secret": "xxx",
  "ai": {
    "base_url": "https://api.deepseek.com",
    "api_key": "sk-xxx",
    "model": "deepseek-chat"
  }
}"""


def load_config(path=CONFIG_FILE):
    """读取配置里的 ai 段：base_url / api_key / model"""
    if not os.path.exists(path):
        raise RuntimeError("配置文件不存在：" + path + "\n请创建该文件，内容示例：\n" + CONFIG_EXAMPLE)

    with open(path, encoding="utf-8") as f:
        config = json.load(f)

    ai = config.get("ai") or {}
    if not ai.get("api_key"):
        raise RuntimeError("未配置模型密钥：请在 " + path + " 的 ai.api_key 中填入")

    ai.setdefault("base_url", "https://api.deepseek.com")
    ai.setdefault("model", "deepseek-chat")
    return ai


def _request_once(config, payload, timeout):
    """发起一次请求，任何失败都抛 RuntimeError"""
    url = config["base_url"].rstrip("/") + "/chat/completions"

    try:
        r = requests.post(url, headers={
            "Authorization": "Bearer " + config["api_key"],
            "Content-Type": "application/json",
        }, json=payload, timeout=timeout)
    except requests.RequestException as e:
        raise RuntimeError("请求异常：%s" % e)

    if r.status_code != 200:
        raise RuntimeError("HTTP %d：%s" % (r.status_code, r.text[:300]))

    data = r.json()
    if not (data.get("choices") or []):
        raise RuntimeError("返回内容异常：" + json.dumps(data, ensure_ascii=False)[:300])
    return data


def _request(config, payload, timeout):
    """带重试的请求：最多 RETRY_TIMES 次，等待时间按 5/10/15 秒递增"""
    for attempt in range(1, RETRY_TIMES + 1):
        try:
            return _request_once(config, payload, timeout)
        except RuntimeError as e:
            if attempt == RETRY_TIMES:
                raise RuntimeError("%s（已重试 %d 次）" % (e, RETRY_TIMES))
            wait = RETRY_DELAY * attempt
            print("调用模型失败（第 %d/%d 次）：%s；%d 秒后重试"
                  % (attempt, RETRY_TIMES, e, wait), file=sys.stderr)
            time.sleep(wait)


def chat(messages, temperature=0.3, max_tokens=16000, timeout=600, max_continuations=3):
    """调用 /chat/completions，返回模型输出的文本

    部分思考型模型会把推理 token 计入输出配额，长文本可能被截断（finish_reason=length），
    这里检测到截断会自动续写，最多续 max_continuations 次。
    """
    config = load_config()

    parts = []
    current = list(messages)
    for _ in range(max_continuations):
        data = _request(config, {
            "model": config["model"],
            "messages": current,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }, timeout)

        choice = data["choices"][0]
        content = (choice.get("message") or {}).get("content") or ""
        parts.append(content)

        if choice.get("finish_reason") != "length":
            break

        current = current + [
            {"role": "assistant", "content": content},
            {"role": "user", "content": "输出被长度限制截断了，请紧接上文继续写，不要重复已有内容。"},
        ]

    return "".join(parts).strip()


def model_name():
    """返回当前配置的模型名（读不到配置时返回 '模型'）"""
    try:
        return load_config()["model"]
    except (RuntimeError, ValueError):
        return "模型"
