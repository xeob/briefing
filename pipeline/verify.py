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

# 시간외 특징주 섹션 분리(2026-10-19) — 이 섹션 수치는 '시간외' 기준이라 정규장 대조에서 떼어낸다.
#   · #2에 그대로 걸리면 정규장 등락률과 달라 오탐으로 게시가 막힌다(실적일엔 낮·밤 둘 다 움직인다).
#   · #11은 "(티커)가 페이지 어디든 있으면 통과"라서, 시간외 행이 실적 섹션 누락을 가려준다.
#   섹션이 없는 날엔 ah_sec="" → html_main은 html과 동일해 기존 동작이 그대로 유지된다.
L_UP, L_DN = 'class="lbl">특징주 · 급등', 'class="lbl">특징주 · 급락'
L_AH, L_REL = 'class="lbl">시간외 특징주', 'class="lbl">발표된 지표'
L_EARN, L_SCHED = 'class="lbl">실적 발표', 'class="lbl">미국장 주요 일정'
AH_LBL = L_AH

def seg(start, *ends):
    """start 다음부터 ends 중 '가장 먼저' 나오는 경계 앞까지. 경계가 하나도 없으면 끝까지."""
    if start not in html:
        return ""
    s = html.split(start, 1)[1]
    cuts = [s.index(e) for e in ends if e in s]
    return s[:min(cuts)] if cuts else s

# 개별 행 헤더: 종목명 (티커) [+ 업종 꼬리표 mv-t] + 등락률(mv-p) — 꼬리표는 2026-10-23 신설이라 '있어도/없어도' 통과
TAG = r'(?:<span class="mv-t">[^<]*</span>)?'
ah_sec = seg(L_AH, L_REL)
html_main = html.replace(ah_sec, "") if ah_sec else html

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
for m in re.finditer(r'mv-n">[^<(]*\(([A-Z]{1,6})\)</span>' + TAG + r'<span class="mv-p[^"]*">([-+−][\d.]+)%', html_main):
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
#     예외(2026-10-27): **섹터 집계 강세/약세 1~2위 업종**의 묶음은 `2종목 이상 + 최상위 |5%|+`면 통과.
#     그날 자금 흐름의 주역 업종인데 큰 폭 종목이 개별 행으로 올라가면 잔여 앵커가 1~2개로 줄어 묶음이 서지 않고,
#     그러면 나머지 자격 종목의 수치가 지면에서 사라진다(2026-10-26 실측: 광통신 강세 1위인데 루멘텀·노키아·시스코가
#     개별로 가고 코히런트 +5.83%·시에나 +4.89%가 어디에도 안 실렸다). 20세션 측정 추가 묶음 +0.65행/일.
_sec_top2 = []
if isinstance(mv.get("sectors"), dict):
    _sec_top2 = (mv["sectors"].get("strong") or [])[:2] + (mv["sectors"].get("weak") or [])[:2]
for m in re.finditer(r'mv-n">(그 외[^<]*동반[^<]*)</span></div><div class="mv-r">(.*?)</div>', html):
    label, body = m.group(1).strip(), m.group(2)
    pcts = [abs(num(x)) for x in re.findall(r'class="(?:up|down)">([+\-−][\d.]+)%', body)]
    if not pcts:
        continue
    big = sum(1 for p in pcts if p >= 5)
    lead = any(lb and lb in label for lb in _sec_top2)      # 섹터 1~2위 업종의 묶음인가
    if lead:
        if len(pcts) < 2 or max(pcts) < 5:
            issues.append(f"[특징주] 묶음 '{label}'(섹터 상위 업종)은 2종목 이상이고 최상위가 |5%|+여야 함 "
                          f"— 현재 {len(pcts)}종목·최상위 {max(pcts):.2f}%")
    elif big < 3:
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

# 11) 실적 발표 누락 차단: earnings.json must_cover(그 세션 발표 화이트리스트)가 본문에 있는지(티커 매칭)
#     수치 자체는 API가 T+1이라 대조 불가 — 여기서 막는 건 '누락'(리바이스 실적행 사고와 같은 계열).
try:
    ea = json.load(open("out/earnings.json"))
