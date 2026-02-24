# coding=utf-8
import requests

r = requests.get("http://qt.gtimg.cn/q=sh000001,sz001289,sz000625,sz300039,sh601216,sz000099,sh603069,sz002180,sz002129,sz002276,sh601727,sh600219,sz000564,sh600756,sh600996,sh600737,sh600110,sz300738")


# r = requests.get("http://hq.sinajs.cn/list=sz002581,sh601168,sz000158,sh603919,sz002665")

response = r.text

strList = response.split("\n")

profit = 0

for one in strList:
    if one == '':
        break
    options = one.split('=')[1][1:].split('~')
    name = options[1]
    start = options[4]
    now = options[3]

    startFloat = float(start)
    nowFloat = float(now)
    range = (nowFloat - startFloat) / startFloat
    range = str(round(range * 100, 2))
    print(name + "\topen:" + start + "\tnow:" + now + "\trange:" + range + "%")

profit = str(round(profit, 2))
