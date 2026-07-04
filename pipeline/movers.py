#!/usr/bin/env python3
"""특징주 후보 수집 + 자격(티어별 황금 등락률) 판정 → out/movers.json

깔때기:
  수집  = Yahoo 스크리너 day_gainers/losers (시총 $10B+) ∪ watchlist.txt 전수
  자격  = M7 ±2% / 메가캡($200B+) ±3% / 그 외 ±4%
  출력  = qualified_up / qualified_down (우선순위: 티어 → |등락률|), 각 최대 25
  시총  = 스크리너 값 우선, 없으면 CNBC 조회(mktcapView), 그것도 실패하면 MEGA_HINT
이후(생성 단계, RUN.md 4단계): 2차 재료 게이트(A/B급 통과·C급 제외·$50B 이하 A급만·
재료 없으면 7%+라도 제외, M7·메가캡 면제) → 3차 등락률순 top10+M7·메가캡 예외 →
4차 동반 묶음(같은 실제 업종 |5%|+ 5개 이상). 화면 표시는 |등락률| 큰 순."""
import json, time, os, subprocess

os.chdir(os.path.dirname(os.path.abspath(__file__)))

M7 = {"AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA"}
# 시총 데이터가 없는(워치리스트 단독 조회) 종목의 메가캡 판정 힌트 — 스크리너에 잡히면 실시총이 우선
MEGA_HINT = {"AVGO", "TSM", "ASML", "LLY", "JPM", "V", "UNH", "XOM", "WMT", "MA", "ORCL",
             "NFLX", "COST", "PG", "JNJ", "HD", "BAC", "MU", "PLTR", "AMD", "KLAC", "SNDK",
             "AMAT", "LRCX", "QCOM", "TXN", "INTC", "CRM", "KO", "CVX", "MRK", "GS", "CAT"}

def get(url):
    r = subprocess.run(["curl", "-s", "-m", "15", "-H", "User-Agent: Mozilla/5.0", url],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)

def cnbc_cap_b(sym):
    """CNBC에서 시총($B) 조회 — 워치리스트 단독 종목의 시총 공백 보완. 실패 시 None."""
    try:
        d = get(f"https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols={sym}&requestMethod=itv&noform=1&partnerId=2&fund=1&output=json")
        v = str(d["FormattedQuoteResult"]["FormattedQuote"][0].get("mktcapView", "")).strip()
        if not v:
            return None
        unit = v[-1].upper()
        num = float(v[:-1].replace(",", ""))
        return round({"T": num * 1000, "B": num, "M": num / 1000}.get(unit, 0), 1) or None
    except Exception:
        return None

# 워치리스트: [그룹] 헤더 파싱 (그룹은 커버리지 용도)
groups, cur = {}, None
for line in open("watchlist.txt"):
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    if line.startswith("[") and line.endswith("]"):
        cur = line[1:-1]
        continue
    for s in line.split():
        groups[s] = cur

out, errors = {}, []

for scr in ("day_gainers", "day_losers"):
    try:
        d = get(f"https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?scrIds={scr}&count=100")
        for q in d["finance"]["result"][0]["quotes"]:
            cap = q.get("marketCap") or 0
            pct = q.get("regularMarketChangePercent")
            if pct is None or cap < 10e9:
                continue
            vol, avg = q.get("regularMarketVolume"), q.get("averageDailyVolume3Month")
            vr = round(vol / avg, 2) if vol and avg else None
            out[q["symbol"]] = {"symbol": q["symbol"], "name": q.get("shortName"),
                                "pct": round(pct, 2), "mktcap_b": round(cap / 1e9, 1),
                                "vol_ratio": vr, "group": groups.get(q["symbol"]), "src": scr}
    except Exception as e:
        errors.append(f"screener {scr}: {e}")

for s in groups:
    if s in out:
        continue
    try:
        d = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{s}?range=2d&interval=1d")
        r = d["chart"]["result"][0]
        closes = [c for c in r["indicators"]["quote"][0]["close"] if c]
        if len(closes) >= 2:
            pct = (closes[-1] / closes[-2] - 1) * 100
        else:
            m = r["meta"]
            prev, last = m.get("chartPreviousClose"), m.get("regularMarketPrice")
            if not (prev and last):
                continue
            pct = (last / prev - 1) * 100
        if abs(pct) < 2.0:
            continue
        out[s] = {"symbol": s, "name": r["meta"].get("shortName") or s,
                  "pct": round(pct, 2), "mktcap_b": cnbc_cap_b(s), "vol_ratio": None,
                  "group": groups.get(s), "src": "watchlist"}
        time.sleep(0.15)
    except Exception as e:
        errors.append(f"chart {s}: {e}")

def tier(r):
    """0=M7, 1=메가캡($200B+), 2=그 외 — 자격 기준·우선순위 겸용"""
    if r["symbol"] in M7:
        return 0
    cap = r.get("mktcap_b")
    if (cap and cap >= 200) or (cap is None and r["symbol"] in MEGA_HINT):
        return 1
    return 2

THRESH = {0: 2.0, 1: 3.0, 2: 4.0}

rows = list(out.values())
for r in rows:
    r["tier"] = tier(r)
    r["qualified"] = abs(r["pct"]) >= THRESH[r["tier"]]

qual = sorted([r for r in rows if r["qualified"]], key=lambda x: (x["tier"], -abs(x["pct"])))

def candidates(side):
    """후보 목록: M7·메가캡 전원 + 일반 티어 |7%|+ 전원 강제 포함, 이후 등락률순 채움 (최대 25)"""
    m7mega = [r for r in side if r["tier"] <= 1]
    gen_big = [r for r in side if r["tier"] == 2 and abs(r["pct"]) >= 7]
    gen_rest = [r for r in side if r["tier"] == 2 and abs(r["pct"]) < 7]
    return (m7mega + gen_big + gen_rest)[:25]

q_up = candidates([r for r in qual if r["pct"] > 0])
q_down = candidates([r for r in qual if r["pct"] < 0])

os.makedirs("out", exist_ok=True)
json.dump({"generated_kst": time.strftime("%Y-%m-%d %H:%M"), "errors": errors,
           "rule": "자격: M7 ±2% / 메가캡 ±3% / 그외 ±4% · 우선순위: 티어→|등락률| · 최종 표시는 |등락률|순",
           "qualified_up": q_up, "qualified_down": q_down, "all": rows},
          open("out/movers.json", "w"), ensure_ascii=False, indent=1)

TN = {0: "M7", 1: "메가캡", 2: "일반"}
print(f"전체 {len(rows)}건 → 자격 통과 급등 {len([r for r in qual if r['pct']>0])} / 급락 {len([r for r in qual if r['pct']<0])} (오류 {len(errors)})")
print("=== 급등 후보 (우선순위: 티어→등락률) ===")
for r in q_up:
    print(f"{r['symbol']:6} {r['pct']:+7.2f}%  [{TN[r['tier']]:3}] cap:{r.get('mktcap_b')}B  {(r.get('name') or '')[:24]}")
print("=== 급락 후보 ===")
for r in q_down:
    print(f"{r['symbol']:6} {r['pct']:+7.2f}%  [{TN[r['tier']]:3}] cap:{r.get('mktcap_b')}B  {(r.get('name') or '')[:24]}")
