# coding=utf-8
import requests

r = requests.get("http://qt.gtimg.cn/q=sh000001,sz002837,sz300346,sz002460,sz002412,sz300809,sz000021,sz002185,sh603212,sh600875,sz000066")


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
