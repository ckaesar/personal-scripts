# coding=utf-8
"""国际指数与期指行情：新浪（国际期指 + 全球指数）+ 腾讯（美股 / 港股指数）

腾讯 qt.gtimg.cn 与 A 股脚本同一套字段（第 2 段名称、第 4 段现价、第 5 段昨收）；
新浪 hq.sinajs.cn 两套字段：
  hf_  国际期指：第 1 段现价、第 8 段昨收、第 14 段名称
  znb_ 全球指数：第 1 段名称、第 2 段现价、第 10 段昨收
新浪的 int_ 现货国际指数（int_dji 等）实测数据不更新，故不使用。
"""
import sys

import requests

import utf8

utf8.enable()

TENCENT_URL = "http://qt.gtimg.cn/q="
SINA_URL = "https://hq.sinajs.cn/list="
SINA_HEADERS = {"Referer": "https://finance.sina.com.cn/"}

# 国际期指（新浪 hf_）
SINA_HF_CODES = [
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

# 全球指数（新浪 znb_）：腾讯和新浪 int_ 都没有韩国综合，znb_KOSPI 可用
SINA_ZNB_CODES = [
    "znb_KOSPI",     # 首尔综合指数（韩国综合）
]

# znb_ 返回的名字是「首尔综合指数」，统一显示成用户习惯的叫法
NAME_OVERRIDES = {
    "znb_KOSPI": "韩国综合指数",
}

# 输出顺序：先期指，后指数现货
ORDER = SINA_HF_CODES + TENCENT_CODES + SINA_ZNB_CODES


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


def fetch_sina(codes):
    """新浪行情（hf_ 期指 + znb_ 全球指数），返回 {代码: (名称, 昨收, 现价)}"""
    r = requests.get(SINA_URL + ",".join(codes), headers=SINA_HEADERS, timeout=15)
    r.encoding = "gbk"

    quotes = {}
    for line in r.text.strip().split("\n"):
        if '="' not in line:
            continue
        parts = line.split('="')[1].strip('";').split(",")
        code = line.split("=")[0].replace("var hq_str_", "").strip()

        if code.startswith("hf_") and len(parts) >= 14:
            quotes[code] = (parts[13], parts[7], parts[0])
        elif code.startswith("znb_") and len(parts) >= 10 and parts[1]:
            quotes[code] = (NAME_OVERRIDES.get(code, parts[0]),
                            "%.2f" % float(parts[9]), "%.2f" % float(parts[1]))
    return quotes


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
    quotes.update(safe_fetch(fetch_sina, SINA_HF_CODES + SINA_ZNB_CODES))
    quotes.update(safe_fetch(fetch_tencent, TENCENT_CODES))
    print_quotes(quotes)


if __name__ == "__main__":
    main()