except Exception:
    ea = None
if ea:
    for e in ea.get("must_cover", []):
        sym = e.get("symbol", "")
        if sym and f"({sym})" not in html_main:
            issues.append(f"[실적] '{e.get('name_ko', sym)} ({sym})' 누락 — {ea.get('session_et')} 세션 발표 "
                          f"{e.get('tier')} 종목은 실적 발표 섹션에 반드시 포함(earnings.json must_cover)")

# 12) 실적 '예정' 누락 차단: earnings.json upcoming(향후 N일 $100B+) 종목이 미국장 주요 일정 표에 있는지
#     모델 리서치에 맡기면 반복 누락됐던 항목(리바이스 사고) — 스크립트 로스터로 강제한다.
if ea:
    sm3 = re.search(r'미국장 주요 일정.*?</table>', html, re.S)
    sched3 = sm3.group(0) if sm3 else html
    for e in ea.get("upcoming", []):
        sym = e.get("symbol", "")
        if sym and f"({sym})" not in sched3:
            issues.append(f"[실적예정] '{e.get('name_ko', sym)} ({sym})' 누락 — {e.get('date')} 발표 예정"
                          f"({e.get('tier')}·${e.get('cap_b')}B), 미국장 주요 일정에 실적 행으로 포함할 것")

# 13) SK하이닉스 ADR 상시 행: movers.json skhy가 있으면 매일 SKHY 행이 올바른 파트(상승=급등·하락=급락)에
#     있어야 하고, 헤더 등락률·20시·괴리 수치가 원본과 일치해야 한다(2026-09-18 결정 — 한국 하이닉스와 직결).
sk = mv.get("skhy")
if sk:
    up_sec = seg(L_UP, L_DN)
    dn_sec = seg(L_DN, L_AH, L_REL)
    want, other = (up_sec, dn_sec) if sk["side"] == "up" else (dn_sec, up_sec)
    side_ko = "급등" if sk["side"] == "up" else "급락"
    if "(SKHY)" not in want:
        other_ko = "급락" if sk["side"] == "up" else "급등"
        where = f"{side_ko} 파트가 아니라 {other_ko} 파트에 있음" if "(SKHY)" in other else f"{side_ko} 파트에 없음"
        issues.append(f"[하이닉스] SK하이닉스 ADR (SKHY) 행이 {where} — 특징주 자격과 무관하게 매일 표시"
                      f"(ADR {sk['pct_close']:+.2f}% → {side_ko} 파트: 자격 충족 시 본 순위, 아니면 맨 아래)")
    else:
        m = re.search(r'\(SKHY\)</span>' + TAG + r'<span class="mv-p[^"]*">([-+−]?[\d.]+)%</span></div><div class="mv-r">(.*?)</div>',
                      want, re.S)
        if not m:
            issues.append("[하이닉스] SKHY 행 형식을 인식할 수 없음 — 템플릿 형식(mv-n/mv-p/mv-r) 그대로 작성")
        else:
            if abs(num(m.group(1)) - sk["pct_close"]) > 0.15:
                issues.append(f"[하이닉스] SKHY 등락률 HTML {m.group(1)}% ≠ 원본 {sk['pct_close']:+.2f}%")
            body = re.sub(r'<[^>]+>', ' ', m.group(2))
            got = [num(x) for x in re.findall(r'[-+−]?\d+\.\d+(?=%)', body)]
            for label, val in (("20시", sk.get("pct_20")), ("한국장 마감 후", sk.get("gap"))):
                if val is not None and not any(abs(g - val) <= 0.1 for g in got):
                    issues.append(f"[하이닉스] SKHY {label} 수치({val:+.2f}%)가 본문에 없음 — movers.json skhy 값 그대로")

# 14) 시간외 특징주 섹션: movers.json afterhours 와 1:1 대조 (2026-10-19 신설)
#     rows가 있으면 전부 게재(누락 차단) / rows가 없으면 섹션 자체 금지(날조·재탕 차단).
#     표시 수치는 movers.json 값 그대로여야 하고, 기준시각(ET·KST)을 반드시 적는다.
ah = mv.get("afterhours") or {}
ah_rows = ah.get("rows") or []
if ah_rows and not ah_sec:
    lst = ", ".join("%s %+.2f%%" % (r["symbol"], r["pct"]) for r in ah_rows)
    issues.append(f"[시간외] 시간외 특징주 섹션 누락 — afterhours.rows {len(ah_rows)}건({lst})은 "
                  "특징주 급락 아래 섹션에 전부 게재")
