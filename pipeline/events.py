#!/usr/bin/env python3
"""미국 주요 일정·발표지표를 실제 캘린더에서 수집 → out/events.json  (모든 날짜·시각 = 한국시간 KST)
소스: Nasdaq 경제캘린더(날짜별) + Nasdaq IPO + events_manual.txt(수동, KST로 기입).
★ Nasdaq 날짜는 실측상 실제 ET 날짜보다 +1일 어긋남 → 매 실행 Forex Factory(공식 ET 날짜) 앵커와
  대조해 오프셋을 자동 캘리브레이션한 뒤 보정하고, ET→KST로 변환해 저장한다.
  (검증 앵커 5건: NFP·신규실업수당 실제7/2→Nasdaq7/3, ISM제조 7/1→7/2, ISM서비스 7/6→7/7, FOMC 7/8→7/9)

- must_include: 1순위(반드시 일정 표에 포함 — 누락 시 verify.py가 게시 차단)
- optional    : 2순위(자리 남으면)
- released    : 최근 발표 지표(date=미국 세션 ET 날짜, kst=한국시간) — 전년비·전월비·근원을 각각 별도 항목으로
                (basis="전년비"/"전월비"/"" ). 변형은 FF 라벨↔Nasdaq 예상치 대조로 확정. 발표된 지표 표에 빠짐없이
- passed      : 생성 시각 기준 이미 지난 일정(밤사이 이미 끝난 FOMC 의사록 등) — 일정 표에서 제외, '미국 시장' 서술용"""
import json, os, re, subprocess, datetime, collections

os.chdir(os.path.dirname(os.path.abspath(__file__)))
try:
    from zoneinfo import ZoneInfo
    ET, KSTZ = ZoneInfo("America/New_York"), ZoneInfo("Asia/Seoul")
except Exception:
    ET = KSTZ = None
KST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(KST)
today = now.date()

# 정규화: (id, 순위, [매치], [제외], 한글제목, [verify 키워드], FF제목(캘리브레이션용))
CANON = [
    ("CPI",     1, ["cpi", "consumer price index"], ["expectation", "cleveland", "nowcast", "cpi index", "n.s.a"], "소비자물가지수(CPI)", ["CPI", "소비자물가"], "cpi m/m"),
    ("PCE",     1, ["pce"], ["nowcast"], "PCE 물가지수", ["PCE"], "core pce price index m/m"),
    ("PPI",     1, ["ppi", "producer price"], [], "생산자물가지수(PPI)", ["PPI", "생산자물가"], "ppi m/m"),
    ("NFP",     1, ["nonfarm", "non-farm", "employment change"], ["adp", "weekly", "trends"], "고용보고서(비농업)", ["고용", "NFP", "비농업"], "non-farm employment change"),
    ("UNRATE",  1, ["unemployment rate"], ["u6", "u-6", "underemployment"], "실업률", ["실업률"], "unemployment rate"),
    ("AHE",     1, ["average hourly earnings"], [], "시간당 평균임금", ["시간당", "임금"], "average hourly earnings m/m"),
    ("FOMC",    1, ["fomc", "federal funds", "fed interest rate", "interest rate decision"], ["member"], "FOMC", ["FOMC", "의사록", "연준", "금리"], "fomc meeting minutes"),
    ("FEDCHAIR",1, ["powell", "fed chair", "fed chairman"], [], "연준 의장 발언", ["연준", "의장"], "fed chairman warsh speaks"),
    ("ISM_MFG", 1, ["ism manufacturing pmi"], [], "ISM 제조업 PMI", ["ISM", "제조업"], "ism manufacturing pmi"),
    ("ISM_SVC", 1, ["ism non-manufacturing pmi", "ism services pmi"], [], "ISM 서비스업 PMI", ["ISM", "서비스업"], "ism services pmi"),
    ("RETAIL",  1, ["retail sales"], [], "소매판매", ["소매판매"], "core retail sales m/m"),
    ("GDP",     1, ["gdp"], ["gdpnow", "now"], "GDP", ["GDP", "성장률"], "advance gdp q/q"),
    ("JOBLESS", 2, ["initial jobless claims"], [], "신규 실업수당청구", ["실업수당", "신규 실업"], "unemployment claims"),
    ("ADP",     2, ["adp employment"], ["weekly"], "ADP 고용", ["ADP"], "adp non-farm employment change"),
    ("CONF",    2, ["consumer confidence", "cb consumer"], [], "소비자신뢰지수", ["소비자신뢰"], "cb consumer confidence"),
    ("MICH",    2, ["michigan"], [], "미시간 소비심리", ["미시간", "소비심리"], "prelim uom consumer sentiment"),
    ("JOLTS",   2, ["jolts"], [], "JOLTS 구인", ["JOLTS", "구인"], "jolts job openings"),
    ("DURABLE", 2, ["durable goods"], [], "내구재 주문", ["내구재"], "core durable goods orders m/m"),
    ("HOUSING", 2, ["housing starts", "building permits"], [], "주택착공·건축허가", ["주택착공", "건축허가"], "housing starts"),
    ("EXHOME",  2, ["existing home sales"], [], "기존주택판매", ["기존주택"], "existing home sales"),
    ("NEWHOME", 2, ["new home sales"], [], "신규주택판매", ["신규주택"], "new home sales"),
    ("INDPROD", 2, ["industrial production"], [], "산업생산", ["산업생산"], "industrial production m/m"),
    ("FEDSPK",  2, ["speaks"], ["chair", "powell", "chairman"], "연준 위원 발언", ["연준"], None),
]

