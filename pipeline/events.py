#!/usr/bin/env python3
"""미국 주요 일정·발표지표를 실제 캘린더에서 수집 → out/events.json
소스: Nasdaq 경제캘린더(날짜별) + Nasdaq IPO + events_manual.txt(수동).
모델의 '날짜 추측'을 막고, 중요 이벤트 누락을 verify.py가 차단하게 하는 근거 데이터.

- must_include: 반드시 미국장 주요 일정에 포함(1순위). 누락 시 verify.py가 게시 차단.
- optional    : 자리 남으면(중요도 2순위).
- released    : 직전 세션에 발표된 주요 지표(발표된 지표 표에 빠짐없이).
선별 = 중요도(등급) 기반. Nasdaq은 등급이 없어 '정규화 키워드'로 1/2순위를 결정한다."""
import json, os, subprocess, datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))
KST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(KST)
today = now.date()

# 정규화 규칙: (id, 순위(1/2), [매치 substring], [제외 substring], 한글제목, [verify 매칭 키워드])
CANON = [
    ("CPI",     1, ["cpi", "consumer price index"], ["expectation", "cleveland", "nowcast"], "소비자물가지수(CPI)", ["CPI", "소비자물가"]),
    ("PCE",     1, ["pce"], ["nowcast"], "PCE 물가지수", ["PCE"]),
    ("PPI",     1, ["ppi", "producer price"], [], "생산자물가지수(PPI)", ["PPI", "생산자물가"]),
    ("NFP",     1, ["nonfarm", "non-farm", "employment change"], ["adp", "weekly", "trends"], "고용보고서(비농업)", ["고용", "NFP", "비농업"]),
    ("UNRATE",  1, ["unemployment rate"], [], "실업률", ["실업률"]),
    ("FOMC",    1, ["fomc", "federal funds", "fed interest rate", "interest rate decision"], ["member"], "FOMC", ["FOMC", "의사록", "연준", "금리"]),
    ("FEDCHAIR",1, ["powell", "fed chair", "fed chairman"], [], "연준 의장 발언", ["연준", "의장", "파월"]),
    ("ISM_MFG", 1, ["ism manufacturing pmi"], [], "ISM 제조업 PMI", ["ISM", "제조업"]),
    ("ISM_SVC", 1, ["ism non-manufacturing pmi", "ism services pmi"], [], "ISM 서비스업 PMI", ["ISM", "서비스업"]),
    ("RETAIL",  1, ["retail sales"], [], "소매판매", ["소매판매"]),
    ("GDP",     1, ["gdp"], ["gdpnow", "now"], "GDP", ["GDP", "성장률"]),
    # 2순위
    ("JOBLESS", 2, ["initial jobless claims"], [], "신규 실업수당청구", ["실업수당", "신규 실업"]),
    ("ADP",     2, ["adp employment"], ["weekly"], "ADP 고용", ["ADP"]),
    ("CONF",    2, ["consumer confidence", "cb consumer"], [], "소비자신뢰지수", ["소비자신뢰"]),
    ("MICH",    2, ["michigan"], [], "미시간 소비심리", ["미시간", "소비심리"]),
    ("JOLTS",   2, ["jolts"], [], "JOLTS 구인", ["JOLTS", "구인"]),
    ("DURABLE", 2, ["durable goods"], [], "내구재 주문", ["내구재"]),
    ("FEDSPK",  2, ["speaks"], ["chair", "powell", "chairman"], "연준 위원 발언", ["연준"]),
]

def classify(name):
    t = name.lower()
    for cid, tier, inc, exc, ko, kws in CANON:
        if any(s in t for s in inc) and not any(s in t for s in exc):
            return cid, tier, ko, kws
    return None

def curl_json(url):
    r = subprocess.run(["curl", "-s", "-m", "12", "-H", "User-Agent: Mozilla/5.0",
                        "-H", "Accept: application/json", url], capture_output=True, text=True)
    return json.loads(r.stdout)

def clean(v):
    return str(v or "").replace("&nbsp;", "").strip()

out = {"generated_kst": now.strftime("%Y-%m-%d %H:%M"),
       "window": {"today": str(today)}, "must_include": [], "optional": [], "released": [], "errors": []}

# 1) Nasdaq 경제캘린더: 발표(직전 3일)~예고(향후 12일)를 날짜별로 수집, 정규화·중복제거
canon_seen = {}
for off in range(-3, 13):
    day = today + datetime.timedelta(days=off)
    ds = day.isoformat()
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
        rec = {"date": ds, "time": clean(r.get("gmt")), "title": ko, "impact": ("High" if tier == 1 else "Medium"),
               "cat": "지표", "src": "nasdaq", "keywords": kws}
        if actual:  # 발표됨
            rec = {**rec, "actual": actual, "forecast": clean(r.get("consensus")), "previous": clean(r.get("previous"))}
        # 중복: 발표값 있는 레코드를 우선 보존
        if key not in canon_seen or (actual and "actual" not in canon_seen[key]):
            canon_seen[key] = rec

for (ds, cid), rec in canon_seen.items():
    d0 = datetime.date.fromisoformat(ds)
    tier1 = rec["impact"] == "High"
    if "actual" in rec and today - datetime.timedelta(days=3) <= d0 <= today:
        out["released"].append(rec)
    if today <= d0 <= today + datetime.timedelta(days=(12 if tier1 else 7)):
        (out["must_include"] if tier1 else out["optional"]).append(rec)

# 2) Nasdaq 대형 IPO($500M+) → optional (best-effort)
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
                out["optional"].append({"date": clean(r.get("expectedPriceDate")), "time": "",
                                        "title": f"{nm} 상장", "impact": "IPO", "cat": "IPO", "src": "nasdaq", "keywords": [nm]})
except Exception as ex:
    out["errors"].append(f"nasdaq ipo: {str(ex)[:50]}")

# 3) 수동 목록: in-window(향후 12일)면 must_include
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

for k in ("must_include", "optional", "released"):
    out[k].sort(key=lambda x: (x["date"], x.get("time", "")))

os.makedirs("out", exist_ok=True)
json.dump(out, open("out/events.json", "w"), ensure_ascii=False, indent=1)
print(f"must_include {len(out['must_include'])} / optional {len(out['optional'])} / released {len(out['released'])} (오류 {len(out['errors'])}) → out/events.json")
print("  [반드시 포함 · 1순위]")
for e in out["must_include"]:
    print(f"    {e['date']} {e.get('time','')} · {e['cat']} · {e['title']}")
print("  [발표된 지표]")
for e in out["released"]:
    print(f"    {e['date']} · {e['title']}: {e.get('actual','')} (예상 {e.get('forecast','')})")
for er in out["errors"]:
    print("  오류:", er)
