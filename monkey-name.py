# coding=utf-8
import codecs
import sys

import requests

SEARCH_URL = "https://smartbox.gtimg.cn/s3/"
QUOTE_URL = "http://qt.gtimg.cn/q="


def search_stock(keyword):
    """根据股票名称/拼音查询候选股票"""
    r = requests.get(SEARCH_URL, params={"v": "2", "q": keyword, "t": "all"}, timeout=10)

    text = r.text
    body = text.split('"')[1] if '"' in text else ""

    stocks = []
    for one in body.split("^"):
        options = one.split("~")
        if len(options) < 3:
            continue
        stocks.append({
            "code": options[0] + options[1],
            "name": codecs.decode(options[2], "unicode_escape"),
            "type": options[4] if len(options) > 4 else "",
        })
    return stocks


def pick_stock(stocks):
    """优先取 A 股，其次取第一个候选"""
    aStocks = [one for one in stocks if one["type"] == "GP-A"]
    if aStocks:
        return aStocks[0], aStocks
    if stocks:
        return stocks[0], stocks
    return None, []


def print_quote(stock):
    """参考 monkey.py 的接口和打印格式输出行情"""
    r = requests.get(QUOTE_URL + stock["code"], timeout=10)

    line = r.text.strip().split("\n")[0]
    if "=" not in line:
        print(stock["name"] + "\t未获取到行情")
        return

    options = line.split("=")[1][1:].split("~")
    if len(options) < 5:
        print(stock["name"] + "\t未获取到行情")
        return

    name = options[1]
    start = options[4]
    now = options[3]

    startFloat = float(start)
    nowFloat = float(now)
    range = (nowFloat - startFloat) / startFloat
    range = str(round(range * 100, 2))
    print(name + "\topen:" + start + "\tnow:" + now + "\trange:" + range + "%")


def main():
    keywords = sys.argv[1:]
    if not keywords:
        print("用法：python monkey-name.py 股票名称 [股票名称 ...]")
        print("示例：python monkey-name.py 贵州茅台 平安银行")
        return

    for keyword in keywords:
        stock, candidates = pick_stock(search_stock(keyword))
        if stock is None:
            print(keyword + "\t未找到匹配的股票")
            continue
        if len(candidates) > 1:
            names = [one["name"] + "(" + one["code"] + ")" for one in candidates]
            print("提示：" + keyword + " 匹配到多个结果，已取第一个，候选：" + ", ".join(names))
        print_quote(stock)


if __name__ == "__main__":
    main()