# 연준 인사 영→한 (발언자 이름 표기용; 미등록은 영문 성 그대로)
FED_KO = {"powell": "파월", "warsh": "워시", "williams": "윌리엄스", "waller": "월러",
          "jefferson": "제퍼슨", "barr": "바", "bowman": "보먼", "cook": "쿡", "kugler": "쿠글러",
          "goolsbee": "굴스비", "musalem": "무살렘", "schmid": "슈미드", "logan": "로건",
          "kashkari": "카슈카리", "daly": "데일리", "bostic": "보스틱", "collins": "콜린스",
          "harker": "하커", "hammack": "해맥"}

def fed_name(event_name):
    """'Fed Waller Speaks' / 'FOMC Member Williams Speaks' → 한글 이름"""
    words = [w.strip(".,") for w in event_name.split()]
    for i, w in enumerate(words):
        if w.lower().startswith("speak") and i > 0:
            nm = words[i - 1]
            return FED_KO.get(nm.lower(), nm)
    return ""

# 발표지표 변형 표기 — Nasdaq은 전월비·전년비 행 이름이 똑같아(둘 다 "CPI") 자체 구분이 불가능하다.
# → Forex Factory의 라벨된 제목("CPI m/m"/"CPI y/y")의 예상치와 Nasdaq consensus를 대조해 변형을 확정한다.
#   (실측 확인: FF 'CPI m/m' 예상 -0.1% ↔ Nasdaq CPI(-0.4%) consensus -0.1% / FF 'CPI y/y' 3.8% ↔ Nasdaq CPI(3.5%) 3.8%)
VAR_KO = {"m/m": "전월비", "y/y": "전년비", "q/q": "전분기비"}
CORE_KO = {"CPI": "근원 CPI", "PPI": "근원 PPI", "PCE": "근원 PCE",
           "RETAIL": "근원 소매판매", "DURABLE": "근원 내구재"}

def nnum(s):
    """예상치 대조용 정규화: '3.8%' → '3.8'"""
    return str(s or "").replace("%", "").replace(",", "").strip()

def classify(name):
    t = name.lower()
    for cid, tier, inc, exc, ko, kws, ff in CANON:
        if any(s in t for s in inc) and not any(s in t for s in exc):
            return cid, tier, ko, kws
    return None

