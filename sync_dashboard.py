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
HOTELS = os.path.join(BASE, "beijing-2026-hotels-spec.html")

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
def parse_flights(html):
    """返回 {航班号: (优先日价格int, trend或None)}；trend = (箭头字符, 金额int)"""
    out = {}
    for code in ["KN5996", "NS8028", "MU5150", "CA8387", "CA1541", "CA1535"]:
        m = re.search(code + r"\s*<b>¥(\d+)</b>(?:（([↓↑])¥(\d+))?", html)
        if not m:
            return None  # 任一航班缺失 -> 视为解析失败
        price = int(m.group(1))
        trend = None
        if m.group(2):
            trend = (m.group(2), int(m.group(3)))
        out[code] = (price, trend)
    return out


def flight_mut(trend):
    if trend:
        arrow = "↓降" if trend[0] == "↓" else "↑涨"
        return f"{arrow}¥{trend[1]}·✓确认"
    return "✓确认"


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

    m = re.search(r"7月 实况\+预报</div><div class=\"v\">~?(\d+)<small>mm</small>", html)
    total = m.group(1) if m else "?"
    return (hi_t, lo_t, prec_t, total)


# ---------------- 酒店 ----------------
def clean_price(t):
    t2 = t.replace("双床房", "").replace("约", "").strip()
    m = re.search(r"¥(\d+)(?:[–-](\d+))?", t2)
    if not m:
        return t2
    lo = m.group(1)
    hi = m.group(2)
    ref = "参考" if "参考" in t2 else ""
    if hi:
        return f"¥{lo}–{hi}{'起' if '起' in t2 else ''}{ref}"
    if ref:
        return f"¥{lo}{ref}"
    return f"¥{lo}{'起' if '起' in t2 else ''}"


def parse_hotels(html):
    spec = re.findall(r'<span class="price">([^<]*)</span>', html)
    reco = re.findall(r'<div class="price">([^<]*)<span', html)
    if len(spec) < 4 or len(reco) < 3:
        return None
    spec_c = [clean_price(x) for x in spec[:4]]
    reco_c = [clean_price(x) for x in reco[:3]]
    return spec_c + reco_c  # [东方,京伦,国际艺苑,金龙, 康福瑞,如家neo,汉庭]


