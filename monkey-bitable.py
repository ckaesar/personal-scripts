# coding=utf-8
import sys

import requests

import feishu_bitable as fb

# 行情接口与打印格式参考 monkey.py
QUOTE_URL = "http://qt.gtimg.cn/q="
BATCH_SIZE = 50
DEFAULT_FIELD = "股票代码"


def get_codes(url, field_name):
    """读取多维表格指定视图的代码列，按出现顺序去重"""
    app_token, table_id, view_id = fb.parse_table_url(url)
    if not app_token or not table_id:
        raise RuntimeError("没能从链接中解析出 app_token 和 table_id，请检查链接")

    app_id, app_secret = fb.load_config()
    token = fb.get_tenant_access_token(app_id, app_secret)
    records = fb.search_records(token, app_token, table_id, [field_name], view_id)

    codes = []
    for one in records:
        code = fb.format_value(one.get(field_name)).strip()
        if code and code not in codes:
            codes.append(code)
    return codes


def print_quotes(codes):
    """批量查询行情并打印"""
    failed = 0
    for i in range(0, len(codes), BATCH_SIZE):
        batch = codes[i:i + BATCH_SIZE]
        r = requests.get(QUOTE_URL + ",".join(batch), timeout=15)

        for line in r.text.strip().split("\n"):
            if "=" not in line:
                continue
            options = line.split("=")[1][1:].split("~")
            if len(options) < 5:
                failed += 1
                continue

            name = options[1]
            start = options[4]
            now = options[3]

            startFloat = float(start)
            nowFloat = float(now)
            rangeValue = (nowFloat - startFloat) / startFloat
            rangeValue = str(round(rangeValue * 100, 2))
            print(name + "\topen:" + start + "\tnow:" + now + "\trange:" + rangeValue + "%")

    if failed:
        print(str(failed) + " 个代码未取到行情", file=sys.stderr)


def main():
    args = sys.argv[1:]
    if not args:
        print("用法：python monkey-bitable.py <多维表格链接> [列名，默认 " + DEFAULT_FIELD + "]")
        print("示例：python monkey-bitable.py \"https://xxx.feishu.cn/wiki/PoqXwHD95iU3VSkkxuEc0vL9nrb?table=tblpyRBAhEwCBTh9&view=vewBlj9X0G\"")
        print("说明：读取指定视图的代码列，再用 " + QUOTE_URL + " 查行情并打印")
        return

    field_name = args[1] if len(args) > 1 else DEFAULT_FIELD

    try:
        codes = get_codes(args[0], field_name)
    except RuntimeError as e:
        print(e)
        return

    if not codes:
        print("没有读取到股票代码（列名：" + field_name + "）")
        return

    print_quotes(codes)


if __name__ == "__main__":
    main()