if ah_sec and not ah_rows:
    issues.append(f"[시간외] 자격 통과 0건(status={ah.get('status')})인데 섹션이 있음 — "
                  "섹션(제목 포함) 통째로 삭제(어제 자료 재탕·임의 추가 금지)")
if ah_sec:
    if 'class="mv-p' in ah_sec:
        issues.append('[시간외] 섹션에 class="mv-p" 사용 — 시간외 등락률은 class="ah-p"로 표기'
                      "(mv-p는 정규장 대조 #2에 걸려 오탐을 만든다)")
    if "(SKHY)" in ah_sec:
        issues.append("[시간외] SKHY 행은 시간외 섹션에 넣지 않는다 — 하이닉스 ADR은 전용 상시 행(급등/급락 파트 맨 아래)")
    for lb, v in (("ET", ah.get("cut_et_hm")), ("KST", ah.get("cut_kst_hm"))):
        if v and v not in ah_sec:
            issues.append(f"[시간외] 기준시각 {lb} {v} 표기 없음 — 제목 줄에 "
                          f"'{ah.get('cut_et_hm')} ET · {ah.get('cut_kst_hm')} KST 기준' 병기(검증 가능성)")
    want = {r["symbol"]: r["pct"] for r in ah_rows}
    got = {m.group(1): num(m.group(2)) for m in
           re.finditer(r'mv-n">[^<(]*\(([A-Z]{1,6})\)</span><span class="ah-p[^"]*">[^<]*?([-+−][\d.]+)%', ah_sec)}
    n_mvn = ah_sec.count('class="mv-n"')
    if n_mvn != len(got):
        issues.append(f"[시간외] 행 형식 인식 실패(인식 {len(got)}건 / mv-n {n_mvn}건) — "
                      "템플릿 형식 그대로: mv-n에 '한글명 (TICKER)', 이어서 ah-p에 '시간외 +0.00%'")
    for sym, pct in want.items():
        if sym not in got:
            issues.append(f"[시간외] {sym} 행 누락 — afterhours.rows({pct:+.2f}%)는 전부 게재")
        elif abs(got[sym] - pct) > 0.15:
            issues.append(f"[시간외] {sym} 등락률 HTML {got[sym]:+.2f}% ≠ 원본 {pct:+.2f}% (movers.json 값 그대로)")
    for sym in got:
        if sym not in want:
            issues.append(f"[시간외] {sym} 행은 afterhours.rows에 없음 — 임의 추가 금지"
                          "(기준 미달·거래대금 미달·2소스 미확인 중 하나로 걸러진 종목)")

# 15) 실적 발표 종목이 자격까지 통과했으면 특징주 개별 행 필수 (2026-10-23 신설)
#     2026-10-22 세션 사고: 록히드마틴 +6.96%(시총 $136B → 일반 티어 기준 4% 통과, 실적 상회 = A급 재료)가
#     '실적 발표' 섹션에만 실리고 특징주에서 빠졌다. 급등 개별이 8행뿐이라 자리도 있었는데 누락됐고,
#     감사 기록 ⓐ가 |7%|+만 대상이라 보고서에도 남지 않았다.
#     기계로 판정 가능한 교집합(그 세션 실적 발표 ∩ 자격 통과)만 강제한다 — 재료 유무 판단이 필요 없다.
#     해당 파트가 이미 10행(상위 10 규칙 상한)이면 밀려난 것이 정당하므로 차단하지 않는다.
if ea:
    qual_pct = {r["symbol"]: r["pct"] for r in mv.get("all", []) if r.get("qualified") and r.get("symbol")}
    up_sec15 = seg(L_UP, L_DN)
    dn_sec15 = seg(L_DN, L_AH, L_REL)
    IND = r'mv-n">[^<(]*\(([A-Z][A-Z.\-]{0,5})\)</span>' + TAG + r'<span class="mv-p'
    rows15 = {"up": re.findall(IND, up_sec15), "down": re.findall(IND, dn_sec15)}
    for e in ea.get("must_cover", []):
        sym = e.get("symbol", "")
        if sym not in qual_pct:
            continue                        # 자격 미달이면 개별 의무 없음
        pct = qual_pct[sym]
        side = "up" if pct > 0 else "down"
        side_ko = "급등" if side == "up" else "급락"
        if sym in rows15[side] or len(rows15[side]) >= 10:
            continue
        issues.append(f"[특징주] '{e.get('name_ko', sym)} ({sym})' {pct:+.2f}% 누락 — 그 세션 실적 발표 종목이 "
                      f"자격을 통과했고 {side_ko} 파트가 {len(rows15[side])}행(10행 미만)이라 자리가 있다. "
                      "실적(확정 공시)은 A급 재료이므로 개별 행으로 게재할 것(묶음행·실적 발표 섹션만으로는 불충분)")

