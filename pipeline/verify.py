#!/usr/bin/env python3
"""최종 검증기 — 생성된 out/index.html의 숫자가 원본 데이터와 일치하는지 기계적으로 대조.
모델의 전사 오류(숫자 잘못 옮김)·산술 오류·날짜 오류를 잡는다.
불일치가 있으면 목록 출력 + exit 1. 통과면 exit 0. 게시 전에 반드시 실행."""
import json, os, re, sys, datetime, html as _html

os.chdir(os.path.dirname(os.path.abspath(__file__)))
html = open("out/index.html", encoding="utf-8").read()
mk = json.load(open("out/market.json"))
mv = json.load(open("out/movers.json"))
issues = []

def num(s):
    return float(str(s).replace(",", "").replace("−", "-").replace("+", "").replace("%", "").strip())

# 1) 지수 카드: 이름/종가/등락률 대조
for m in re.finditer(r'idx-name">(.*?)</div>\s*<div class="idx-val">(.*?)</div>\s*<div class="idx-chg[^"]*">(.*?)</div>', html):
    name, val, chg = _html.unescape(m.group(1).strip()), m.group(2), m.group(3)
    ref = mk["indices"].get(name)
    if not ref:
        issues.append(f"[지수] '{name}' market.json에 없음 (이름 확인)")
        continue
    if abs(num(val) - ref["close"]) > max(1, ref["close"] * 0.0005):
        issues.append(f"[지수] {name} 종가 HTML {val} ≠ 원본 {ref['close']:,}")
    pm = re.search(r'\(([-+−][\d.]+)%\)', chg)
    if pm and abs(num(pm.group(1)) - ref["pct"]) > 0.06:
        issues.append(f"[지수] {name} 등락률 HTML {pm.group(1)}% ≠ 원본 {ref['pct']:+.2f}%")
    cm = re.search(r'([-+−][\d,]+\.?\d*)\s*\(', chg)
    if cm and pm:  # 내부 정합성: 등락폭/종가 ↔ 등락률
        close, ch = num(val), num(cm.group(1))
        if close - ch != 0:
            calc = ch / (close - ch) * 100
            if abs(calc - num(pm.group(1))) > 0.1:
                issues.append(f"[지수] {name} 내부 불일치: 등락폭 {cm.group(1)}·종가 {val} → {calc:+.2f}% 인데 표기 {pm.group(1)}%")

# 2) 특징주: (티커) + 등락률 → movers.json 대조
allmv = {r["symbol"]: r["pct"] for r in mv.get("all", [])}
for m in re.finditer(r'mv-n">[^<(]*\(([A-Z]{1,6})\)</span><span class="mv-p[^"]*">([-+−][\d.]+)%', html):
    tk, pct = m.group(1), num(m.group(2))
    if tk in allmv and abs(pct - allmv[tk]) > 0.15:
        issues.append(f"[특징주] {tk} 등락률 HTML {pct:+.2f}% ≠ 원본 {allmv[tk]:+.2f}%")

# 3) 날짜: 헤더에 오늘 날짜(현지) 포함 여부
today = datetime.datetime.now()
ymd = f"{today.year}.{today.month:02d}.{today.day:02d}"
hm = re.search(r'head-date">(.*?)<', html)
if hm and ymd not in hm.group(1):
    issues.append(f"[날짜] 헤더 '{hm.group(1).strip()}' 에 오늘({ymd}) 없음")

# 4) market.py 자체 오류(교차검증 불일치·이상치) 전달
for e in mk.get("errors", []):
    issues.append(f"[market.py] {e}")

if issues:
    print(f"❌ 검증 실패 {len(issues)}건 — 수정 후 재검증:")
    for i in issues:
        print("  •", i)
    sys.exit(1)
print("✅ 검증 통과 — 지수·특징주 수치가 원본과 일치, 날짜 정상")
