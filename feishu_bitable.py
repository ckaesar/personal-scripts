# coding=utf-8
"""飞书多维表格读取的公共逻辑"""
import json
import os
from urllib.parse import parse_qs, urlparse

import requests

# 飞书开放平台接口
TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
RECORD_URL = "https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search"
FIELD_URL = "https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
PAGE_SIZE = 500

# 凭证放在同目录的配置文件中（已加入 .gitignore），格式：
# {"app_id": "cli_xxx", "app_secret": "xxx"}
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feishu-config.json")


def load_config(path=CONFIG_FILE):
    """从配置文件读取飞书应用凭证"""
    if not os.path.exists(path):
        raise RuntimeError("配置文件不存在：" + path + "\n请创建该文件，内容示例：{\"app_id\": \"cli_xxx\", \"app_secret\": \"xxx\"}")

    with open(path, encoding="utf-8") as f:
        config = json.load(f)

    app_id = config.get("app_id")
    app_secret = config.get("app_secret")
    if not app_id or not app_secret:
        raise RuntimeError("配置文件缺少 app_id 或 app_secret：" + path)
    return app_id, app_secret


def get_tenant_access_token(app_id, app_secret):
    """获取自建应用的 tenant_access_token"""
    r = requests.post(TOKEN_URL, json={
        "app_id": app_id,
        "app_secret": app_secret,
    }, timeout=15)

    result = r.json()
    if result.get("code") != 0:
        raise RuntimeError("获取 tenant_access_token 失败：" + json.dumps(result, ensure_ascii=False))
    return result["tenant_access_token"]


def parse_table_url(url):
    """从多维表格链接解析 app_token、table_id、view_id，支持 /base/ 与 /wiki/ 两种形态"""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    table_id = (query.get("table") or [""])[0]
    view_id = (query.get("view") or [""])[0]

    app_token = ""
    for prefix in ("/base/", "/wiki/"):
        if prefix in parsed.path:
            app_token = parsed.path.split(prefix, 1)[1].split("/")[0]
            break
    return app_token, table_id, view_id


def list_fields(token, app_token, table_id):
    """获取数据表的列（字段）名称，顺序与表格中的列顺序一致"""
    url = FIELD_URL.format(app_token=app_token, table_id=table_id)
    headers = {"Authorization": "Bearer " + token}

    names = []
    page_token = ""
    while True:
        params = {"page_size": 100}
        if page_token:
            params["page_token"] = page_token

        result = requests.get(url, headers=headers, params=params, timeout=30).json()
        if result.get("code") != 0:
            raise RuntimeError("获取列信息失败：" + json.dumps(result, ensure_ascii=False))

        data = result.get("data") or {}
        for one in data.get("items") or []:
            names.append(one["field_name"])

        if not data.get("has_more"):
            break
        page_token = data.get("page_token") or ""
        if not page_token:
            break
    return names


def search_records(token, app_token, table_id, field_names=None, view_id=""):
    """分页查询记录，可指定视图和列，返回 fields 列表"""
    url = RECORD_URL.format(app_token=app_token, table_id=table_id)
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json; charset=utf-8",
    }
    body = {}
    if view_id:
        body["view_id"] = view_id
    if field_names:
        body["field_names"] = field_names

    records = []
    page_token = ""
    while True:
        params = {"page_size": PAGE_SIZE}
        if page_token:
            params["page_token"] = page_token

        r = requests.post(url, headers=headers, params=params, json=body, timeout=30)
        result = r.json()
        if result.get("code") != 0:
            raise RuntimeError("查询记录失败：" + json.dumps(result, ensure_ascii=False))

        data = result.get("data") or {}
        for one in data.get("items") or []:
            records.append(one.get("fields") or {})

        if not data.get("has_more"):
            break
        page_token = data.get("page_token") or ""
        if not page_token:
            break
    return records


def format_value(value):
    """把多维表格的字段值转成便于展示的文本（日期字段为毫秒时间戳，这里原样输出）"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(format_value(one) for one in value)
    if isinstance(value, dict):
        if "text" in value:
            return str(value["text"])
        if "name" in value:
            return str(value["name"])
        if "value" in value:
            return format_value(value["value"])
        return json.dumps(value, ensure_ascii=False)
    return str(value)
