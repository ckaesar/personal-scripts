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
| [monkey-target.py](monkey-target.py) | 读目标价表的代码与目标价，对比当前股价 | 无 |
| [monkey-intl.py](monkey-intl.py) | 国际指数与期指（A50/日经/恒指期货 + 道指/纳指/标普/恒指/恒生科技/韩国综合） | 无 |
| [trade-analysis/monkey-review.py](trade-analysis/monkey-review.py) | 交易复盘分析（脚本统计 + AI 分析），产出报告与统计材料 | 无 |
| [ai_client.py](ai_client.py) | OpenAI 兼容模型调用封装（供 monkey-review.py 使用，配置读 feishu-config.json 的 ai 段） | — |
| [feishu_bitable.py](feishu_bitable.py) | 飞书多维表格读取的公共模块（被上面两个脚本调用，不直接运行） | — |
| [utf8.py](utf8.py) | 修正服务器 ascii 环境下的输出编码与中文命令行入参（各脚本打印前调用，不直接运行） | — |

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

### trade-analysis/monkey-review.py

交易复盘分析。脚本负责取数与统计（客观、可核对），**分析结论交由 AI 生成**（OpenAI 兼容接口）。脚本在 `trade-analysis/`，产物统一写在 `trade-analysis/reports/`：

```bash
cd trade-analysis
python monkey-review.py
```

| 文件 | 内容 |
|---|---|
| `index.html` | **入口页**：列出 `reports/` 下的历史报告（静态托管访问 `trade-analysis/` 目录时用） |
| `reports/report-YYYYMMDD.html` | **单文件 HTML 报告**：全量 / 近期 / 对比三份内容，顶部 tab 切换 |
| `reports/trade-facts-*.md` | 喂给模型的统计材料（结构化事实，便于核对 AI 的依据） |

- 报告为**单文件原生 HTML**（内嵌 CSS/JS，无任何外部框架或资源），双击即可在任意环境打开
- **近期区间**：默认取近 30 天的已清仓记录；若不足 30 笔，则改为取最近 30 笔，tab、表头与材料标题都会显示实际区间
- **图表为脚本生成的原生 SVG**：月度盈亏柱状图、累计盈亏折线图、持股周期胜率、止损模拟、板块盈亏、仓位分层、每笔盈亏序列，对比页还有全量 vs 近期的分组对比图
- AI 以「顶级交易分析师」角色输出，要求表格化、分层列表、并列对比等结构化表达；正文严禁输出 SVG/HTML/图片语法（脚本另做兜底清理）
- 数据与结论严格以本次运行实时拉取的数据为唯一事实来源（prompt 中强制约束，禁止编造）
- 文件名只带日期，当天重复执行会**覆盖**

**统一配置** 项目所有凭证与模型配置都放在 `feishu-config.json`（已加入 `.gitignore`）：

```json
{
  "app_id": "cli_xxx",
  "app_secret": "xxx",
  "ai": {
    "base_url": "https://api.deepseek.com",
    "api_key": "sk-xxx",
    "model": "deepseek-chat"
  }
}
```

- `ai` 段只被 monkey-review.py 使用；`base_url` 兼容任何 OpenAI 协议服务（通义 `compatible-mode/v1`、OpenAI、Kimi、智谱、本地 Ollama 等）
- 未填 `ai.api_key` 时脚本直接提示并退出；调用失败会自动重试（最多 3 次，等待 5/10/15 秒），仍失败则提示原因且不生成报告
- 发给模型的内容：统计指标、分组结果、盈亏明细（含复盘原文摘要）、止损模拟；不包含飞书凭证

**报告结构**（AI 按固定框架输出，prompt 见脚本顶部 `SYSTEM_PROMPT`）：一句话诊断 → 账户体检解读 → 按危害排序的问题 → 已被验证的优势 → 改进的量化空间 → 立刻要立的硬纪律 → 长期机制；之后是脚本生成的可视化图表与数据附录（账户体检、持股周期、止损模拟、板块、仓位、月度、跟操与止损标记、关键词、亏损 Top10）。

