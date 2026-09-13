# coding=utf-8
"""交易复盘分析：每次执行生成一个单文件 HTML 报告（全量 / 最近区间 / 对比，顶部切换）

脚本负责取数与统计（客观、可核对），分析部分交给大模型（OpenAI 兼容接口）。
HTML 不引用任何外部框架/资源，双击即可打开；图表为脚本生成的原生 SVG。

产出都写在脚本所在目录下的 reports/ 中：
  reports/report-YYYYMMDD.html         单文件报告（三个 tab）
  reports/trade-facts-*.md             喂给模型的统计材料（便于核对 AI 依据）
入口页写在 trade-analysis/index.html（列出 reports/ 下的历史报告，便于静态托管访问目录）

模型配置读取自项目根目录 feishu-config.json 的 ai 段。
"""
import html
import os
import re
import statistics as st
import sys
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE_DIR))

import ai_client
import feishu_bitable as fb

# 已清仓记录视图
URL = "https://my.feishu.cn/wiki/PoqXwHD95iU3VSkkxuEc0vL9nrb?table=tblpyRBAhEwCBTh9&view=vewwqbPGtD"
OUT_DIR = os.path.join(BASE_DIR, "reports")
RECENT_DAYS = 30
# 近一个月笔数不足该值时，改为取最近这么多笔交易
RECENT_MIN_COUNT = 30

FIELDS = ["股票名称", "股票代码", "买入日期", "买入价格", "买入总成本", "卖出日期", "卖出价格",
          "持股天数", "盈亏金额", "盈亏比", "标签", "是否跟操", "是否严格止盈/止损",
          "操作计划", "复盘内容", "反思"]

DAY_BINS = [(0, 2), (3, 5), (6, 10), (11, 20), (21, 100000)]
COST_BINS = [(0, 30000), (30000, 50000), (50000, 70000), (70000, 10 ** 9)]
STOP_LIMITS = [-5, -8, -10, -15]

KEYWORDS = ["止损", "止盈", "追高", "追涨", "补仓", "加仓", "恐慌", "犹豫", "没执行", "未执行",
            "贪婪", "贪心", "恐惧", "重仓", "满仓", "割肉", "抄底", "扛", "冲高", "回落",
            "破位", "均线", "轨道线", "量能", "涨停", "大盘", "仓位", "计划", "反T"]

REVERSAL_WORDS = ["反T", "反t"]
ADD_WORDS = ["加仓", "补仓", "摊平", "摊成本", "躺", "扛", "死扛", "持有"]
FOLLOW_TAGS = ["教父", "老师", "推荐", "跟操", "股票池", "VIP", "报告"]

# 喂给模型的明细条数与文本长度上限（控制 token）
LOSS_DETAIL = 10
WIN_DETAIL = 5
TEXT_LIMIT = 160

UP_COLOR = "#16a34a"
DOWN_COLOR = "#dc2626"
BRAND_COLOR = "#2563eb"

SYSTEM_PROMPT = """你是一位顶级交易分析师（top-tier trading analyst），长期在机构自营与对冲基金一线做交易复盘与风控诊断。

最重要的前提（违反即视为无效分析）：
- 你只能使用材料中给出的数字与文本。这些数据是脚本在本次运行时实时从多维表格拉取的，是唯一事实来源
- 严禁编造、估算、脑补或凭记忆补充任何数据（包括行情、宏观、公司基本面、新闻、人物），严禁使用材料之外的数字
- 若材料没有提供某项信息，就不要写它，不要用"可能""大概"填补

写作要求：
1. 以顶级交易分析师的视角下判断：先给结论，再给证据；不堆砌形容词，不写正确的废话
2. 引用数字必须与材料逐字一致：不得改写、换算、四舍五入或替换（例如材料写「最长连亏 7 笔、最长连盈 4 笔」，就不能写成「最长连亏 4 笔」）
3. 引用复盘/计划原文必须是材料中逐字出现的内容，不得改写或拼接；基于文本推断时标注「从复盘文本看」
4. 问题按危害程度排序，每个问题给出：数据证据 + 典型案例 + 复盘原文引用（可精简）
5. 给出能立即执行的硬性纪律，必须带具体阈值（止损百分比、仓位上限、次数限制等），不要空泛建议
6. 表达要可视化、结构化：多用 Markdown 表格、分层列表、并列对比（A vs B）、加粗关键数字；避免大段文字堆砌，单段不超过 4 行
7. 报告中已有脚本生成的原生 SVG 图表与数据附录：正文里**绝对不要**输出 SVG/HTML 标签、图片语法（如 `![...](...)`）、data URI、base64 或代码块，也不要尝试自己画图；引用图表里的关键数字即可
8. 正文只允许使用 Markdown 文本、表格、列表、引用与加粗；不要写报告大标题（一级标题），直接以 `##` 二级标题开始
9. 结构固定为：一句话诊断 / 账户体检解读 / 按危害排序的问题 / 已被验证的优势 / 改进的量化空间 / 立刻要立的硬纪律 / 长期机制
10. 全文 1200-1800 字
"""