# 16) 섹터 파트 ↔ movers.json sectors (2026-10-23 신설)
#     섹터 선정이 모델의 서술 판단이던 탓에 2026-10-22 세션엔 데이터 상위(건설·주택 +7.1%p·소매·유통 +5.3%p)가
#     빠지고 '금융'(자산운용 +4.0%p와 은행 +1.2%p가 섞인 말)이 강세로 적혔다. 집계 결과에 묶어 기계 대조한다.
sc = mv.get("sectors") or {}
if sc.get("sectors") is not None:
    med = {x["label"]: x["median"] for x in sc["sectors"]}
    for tag, key, ko in (("t-strong", "strong", "강세"), ("t-weak", "weak", "약세")):
        m = re.search(tag + r'">[^<]*</span>\s*<div class="sector-names">(.*?)</div>', html, re.S)
        if not m:
            issues.append(f"[섹터] {ko} 줄을 찾을 수 없음 — 템플릿 형식(sector-names) 그대로 작성")
            continue
        field = m.group(1)
        want = sc.get(key) or []
        if not want:
            if re.search(r'[-+−][\d.]+%', field):
                issues.append(f"[섹터] {ko} 후보가 없는 날인데 업종이 적혀 있음 — '뚜렷한 업종 없음' 한 줄로 "
                              f"(기준: {sc.get('rule', '')[:40]}…)")
            continue
        got = []
        for chunk in re.split(r'\s+·\s+', field.strip()):
            mm = re.search(r'^(.*?)&nbsp;<span class="(?:up|down)">([-+−][\d.]+)%</span>', chunk.strip(), re.S)
            if mm:
                got.append((re.sub(r'<[^>]+>', '', mm.group(1)).strip(), mm.group(2)))
        got_lbl = [g[0] for g in got]
        if len(got_lbl) != len(want):
            issues.append(f"[섹터] {ko} 업종 수 {len(got_lbl)}개 ≠ 집계 {len(want)}개 "
                          f"({' · '.join(want)}) — sectors.{key} 그대로, 업종명&nbsp;수치 형식")
        for lb in want:
            if lb not in got_lbl:
                issues.append(f"[섹터] {ko}에 '{lb}'({med.get(lb, 0):+.2f}%) 누락 — sectors.{key} 전부 게재")
        for lb, pv in got:
            lb = lb.strip()
            if lb not in want:
                issues.append(f"[섹터] {ko}의 '{lb}'는 집계 선정 밖 — sectors.{key}({' · '.join(want)})만 쓸 것")
            elif abs(num(pv) - med[lb]) > 0.15:
                issues.append(f"[섹터] '{lb}' 중위 등락률 HTML {num(pv):+.2f}% ≠ 원본 {med[lb]:+.2f}%")

