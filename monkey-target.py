# coding=utf-8
"""读取飞书表格的股票代码与目标价，对比当前股价"""
import importlib.util
import os
import sys

import feishu_bitable as fb

# 目标多维表格：目标价表（指定视图）
URL = "https://my.feishu.cn/wiki/PoqXwHD95iU3VSkkxuEc0vL9nrb?table=tblWHACMsYJgMF7R&view=vewUfhc8OY"
CODE_FIELD = "股票代码"
TARGET_FIELD = "目标价"

SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monkey-bitable.py")


def load_monkey():
    """加载通用脚本 monkey-bitable.py（文件名带连字符，不能直接 import）"""
    spec = importlib.util.spec_from_file_location("monkey_bitable", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_items(url):
    """读取代码与目标价，返回 [(代码, 目标价或 None)]，顺序与表格一致"""
    app_token, table_id, view_id = fb.parse_table_url(url)
    if not app_token or not table_id:
        raise RuntimeError("没能从链接中解析出 app_token 和 table_id，请检查链接")

    app_id, app_secret = fb.load_config()
    token = fb.get_tenant_access_token(app_id, app_secret)
    records = fb.search_records(token, app_token, table_id, [CODE_FIELD, TARGET_FIELD], view_id)

    items = []
    for one in records:
        code = fb.format_value(one.get(CODE_FIELD)).strip()
        if not code:
            continue

        target = fb.format_value(one.get(TARGET_FIELD)).strip()
        items.append((code, float(target) if target else None))
    return items


def main():
    monkey = load_monkey()

    try:
        items = get_items(URL)
    except RuntimeError as e:
        print(e)
        return
    except ValueError as e:
        print("目标价不是数字：" + str(e))
        return

    if not items:
        print("没有读取到股票代码")
        return

    quotes = monkey.fetch_quotes([code for code, target in items])

    failed = 0
    for code, target in items:
        one = quotes.get(code)
        if not one:
            failed += 1
            continue

        prevClose = one["prev_close"]
        now = float(one["now"])
        rangeValue = (now - float(prevClose)) / float(prevClose) * 100

        if target is None:
            # 目标价为空时默认取当前股价
            target = now

        diff = target - now
        rate = diff / now * 100 if now else 0
        print(one["name"] + "\topen:" + prevClose + "\tnow:" + one["now"]
              + "\trange:" + str(round(rangeValue, 2)) + "%"
              + "\ttarget:" + "%.2f" % target
              + "\tdiff:" + "%.2f" % diff
              + "\trate:" + "%.2f" % rate + "%")

    if failed:
        print(str(failed) + " 个代码未取到行情", file=sys.stderr)


if __name__ == "__main__":
    main()
