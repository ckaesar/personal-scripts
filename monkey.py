# coding=utf-8
import requests

r = requests.get("http://qt.gtimg.cn/q=sh000001,sz300039,sz001289,sz300812,sz000977")


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
