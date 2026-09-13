# personal-scripts

各种场景的脚本，包括 python、shell、js 等。

## 环境准备

依赖 Python 3 和 requests：

```bash
pip install requests
```

## 脚本清单

| 脚本 | 用途 | 入参 |
|---|---|---|
| [monkey.py](monkey.py) | 查询写死在脚本里的几只股票/指数行情 | 无（改脚本里的代码列表） |
| [monkey-bk.py](monkey-bk.py) | 同上，另一组代码 | 无 |
| [monkey-jj.py](monkey-jj.py) | 同上，含基金代码 | 无 |
| [monkey-name.py](monkey-name.py) | 按股票名称查代码并输出行情 | 股票名称，可多个 |
| [monkey-list.py](monkey-list.py) | 获取全部 A 股代码和名称，写入 stocks.csv | 无 |
| [feishu-bitable.py](feishu-bitable.py) | 读取飞书多维表格指定表格、视图、列的值 | 表格链接或 app_token + table_id，列名可选 |
| [monkey-bitable.py](monkey-bitable.py) | 读飞书多维表格指定视图的代码列，输出行情 | 多维表格链接，列名可选 |
| [monkey-hold.py](monkey-hold.py) | 持仓表视图的快捷查询（固定链接，复用 monkey-bitable.py） | 无 |
| [feishu_bitable.py](feishu_bitable.py) | 飞书多维表格读取的公共模块（被上面两个脚本调用，不直接运行） | — |

## 股票行情脚本

数据源：腾讯行情接口 `http://qt.gtimg.cn/q=<带市场前缀的代码>`，支持一次查多只（逗号分隔）。
代码格式：沪市 `sh600xxx`、科创板 `sh688xxx`、深市 `sz000xxx/sz300xxx`、北交所 `bj920xxx`。

### monkey.py / monkey-bk.py / monkey-jj.py

查询脚本内写死的代码列表，三者仅代码列表不同。换股票需要编辑脚本里的 URL。

```bash
python monkey.py
```

输出（tab 分隔）：

```text
贵州茅台	open:1285.13	now:1266.50	range:-1.45%
```

字段口径与腾讯接口字段一一对应：`open` 是接口第 4 个字段（**昨收**）、`now` 是现价（第 3 个字段）、`range` 是相对昨收的涨跌幅，即当日涨跌幅。

### monkey-name.py

按名称反查代码，再输出行情。名称支持模糊匹配和拼音，命中多个时取第一个 A 股并提示候选。

```bash
python monkey-name.py 贵州茅台 平安银行
python monkey-name.py 平安
python monkey-name.py gzmt
```

输出：

```text
贵州茅台	open:1285.13	now:1266.50	range:-1.45%
提示：平安 匹配到多个结果，已取第一个，候选：平安银行(sz000001), 平安电工(sz001359)
平安银行	open:11.85	now:11.80	range:-0.42%
```

查不到时输出 `<名称>	未找到匹配的股票`。

### monkey-list.py

从巨潮资讯拉取全部 A 股（沪深京）代码和名称，写入当前目录的 `stocks.csv`（utf-8-sig，两列 `code,name`，Excel 可直接打开）。

```bash
python monkey-list.py
```

输出：`共 6171 只，已保存到 stocks.csv`

注意：该列表包含已退市/终止上市的公司（如 `sh600001 邯郸钢铁`），比在市股票多几百只。

### monkey-bitable.py

读取飞书多维表格**指定视图**中的代码列，再查行情，打印格式与 monkey.py 一致。

```bash
python monkey-bitable.py "<多维表格链接>"
python monkey-bitable.py "<多维表格链接>" 股票代码
```

链接形如 `https://xxx.feishu.cn/wiki/<token>?table=tblxxxx&view=vewxxxx`，脚本自动解析 `app_token`、`table_id`、`view_id`，列名默认「股票代码」，按出现顺序去重后每 50 个一批查询。

输出：

```text
元力股份	open:18.35	now:18.02	range:-1.8%
电力ETF广发	open:1.062	now:1.054	range:-0.75%
```

### monkey-hold.py

固定了持仓表链接与视图的快捷脚本，直接运行即可，逻辑全部复用 monkey-bitable.py。

```bash
python monkey-hold.py
```

换表格或视图时，编辑脚本顶部的 `URL`。

## 飞书多维表格脚本

### 配置

凭证放在项目根目录的 `feishu-config.json`（已加入 `.gitignore`，不会提交）：

```json
{
  "app_id": "cli_xxx",
  "app_secret": "xxx"
}
```

使用前需要在飞书开放平台完成：

1. 创建企业自建应用，拿到 App ID / App Secret
2. 开通多维表格相关权限（如 `bitable:app` 或 `bitable:app:readonly`）
3. 在多维表格「…」→ 添加文档应用，把该应用加为「可编辑」或「可管理」，否则会出现接口成功但返回数据为空

### feishu-bitable.py

读取指定表格、指定列的值。

```bash
python feishu-bitable.py "<多维表格链接>" 股票名称 股票代码
python feishu-bitable.py "<多维表格链接>"                 # 不传列名时输出全部列
python feishu-bitable.py <app_token> <table_id> 股票代码
```

说明：

- 链接支持 `/base/xxx` 和 `/wiki/xxx` 两种形态，后者（wiki）的 node_token 可直接作为 app_token 使用
- 链接里带 `view` 参数时只读该视图的记录
- 输出为 tab 分隔的表头 + 数据行，记录条数打印到 stderr，便于重定向保存
- 列名写错时会提示「列名不存在」并列出表格可用列
- 日期字段返回毫秒时间戳，脚本原样输出

## 备注

- 行情接口为公开接口，非官方授权，仅用于个人查看
- 部分数据源不稳定：新浪列表接口高频请求会返回 HTTP 456，东方财富 `push2.eastmoney.com` 在部分网络下连接被重置，因此 `monkey-list.py` 采用巨潮资讯接口
