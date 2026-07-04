#!/usr/bin/env python3
"""향후 45일 미국 1순위(tier-1) 경제 일정을 Nasdaq에서 수집해 events_static.json 생성 (KST 보정 포함).
클라우드에서 Nasdaq이 막혔을 때 events.py가 쓰는 폴백. 로컬(Mac)에서 주기적으로 재생성."""
import json, subprocess, datetime, time, sys

OFFSET = 1  # Nasdaq 날짜 = 실제 ET +1 (2026-07-04 FF 앵커 6건 실측)
try:
    from zoneinfo import ZoneInfo
    ET, KSTZ = ZoneInfo("America/New_York"), ZoneInfo("Asia/Seoul")
except Exception:
    ET = KSTZ = None

CANON = [
    ("CPI", ["cpi", "consumer price index"], ["expectation", "cleveland", "nowcast"], "소비자물가지수(CPI)", ["CPI", "소비자물가"]),
    ("PCE", ["pce"], ["nowcast"], "PCE 물가지수", ["PCE"]),
    ("PPI", ["ppi", "producer price"], [], "생산자물가지수(PPI)", ["PPI", "생산자물가"]),
    ("NFP", ["nonfarm", "non-farm", "employment change"], ["adp", "weekly", "trends"], "고용보고서(비농업)", ["고용", "NFP", "비농업"]),
    ("UNRATE", ["unemployment rate"], ["u6", "u-6", "underemployment"], "실업률", ["실업률"]),
    ("FOMC", ["fomc", "federal funds", "fed interest rate", "interest rate decision"], ["member"], "FOMC", ["FOMC", "의사록", "연준", "금리"]),
    ("ISM_MFG", ["ism manufacturing pmi"], [], "ISM 제조업 PMI", ["ISM", "제조업"]),
    ("ISM_SVC", ["ism non-manufacturing pmi", "ism services pmi"], [], "ISM 서비스업 PMI", ["ISM", "서비스업"]),
    ("RETAIL", ["retail sales"], [], "소매판매", ["소매판매"]),
    ("GDP", ["gdp"], ["gdpnow", "now"], "GDP", ["GDP", "성장률"]),
]

def classify(name):
    t = name.lower()
    for cid, inc, exc, ko, kws in CANON:
        if any(s in t for s in inc) and not any(s in t for s in exc):
            return cid, ko, kws
    return None

def to_kst(et_day, hhmm):
    if not hhmm or ":" not in hhmm:
        return et_day.isoformat(), ""
    try:
        h, m = (int(x) for x in hhmm.split(":")[:2])
    except ValueError:
        return et_day.isoformat(), ""
    if ET:
        dt = datetime.datetime(et_day.year, et_day.month, et_day.day, h, m, tzinfo=ET).astimezone(KSTZ)
    else:
        dt = datetime.datetime(et_day.year, et_day.month, et_day.day, h, m) + datetime.timedelta(hours=13)
    return dt.date().isoformat(), dt.strftime("%H:%M")

today = datetime.date.today()
seen, events, fails = {}, [], 0
for off in range(0, 46):
    ds = (today + datetime.timedelta(days=off)).isoformat()
    ok = False
    for attempt in range(3):
        try:
            r = subprocess.run(["curl", "-s", "-m", "12", "-H", "User-Agent: Mozilla/5.0",
                                "-H", "Accept: application/json",
                                f"https://api.nasdaq.com/api/calendar/economicevents?date={ds}"],
                               capture_output=True, text=True)
            d = json.loads(r.stdout)
            ok = True
            break
        except Exception:
            time.sleep(1 + attempt)
    if not ok:
        fails += 1
        continue
    for row in (d.get("data") or {}).get("rows") or []:
        if "United States" not in str(row.get("country", "")):
            continue
        cl = classify(str(row.get("eventName", "")))
        if not cl:
            continue
        cid, ko, kws = cl
        et_day = datetime.date.fromisoformat(ds) - datetime.timedelta(days=OFFSET)
        kd, kt = to_kst(et_day, str(row.get("gmt", "")).replace("&nbsp;", "").strip())
        key = (kd, cid)
        if key in seen:
            continue
        seen[key] = True
        events.append({"date": kd, "time": kt, "title": ko, "impact": "High", "cat": "지표",
                       "src": "static", "keywords": kws})
    time.sleep(0.35)

events.sort(key=lambda x: (x["date"], x["time"]))
out = {"generated": today.isoformat(), "offset_used": OFFSET, "coverage_days": 45, "events": events}
json.dump(out, open("/Users/xeob/Downloads/claude/briefing/events_static.json", "w"), ensure_ascii=False, indent=1)
print(f"1순위 {len(events)}건 (조회실패 {fails}일) → events_static.json")
for e in events:
    print(f"  {e['date']} {e['time']} {e['title']}")