def curl_json(url, retries=3):
    """재시도 포함(클라우드에서 Nasdaq이 연속 호출 제한으로 간헐 실패한 사례 — 2026-07-04 CPI 누락 사고)"""
    import time as _t
    last = None
    for i in range(retries):
        try:
            r = subprocess.run(["curl", "-s", "-m", "12", "-H", "User-Agent: Mozilla/5.0",
                                "-H", "Accept: application/json", url], capture_output=True, text=True)
            return json.loads(r.stdout)
        except Exception as ex:
            last = ex
            _t.sleep(1 + i)
    raise last

def clean(v):
    return str(v or "").replace("&nbsp;", "").strip()

def to_kst(et_day, hhmm):
    """ET 날짜+시각 → (KST 'YYYY-MM-DD', 'HH:MM'). 시각 없으면 ET 날짜 그대로(주간 이벤트는 날짜 동일)."""
    if not hhmm or ":" not in hhmm:
        return et_day.isoformat(), ""
    try:
        h, m = (int(x) for x in hhmm.split(":")[:2])
    except ValueError:
        return et_day.isoformat(), ""
    if ET:
        dt = datetime.datetime(et_day.year, et_day.month, et_day.day, h, m, tzinfo=ET).astimezone(KSTZ)
    else:  # zoneinfo 없을 때 EDT 고정 +13h
        dt = datetime.datetime(et_day.year, et_day.month, et_day.day, h, m) + datetime.timedelta(hours=13)
    return dt.date().isoformat(), dt.strftime("%H:%M")

out = {"generated_kst": now.strftime("%Y-%m-%d %H:%M"), "timezone": "KST(한국시간) — released.date만 미국 세션(ET) 날짜",
       "must_include": [], "optional": [], "released": [], "passed": [], "errors": []}

# 1) Nasdaq 원시 수집 (query 날짜 그대로, 이후 보정) — 호출 간격으로 제한 회피
import time as _time
raw = {}
released_raw = []  # 발표값 행 '전부' 보존 — raw는 일정용이라 지표당 1건으로 축약되어 전월비/전년비/근원이 사라진다
for off in range(-3, 14):
    ds = (today + datetime.timedelta(days=off)).isoformat()
    _time.sleep(0.3)
    try:
        d = curl_json(f"https://api.nasdaq.com/api/calendar/economicevents?date={ds}")
    except Exception as ex:
        out["errors"].append(f"nasdaq econ {ds}: {str(ex)[:50]}")
        continue
    for r in (d.get("data") or {}).get("rows") or []:
        if "United States" not in str(r.get("country", "")):
            continue
        ename = str(r.get("eventName", ""))
        cl = classify(ename)
        if not cl:
            continue
        cid, tier, ko, kws = cl
        if cid in ("FEDSPK", "FEDCHAIR"):  # 발언자 이름 표기 + 발언자별 구분
            nm = fed_name(ename)
            if nm:
                ko = f"연준 의장 {nm} 발언" if cid == "FEDCHAIR" else f"연준 {nm} 발언"
                kws = [nm]  # 발언자 이름으로 verify가 개별 강제(연준 발언 항상 표 게재)
                cid = f"{cid}:{nm}"
        key = (ds, cid)
        actual = clean(r.get("actual"))
        rec = {"nasdaq_date": ds, "time_et": clean(r.get("gmt")), "cid": cid, "tier": tier,
               "title": ko, "keywords": kws}
        if actual:
            rec.update(actual=actual, forecast=clean(r.get("consensus")), previous=clean(r.get("previous")))
            released_raw.append({"ds": ds, "cid": cid, "ko": ko, "ename": ename, "time_et": clean(r.get("gmt")),
                                 "actual": actual, "forecast": clean(r.get("consensus")),
                                 "previous": clean(r.get("previous"))})
        def score(x):  # 중복 시 우선순위: 발표값 있음 > 예상치 있음
            return (("actual" in x), bool(x.get("forecast")))
        if key not in raw or score(rec) > score(raw[key]):
            raw[key] = rec

# 2) Forex Factory 수집 — ⓐ날짜 캘리브레이션 앵커 ⓑ전월비/전년비 변형 라벨(Nasdaq은 두 행 이름이 같아 구분 불가)
#    주 경계(월요일 브리핑이 금요일 발표를 다룸) 대비로 이번 주 + 지난 주 모두 조회한다.
offset = None
ff_this = []
try:
    ff_this = [e for e in curl_json("https://nfs.faireconomy.media/ff_calendar_thisweek.json")
               if e.get("country") == "USD"]
