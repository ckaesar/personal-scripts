# coding=utf-8
import csv

import requests

# 巨潮资讯股票列表，沪深京一次全量返回；字段：code 代码 / zwjc 中文简称 / category 类别
LIST_URL = "http://www.cninfo.com.cn/new/data/szse_stock.json"
CSV_FILE = "stocks.csv"


def get_market(code):
    """根据代码判断交易所前缀"""
    if code.startswith("6"):
        return "sh"
    if code.startswith(("0", "3")):
        return "sz"
    return "bj"


def get_all_stocks():
    """获取全部 A 股（沪深京）的代码和名称"""
    r = requests.get(LIST_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)

    stocks = []
    for one in r.json()["stockList"]:
        if one["category"] != "A股":
            continue
        stocks.append({"code": get_market(one["code"]) + one["code"], "name": one["zwjc"]})
    return stocks


def save_csv(stocks):
    """把代码和名称两列写入 CSV（utf-8-sig 便于 Excel 直接打开）"""
    with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["code", "name"])
        for one in stocks:
            writer.writerow([one["code"], one["name"]])


def main():
    stocks = get_all_stocks()
    save_csv(stocks)
    print("共 " + str(len(stocks)) + " 只，已保存到 " + CSV_FILE)


if __name__ == "__main__":
    main()