`trade-analysis/` 下的 `*.md`、`*.html` 已在 `.gitignore`（含个人交易数据，不要提交）；脚本本身正常入库。

调整口径改脚本顶部常量：`URL`、`RECENT_DAYS`、`DAY_BINS` / `COST_BINS` / `STOP_LIMITS` / `KEYWORDS` / `LOSS_DETAIL`（喂给模型的明细条数）。

### monkey-target.py

读取目标价表的「股票代码」和「目标价」，与当前股价对比，逻辑复用 monkey-bitable.py 的行情查询。

```bash
python monkey-target.py
```

输出（tab 分隔）：

```text
华天科技	open:16.38	now:16.20	range:-1.1%	target:15.00	diff:-1.20	rate:-7.41%
诺德股份	open:11.25	now:10.83	range:-3.73%	target:10.83	diff:0.00	rate:0.00%
```

- `open`：昨收价（行情接口第 4 个字段，与 monkey.py 口径一致）
- `now`：当前股价
- `range`：(当前股价 − 昨收) / 昨收
- `target`：目标价，表格里为空时默认取当前股价
- `diff`：目标价 − 当前股价
- `rate`：(目标价 − 当前股价) / 当前股价

换表格或视图时，编辑脚本顶部的 `URL`。

### monkey-intl.py

国际指数与期指，两个数据源合并输出（不需要飞书配置）。

```bash
python monkey-intl.py
```

输出（tab 分隔，口径与其它脚本一致：`open` 是昨收）：

```text
富时中国A50期货	open:13039.000	now:13106.440	range:0.52%
日经225指数期货	open:62255.000	now:62781.600	range:0.85%
恒生指数期货	open:23115.000	now:23228.150	range:0.49%
道琼斯	open:52867.98	now:52215.16	range:-1.23%
纳斯达克	open:26008.86	now:25955.34	range:-0.21%
标普500	open:7663.43	now:7623.68	range:-0.52%
恒生指数	open:23093.370	now:23211.810	range:0.51%
恒生科技指数	open:3871.660	now:3857.530	range:-0.36%
韩国综合指数	open:5550.30	now:5469.47	range:-1.46%
```

| 数据源 | 覆盖标的 | 说明 |
|---|---|---|
| 新浪 `hf_` | A50、日经225、恒指的**期货** | `hq.sinajs.cn/list=hf_CHA50CFD`，必须带 `Referer: https://finance.sina.com.cn/` |
| 腾讯 | 道指 / 纳指综指 / 标普500 / 恒指 / 恒生科技（**现货指数**） | `qt.gtimg.cn/q=usDJI`，字段与 A 股脚本完全相同 |
| 东财 / Yahoo | 韩国综合指数（腾讯、新浪都没有） | 东财 `push2.eastmoney.com` 的 `100.KS11` 优先，取不到再用 Yahoo `^KS11`（非官方）兜底 |

- 期指和现货是两个价格，A50/日经/恒指的期货与对应指数会有价差
- 新浪的 `int_` 现货国际指数（`int_dji`、`int_nikkei` 等）实测长期不更新，脚本没有采用；`int_kospi`、`int_dax` 直接返回空
- 韩国综合指数腾讯、新浪都没有：脚本先试东财（国内可访问），失败再试 Yahoo（非官方接口，国内不一定连得上）
- 单个数据源失败只影响它自己那几行（原因打到 stderr），不会导致整批没输出
- 加/换标的改脚本顶部的 `SINA_CODES` / `TENCENT_CODES`；韩国综合改 `KOSPI_EASTMONEY_SECID` / `KOSPI_YAHOO_SYMBOL`

## 飞书多维表格脚本

### 配置

凭证放在项目根目录的 `feishu-config.json`（已加入 `.gitignore`，不会提交）：

```json
{
  "app_id": "cli_xxx",
  "app_secret": "xxx"
}
```

该文件同时也是项目统一配置文件，模型密钥放在 `ai` 段（见 monkey-review.py 一节）。

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
