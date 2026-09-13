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


def fetch_quotes(codes, batch_size=BATCH_SIZE):
    """批量查询行情，返回 {代码: {name, now, prev_close}}"""
    quotes = {}
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        r = requests.get(QUOTE_URL + ",".join(batch), timeout=15)

        for line in r.text.strip().split("\n"):
            if "=" not in line:
                continue
            options = line.split("=")[1][1:].split("~")
            if len(options) < 5:
                continue

            code = line.split("=")[0].replace("v_", "").strip()
            quotes[code] = {
                "name": options[1],
                "now": options[3],
                "prev_close": options[4],
            }
    return quotes


def print_quotes(codes):
    """批量查询行情并打印"""
    quotes = fetch_quotes(codes)

    failed = 0
    for code in codes:
        one = quotes.get(code)
        if not one:
            failed += 1
            continue

        prevClose = one["prev_close"]
        now = one["now"]

        prevFloat = float(prevClose)
        nowFloat = float(now)
        rangeValue = (nowFloat - prevFloat) / prevFloat
        rangeValue = str(round(rangeValue * 100, 2))
        print(one["name"] + "\topen:" + prevClose + "\tnow:" + now + "\trange:" + rangeValue + "%")

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
