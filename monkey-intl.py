# coding=utf-8
"""国际指数与期指行情：新浪（国际期指）+ 腾讯（美股 / 港股指数）+ 东财 / Yahoo（韩国综合）

腾讯 qt.gtimg.cn 与 A 股脚本同一套字段（第 2 段名称、第 4 段现价、第 5 段昨收）；
新浪 hq.sinajs.cn 的 hf_ 系列是国际期货，逗号分段（第 1 段现价、第 8 段昨收、第 14 段名称）；
韩国综合指数腾讯和新浪都没有，先用东财（国内可访问），取不到再用 Yahoo（非官方，国内不一定连得上）。
新浪的 int_ 现货国际指数（int_dji 等）实测数据不更新，故不使用。
"""
import sys

import requests

import utf8

utf8.enable()

TENCENT_URL = "http://qt.gtimg.cn/q="
SINA_URL = "https://hq.sinajs.cn/list="
SINA_HEADERS = {"Referer": "https://finance.sina.com.cn/"}
EASTMONEY_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"
UA_HEADERS = {"User-Agent": "Mozilla/5.0"}

# 国际期指（新浪 hf_），逗号分段：第 1 段现价、第 8 段昨收、第 14 段名称
SINA_CODES = [
    "hf_CHA50CFD",   # 富时中国A50期货
    "hf_NK",         # 日经225指数期货
    "hf_HSI",        # 恒生指数期货
]

# 美股 / 港股指数（腾讯，字段与 A 股一致）
TENCENT_CODES = [
    "usDJI",         # 道琼斯
    "usIXIC",        # 纳斯达克综指
    "usINX",         # 标普500
    "hkHSI",         # 恒生指数
    "hkHSTECH",      # 恒生科技指数
]

# 韩国综合指数：东财 secid、Yahoo 代码、兜底用的显示名
KOSPI_KEY = "kospi"
KOSPI_EASTMONEY_SECID = "100.KS11"
KOSPI_YAHOO_SYMBOL = "^KS11"
KOSPI_NAME = "韩国综合指数"

# 输出顺序：先期指，后指数现货
ORDER = SINA_CODES + TENCENT_CODES + [KOSPI_KEY]


def fetch_tencent(codes):
    """腾讯行情，返回 {代码: (名称, 昨收, 现价)}"""
    r = requests.get(TENCENT_URL + ",".join(codes), timeout=15)
    r.encoding = "gbk"  # 接口返回 GBK，不指定的话中文名可能乱码

    quotes = {}
    for line in r.text.strip().split("\n"):
        if "=" not in line:
            continue
        parts = line.split("=")[1].strip('";').split("~")
        if len(parts) < 5:
            continue
        code = line.split("=")[0].replace("v_", "").strip()
        quotes[code] = (parts[1], parts[4], parts[3])
    return quotes


def fetch_sina_hf(codes):
    """新浪国际期指，返回 {代码: (名称, 昨收, 现价)}"""
    r = requests.get(SINA_URL + ",".join(codes), headers=SINA_HEADERS, timeout=15)
    r.encoding = "gbk"

    quotes = {}
    for line in r.text.strip().split("\n"):
        if '="' not in line:
            continue
        parts = line.split('="')[1].strip('";').split(",")
        if len(parts) < 14:
            continue
        code = line.split("=")[0].replace("var hq_str_", "").strip()
        quotes[code] = (parts[13], parts[7], parts[0])
    return quotes


def fetch_kospi():
    """韩国综合指数，返回 {KOSPI_KEY: (名称, 昨收, 现价)}；东财优先，Yahoo 兜底"""
    for fetch in (kospi_from_eastmoney, kospi_from_yahoo):
        try:
            one = fetch()
        except requests.RequestException:
            continue
        if one:
            return {KOSPI_KEY: one}
    return {}


def kospi_from_eastmoney():
    """东财 ulist：f2 现价、f14 名称、f18 昨收"""
    r = requests.get(EASTMONEY_URL, headers=UA_HEADERS, timeout=15, params={
        "fltt": 2,
        "fields": "f2,f14,f18",
        "secids": KOSPI_EASTMONEY_SECID,
    })
    rows = ((r.json().get("data") or {}).get("diff") or [])
    if not rows:
        return None
    one = rows[0]
    return (one.get("f14") or KOSPI_NAME, "%.2f" % float(one["f18"]), "%.2f" % float(one["f2"]))


def kospi_from_yahoo():
    """Yahoo chart 兜底：meta 里的 regularMarketPrice / chartPreviousClose"""
    r = requests.get(YAHOO_URL + KOSPI_YAHOO_SYMBOL, headers=UA_HEADERS, timeout=15,
                     params={"range": "1d", "interval": "1d"})
    result = (r.json().get("chart") or {}).get("result") or []
    if not result:
        return None
    meta = result[0].get("meta") or {}
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    now = meta.get("regularMarketPrice")
    if prev is None or now is None:
        return None
    return (KOSPI_NAME, "%.2f" % float(prev), "%.2f" % float(now))


def safe_fetch(fetch, *args):
    """单个数据源失败（网络、返回格式变化）不影响其它源"""
    try:
        return fetch(*args)
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        print("取数失败（" + fetch.__name__ + "）：" + str(e), file=sys.stderr)
        return {}


def print_quotes(quotes):
    """按现有脚本的格式打印：名称 open:昨收 now:现价 range:涨跌幅%"""
    failed = 0
    for code in ORDER:
        one = quotes.get(code)
        if not one:
            failed += 1
            continue

        name, prevClose, now = one
        prevFloat = float(prevClose)
        nowFloat = float(now)
        rangeValue = (nowFloat - prevFloat) / prevFloat * 100 if prevFloat else 0
        print(name + "\topen:" + prevClose + "\tnow:" + now
              + "\trange:" + str(round(rangeValue, 2)) + "%")

    if failed:
        print(str(failed) + " 个标的未取到行情", file=sys.stderr)


def main():
    quotes = {}
    quotes.update(safe_fetch(fetch_sina_hf, SINA_CODES))
    quotes.update(safe_fetch(fetch_tencent, TENCENT_CODES))
    quotes.update(safe_fetch(fetch_kospi))
    print_quotes(quotes)


if __name__ == "__main__":
    main()