except Exception as ex:
    out["errors"].append(f"ff thisweek: {str(ex)[:40]}")
# 변형 라벨 맵: "ET날짜|기저명" → {정규화예상치: 변형}   예: "2026-07-14|cpi" → {"-0.1": "m/m", "3.8": "y/y"}
# FF는 '이번 주' 파일만 제공한다(lastweek/nextweek는 404). 그래서 월요일 브리핑이 금요일 발표(예: PCE)를 다룰 때
# 라벨이 비지 않도록 events_static.json에 누적 캐시해 재사용한다(매일 실행이라 각 날짜를 그 주에 한 번은 수집).
ffvar = {}
if os.path.exists("events_static.json"):
    try:
        ffvar.update(json.load(open("events_static.json")).get("ff_variants", {}) or {})
    except Exception:
        pass
for e in ff_this:  # 라이브 값이 캐시를 덮어씀
    mv = re.match(r"^(.*?)\s+(m/m|y/y|q/q)$", (e.get("title") or "").strip().lower())
    fc = nnum(e.get("forecast"))
    if mv and fc:
        ffvar.setdefault(f"{e.get('date', '')[:10]}|{mv.group(1).strip()}", {})[fc] = mv.group(2)
try:
    ffmap = {}
    for e in ff_this:  # 캘리브레이션 앵커는 이번 주만 — 지난 주 날짜가 섞이면 오프셋이 틀어진다
        ffmap[(e.get("title") or "").strip().lower()] = e.get("date", "")[:10]
    fftitle = {cid: t for cid, _, _, _, _, _, t in CANON if t}
    diffs = []
    for (ds, cid), rec in raw.items():
        t = fftitle.get(cid)
        if t and t in ffmap:
            d1 = datetime.date.fromisoformat(ds)
            d2 = datetime.date.fromisoformat(ffmap[t])
            if abs((d1 - d2).days) <= 2:  # 같은 이벤트로 볼 수 있는 범위만
                diffs.append((d1 - d2).days)
    if diffs:
        offset = collections.Counter(diffs).most_common(1)[0][0]
        out["calibration"] = f"FF 앵커 {len(diffs)}건 → Nasdaq 오프셋 {offset:+d}일 보정"
except Exception as ex:
    out["errors"].append(f"calibration: {str(ex)[:50]}")
if offset is None:
    offset = 1  # 실측 기본값: Nasdaq = 실제 ET + 1일 (2026-07-04 앵커 5건 검증)
    out["calibration"] = "FF 앵커 없음 → 실측 기본 오프셋 +1일 적용"

# 3) 보정·KST 변환·분류
for (ds, cid), rec in raw.items():
    et_day = datetime.date.fromisoformat(ds) - datetime.timedelta(days=offset)
    kst_date, kst_time = to_kst(et_day, rec["time_et"])
    tier1 = rec["tier"] == 1
    # 연준 발언(의장·위원 모두)은 항상 일정 표에 개별 게재 → must_include(verify가 강제).
    # 이미 지난 발언은 뒤의 is_past 필터가 passed로 분리하므로 must_include엔 미래분만 남는다.
    always = tier1 or str(cid).startswith(("FEDCHAIR", "FEDSPK"))
    base = {"date": kst_date, "time": kst_time, "date_et": et_day.isoformat(),
            "title": rec["title"], "impact": "High" if tier1 else "Medium",
            "cat": "지표", "src": "nasdaq", "keywords": rec["keywords"]}
    d0 = datetime.date.fromisoformat(kst_date)
    if today <= d0 <= today + datetime.timedelta(days=(12 if always else 7)):
        (out["must_include"] if always else out["optional"]).append(base)