# ---------------- 组装 mobile-view ----------------
def build_mobile_view(flights, wh, hotels):
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

    # 机票行（顺序：去程3 + 回程3）
    fmap = {
        "KN5996": ("KN5996 中联航", flights["KN5996"]),
        "NS8028": ("NS8028 河北航", flights["NS8028"]),
        "MU5150": ("MU5150 东航", flights["MU5150"]),
        "CA8387": ("CA8387 国航(大兴)", flights["CA8387"]),
        "CA1541": ("CA1541 国航(首都)", flights["CA1541"]),
        "CA1535": ("CA1535 国航(首都)", flights["CA1535"]),
    }
    dep_codes = ["KN5996", "NS8028", "MU5150"]
    ret_codes = ["CA8387", "CA1541", "CA1535"]
    dep_rows = ""
    for c in dep_codes:
        label, (price, trend) = fmap[c]
        mut = flight_mut(trend)
        color = ' style="color:#2e7d54"' if (trend and trend[0] == "↓") else ""
        dep_rows += f'        <tr><td>{label}</td><td class="pri">¥{price}</td><td class="mut"{color}>{mut}</td></tr>\n'
    ret_rows = ""
    for c in ret_codes:
        label, (price, trend) = fmap[c]
        mut = flight_mut(trend)
        color = ' style="color:#c0392b"' if (trend and trend[0] == "↑") else ""
        ret_rows += f'        <tr><td>{label}</td><td class="pri">¥{price}</td><td class="mut"{color}>{mut}</td></tr>\n'

    # 酒店行
    spec = hotels[:4]
    reco = hotels[4:7]
    hotel_notes = {
        "东方饭店": "前门·虎坊桥530m·洗衣✓",
        "京伦饭店": "国贸",
        "国际艺苑": "王府井",
        "金龙温泉": "建国门·含私汤",
        "康福瑞": "牛街370m·洗衣✓·早餐优",
        "如家neo前门": "珠市口220m",
        "汉庭宣武门": "菜市口470m",
    }
    pri_set = {"东方饭店", "康福瑞"}
    hotel_rows = ""
    spec_labels = ["东方饭店", "京伦饭店", "国际艺苑", "金龙温泉"]
    for lbl, price in zip(spec_labels, spec):
        cls = ' class="pri"' if lbl in pri_set else ""
        hotel_rows += f'        <tr><td>{lbl}</td><td{cls}>{price}</td><td class="mut">{hotel_notes[lbl]}</td></tr>\n'
    hotel_rows += '        <tr class="sec"><td colspan="3">每日推荐（洗衣·床1.2m·近地铁·近前门牛街·400–600）</td></tr>\n'
    reco_labels = ["康福瑞", "如家neo前门", "汉庭宣武门"]
    for lbl, price in zip(reco_labels, reco):
        cls = ' class="pri"' if lbl in pri_set else ""
        hotel_rows += f'        <tr><td>{lbl}</td><td{cls}>{price}</td><td class="mut">{hotel_notes[lbl]}</td></tr>\n'

    return f'''    <a class="mcard" style="--mc:#FF5C1A" href="beijing-2026-hotels-spec.html">
      <div class="mhead"><span class="lt"><span class="dot" style="background:#FF5C1A"></span>指定酒店 + 每日推荐</span><span class="go">完整详情 ↗</span></div>
      <table class="mtbl">
{hotel_rows}      </table>
    </a>

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
        <tr><td>7月累计</td><td>~{total}mm</td><td class="mut">实况+预报</td></tr>
        <tr><td>8月展望</td><td>雨季</td><td class="mut">伞随身·防短时暴雨</td></tr>
      </table>
    </a>

    <a class="mcard" style="--mc:#2E8B57" href="beijing-2026-myflights.html">
      <div class="mhead"><span class="lt"><span class="dot" style="background:#2E8B57"></span>机票价格（指定6航班）</span><span class="go">完整详情 ↗</span></div>
      <table class="mtbl">
        <tr class="sec"><td colspan="3">去程 8/15 宁波→北京（大兴）</td></tr>
{dep_rows}        <tr class="sec"><td colspan="3">回程 8/21 北京→宁波 · ⚠️全线涨价</td></tr>
{ret_rows}      </table>
    </a>'''


def main():
    dash = read(DASH)
    if START not in dash or END not in dash:
        print("[ERROR] dashboard 未找到同步锚点，跳过。")
        return 1

    flights = parse_flights(read(FLIGHTS))
    wh = parse_weather(read(WEATHER))
    hotels = parse_hotels(read(HOTELS))
    if flights is None:
        print("[ERROR] 机票页解析失败，跳过写入。")
        return 1
    if wh is None:
        print("[ERROR] 天气页解析失败，跳过写入。")
        return 1
    if hotels is None:
        print("[ERROR] 酒店页解析失败，跳过写入。")
        return 1

    new_block = build_mobile_view(flights, wh, hotels)
    pre = dash.split(START, 1)[1]
    old_block = pre.split(END, 1)[0]
    if old_block.strip() == new_block.strip():
        print("[OK] 首页概览已是最新，无需改动。")
        return 0

    new_dash = dash.replace(START + old_block + END, START + "\n" + new_block + "\n  " + END, 1)
    with open(DASH, "w", encoding="utf-8") as f:
        f.write(new_dash)

    # 输出同步摘要
    fv = " | ".join(f"{c}¥{flights[c][0]}" for c in ["KN5996", "NS8028", "MU5150", "CA8387", "CA1541", "CA1535"])
    print(f"[SYNC] 机票: {fv}")
    print(f"[SYNC] 天气: 今日{wh[0]}℃/{wh[1]}℃ 雨{wh[2]}mm({rain_level(wh[2])}) 7月累计~{wh[3]}mm")
    print(f"[SYNC] 酒店: 东方{hotels[0]} 康福瑞{hotels[4]} 如家{hotels[5]} 汉庭{hotels[6]}")
    print("[DONE] 已重写首页 mobile-view 概览表格。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
