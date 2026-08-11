# -*- coding: utf-8 -*-
"""
sync_dashboard.py — 北京看板首页(手机端概览)自动同步脚本

每天由自动化(10:10)运行：从三个子页抽取最新值，重写
beijing-2026-dashboard.html 中 <!-- MOBILE-VIEW-START/END --> 之间的
手机端概览表格，使首页永远与各子页(每日10:00自动刷新)一致。

设计要点：
- 只重写锚点之间的 mobile-view 内容；桌面端 iframe 本就自动更新，不动。
- 纯标准库( re / os / datetime )，无第三方依赖。
- 解析失败时打印告警并「不写文件」，避免覆盖出半截内容。
"""
import re
import os
import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.join(BASE, "beijing-2026-dashboard.html")
FLIGHTS = os.path.join(BASE, "beijing-2026-myflights.html")
WEATHER = os.path.join(BASE, "beijing-2026-7-8-weather.html")
BUDGET = os.path.join(BASE, "beijing-2026-budget.html")

START = "<!-- MOBILE-VIEW-START -->"
END = "<!-- MOBILE-VIEW-END -->"


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def arr(html, name):
    m = re.search(name + r"=\[([^\]]*)\]", html)
    if not m:
        return None
    return [float(x) for x in m.group(1).split(",") if x.strip() != ""]


# ---------------- 机票 ----------------
# 机票页已改为「已购记录」（携程实付 ¥6248），不再做每日价格追踪，
# 故不再解析航班价格；航班卡片由 build_mobile_view 直接生成固定内容。


# ---------------- 天气 ----------------
def rain_level(p):
    if p >= 80:
        return "暴雨"
    if p >= 50:
        return "大雨"
    if p >= 25:
        return "中雨"
    if p >= 10:
        return "小雨"
    if p > 0:
        return "阵雨"
    return "晴"


def parse_weather(html):
    hi = arr(html, "aHi")
    lo = arr(html, "aLo")
    prec = arr(html, "aPrec")
    if hi is None or lo is None or prec is None:
        return None
    fHi = arr(html, "fHi") or []
    fLo = arr(html, "fLo") or []
    fPrec = arr(html, "fPrec") or []
    f2Hi = arr(html, "f2Hi") or []
    f2Lo = arr(html, "f2Lo") or []
    f2Prec = arr(html, "f2Prec") or []
    pHi = arr(html, "pHi") or []
    pLo = arr(html, "pLo") or []
    pPrec = arr(html, "pPrec") or []
    hi = hi + fHi + f2Hi + pHi
    lo = lo + fLo + f2Lo + pLo
    prec = prec + fPrec + f2Prec + pPrec
    if not hi or not lo or not prec:
        return None

    today = datetime.date.today()
    if today.month == 7:
        idx = today.day - 1
    elif today.month == 8:
        idx = 31 + today.day - 1
    else:
        idx = len(hi) - 1
    idx = max(0, min(idx, len(hi) - 1))
    hi_t = int(round(hi[idx]))
    lo_t = int(round(lo[idx]))
    prec_t = int(round(prec[idx]))

    m = re.search(r"7.{0,3}8月 累计</div><div class=\"v\">~?(\d+)<small>mm</small>", html)
    total = m.group(1) if m else "?"
    return (hi_t, lo_t, prec_t, total)


# ---------------- 酒店 ---------------- （已移除：酒店模块不再展示，删除 hotels-spec.html）


# ---------------- 预算 ----------------
def parse_budget(html):
    """返回 (总额字符串, 人均字符串, [(项目,金额,购买途径), ...])，失败返回 None。"""
    m = re.search(r'<b id="budgetTotal">¥([\d,]+)</b>', html)
    if not m:
        return None
    total = m.group(1)
    m2 = re.search(r'<div class="t-per">([^<]*)</div>', html)
    per = m2.group(1).strip() if m2 else ""
    sec = re.search(r'📊 预算汇总.*?<tbody>(.*?)</tbody>', html, re.S)
    rows = []
    if sec:
        for rm in re.finditer(
            r'<tr><td>([^<]+)</td><td[^>]*>¥?([\d.]+)</td><td>([^<]*)</td>', sec.group(1)):
            rows.append((rm.group(1).strip(), rm.group(2).strip(), rm.group(3).strip()))
    if not rows:
        return None
    return (total, per, rows)


