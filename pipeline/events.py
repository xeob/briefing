#!/usr/bin/env python3
"""미국 주요 일정·발표지표를 실제 캘린더에서 수집 → out/events.json  (모든 날짜·시각 = 한국시간 KST)
소스: Nasdaq 경제캘린더(날짜별) + Nasdaq IPO + events_manual.txt(수동, KST로 기입).
★ Nasdaq 날짜는 실측상 실제 ET 날짜보다 +1일 어긋남 → 매 실행 Forex Factory(공식 ET 날짜) 앵커와
  대조해 오프셋을 자동 캘리브레이션한 뒤 보정하고, ET→KST로 변환해 저장한다.
  (검증 앵커 5건: NFP·신규실업수당 실제7/2→Nasdaq7/3, ISM제조 7/1→7/2, ISM서비스 7/6→7/7, FOMC 7/8→7/9)

- must_include: 1순위(반드시 일정 표에 포함 — 누락 시 verify.py가 게시 차단)
- optional    : 2순위(자리 남으면)
- released    : 최근 발표 지표(date=미국 세션 ET 날짜, kst=한국시간) — 발표된 지표 표에 빠짐없이"""
import json, os, subprocess, datetime, collections

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
    ("CPI",     1, ["cpi", "consumer price index"], ["expectation", "cleveland", "nowcast"], "소비자물가지수(CPI)", ["CPI", "소비자물가"], "cpi m/m"),
    ("PCE",     1, ["pce"], ["nowcast"], "PCE 물가지수", ["PCE"], "core pce price index m/m"),
    ("PPI",     1, ["ppi", "producer price"], [], "생산자물가지수(PPI)", ["PPI", "생산자물가"], "ppi m/m"),
    ("NFP",     1, ["nonfarm", "non-farm", "employment change"], ["adp", "weekly", "trends"], "고용보고서(비농업)", ["고용", "NFP", "비농업"], "non-farm employment change"),
    ("UNRATE",  1, ["unemployment rate"], ["u6", "u-6", "underemployment"], "실업률", ["실업률"], "unemployment rate"),
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
    ("FEDSPK",  2, ["speaks"], ["chair", "powell", "chairman"], "연준 위원 발언", ["연준"], None),
]

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
       "must_include": [], "optional": [], "released": [], "errors": []}

# 1) Nasdaq 원시 수집 (query 날짜 그대로, 이후 보정) — 호출 간격으로 제한 회피
import time as _time
raw = {}
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
        cl = classify(str(r.get("eventName", "")))
        if not cl:
            continue
        cid, tier, ko, kws = cl
        key = (ds, cid)
        actual = clean(r.get("actual"))
        rec = {"nasdaq_date": ds, "time_et": clean(r.get("gmt")), "cid": cid, "tier": tier,
               "title": ko, "keywords": kws}
        if actual:
            rec.update(actual=actual, forecast=clean(r.get("consensus")), previous=clean(r.get("previous")))
        def score(x):  # 중복 시 우선순위: 발표값 있음 > 예상치 있음
            return (("actual" in x), bool(x.get("forecast")))
        if key not in raw or score(rec) > score(raw[key]):
            raw[key] = rec

# 2) 캘리브레이션: Forex Factory(공식 ET 날짜) 앵커와 대조 → Nasdaq 날짜 오프셋 산출
offset = None
try:
    ff = curl_json("https://nfs.faireconomy.media/ff_calendar_thisweek.json")
    ffmap = {}
    for e in ff:
        if e.get("country") == "USD":
            ffmap[e.get("title", "").strip().lower()] = e.get("date", "")[:10]
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
    base = {"date": kst_date, "time": kst_time, "date_et": et_day.isoformat(),
            "title": rec["title"], "impact": "High" if tier1 else "Medium",
            "cat": "지표", "src": "nasdaq", "keywords": rec["keywords"]}
    if "actual" in rec and today - datetime.timedelta(days=3) <= et_day <= today:
        out["released"].append({**base, "date": et_day.isoformat(), "kst": f"{kst_date} {kst_time}",
                                "actual": rec["actual"], "forecast": rec.get("forecast", ""),
                                "previous": rec.get("previous", "")})
    d0 = datetime.date.fromisoformat(kst_date)
    if today <= d0 <= today + datetime.timedelta(days=(12 if tier1 else 7)):
        (out["must_include"] if tier1 else out["optional"]).append(base)

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
        if (today - gen).days > 14:
            out["errors"].append(f"⚠ events_static.json 생성 {(today-gen).days}일 경과 — 로컬에서 재생성 필요")
    except Exception as ex:
        out["errors"].append(f"static merge: {str(ex)[:50]}")

for k in ("must_include", "optional", "released"):
    out[k].sort(key=lambda x: (x["date"], x.get("time", "")))

os.makedirs("out", exist_ok=True)
json.dump(out, open("out/events.json", "w"), ensure_ascii=False, indent=1)
print(f"must_include {len(out['must_include'])} / optional {len(out['optional'])} / released {len(out['released'])} (오류 {len(out['errors'])}) → out/events.json")
print(" ", out.get("calibration", ""))
print("  [반드시 포함 · 1순위 · 한국시간]")
for e in out["must_include"]:
    print(f"    {e['date']} {e.get('time','')} · {e['cat']} · {e['title']}")
print("  [발표된 지표 · date=미국 세션일]")
for e in out["released"]:
    print(f"    {e['date']} · {e['title']}: {e.get('actual','')} (예상 {e.get('forecast','')})")
for er in out["errors"]:
    print("  오류:", er)