# 3.5) 발표된 지표(released): 전년비·전월비·근원을 '각각 별도 항목'으로.
#      Nasdaq은 전월비·전년비 행 이름이 똑같아(둘 다 "CPI") 그대로 쓰면 어느 쪽인지 알 수 없고,
#      raw는 지표당 1건으로 축약돼 임의의 변형만 살아남았다(과거: 근원 전월비가 헤드라인 CPI로 오라벨).
#      → FF의 라벨된 예상치와 Nasdaq consensus를 대조해 변형을 확정. 확정 못 하면 추측하지 말고 생략.
#      변형이 없는 지표(실업률·ISM·수당 등)는 기준 라벨 없이 고유 형태 그대로.
#      ★ 모호성은 '데이터 자체'로 판정한다(FF 장애에 안전): 같은 (날짜·지표·근원여부)에 행이 2개 이상이면
#        변형이 존재하므로 라벨 필수 — 라벨을 못 얻으면 생략. 행이 1개면 단일 형태이므로 FF 없이도 그대로 게재.
seen_rel, groups = set(), {}
for r in released_raw:
    et_day = datetime.date.fromisoformat(r["ds"]) - datetime.timedelta(days=offset)
    if not (today - datetime.timedelta(days=3) <= et_day <= today):
        continue
    base_name = r["ename"].strip().lower()
    groups.setdefault((et_day, r["cid"], base_name.startswith("core")), []).append((r, base_name))
for (et_day, cid, is_core), rows in groups.items():
    for r, base_name in rows:
        basis = ""
        if len(rows) > 1:  # 변형(전월비·전년비 등) 존재 → 라벨 확정 필수
            var = (ffvar.get(f"{et_day.isoformat()}|{base_name}") or {}).get(nnum(r["forecast"]))
            if not var:  # 어느 변형인지 확정 불가 → 추측·날조 금지, 생략하고 사람이 확인
                out["errors"].append(f"⚠ {r['ename']} {r['actual']}(예상 {r['forecast']}) 변형 식별 실패 "
                                     "— 발표지표에서 생략, 웹 확인 필요")
                continue
            basis = VAR_KO.get(var, "")
        title = (CORE_KO.get(cid, "근원 " + r["ko"])) if is_core else r["ko"]
        key = (et_day.isoformat(), title, basis)
        if key in seen_rel:
            continue
        seen_rel.add(key)
        kst_date, kst_time = to_kst(et_day, r["time_et"])
        out["released"].append({"date": et_day.isoformat(), "time": kst_time, "kst": f"{kst_date} {kst_time}",
                                "title": title, "basis": basis, "cat": "지표", "src": "nasdaq",
                                "actual": r["actual"], "forecast": r.get("forecast", ""),
                                "previous": r.get("previous", "")})

# 4) Nasdaq 대형 IPO($500M+) → optional
try:
    for mon in {today.strftime("%Y-%m"), (today + datetime.timedelta(days=12)).strftime("%Y-%m")}:
        d = curl_json(f"https://api.nasdaq.com/api/ipo/calendar?date={mon}")
        for r in ((d.get("data") or {}).get("upcoming") or {}).get("upcomingTable", {}).get("rows") or []:
            val = clean(r.get("dollarValueOfSharesOffered")).replace("$", "").replace(",", "")
            try:
                big = float(val) >= 500_000_000
            except ValueError:
                big = False
            if big and r.get("companyName"):
                nm = r["companyName"].strip()
                pd = clean(r.get("expectedPriceDate"))
                try:  # m/d/Y → ISO
                    mth, dy, yr = pd.split("/")
                    pd = f"{yr}-{int(mth):02d}-{int(dy):02d}"
                except (ValueError, AttributeError):
                    pass
                out["optional"].append({"date": pd, "time": "", "title": f"{nm} 상장",
                                        "impact": "IPO", "cat": "IPO", "src": "nasdaq", "keywords": [nm]})
except Exception as ex:
    out["errors"].append(f"nasdaq ipo: {str(ex)[:50]}")

