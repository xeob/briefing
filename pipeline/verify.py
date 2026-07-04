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

# 2b) 시장 지표 6종 칩: HTML 값 ↔ market.json 대조 (전사 오류 검출)
chips = re.findall(r'class="chip">([^<]+)</span>', html)
for name, val in mk.get("indicators", {}).items():
    hit = [c.strip() for c in chips if c.strip().startswith(name)]
    if not hit:
        issues.append(f"[지표] '{name}' 칩이 HTML에 없음")
        continue
    hv = hit[0][len(name):].strip()
    try:
        if abs(num(hv) - num(val)) > max(abs(num(val)) * 0.001, 0.005):
            issues.append(f"[지표] {name} HTML '{hv}' ≠ 원본 '{val}'")
    except Exception:
        if hv.replace(" ", "") != str(val).replace(" ", ""):
            issues.append(f"[지표] {name} HTML '{hv}' ≠ 원본 '{val}'")

# 3) 날짜: 헤더에 오늘 날짜(현지) 포함 여부
today = datetime.datetime.now()
ymd = f"{today.year}.{today.month:02d}.{today.day:02d}"
hm = re.search(r'head-date">(.*?)<', html)
if hm and ymd not in hm.group(1):
    issues.append(f"[날짜] 헤더 '{hm.group(1).strip()}' 에 오늘({ymd}) 없음")

# 4) market.py 자체 오류(교차검증 불일치·이상치) 전달
for e in mk.get("errors", []):
    issues.append(f"[market.py] {e}")

# 5) 주요 뉴스 날짜창: 링크 URL의 날짜 토큰이 창 밖(전일 이전)이면 구뉴스로 간주
#    창 = 전일 00:00 ~ 당일(관대). 전일보다 이전 날짜면 위반(예: 7/4 발행에 7/2·6/25 기사).
win_start = (today - datetime.timedelta(days=1)).date()
news_html = html.split("핫한 키워드")[0]  # 주요 뉴스 영역만
seen = set()
for m in re.finditer(r'href="([^"]+)"', news_html):
    url = m.group(1)
    dm = re.search(r'(?:^|[/A])(20\d{2})[/\-]?(\d{2})[/\-]?(\d{2})(?:\D|\d{2,}|$)', url)
    if not dm:
        continue
    try:
        d = datetime.date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
    except ValueError:
        continue
    if not (today.date() - datetime.timedelta(days=120) <= d <= today.date()):
        continue  # 날짜로 보기 어려운 토큰(먼 과거/미래)은 무시
    if d < win_start and url not in seen:
        seen.add(url)
        issues.append(f"[뉴스] 창 밖 구뉴스 의심({d}): {url[:70]} — 전일 15:20~발행 창 기사로 교체")

# 6) 특징주 묶음행: 종목명+% 결합(&nbsp;) 및 억지 <br> 검사
for m in re.finditer(r'그 외[^<]*동반[^<]*</span></div><div class="mv-r">(.*?)</div>', html):
    body = m.group(1)
    if re.search(r'[가-힣A-Za-z0-9] <span class="(?:up|down)">', body):
        issues.append("[특징주] 묶음행 종목명과 %가 &nbsp;로 결합되지 않음 — 줄바꿈이 종목명/%를 가름")
    if body.count("<br>") > 1:
        issues.append("[특징주] 묶음행에 <br> 과다 — 공통이유 앞 1개만 허용(종목 나열 중간 <br> 금지)")

# 7) 특징주: 개별 자리가 남는데(<10) |7%|+ 종목이 동반 묶음에 있으면 오류.
#    근거: 7%+는 촉매 못 찾아도 "이유 미확인"으로 개별 유지 자격 → 자리가 남으면 개별로 승격해야 함.
#    반대로 7% 미만(촉매 없으면 개별 기준 미달 가능)이거나 개별 10이 꽉 찼으면 편집 판단 존중 — 차단 안 함.
iu, idn = [], []
for m in re.finditer(r'mv-n">[^<]*\([A-Z]{1,6}\)</span><span class="mv-p (up|down)">([+\-−][\d.]+)%', html):
    (iu if m.group(1) == "up" else idn).append(abs(num(m.group(2))))
for m in re.finditer(r'그 외[^<]*동반[^<]*</span></div><div class="mv-r">(.*?)</div>', html):
    body = m.group(1)
    bu = [abs(num(x)) for x in re.findall(r'class="up">([+\-−][\d.]+)%', body)]
    bd = [abs(num(x)) for x in re.findall(r'class="down">([+\-−][\d.]+)%', body)]
    if bu and len(iu) < 10 and max(bu) >= 7:
        issues.append(f"[특징주] 개별 급등 {len(iu)}개로 자리가 남는데 동반강세 묶음에 +{max(bu):.1f}% 종목 — 7%+는 개별 자격(이유 미확인 가능), 개별로 승격할 것")
    if bd and len(idn) < 10 and max(bd) >= 7:
        issues.append(f"[특징주] 개별 급락 {len(idn)}개로 자리가 남는데 동반하락 묶음에 −{max(bd):.1f}% 종목 — 7%+는 개별 자격(이유 미확인 가능), 개별로 승격할 것")

# 8) 일정 1순위 누락 차단: events.json의 must_include가 미국장 주요 일정 표에 있는지(키워드 매칭)
try:
    ev = json.load(open("out/events.json"))
except Exception:
    ev = None
if ev:
    sm = re.search(r'미국장 주요 일정.*?</table>', html, re.S)
    sched = sm.group(0) if sm else html
    for e in ev.get("must_include", []):
        if not any(kw and kw in sched for kw in e.get("keywords", [])):
            issues.append(f"[일정] 1순위 '{e['title']}'({e['date']}) 누락 — 미국장 주요 일정에 반드시 포함(events.json)")

if issues:
    print(f"❌ 검증 실패 {len(issues)}건 — 수정 후 재검증:")
    for i in issues:
        print("  •", i)
    sys.exit(1)
print("✅ 검증 통과 — 지수·시장지표·특징주 수치가 원본과 일치, 날짜 정상")