HTML_HEAD = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>交易分析报告 · __TITLE__</title>
<style>
:root{--bg:#f6f8fb;--card:#fff;--line:#e5e7eb;--text:#111827;--muted:#6b7280;--up:#16a34a;--down:#dc2626;--brand:#2563eb;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;}
header{position:sticky;top:0;background:#fff;border-bottom:1px solid var(--line);padding:16px 20px 12px;z-index:10}
h1{font-size:18px;margin:0 0 4px}
.meta{color:var(--muted);font-size:12px}
.tabs{display:flex;gap:8px;margin-top:12px;overflow-x:auto;padding-bottom:2px}
.tab{border:1px solid var(--line);background:#fff;padding:8px 14px;border-radius:999px;cursor:pointer;font-size:13px;white-space:nowrap;color:var(--muted);font-family:inherit}
.tab:hover{border-color:var(--brand);color:var(--brand)}
.tab.active{background:var(--brand);border-color:var(--brand);color:#fff;font-weight:600}
.badge{display:inline-block;background:rgba(37,99,235,.1);color:var(--brand);border-radius:999px;padding:1px 8px;font-size:12px;margin-left:6px}
.tab.active .badge{background:rgba(255,255,255,.25);color:#fff}
main{padding:20px;max-width:1020px;margin:0 auto}
.panel{display:none}
.panel.active{display:block}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:6px 20px 18px;margin-bottom:16px;box-shadow:0 1px 2px rgba(16,24,40,.04)}
.card h2{font-size:16px;margin:18px 0 10px}
.card h3{font-size:15px;margin:16px 0 8px}
.card h4{font-size:14px;margin:14px 0 6px;color:#374151}
table{width:100%;border-collapse:collapse;margin:10px 0;font-size:13px}
th,td{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
th{background:#f9fafb;font-weight:600;color:#374151}
tr:hover td{background:#fafbfc}
ul,ol{margin:8px 0;padding-left:22px}
li{margin:4px 0}
code{background:#f3f4f6;padding:1px 5px;border-radius:4px;font-size:12px}
blockquote{margin:10px 0;padding:8px 12px;border-left:3px solid var(--brand);background:#f8fafc;color:#374151;border-radius:0 8px 8px 0}
.note{color:var(--muted);font-size:12px;margin:6px 0 0}
.chart{width:100%;height:auto;display:block;margin:6px 0 2px}
.chart text{font-size:12px;fill:#374151;font-family:inherit}
.chart .lbl{fill:#6b7280}
.chart .val{fill:#111827;font-weight:600}
.chart-title{font-size:14px;font-weight:600;margin:18px 0 4px}
.chart-sub{color:var(--muted);font-size:12px;margin:0 0 6px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:760px){.grid2{grid-template-columns:1fr}}
.legend{color:var(--muted);font-size:12px;margin:2px 0 8px}
.dot{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:4px;vertical-align:middle}
footer{color:var(--muted);font-size:12px;padding:0 20px 40px;max-width:1020px;margin:0 auto}
</style>
</head>
<body>
<header>
  <h1>交易分析报告</h1>
  <div class="meta">__META__</div>
  <nav class="tabs">__TABS__</nav>
</header>
<main>__PANELS__</main>
<footer>本报告由 <code>trade-analysis/monkey-review.py</code> 生成：数据与图表由脚本实时统计，分析正文由 AI 生成。所有数字以数据附录为准。</footer>
<script>
document.querySelectorAll('.tab').forEach(function(btn){
  btn.addEventListener('click', function(){
    document.querySelectorAll('.tab').forEach(function(b){b.classList.remove('active');});
    document.querySelectorAll('.panel').forEach(function(p){p.classList.remove('active');});
    btn.classList.add('active');
    document.getElementById(btn.dataset.target).classList.add('active');
  });
});
</script>
</body>
</html>
"""


# ---------- 数据与统计 ----------

def to_num(value):
    """把字段值转成数字，失败返回 None"""
    text = fb.format_value(value).strip().replace("%", "").replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def clip(text, size=40):
    text = " ".join(str(text).split())
    return text if len(text) <= size else text[:size] + "..."


def load_trades():
    """读取已清仓记录"""
    app_token, table_id, view_id = fb.parse_table_url(URL)
    app_id, app_secret = fb.load_config()
    token = fb.get_tenant_access_token(app_id, app_secret)
    records = fb.search_records(token, app_token, table_id, FIELDS, view_id)

    trades = []
    for one in records:
        sell_ts = to_num(one.get("卖出日期"))
        review = fb.format_value(one.get("复盘内容"))
        plan = fb.format_value(one.get("操作计划"))
        reflect = fb.format_value(one.get("反思"))
        trades.append({
            "name": fb.format_value(one.get("股票名称")),
            "cost": to_num(one.get("买入总成本")) or 0,
            "pnl": to_num(one.get("盈亏金额")) or 0,
            "rate": to_num(one.get("盈亏比")),
            "days": to_num(one.get("持股天数")),
            "sell_ts": sell_ts,
            "month": datetime.fromtimestamp(sell_ts / 1000).strftime("%Y-%m") if sell_ts else "",
            "tag": fb.format_value(one.get("标签")),
            "follow": fb.format_value(one.get("是否跟操")) or "(空)",
            "strict": fb.format_value(one.get("是否严格止盈/止损")) or "(空)",
            "plan": plan,
            "review": review,
            "reflect": reflect,
            "text": review + " " + plan + " " + reflect,
        })
    return [t for t in trades if t["sell_ts"]]


def basic_stats(trades):
    """核心指标"""
    pnls = [t["pnl"] for t in trades]
    wins = [t["pnl"] for t in trades if t["pnl"] > 0]
    losses = [t["pnl"] for t in trades if t["pnl"] < 0]
    rates = [t["rate"] for t in trades if t["rate"] is not None]
    days = [t["days"] for t in trades if t["days"] is not None]

    stats = {
        "count": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "flats": len(pnls) - len(wins) - len(losses),
        "win_rate": len(wins) / len(pnls) * 100 if pnls else 0,
        "total_pnl": sum(pnls),
        "avg_pnl": st.mean(pnls) if pnls else 0,
        "avg_win": st.mean(wins) if wins else 0,
        "avg_loss": st.mean(losses) if losses else 0,
        "pl_ratio": (st.mean(wins) / abs(st.mean(losses))) if wins and losses else 0,
        "profit_factor": (sum(wins) / abs(sum(losses))) if wins and losses else 0,
        "max_win": max(wins) if wins else 0,
        "max_loss": min(losses) if losses else 0,
        "avg_win_rate": st.mean([r for r in rates if r > 0]) if [r for r in rates if r > 0] else 0,
        "avg_loss_rate": st.mean([r for r in rates if r < 0]) if [r for r in rates if r < 0] else 0,
        "avg_days": st.mean(days) if days else 0,
        "med_days": st.median(days) if days else 0,
        "max_days": max(days) if days else 0,
        "avg_cost": st.mean([t["cost"] for t in trades if t["cost"]]) if trades else 0,
        "reflex_rate": len([t for t in trades if t["reflect"].strip()]) / len(trades) * 100 if trades else 0,
    }
    stats["expect"] = stats["win_rate"] / 100 * stats["avg_win"] + (100 - stats["win_rate"]) / 100 * stats["avg_loss"]
    return stats


def group_stat(trades, key_func):
    """按自定义分组统计，返回 [(分组名, 笔数, 胜率, 总盈亏, 平均盈亏比)]"""
    groups = {}
    for t in trades:
        for name in key_func(t):
            groups.setdefault(name, []).append(t)

    rows = []
    for name, items in groups.items():
        wins = [x for x in items if x["pnl"] > 0]
        rates = [x["rate"] for x in items if x["rate"] is not None]
        rows.append((name, len(items), len(wins) / len(items) * 100, sum(x["pnl"] for x in items),
                     st.mean(rates) if rates else 0))
    return rows


def sum_pnl(trades):
    return sum(t["pnl"] for t in trades)


def avg_pnl(trades):
    return sum_pnl(trades) / len(trades) if trades else 0


def tag_stats(trades):
    return [r for r in group_stat(trades, lambda t: [x.strip() for x in t["tag"].split(",") if x.strip()])
            if r[1] >= 2]


def max_drawdown(trades):
    """按卖出时间顺序的累计盈亏最大回撤"""
    equity = 0
    peak = 0
    dd = 0
    for t in sorted(trades, key=lambda x: x["sell_ts"]):
        equity += t["pnl"]
        peak = max(peak, equity)
        dd = min(dd, equity - peak)
    return dd


def streaks(trades):
    """返回 (最长连盈, 最长连亏)"""
    cur_win = cur_loss = best_win = best_loss = 0
    for t in sorted(trades, key=lambda x: x["sell_ts"]):
        if t["pnl"] > 0:
            cur_win += 1
            cur_loss = 0
        elif t["pnl"] < 0:
            cur_loss += 1
            cur_win = 0
        best_win = max(best_win, cur_win)
        best_loss = max(best_loss, cur_loss)
    return best_win, best_loss


def stop_loss_sim(trades, limit):
    """止损模拟：把幅度超过 limit 的亏损单按 limit 计"""
    total = 0
    cut = 0
    for t in trades:
        if t["rate"] is not None and t["rate"] < limit:
            total += t["cost"] * limit / 100
            cut += 1
        else:
            total += t["pnl"]
    return total, cut


def day_bin_rows(trades):
    """持股周期分组"""
    rows = []
    for lo, hi in DAY_BINS:
        g = [t for t in trades if t["days"] is not None and lo <= t["days"] <= hi]
        if not g:
            continue
        w = [x for x in g if x["pnl"] > 0]
        rows.append(("%d-%d 天" % (lo, hi) if hi < 100000 else "%d 天以上" % lo,
                     len(g), len(w) / len(g) * 100, sum_pnl(g), avg_pnl(g)))
    return rows


def cost_bin_rows(trades):
    """仓位分层"""
    rows = []
    for lo, hi in COST_BINS:
        g = [t for t in trades if t["cost"] and lo <= t["cost"] < hi]
        if not g:
            continue
        w = [x for x in g if x["pnl"] > 0]
        label = "%.0f万以上" % (lo / 10000) if hi >= 10 ** 9 else "%.0f-%.0f万" % (lo / 10000, hi / 10000)
        rows.append((label, len(g), len(w) / len(g) * 100, sum_pnl(g), avg_pnl(g)))
    return rows


# ---------- Markdown → HTML ----------

def esc(text):
    return html.escape(str(text), quote=False)


def inline_md(text):
    """行内元素：加粗、行内代码"""
    out = esc(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"`(.+?)`", r"<code>\1</code>", out)
    return out


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def html_table(header, rows):
    out = ["<table><thead><tr>"]
    out += ["<th>%s</th>" % inline_md(h) for h in header]
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>" + "".join("<td>%s</td>" % inline_md(c) for c in row) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def clean_ai_text(text):
    """清理模型输出里不该出现的内容：代码块、内联 SVG/HTML、图片语法、data URI"""
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"<svg[\s\S]*?</svg>", "", text, flags=re.I)
    text = re.sub(r"</?(?:div|span|p|br|img|table|thead|tbody|tr|td|th|style|script)\b[^>]*>", "", text, flags=re.I)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"data:image/[^\s)\"']+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def md_to_html(text):
    """把 AI 输出的 Markdown 转成 HTML（支持标题/表格/列表/引用/段落）"""
    lines = clean_ai_text(text).split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        if not stripped:
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = min(len(m.group(1)) + 1, 6)
            out.append("<h%d>%s</h%d>" % (level, inline_md(m.group(2)), level))
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-|]+\|$", lines[i + 1].strip()):
            header = split_row(lines[i])
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            out.append(html_table(header, rows))
            continue

        if re.match(r"^\s*[-*]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*]\s+", "", lines[i]).strip())
                i += 1
            out.append("<ul>" + "".join("<li>%s</li>" % inline_md(x) for x in items) + "</ul>")
            continue

        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\s*\d+\.\s+", "", lines[i]).strip())
                i += 1
            out.append("<ol>" + "".join("<li>%s</li>" % inline_md(x) for x in items) + "</ol>")
            continue

        if stripped.startswith(">"):
            out.append("<blockquote>%s</blockquote>" % inline_md(stripped.lstrip("> ").strip()))
            i += 1
            continue

        para = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,6}\s|\s*[-*]\s|\s*\d+\.\s|\||>)", lines[i]):
            para.append(lines[i].strip())
            i += 1
        out.append("<p>%s</p>" % inline_md(" ".join(para)))
    return "\n".join(out)


# ---------- SVG 图表 ----------

def svg_v_bars(items, width=680, height=250, pad_bottom=34, pad_top=22):
    """纵向柱状图：items = [(标签, 数值)]，正负分色"""
    if not items:
        return ""
    values = [v for _, v in items]
    hi, lo = max(max(values), 0), min(min(values), 0)
    span = (hi - lo) or 1
    plot_h = height - pad_top - pad_bottom
    zero_y = pad_top + hi / span * plot_h
    slot = (width - 20) / len(items)
    bar_w = min(slot * 0.58, 60)

    parts = ['<svg viewBox="0 0 %d %d" class="chart" role="img">' % (width, height)]
    parts.append('<line x1="0" y1="%.1f" x2="%d" y2="%.1f" stroke="#e5e7eb"/>' % (zero_y, width, zero_y))
    for idx, (label, value) in enumerate(items):
        cx = 10 + slot * idx + slot / 2
        h = max(abs(value) / span * plot_h, 1)
        y = zero_y - h if value >= 0 else zero_y
        color = UP_COLOR if value >= 0 else DOWN_COLOR
        parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" fill="%s"/>'
                     % (cx - bar_w / 2, y, bar_w, h, color))
        ty = y - 7 if value >= 0 else y + h + 15
        parts.append('<text x="%.1f" y="%.1f" text-anchor="middle" class="val">%+.0f</text>' % (cx, ty, value))
        parts.append('<text x="%.1f" y="%d" text-anchor="middle" class="lbl">%s</text>'
                     % (cx, height - 12, esc(label)))
    parts.append("</svg>")
    return "".join(parts)


def svg_line(values, labels, width=680, height=240, pad_bottom=32, pad_top=24):
    """折线 + 面积图，标注 0 轴"""
    if not values:
        return ""
    hi, lo = max(max(values), 0), min(min(values), 0)
    span = (hi - lo) or 1
    plot_h = height - pad_top - pad_bottom
    step = (width - 40) / max(len(values) - 1, 1)

    def px(idx):
        return 20 + step * idx

    def py(value):
        return pad_top + (hi - value) / span * plot_h

    points = [(px(i), py(v)) for i, v in enumerate(values)]
    line = " ".join("%.1f,%.1f" % p for p in points)
    area = "M %.1f,%.1f L " % (points[0][0], py(0)) + " L ".join("%.1f,%.1f" % p for p in points) + \
           " L %.1f,%.1f Z" % (points[-1][0], py(0))

    parts = ['<svg viewBox="0 0 %d %d" class="chart" role="img">' % (width, height)]
    parts.append('<line x1="0" y1="%.1f" x2="%d" y2="%.1f" stroke="#e5e7eb"/>' % (py(0), width, py(0)))
    parts.append('<path d="%s" fill="rgba(37,99,235,.10)"/>' % area)
    parts.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2.2"/>' % (line, BRAND_COLOR))
    for (x, y), value in zip(points, values):
        parts.append('<circle cx="%.1f" cy="%.1f" r="3.2" fill="#fff" stroke="%s" stroke-width="2"/>'
                     % (x, y, BRAND_COLOR))
        parts.append('<text x="%.1f" y="%.1f" text-anchor="middle" class="val">%+.0f</text>'
                     % (x, y - 10 if value >= 0 else y + 18, value))
    for i, label in enumerate(labels):
        parts.append('<text x="%.1f" y="%d" text-anchor="middle" class="lbl">%s</text>'
                     % (px(i), height - 10, esc(label)))
    parts.append("</svg>")
    return "".join(parts)


def svg_h_bars(items, unit="", width=680, bar_h=22, gap=9, label_w=104):
    """横向条形图：items = [(标签, 数值)]"""
    if not items:
        return ""
    max_abs = max(abs(v) for _, v in items) or 1
    chart_w = width - label_w - 86
    height = len(items) * (bar_h + gap) + 8
    parts = ['<svg viewBox="0 0 %d %d" class="chart" role="img">' % (width, height)]
    y = 4
    for label, value in items:
        w = max(abs(value) / max_abs * chart_w, 2)
        color = UP_COLOR if value >= 0 else DOWN_COLOR
        parts.append('<text x="%d" y="%.1f" text-anchor="end" class="lbl">%s</text>'
                     % (label_w - 8, y + bar_h * 0.72, esc(label)))
        parts.append('<rect x="%d" y="%d" width="%.1f" height="%d" rx="4" fill="%s"/>' % (label_w, y, w, bar_h, color))
        text = ("%.1f%s" % (value, unit)) if unit == "%" else ("%+.0f%s" % (value, unit))
        parts.append('<text x="%.1f" y="%.1f" class="val">%s</text>' % (label_w + w + 6, y + bar_h * 0.72, text))
        y += bar_h + gap
    parts.append("</svg>")
    return "".join(parts)


def svg_trade_series(trades, width=680, height=170, pad_top=14, pad_bottom=22):
    """每笔盈亏柱状序列（按卖出时间）"""
    seq = [t["pnl"] for t in sorted(trades, key=lambda x: x["sell_ts"])]
    if not seq:
        return ""
    hi, lo = max(max(seq), 0), min(min(seq), 0)
    span = (hi - lo) or 1
    plot_h = height - pad_top - pad_bottom
    zero_y = pad_top + hi / span * plot_h
    bar_w = max((width - 10) / len(seq) * 0.8, 1)

    parts = ['<svg viewBox="0 0 %d %d" class="chart" role="img">' % (width, height)]
    parts.append('<line x1="0" y1="%.1f" x2="%d" y2="%.1f" stroke="#e5e7eb"/>' % (zero_y, width, zero_y))
    for idx, value in enumerate(seq):
        x = 5 + idx * (width - 10) / len(seq)
        h = max(abs(value) / span * plot_h, 1)
        y = zero_y - h if value >= 0 else zero_y
        color = UP_COLOR if value >= 0 else DOWN_COLOR
        parts.append('<rect x="%.2f" y="%.1f" width="%.2f" height="%.1f" fill="%s"/>' % (x, y, bar_w, h, color))
    parts.append('<text x="0" y="%d" class="lbl">最早</text>' % (height - 4))
    parts.append('<text x="%d" y="%d" text-anchor="end" class="lbl">最近（共 %d 笔）</text>' % (width, height - 4, len(seq)))
    parts.append("</svg>")
    return "".join(parts)


def svg_grouped_bars(rows, width=680, bar_h=18, gap=10, label_w=126):
    """对比图：rows = [(指标, 全量值, 近期值)]，每组两条"""
    if not rows:
        return ""
    max_abs = max(max(abs(a), abs(b)) for _, a, b in rows) or 1
    chart_w = width - label_w - 110
    group_h = bar_h * 2 + gap
    height = len(rows) * (group_h + 6) + 6
    parts = ['<svg viewBox="0 0 %d %d" class="chart" role="img">' % (width, height)]
    y = 3
    for label, va, vb in rows:
        parts.append('<text x="%d" y="%.1f" text-anchor="end" class="lbl">%s</text>'
                     % (label_w - 8, y + group_h * 0.55, esc(label)))
        for offset, value, color in ((0, va, "#94a3b8"), (bar_h + 2, vb, BRAND_COLOR)):
            w = max(abs(value) / max_abs * chart_w, 2)
            parts.append('<rect x="%d" y="%.1f" width="%.1f" height="%d" rx="3" fill="%s"/>'
                         % (label_w, y + offset, w, bar_h, color))
            text = ("%.1f" % value) if abs(value) <= 200 and value != int(value) else "%+.0f" % value
            parts.append('<text x="%.1f" y="%.1f" class="val">%s</text>'
                         % (label_w + w + 6, y + offset + bar_h * 0.78, text))
        y += group_h + 6
    parts.append("</svg>")
    return "".join(parts)


# ---------- 报告区块 ----------

def chart_section(trades):
    """可视化图表区"""
    s = basic_stats(trades)
    out = ['<div class="card"><h2>数据可视化</h2>',
           '<p class="chart-sub">全部图表由脚本按实时数据生成，原生 SVG，不依赖任何外部资源。</p>',
           '<div class="legend"><span class="dot" style="background:%s"></span>盈利 '
           '<span class="dot" style="background:%s;margin-left:12px"></span>亏损</div>' % (UP_COLOR, DOWN_COLOR)]

    months = sorted(group_stat(trades, lambda t: [t["month"]]), key=lambda r: r[0])
    out.append('<div class="chart-title">月度盈亏</div>')
    out.append(svg_v_bars([(r[0][2:], r[3]) for r in months]))
    if months:
        out.append('<p class="chart-sub">%s ~ %s，共 %d 个月。</p>'
                   % (months[0][0], months[-1][0], len(months)))

    if len(months) >= 2:
        equity = 0
        curve = []
        for _, _, _, pnl, _ in months:
            equity += pnl
            curve.append(equity)
        out.append('<div class="chart-title">累计盈亏走势（按月末）</div>')
        out.append(svg_line(curve, [r[0][2:] for r in months]))
        out.append('<p class="chart-sub">曲线为累计盈亏，最终值 %.0f。</p>' % curve[-1])

    out.append('<div class="grid2">')

    out.append('<div><div class="chart-title">持股周期胜率</div>')
    out.append(svg_h_bars([(r[0], r[2]) for r in day_bin_rows(trades)], unit="%", width=520, label_w=88))
    out.append('</div>')

    sim_rows = [("实际结果", s["total_pnl"])]
    for limit in STOP_LIMITS:
        sim_rows.append(("限制 %d%%" % limit, stop_loss_sim(trades, limit)[0]))
    out.append('<div><div class="chart-title">止损模拟：把单笔亏损截断在不同位置</div>')
    out.append(svg_h_bars(sim_rows, width=520, label_w=88))
    out.append('</div>')

    tags = tag_stats(trades)
    best = sorted([r for r in tags if r[3] > 0], key=lambda r: -r[3])[:5]
    worst = sorted([r for r in tags if r[3] < 0], key=lambda r: r[3])[:5]
    out.append('<div><div class="chart-title">板块盈亏（赚 Top5 / 亏 Top5）</div>')
    out.append(svg_h_bars([(r[0], r[3]) for r in best + worst], width=520, label_w=88))
    out.append('</div>')

    out.append('<div><div class="chart-title">仓位分层盈亏</div>')
    out.append(svg_h_bars([(r[0], r[3]) for r in cost_bin_rows(trades)], width=520, label_w=88))
    out.append('</div>')

    out.append('</div>')

    out.append('<div class="chart-title">每笔盈亏序列（按卖出时间）</div>')
    out.append(svg_trade_series(trades))
    out.append('</div>')
    return "".join(out)


def appendix_section(trades):
    """数据附录：全部为 HTML 表格"""
    s = basic_stats(trades)
    out = ['<div class="card"><h2>数据附录（脚本生成，未经 AI 修改）</h2>']

    out.append('<h3>A1. 账户体检</h3>')
    out.append(html_table(["指标", "数值"], [
        ["交易笔数", "%d（盈 %d / 亏 %d / 平 %d）" % (s["count"], s["wins"], s["losses"], s["flats"])],
        ["胜率", "%.1f%%" % s["win_rate"]],
        ["总盈亏", "%.0f（平均每笔 %.0f）" % (s["total_pnl"], s["avg_pnl"])],
        ["平均盈利 / 平均亏损", "%+.0f / %.0f，盈亏比 %.2f" % (s["avg_win"], s["avg_loss"], s["pl_ratio"])],
        ["盈利因子", "%.2f" % s["profit_factor"]],
        ["期望值/笔", "%+.0f" % s["expect"]],
        ["平均获利率 / 平均止损率", "+%.2f%% / %.2f%%" % (s["avg_win_rate"], s["avg_loss_rate"])],
        ["最大盈利 / 最大亏损", "%+.0f / %.0f" % (s["max_win"], s["max_loss"])],
        ["持股天数（中位/平均/最长）", "%.0f / %.1f / %.0f" % (s["med_days"], s["avg_days"], s["max_days"])],
        ["最大回撤 / 最长连亏 / 最长连盈", "%.0f / %d 笔 / %d 笔"
         % ((max_drawdown(trades),) + (streaks(trades)[1], streaks(trades)[0]))],
        ["反思填写率", "%.0f%%" % s["reflex_rate"]],
    ]))

    out.append('<h3>A2. 持股周期</h3>')
    out.append(html_table(["持股区间", "笔数", "胜率", "总盈亏", "平均每笔"],
                          [[r[0], r[1], "%.1f%%" % r[2], "%.0f" % r[3], "%.0f" % r[4]]
                           for r in day_bin_rows(trades)]))

    out.append('<h3>A3. 计划与执行（操作计划里是否写了止损位）</h3>')
    out.append(html_table(["分组", "笔数", "胜率", "总盈亏", "平均每笔"], [
        [label, len(g), "%.1f%%" % (len([x for x in g if x["pnl"] > 0]) / len(g) * 100),
         "%.0f" % sum_pnl(g), "%.0f" % avg_pnl(g)]
        for label, g in [("写了止损位", [t for t in trades if "止损" in t["plan"]]),
                         ("没写止损位", [t for t in trades if "止损" not in t["plan"]])] if g]))

    out.append('<h3>A4. 止损模拟</h3>')
    out.append(html_table(["情景", "总盈亏", "说明"], [["实际结果", "%.0f" % s["total_pnl"], "—"]] +
                          [["止损限制 %d%%" % limit, "%.0f" % stop_loss_sim(trades, limit)[0],
                            "%d 笔被截断" % stop_loss_sim(trades, limit)[1]] for limit in STOP_LIMITS]))

    tags = tag_stats(trades)
    best = sorted([r for r in tags if r[3] > 0], key=lambda r: -r[3])[:6]
    worst = sorted([r for r in tags if r[3] < 0], key=lambda r: r[3])[:6]
    out.append('<h3>A5. 板块（标签）表现</h3>')
    tag_rows = [[r[0], r[1], "%.1f%%" % r[2], "%.0f" % r[3], "%.2f%%" % r[4]] for r in best + worst]
    out.append(html_table(["标签", "笔数", "胜率", "总盈亏", "平均盈亏比"], tag_rows))

    out.append('<h3>A6. 仓位分层</h3>')
    out.append(html_table(["买入成本区间", "笔数", "胜率", "总盈亏", "平均每笔"],
                          [[r[0], r[1], "%.1f%%" % r[2], "%.0f" % r[3], "%.0f" % r[4]]
                           for r in cost_bin_rows(trades)]))

    out.append('<h3>A7. 时间分布（按卖出月份）</h3>')
    out.append(html_table(["月份", "笔数", "胜率", "总盈亏", "平均盈亏比"],
                          [(name, n, "%.1f%%" % wr, "%.0f" % pnl, "%.2f%%" % rate)
                           for name, n, wr, pnl, rate in sorted(group_stat(trades, lambda t: [t["month"]]),
                                                                key=lambda x: x[0])]))

    out.append('<h3>A8. 决策来源与止盈止损标记</h3>')
    out.append(html_table(["是否跟操", "笔数", "胜率", "总盈亏", "平均盈亏比"],
                          [(name, n, "%.1f%%" % wr, "%.0f" % pnl, "%.2f%%" % rate)
                           for name, n, wr, pnl, rate in sorted(group_stat(trades, lambda t: [t["follow"]]),
                                                                key=lambda x: -x[1])]))
    out.append(html_table(["严格止盈/止损", "笔数", "胜率", "总盈亏", "平均盈亏比"],
                          [(name, n, "%.1f%%" % wr, "%.0f" % pnl, "%.2f%%" % rate)
                           for name, n, wr, pnl, rate in sorted(group_stat(trades, lambda t: [t["strict"]]),
                                                                key=lambda x: -x[1])]))

    out.append('<h3>A9. 复盘文本关键词</h3>')
    krows = []
    for kw in KEYWORDS:
        hit = [t for t in trades if kw in t["text"]]
        if hit:
            krows.append([kw, len(hit), "%.0f" % sum_pnl(hit)])
    out.append(html_table(["关键词", "命中笔数", "这些笔合计盈亏"], sorted(krows, key=lambda x: -x[1])))

    out.append('<h3>A10. 亏损最大的 10 笔</h3>')
    out.append(html_table(["股票", "成本", "盈亏", "幅度", "持股天数", "标签", "严格止损"], [
        [t["name"], "%.0f" % t["cost"], "%.0f" % t["pnl"],
         ("%.2f%%" % t["rate"]) if t["rate"] is not None else "-",
         ("%.0f" % t["days"]) if t["days"] is not None else "-",
         clip(t["tag"], 16) or "-", t["strict"]]
        for t in sorted(trades, key=lambda x: x["pnl"])[:10]]))

    out.append('</div>')
    return "".join(out)


def detail_line(t):
    """单笔明细的一行文本（供模型材料使用）"""
    return ("- %s | 成本 %.0f | 盈亏 %.0f | 幅度 %s | 持股 %s 天 | 标签 %s | 跟操 %s | 严格止损 %s"
            " | 计划：%s | 复盘：%s"
            % (t["name"], t["cost"], t["pnl"],
               ("%.2f%%" % t["rate"]) if t["rate"] is not None else "-",
               ("%.0f" % t["days"]) if t["days"] is not None else "-",
               t["tag"] or "-", t["follow"], t["strict"],
               clip(t["plan"], 60) or "-", clip(t["review"], TEXT_LIMIT) or "-"))


def build_facts(trades, scope):
    """构造给模型的客观材料（Markdown 文本）"""
    s = basic_stats(trades)
    out = []
    months = sorted(t["month"] for t in trades if t["month"])
    out.append("## 数据来源")
    out.append("本材料由脚本在 %s 实时从飞书多维表格「已清仓」视图拉取，是本次分析的唯一事实来源。"
               % datetime.now().strftime("%Y-%m-%d %H:%M"))
    out.append("范围：%s，%d 笔，%s ~ %s（按卖出日期）" % (scope, s["count"], months[0], months[-1]))
    out.append("")

    out.append("## 核心指标")
    out += ["- 交易笔数：%d（盈 %d / 亏 %d / 平 %d）" % (s["count"], s["wins"], s["losses"], s["flats"]),
            "- 胜率：%.1f%%" % s["win_rate"],
            "- 总盈亏：%.0f，平均每笔 %.0f，期望值/笔 %.0f" % (s["total_pnl"], s["avg_pnl"], s["expect"]),
            "- 平均盈利 %.0f / 平均亏损 %.0f，盈亏比（均盈/均亏）%.2f，盈利因子 %.2f"
            % (s["avg_win"], s["avg_loss"], s["pl_ratio"], s["profit_factor"]),
            "- 平均获利率 +%.2f%% / 平均止损率 %.2f%%" % (s["avg_win_rate"], s["avg_loss_rate"]),
            "- 最大盈利 %.0f / 最大亏损 %.0f" % (s["max_win"], s["max_loss"]),
            "- 平均持仓市值 %.0f" % s["avg_cost"],
            "- 持股天数：中位 %.0f / 平均 %.1f / 最长 %.0f" % (s["med_days"], s["avg_days"], s["max_days"]),
            "- 反思填写率 %.0f%%" % s["reflex_rate"],
            "- 最大回撤 %.0f，最长连亏 %d 笔，最长连盈 %d 笔"
            % ((max_drawdown(trades),) + (streaks(trades)[1], streaks(trades)[0]))]
    out.append("")

    out.append("## 持股周期")
    out += md_table(["区间", "笔数", "胜率", "总盈亏", "平均每笔"],
                    [[r[0], r[1], "%.1f%%" % r[2], "%.0f" % r[3], "%.0f" % r[4]] for r in day_bin_rows(trades)])
    out.append("")

    out.append("## 板块（标签，笔数>=2）")
    out += md_table(["标签", "笔数", "胜率", "总盈亏", "平均盈亏比"],
                    [(name, n, "%.1f%%" % wr, "%.0f" % pnl, "%.2f%%" % rate)
                     for name, n, wr, pnl, rate in sorted(tag_stats(trades), key=lambda r: r[3])])
    out.append("")

    out.append("## 决策来源（是否跟操）")
    out += md_table(["分组", "笔数", "胜率", "总盈亏", "平均盈亏比"],
                    [(name, n, "%.1f%%" % wr, "%.0f" % pnl, "%.2f%%" % rate)
                     for name, n, wr, pnl, rate in sorted(group_stat(trades, lambda t: [t["follow"]]),
                                                          key=lambda x: -x[1])])
    out.append("")

    out.append("## 止盈止损执行标记")
    out += md_table(["标记", "笔数", "胜率", "总盈亏", "平均盈亏比"],
                    [(name, n, "%.1f%%" % wr, "%.0f" % pnl, "%.2f%%" % rate)
                     for name, n, wr, pnl, rate in sorted(group_stat(trades, lambda t: [t["strict"]]),
                                                          key=lambda x: -x[1])])
    out.append("")

    out.append("## 仓位分层")
    out += md_table(["买入成本区间", "笔数", "胜率", "总盈亏", "平均每笔"],
                    [[r[0], r[1], "%.1f%%" % r[2], "%.0f" % r[3], "%.0f" % r[4]] for r in cost_bin_rows(trades)])
    out.append("")

    out.append("## 按卖出月份")
    out += md_table(["月份", "笔数", "胜率", "总盈亏", "平均盈亏比"],
                    [(name, n, "%.1f%%" % wr, "%.0f" % pnl, "%.2f%%" % rate)
                     for name, n, wr, pnl, rate in sorted(group_stat(trades, lambda t: [t["month"]]),
                                                          key=lambda x: x[0])])
    out.append("")

    has_plan = [t for t in trades if "止损" in t["plan"]]
    no_plan = [t for t in trades if "止损" not in t["plan"]]
    out.append("## 计划与执行（操作计划里是否写了止损位）")
    out += md_table(["分组", "笔数", "占比", "胜率", "总盈亏", "平均每笔"], [
        [label, len(g), "%.0f%%" % (len(g) / s["count"] * 100),
         "%.1f%%" % (len([x for x in g if x["pnl"] > 0]) / len(g) * 100), "%.0f" % sum_pnl(g), "%.0f" % avg_pnl(g)]
        for label, g in [("写了止损位", has_plan), ("没写止损位", no_plan)] if g])
    out.append("")

    out.append("## 尾部风险与止损模拟")
    worst = sorted(trades, key=lambda t: t["pnl"])[:5]
    worst_sum = sum_pnl(worst)
    out.append("- 最惨 5 笔合计 %.0f，其余 %d 笔合计 %.0f" % (worst_sum, s["count"] - len(worst),
                                                              s["total_pnl"] - worst_sum))
    for limit in STOP_LIMITS:
        total, cut = stop_loss_sim(trades, limit)
        out.append("- 若单笔止损限制在 %d%%：总盈亏变为 %.0f（%d 笔被截断，改善 %.0f）"
                   % (limit, total, cut, total - s["total_pnl"]))
    out.append("")

    reversal = [t for t in trades if any(w in t["text"] for w in REVERSAL_WORDS)]
    adding = [t for t in trades if t["pnl"] < 0 and any(w in t["text"] for w in ADD_WORDS)]
    follow_tag = [t for t in trades if t["tag"] and any(w in t["tag"] for w in FOLLOW_TAGS)]
    out.append("## 复盘文本关键词统计")
    kw_rows = []
    for kw in KEYWORDS:
        hit = [t for t in trades if kw in t["text"]]
        if hit:
            kw_rows.append([kw, len(hit), "%.0f" % sum_pnl(hit)])
    out += md_table(["关键词", "命中笔数", "这些笔合计盈亏"], sorted(kw_rows, key=lambda x: -x[1]))
    out.append("- 提到「反T」的：%d 笔，合计 %.0f" % (len(reversal), sum_pnl(reversal)))
    out.append("- 提到「加仓/补仓/躺/扛/持有」且亏损的：%d 笔，合计 %.0f" % (len(adding), sum_pnl(adding)))
    out.append("- 标签含「%s」等来源的：%d 笔，合计 %.0f"
               % ("/".join(FOLLOW_TAGS[:4]), len(follow_tag), sum_pnl(follow_tag)))
    out.append("")

    out.append("## 亏损最大的 %d 笔明细" % LOSS_DETAIL)
    for t in sorted(trades, key=lambda x: x["pnl"])[:LOSS_DETAIL]:
        out.append(detail_line(t))
    out.append("")

    out.append("## 盈利最大的 %d 笔明细" % WIN_DETAIL)
    for t in sorted(trades, key=lambda x: -x["pnl"])[:WIN_DETAIL]:
        out.append(detail_line(t))
    out.append("")

    reflects = [t for t in trades if t["reflect"].strip()]
    out.append("## 反思原文（共 %d 条，列出前 15 条）" % len(reflects))
    for t in reflects[:15]:
        out.append("- %s：%s" % (t["name"], clip(t["reflect"], 150)))
    out.append("")
    return "\n".join(out)


def md_table(header, rows):
    """生成 Markdown 表格（给模型的材料用）"""
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for row in rows:
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    return lines


def build_compare_facts(all_trades, recent_trades, label):
    """构造对比材料"""
    a = basic_stats(all_trades)
    b = basic_stats(recent_trades)

    def line(name, key, fmt):
        return "- %s：全量 %s → %s %s" % (name, fmt % a[key], label, fmt % b[key])

    out = ["## 数据来源",
           "本材料由脚本在 %s 实时从飞书多维表格拉取。" % datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    out += ["## 对比数据（全量 vs %s）" % label, ""]
    out += [line("笔数", "count", "%d"), line("胜率", "win_rate", "%.1f%%"),
            line("总盈亏", "total_pnl", "%.0f"), line("平均每笔", "avg_pnl", "%.0f"),
            line("期望值/笔", "expect", "%.0f"), line("盈亏比", "pl_ratio", "%.2f"),
            line("盈利因子", "profit_factor", "%.2f"), line("平均止损率", "avg_loss_rate", "%.2f%%"),
            line("平均获利率", "avg_win_rate", "%.2f%%"), line("最大单笔亏损", "max_loss", "%.0f"),
            line("平均持股天数", "avg_days", "%.1f"), line("反思填写率", "reflex_rate", "%.0f%%")]
    out.append("")

    def discipline(trades):
        has = [t for t in trades if "止损" in t["plan"]]
        return (len(has) / len(trades) * 100 if trades else 0,
                sum_pnl([t for t in trades if "止损" not in t["plan"]]))

    pa, pna = discipline(all_trades)
    pb, pnb = discipline(recent_trades)
    out.append("## 纪律指标对比")
    out.append("- 写了止损位的比例：全量 %.0f%% → %s %.0f%%" % (pa, label, pb))
    out.append("- 无止损计划单的合计盈亏：全量 %.0f → %s %.0f" % (pna, label, pnb))
    out.append("")
    out.append("## %s 的交易明细（按卖出日期倒序）" % label)
    for t in sorted(recent_trades, key=lambda x: -x["sell_ts"])[:20]:
        out.append(detail_line(t))
    out.append("")
    return "\n".join(out)


def ai_analyze(scope, facts):
    """调用模型生成分析正文"""
    return ai_client.chat([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "以下是某个 A 股交易账户「%s」的实时统计数据与交易明细，"
                                    "请严格基于这些数据生成分析报告。\n\n%s" % (scope, facts)},
    ])


def panel(panel_id, active, ai_text, blocks):
    """组装一个 tab 面板"""
    out = ['<section id="%s" class="panel%s">' % (panel_id, " active" if active else "")]
    out.append('<div class="card ai"><p class="note">以下分析由 AI（<code>%s</code>）生成，'
               '数据来自本次运行实时拉取；图表与附录由脚本生成，数字以附录为准。</p>%s</div>'
               % (ai_client.model_name(), md_to_html(ai_text)))
    out += blocks
    out.append("</section>")
    return "".join(out)


def compare_blocks(all_trades, recent_trades, label):
    """对比 tab 的图表与数据对照"""
    a = basic_stats(all_trades)
    b = basic_stats(recent_trades)

    def discipline(trades):
        has = [t for t in trades if "止损" in t["plan"]]
        return (len(has) / len(trades) * 100 if trades else 0,
                sum_pnl([t for t in trades if "止损" not in t["plan"]]))

    pa, pna = discipline(all_trades)
    pb, pnb = discipline(recent_trades)

    rows = [("胜率%", a["win_rate"], b["win_rate"]),
            ("平均每笔", a["avg_pnl"], b["avg_pnl"]),
            ("期望值", a["expect"], b["expect"]),
            ("盈亏比×10", a["pl_ratio"] * 10, b["pl_ratio"] * 10),
            ("盈利因子×10", a["profit_factor"] * 10, b["profit_factor"] * 10),
            ("最大单笔亏损", a["max_loss"], b["max_loss"]),
            ("写止损位比例%", pa, pb),
            ("无计划单盈亏", pna, pnb)]

    out = ['<div class="card"><h2>可视化对比</h2>',
           '<p class="chart-sub">灰色为全量基准，蓝色为 %s；盈亏比与盈利因子乘以 10 以便同图显示。</p>'
           % label,
           svg_grouped_bars(rows)]

    out.append('<h3>数据对照</h3>')
    out.append(html_table(["指标", "全量", label], [
        ["交易笔数", "%d" % a["count"], "%d" % b["count"]],
        ["胜率", "%.1f%%" % a["win_rate"], "%.1f%%" % b["win_rate"]],
        ["总盈亏", "%.0f" % a["total_pnl"], "%.0f" % b["total_pnl"]],
        ["平均每笔", "%.0f" % a["avg_pnl"], "%.0f" % b["avg_pnl"]],
        ["期望值/笔", "%.0f" % a["expect"], "%.0f" % b["expect"]],
        ["盈亏比", "%.2f" % a["pl_ratio"], "%.2f" % b["pl_ratio"]],
        ["盈利因子", "%.2f" % a["profit_factor"], "%.2f" % b["profit_factor"]],
        ["平均止损率", "%.2f%%" % a["avg_loss_rate"], "%.2f%%" % b["avg_loss_rate"]],
        ["最大单笔亏损", "%.0f" % a["max_loss"], "%.0f" % b["max_loss"]],
        ["平均持股天数", "%.1f" % a["avg_days"], "%.1f" % b["avg_days"]],
        ["反思填写率", "%.0f%%" % a["reflex_rate"], "%.0f%%" % b["reflex_rate"]],
    ]))
    out.append(html_table(["纪律指标", "全量", label], [
        ["写了止损位的比例", "%.0f%%" % pa, "%.0f%%" % pb],
        ["无止损计划单的合计盈亏", "%.0f" % pna, "%.0f" % pnb],
    ]))
    out.append('</div>')
    return "".join(out)


def build_page(panels, title):
    """组装单文件 HTML"""
    tabs = []
    for idx, (panel_id, label, _) in enumerate(panels):
        tabs.append('<button class="tab%s" data-target="%s">%s</button>'
                    % (" active" if idx == 0 else "", panel_id, label))
    head = HTML_HEAD.replace("__TITLE__", title)
    head = head.replace("__META__", "生成时间 %s ｜ 数据源：飞书多维表格「已清仓」视图（实时拉取）"
                        % datetime.now().strftime("%Y-%m-%d %H:%M"))
    head = head.replace("__TABS__", "".join(tabs))
    head = head.replace("__PANELS__", "".join(body for _, _, body in panels))
    return head


def write_file(name, content, out_dir=None):
    """写文件（同名覆盖）"""
    out_dir = out_dir or OUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


INDEX_TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>交易复盘报告</title>
<style>
:root{--bg:#f6f8fb;--card:#fff;--line:#e5e7eb;--text:#111827;--muted:#6b7280;--brand:#2563eb;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;}
main{max-width:720px;margin:0 auto;padding:48px 20px}
h1{font-size:22px;margin:0 0 6px}
.meta{color:var(--muted);font-size:12px;margin:0 0 20px}
ul{list-style:none;margin:0;padding:0}
li{background:var(--card);border:1px solid var(--line);border-radius:12px;margin-bottom:10px;box-shadow:0 1px 2px rgba(16,24,40,.04)}
a{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 18px;color:inherit;text-decoration:none}
a:hover{background:#f9fafb}
.day{font-weight:600}
.go{color:var(--brand);font-size:13px}
.badge{background:#eff6ff;color:var(--brand);border:1px solid #bfdbfe;border-radius:999px;font-size:12px;padding:1px 8px;margin-left:8px;font-weight:400}
.empty{color:var(--muted);background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
</style>
</head>
<body>
<main>
<h1>交易复盘报告</h1>
<p class="meta">最近更新 __TIME__ ｜ 数据源：飞书多维表格「已清仓」视图（实时拉取）</p>
<ul>__ITEMS__</ul>
</main>
</body>
</html>
"""


def list_reports():
    """列出 reports 目录下已生成的报告，按日期倒序，返回 [(日期, 文件名)]"""
    if not os.path.isdir(OUT_DIR):
        return []
    names = [n for n in os.listdir(OUT_DIR)
             if n.startswith("report-") and n.endswith(".html")]
    out = []
    for n in sorted(names, reverse=True):
        day = n[len("report-"):-len(".html")]
        if len(day) == 8 and day.isdigit():
            day = "%s-%s-%s" % (day[:4], day[4:6], day[6:])
        out.append((day, n))
    return out


def build_index():
    """生成入口页 index.html：静态托管（如 GitHub Pages）访问目录时可从这里进报告"""
    items = []
    for idx, (day, name) in enumerate(list_reports()):
        badge = '<span class="badge">最新</span>' if idx == 0 else ""
        items.append('<li><a href="reports/%s"><span class="day">%s</span>%s'
                     '<span class="go">查看报告</span></a></li>' % (name, day, badge))
    if not items:
        items.append('<li class="empty">暂无报告，先运行 monkey-review.py 生成。</li>')
    return (INDEX_TPL.replace("__ITEMS__", "".join(items))
                     .replace("__TIME__", datetime.now().strftime("%Y-%m-%d %H:%M")))


def select_recent(trades):
    """取近期交易：优先最近 RECENT_DAYS 天的记录；
    若不足 RECENT_MIN_COUNT 笔，则改取最近 RECENT_MIN_COUNT 笔。
    返回 (交易列表, 区间名称)"""
    cutoff = (datetime.now() - timedelta(days=RECENT_DAYS)).timestamp() * 1000
    recent = [t for t in trades if t["sell_ts"] >= cutoff]
    if len(recent) >= RECENT_MIN_COUNT:
        return recent, "最近 %d 天" % RECENT_DAYS
    recent = sorted(trades, key=lambda x: -x["sell_ts"])[:RECENT_MIN_COUNT]
    return recent, "最近 %d 笔" % len(recent)


def main():
    try:
        ai_client.load_config()
    except RuntimeError as e:
        print(e)
        return

    trades = load_trades()
    if not trades:
        print("没有读取到已清仓记录")
        return

    recent, recent_label = select_recent(trades)
    suffix = datetime.now().strftime("%Y%m%d")

    # 先生成全部内容，任一环节失败则不落盘
    try:
        full_facts = build_facts(trades, "全量")
        recent_facts = build_facts(recent, recent_label) if recent else ""
        compare_facts = build_compare_facts(trades, recent, recent_label) if recent else ""

        panels = [
            ("panel-full", '全量 <span class="badge">%d 笔</span>' % len(trades),
             panel("panel-full", True, ai_analyze("全量", full_facts),
                   [chart_section(trades), appendix_section(trades)])),
            ("panel-recent", '%s <span class="badge">%d 笔</span>' % (recent_label, len(recent)),
             panel("panel-recent", False,
                   ai_analyze(recent_label, recent_facts) if recent else "该区间内没有已清仓记录。",
                   [chart_section(recent), appendix_section(recent)] if recent else [])),
            ("panel-compare", '对比 <span class="badge">全量 vs %s</span>' % recent_label,
             panel("panel-compare", False,
                   ai_analyze("%s vs 全量基准" % recent_label, compare_facts) if recent
                   else "%s 内没有已清仓记录，无法对比。" % recent_label,
                   [compare_blocks(trades, recent, recent_label)] if recent else [])),
        ]

        page = build_page(panels, suffix)
        outputs = [
            ("report-%s.html" % suffix, page),
            ("trade-facts-full-%s.md" % suffix, full_facts),
            ("trade-facts-recent-%s.md" % suffix, recent_facts),
            ("trade-facts-compare-%s.md" % suffix, compare_facts),
        ]
    except RuntimeError as e:
        print("分析失败，未生成报告：" + str(e))
        return

    a = basic_stats(trades)
    print("全量：%d 笔  胜率 %.1f%%  总盈亏 %.0f" % (a["count"], a["win_rate"], a["total_pnl"]))
    if recent:
        b = basic_stats(recent)
        print("%s：%d 笔  胜率 %.1f%%  总盈亏 %.0f" % (recent_label, b["count"], b["win_rate"], b["total_pnl"]))
    else:
        print("%s：没有已清仓记录" % recent_label)
    for name, content in outputs:
        print("已生成 " + write_file(name, content))
    # 入口页写在 trade-analysis/ 下，供静态托管访问目录时使用（报告已落盘后再生成）
    print("已生成 " + write_file("index.html", build_index(), BASE_DIR))


if __name__ == "__main__":
    main()