# 5) 수동 목록(KST 기입): in-window(향후 12일)면 must_include
if os.path.exists("events_manual.txt"):
    for line in open("events_manual.txt", encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "|" not in line:
            continue
        p = [x.strip() for x in line.split("|")]
        try:
            d0 = datetime.date.fromisoformat(p[0])
        except (ValueError, IndexError):
            continue
        if len(p) < 3:
            continue
        kws = [k.strip() for k in p[3].split(",")] if len(p) > 3 and p[3] else [p[2]]
        if today <= d0 <= today + datetime.timedelta(days=12):
            out["must_include"].append({"date": p[0], "time": "", "title": p[2], "impact": "수동",
                                        "cat": p[1], "src": "manual", "keywords": kws,
                                        "note": p[4] if len(p) > 4 else ""})

# 6) 정적 폴백 병합 (events_static.json — 로컬에서 미리 생성한 1순위 일정, KST 보정 완료본):
#    클라우드에서 Nasdaq 일부 날짜 조회가 실패해도 CPI·FOMC 같은 핵심 일정이 비지 않게 보장.
if os.path.exists("events_static.json"):
    try:
        st = json.load(open("events_static.json"))
        have = {(e["date"], e["title"]) for e in out["must_include"]}
        filled = []
        for e in st.get("events", []):
            try:
                d0 = datetime.date.fromisoformat(e["date"])
            except (ValueError, KeyError):
                continue
            if today <= d0 <= today + datetime.timedelta(days=12) and (e["date"], e["title"]) not in have:
                out["must_include"].append(e)
                filled.append(f"{e['date']} {e['title']}")
        if filled:
            out["errors"].append(f"⚠ Nasdaq 실시간 조회에 빠진 1순위를 static으로 보충: {', '.join(filled)} — 시각은 static 기준, 웹으로 재확인 권장")
        gen = datetime.date.fromisoformat(st.get("generated", "2000-01-01"))
        static_fresh = (today - gen).days <= 14
        if not static_fresh:
            out["errors"].append(f"⚠ events_static.json 생성 {(today-gen).days}일 경과 — 로컬에서 재생성 필요")
        # 소스 노이즈 중재: Nasdaq이 같은 지표를 인접 날짜에 중복 게재하는 사례(실측: CPI가 7/14·7/15 양쪽) —
        # static(검증 스냅샷)이 신선하면 static 날짜와 어긋난 live 지표 항목(±4일 내)을 제거
        if static_fresh:
            st_dates = {}
            for e in st.get("events", []):
                st_dates.setdefault(e["title"], set()).add(e["date"])
            cleaned, dropped = [], []
            for e in out["must_include"]:
                t, d = e.get("title"), e.get("date")
                if e.get("cat") == "지표" and e.get("src") == "nasdaq" and t in st_dates and d not in st_dates[t]:
                    near = any(abs((datetime.date.fromisoformat(d) - datetime.date.fromisoformat(sd)).days) <= 4
                               for sd in st_dates[t])
                    if near:
                        dropped.append(f"{t} {d}")
                        continue
                cleaned.append(e)
            if dropped:
                out["must_include"] = cleaned
                out["errors"].append(f"⚠ 소스 중복날짜 정리(static 기준 채택): {', '.join(dropped)} 제거")
        # 완전 중복(같은 날짜·제목) 제거
        uniq, seen2 = [], set()
        for e in out["must_include"]:
            k = (e.get("date"), e.get("title"))
            if k not in seen2:
                seen2.add(k)
                uniq.append(e)
        out["must_include"] = uniq
    except Exception as ex:
        out["errors"].append(f"static merge: {str(ex)[:50]}")

# 6.5) 생성 시각 기준 이미 지난 일정은 일정 표에서 제외 → passed 로 이동.
#      밤사이 이미 끝난 FOMC 의사록 등: 표엔 넣지 않고, 시장에 영향 준 것은 모델이 '미국 시장' 서술에 활용.
#      (시각이 명시된 일정만 판정 — 시각 미상 주간·종일 이벤트는 지난 것으로 보지 않고 그대로 둔다.)
def is_past(e):
    t = e.get("time", "")
    if not t or ":" not in t:
        return False
    try:
        d0 = datetime.date.fromisoformat(e["date"])
        h, m = (int(x) for x in t.split(":")[:2])
    except (ValueError, KeyError):
        return False
    return datetime.datetime(d0.year, d0.month, d0.day, h, m, tzinfo=KST) < now
for bucket in ("must_include", "optional"):
    keep = []
    for e in out[bucket]:
        (out["passed"] if is_past(e) else keep).append(e)
    out[bucket] = keep

# 7) 정적 캘린더 자동 재갱신: 라이브 조회가 전부 성공한 날은 static을 오늘 데이터로 재생성
#    (수동 2주 재생성 불필요 — publish.sh가 갱신본을 저장소에 함께 push해 다음 날 클론에 반영)
query_errs = [e for e in out["errors"] if e.startswith("nasdaq econ")]
if not query_errs:
    try:
        old = json.load(open("events_static.json")) if os.path.exists("events_static.json") else {"events": []}
        horizon = (today + datetime.timedelta(days=13)).isoformat()
        keep_far = [e for e in old.get("events", []) if e.get("date", "") > horizon]  # 창 밖(예: 3주 뒤 FOMC) 보존
        near = [{"date": e["date"], "time": e.get("time", ""), "title": e["title"], "impact": "High",
                 "cat": "지표", "src": "static", "keywords": e.get("keywords", [])}
                for e in out["must_include"] if e.get("src") in ("nasdaq", "static") and e.get("cat") == "지표"]
        seen3, evs = set(), []
        for e in near + keep_far:
            k = (e["date"], e["title"])
            if k not in seen3:
                seen3.add(k)
                evs.append(e)
        evs.sort(key=lambda x: (x["date"], x.get("time", "")))
        # FF 변형(전월비/전년비) 라벨 캐시도 함께 보존 — FF는 이번 주 파일만 주므로 주 경계 대비. 21일 지난 건 정리.
        _cut = (today - datetime.timedelta(days=21)).isoformat()
        ffv_keep = {k: v for k, v in ffvar.items() if k.split("|")[0] >= _cut}
        json.dump({"generated": str(today), "offset_used": offset, "coverage_days": 13,
                   "auto_refreshed": True, "ff_variants": ffv_keep, "events": evs},
                  open("events_static.json", "w"), ensure_ascii=False, indent=1)
        out["static_refresh"] = f"자동 갱신 완료 ({len(evs)}건)"
    except Exception as ex:
        out["errors"].append(f"static refresh: {str(ex)[:50]}")

for k in ("must_include", "optional", "released", "passed"):
    out[k].sort(key=lambda x: (x["date"], x.get("time", "")))
# 발표지표는 표 게재 순서대로: 헤드라인 → 근원, 각각 전년비 → 전월비 (RUN.md 표기 규칙과 일치)
_BORD = {"전년비": 0, "전월비": 1, "전분기비": 1}
out["released"].sort(key=lambda x: (x["date"], x.get("time", ""),
                                    x["title"].startswith("근원"), _BORD.get(x.get("basis", ""), 2)))

os.makedirs("out", exist_ok=True)
json.dump(out, open("out/events.json", "w"), ensure_ascii=False, indent=1)
print(f"must_include {len(out['must_include'])} / optional {len(out['optional'])} / released {len(out['released'])} (오류 {len(out['errors'])}) → out/events.json")
print(" ", out.get("calibration", ""))
print("  [반드시 포함 · 1순위 · 한국시간]")
for e in out["must_include"]:
    print(f"    {e['date']} {e.get('time','')} · {e['cat']} · {e['title']}")
print("  [발표된 지표 · date=미국 세션일]")
for e in out["released"]:
    _b = f" ({e['basis']})" if e.get("basis") else ""
    print(f"    {e['date']} · {e['title']}{_b}: {e.get('actual','')} (예상 {e.get('forecast','')})")
if out["passed"]:
    print("  [지난 일정(표 제외) · 시장 서술용]")
    for e in out["passed"]:
        print(f"    {e['date']} {e.get('time','')} · {e['title']}")
for er in out["errors"]:
    print("  오류:", er)