# ---------------- 组装 mobile-view ----------------
def build_mobile_view(wh, budget):
    budget_total, budget_per, budget_rows = budget
    today = datetime.date.today()
    today_label = f"今日{today.month}/{today.day}"
    hi_t, lo_t, prec_t, total = wh
    rlevel = rain_level(prec_t)
    if prec_t > 0:
        weather_pri = f"{hi_t}℃/{lo_t}℃"
        weather_mut = f"预报雨{prec_t}mm·{rlevel}"
    else:
        weather_pri = f"{hi_t}℃/{lo_t}℃"
        weather_mut = f"无雨·{rlevel}"

    # 机票卡片见下方「已购机票」区块（固定内容，不再解析价格）

    # 预算卡片行（解析自预算页汇总表，含金额与购买途径）
    budget_rows_html = ""
    for _lbl, _amt, _ch in budget_rows:
        budget_rows_html += f'        <tr><td>{_lbl}</td><td class="pri">¥{_amt}</td><td class="mut">{_ch}</td></tr>\n'

    return f'''    <a class="mcard" style="--mc:#2E86DE" href="beijing-2026-booking.html">

    <a class="mcard" style="--mc:#2E86DE" href="beijing-2026-booking.html">
      <div class="mhead"><span class="lt"><span class="dot" style="background:#2E86DE"></span>景点预约时间表</span><span class="go">完整详情 ↗</span></div>
      <table class="mtbl">
        <tr><td>故宫</td><td class="pri">20:00抢</td><td class="mut">提前7天·最难抢</td></tr>
        <tr><td>国博</td><td>17:00</td><td class="mut">提前7天·免费</td></tr>
        <tr><td>天安门升旗</td><td>12:00</td><td class="mut">提前9天·免费</td></tr>
        <tr><td>天坛</td><td>21:00</td><td class="mut">提前7天</td></tr>
        <tr><td>颐和园</td><td>21:00</td><td class="mut">提前7天</td></tr>
        <tr><td>恭王府</td><td>20:00</td><td class="mut">提前10天</td></tr>
        <tr><td>北大</td><td>08:00</td><td><span class="pill warn">截止8/16⚠️</span></td></tr>
        <tr><td>清华</td><td>08:00</td><td><span class="pill bad">已闭园✗</span></td></tr>
      </table>
    </a>

    <a class="mcard" style="--mc:#0EA5A4" href="beijing-2026-7-8-weather.html">
      <div class="mhead"><span class="lt"><span class="dot" style="background:#0EA5A4"></span>天气 / 降雨量</span><span class="go">完整详情 ↗</span></div>
      <table class="mtbl">
        <tr><td>{today_label}</td><td class="pri">{weather_pri}</td><td class="mut">{weather_mut}</td></tr>
        <tr><td>7–8月累计</td><td>~{total}mm</td><td class="mut">实况+预报</td></tr>
        <tr><td>8月展望</td><td>雨季</td><td class="mut">伞随身·防短时暴雨</td></tr>
      </table>
    </a>

    <a class="mcard" style="--mc:#2E8B57" href="beijing-2026-myflights.html">
      <div class="mhead"><span class="lt"><span class="dot" style="background:#2E8B57"></span>已购机票（往返）</span><span class="go">完整详情 ↗</span></div>
      <table class="mtbl">
        <tr><td>去程 8/15</td><td class="pri">CA1542</td><td class="mut">宁波→北京·首都</td></tr>
        <tr><td>回程 8/22</td><td class="pri">CA8387</td><td class="mut">北京→宁波·大兴</td></tr>
        <tr class="sec"><td colspan="3">已购 · 实付 ¥6248（携程·含税）</td></tr>
      </table>
    </a>

    <a class="mcard" style="--mc:#7c3aed" href="beijing-2026-budget.html">
      <div class="mhead"><span class="lt"><span class="dot" style="background:#7c3aed"></span>旅游预算总览</span><span class="go">完整明细 ↗</span></div>
      <table class="mtbl">
{budget_rows_html}        <tr class="sec"><td colspan="3">总预算（估）</td></tr>
        <tr><td><b>合计</b></td><td class="pri">¥{budget_total}</td><td class="mut">{budget_per}</td></tr>
      </table>
    </a>'''


def main():
    dash = read(DASH)
    if START not in dash or END not in dash:
        print("[ERROR] dashboard 未找到同步锚点，跳过。")
        return 1

    wh = parse_weather(read(WEATHER))
    budget = parse_budget(read(BUDGET))
    if wh is None:
        print("[ERROR] 天气页解析失败，跳过写入。")
        return 1
    if budget is None:
        print("[ERROR] 预算页解析失败，跳过写入。")
        return 1

    new_block = build_mobile_view(wh, budget)
    pre = dash.split(START, 1)[1]
    old_block = pre.split(END, 1)[0]
    if old_block.strip() == new_block.strip():
        print("[OK] 首页概览已是最新，无需改动。")
        return 0

    new_dash = dash.replace(START + old_block + END, START + "\n" + new_block + "\n  " + END, 1)
    with open(DASH, "w", encoding="utf-8") as f:
        f.write(new_dash)

    # 输出同步摘要
    print(f"[SYNC] 机票: 已购 ¥6248（携程·CA1542/CA8387）")
    print(f"[SYNC] 天气: 今日{wh[0]}℃/{wh[1]}℃ 雨{wh[2]}mm({rain_level(wh[2])}) 7月累计~{wh[3]}mm")
    print(f"[SYNC] 预算总额: ¥{budget[0]}")
    print("[DONE] 已重写首页 mobile-view 概览表格。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