# 17) 실적 발표 섹션 수치 + 업종 꼬리표 (2026-10-23 신설)
#     ⓐ 실적 섹션 헤더 등락률 = 그 세션 정규장 등락률(movers.json all[].pct)
#     ⓑ 마감 후 발표 종목은 본문에 '시간외 ±%'(afterhours.reporters[].pct, confirmed만) 표기 — 장 전 발표분은 표기 안 함
#        (실측 2026-10-22: 장 전 발표 LMT의 시간외는 −0.20%로 무의미, 마감 후 발표 WDC는 −5.71%로 그게 본반응)
#     ⓒ 개별 행 업종 꼬리표(mv-t) = movers.json all[].sector_short 그대로, 맵에 없으면 꼬리표 금지
allpct = {r["symbol"]: r["pct"] for r in mv.get("all", []) if r.get("symbol")}
allsec = {r["symbol"]: r.get("sector_short") for r in mv.get("all", []) if r.get("symbol")}
reps = ((mv.get("afterhours") or {}).get("reporters")) or {}
earn_sec = seg(L_EARN, L_SCHED)
if ea and earn_sec:
    tim = {e.get("symbol"): (e.get("timing") or "") for e in ea.get("must_cover", [])}
    for m in re.finditer(r'mv-n">[^<(]*\(([A-Z][A-Z.\-]{0,5})\)</span>(.*?)<div class="mv-r">(.*?)</div>',
                         earn_sec, re.S):
        sym, head, body = m.group(1), m.group(2), m.group(3)
        hp = re.search(r'class="mv-p[^"]*">\s*([-+−][\d.]+)%', head)
        if sym in allpct:
            if not hp:
                issues.append(f"[실적] {sym} 헤더에 정규장 등락률 없음 — movers.json 값 {allpct[sym]:+.2f}% 병기"
                              "(헤더 mv-p, 서프라이즈 라벨은 본문으로)")
            elif abs(num(hp.group(1)) - allpct[sym]) > 0.15:
                issues.append(f"[실적] {sym} 헤더 등락률 HTML {num(hp.group(1)):+.2f}% ≠ 원본 {allpct[sym]:+.2f}%")
        r_ah = reps.get(sym) or {}
        shown = re.search(r'시간외\s*([-+−][\d.]+)%', re.sub(r'<[^>]+>', ' ', body))
        after_close = "after" in tim.get(sym, "")
        if shown and not (r_ah.get("confirmed") and r_ah.get("pct") is not None):
            issues.append(f"[실적] {sym} '시간외 {shown.group(1)}%'는 원본 없음/미확인 — "
                          f"afterhours.reporters 확인값만 표기({r_ah.get('reason', '데이터 없음')})")
        elif shown and abs(num(shown.group(1)) - r_ah["pct"]) > 0.15:
            issues.append(f"[실적] {sym} 시간외 HTML {num(shown.group(1)):+.2f}% ≠ 원본 {r_ah['pct']:+.2f}%")
        elif not shown and after_close and r_ah.get("confirmed") and abs(r_ah.get("pct") or 0) >= 1:
            issues.append(f"[실적] {sym}(마감 후 발표) 시간외 {r_ah['pct']:+.2f}% 누락 — 본문 첫 줄에 병기")
for part_name, part in (("급등", seg(L_UP, L_DN)),
                        ("급락", seg(L_DN, L_AH, L_REL))):
    for m in re.finditer(r'mv-n">[^<(]*\(([A-Z][A-Z.\-]{0,5})\)</span>(' + TAG + r')<span class="mv-p', part):
        sym, tag = m.group(1), m.group(2)
        got = re.sub(r'<[^>]+>', '', tag).strip()
        want = allsec.get(sym)
        if want and got != want:
            issues.append(f"[특징주] {part_name} {sym} 업종 꼬리표 '{got or '없음'}' ≠ 원본 '{want}' "
                          "— movers.json all[].sector_short 그대로")
        if got and not want:
            issues.append(f"[특징주] {part_name} {sym} 업종 꼬리표 '{got}'는 업종 맵에 없는 종목 — 꼬리표 생략"
                          "(임의 분류 금지, 맵 보강은 movers.py SECTOR_GROUPS)")

if issues:
    print(f"❌ 검증 실패 {len(issues)}건 — 수정 후 재검증:")
    for i in issues:
        print("  •", i)
    sys.exit(1)
print("✅ 검증 통과 — 지수·시장지표·특징주 수치가 원본과 일치, 날짜 정상")
