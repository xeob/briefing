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

# 7) 특징주 묶음 라벨 금지어: 묶음은 실제 업종명만 — 시장 현상·테마 라벨 차단.
#    (구 검사 "개별<10 & 묶음 7%+ 차단"은 2026-07-04 규칙 개편으로 폐기: 재료 없는 종목은
#     등락률이 높아도 개별 제외 → 묶음 잔류가 정당하므로. 재료 유무는 사람 QA 영역.)
BAN_LABELS = ["순환매", "낙폭과대", "테마", "수혜", "관련주", "동반 반등", "저가 매수"]
for m in re.finditer(r'mv-n">(그 외[^<]*동반[^<]*)</span>', html):
    label = m.group(1)
    hits = [b for b in BAN_LABELS if b in label]
    if hits:
        issues.append(f"[특징주] 묶음 라벨 '{label.strip()}'에 금지어({','.join(hits)}) — 실제 업종명(반도체·은행·방산 등)으로만 묶을 것")

# 7b) 묶음행 실속(앵커) 검사: 각 묶음행에는 |5%| 이상 종목이 3개 이상 있어야 함(성립 조건 ⓑ)
for m in re.finditer(r'mv-n">(그 외[^<]*동반[^<]*)</span></div><div class="mv-r">(.*?)</div>', html):
    label, body = m.group(1).strip(), m.group(2)
    pcts = [abs(num(x)) for x in re.findall(r'class="(?:up|down)">([+\-−][\d.]+)%', body)]
    big = sum(1 for p in pcts if p >= 5)
    if pcts and big < 3:
        issues.append(f"[특징주] 묶음 '{label}'의 |5%|+ 종목이 {big}개(<3) — 성립 조건 미달, 묶음 해체(멤버는 섹터 파트·감사기록으로) 또는 재구성")

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

# 9) 일정 표에 '이미 지난 시각' 일정이 있으면 차단 (생성 시각 기준)
#    예: 7/9 03:00 FOMC 의사록은 06:30 생성 시점엔 지난 일정 → 표에서 빼고 '미국 시장' 섹션/회색 설명글로.
#    events.py가 passed로 분리하지만, 모델이 표에 되살리는 것도 기계 차단. (표 아래 .sched 설명글은 검사 범위 밖)
now2 = datetime.datetime.now()
sm2 = re.search(r'미국장 주요 일정.*?</table>', html, re.S)
if sm2:
    for row in re.finditer(r'<tr>.*?</tr>', sm2.group(0), re.S):
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row.group(0), re.S)
        if not cells:
            continue  # 헤더행(th)·빈행
        when = re.sub(r'<[^>]+>', '', cells[-1]).strip()  # 일시 셀
        dm2 = re.search(r'(\d{1,2})/(\d{1,2})', when)
        tm2 = re.search(r'(\d{1,2}):(\d{2})', when)
        if not (dm2 and tm2):
            continue  # 시각 없는(날짜만) 일정은 지난 것으로 보지 않음
        try:
            ev_dt = datetime.datetime(now2.year, int(dm2.group(1)), int(dm2.group(2)),
                                      int(tm2.group(1)), int(tm2.group(2)))
        except ValueError:
            continue
        if ev_dt - now2 < datetime.timedelta(days=-30):
            continue  # 연말→연초 경계: 30일+ 과거면 내년 일정으로 간주(오탐 방지)
        if ev_dt < now2:
            issues.append(f"[일정] 이미 지난 일정이 표에 있음: '{when}' — 생성 시각({now2:%m/%d %H:%M}) 이전. "
                          "표에서 빼고 필요 시 '미국 시장' 섹션/회색 설명글로 다룰 것")

if issues:
    print(f"❌ 검증 실패 {len(issues)}건 — 수정 후 재검증:")
    for i in issues:
        print("  •", i)
    sys.exit(1)
print("✅ 검증 통과 — 지수·시장지표·특징주 수치가 원본과 일치, 날짜 정상")
