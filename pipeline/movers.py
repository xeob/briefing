#!/usr/bin/env python3
"""특징주 후보 수집 + 자격(티어별 황금 등락률) 판정 → out/movers.json

깔때기:
  수집  = Yahoo 스크리너 day_gainers/losers (시총 $10B+) ∪ CORE_SCAN(M7+주요 메가캡, 코드 내장) 상시 감시
          — 스크리너는 등락률 상위 100만 잡으므로, M7 +2%대처럼 '작지만 자격 있는' 대형주 이동은
            CORE_SCAN이 보장한다 (구 watchlist.txt는 폐지, 2026-07-04)
  자격  = M7 ±2% / 메가캡($200B+) ±3% / 그 외 ±4%
  출력  = qualified_up / qualified_down (우선순위: 티어 → |등락률|), 각 최대 25
  시총  = 스크리너 값 우선, 없으면 CNBC 조회(mktcapView), 그것도 실패하면 MEGA_HINT
이후(생성 단계, RUN.md 4단계): 2차 재료 게이트(A/B급 통과·C급 제외·$50B 이하 A급만·
재료 없으면 7%+라도 제외, M7·메가캡 면제) → 3차 등락률순 top10+M7·메가캡 예외 →
4차 동반 묶음(같은 실제 업종 |5%|+ 5개 이상). 화면 표시는 |등락률| 큰 순."""
import json, time, os, subprocess, datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))

M7 = {"AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA"}
# 시총 데이터가 없는(워치리스트 단독 조회) 종목의 메가캡 판정 힌트 — 스크리너에 잡히면 실시총이 우선
MEGA_HINT = {"AVGO", "TSM", "ASML", "LLY", "JPM", "V", "UNH", "XOM", "WMT", "MA", "ORCL",
             "NFLX", "COST", "PG", "JNJ", "HD", "BAC", "MU", "PLTR", "AMD", "KLAC", "SNDK",
             "AMAT", "LRCX", "QCOM", "TXN", "INTC", "CRM", "KO", "CVX", "MRK", "GS", "CAT",
             "IBM", "ABBV", "PEP", "TMO", "CSCO", "WFC", "MS", "DIS", "ABT", "GE", "LIN",
             "ADBE", "NOW", "PM", "RTX", "AXP", "ARM", "COIN", "UBER", "ISRG", "BA"}

def get(url, tries=4):
    """야후가 간헐적으로 빈 응답을 주므로 재시도 — 조회 실패 종목이 통째로 빠지는 것을 막는다."""
    last = None
    for i in range(tries):
        r = subprocess.run(["curl", "-s", "-m", "15", "-H", "User-Agent: Mozilla/5.0", url],
                           capture_output=True, text=True, check=True)
        try:
            return json.loads(r.stdout)
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last

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

# CORE_SCAN: 스크리너와 무관하게 매일 반드시 확인하는 대형주 (M7 + 주요 메가캡·한국 관심 대형)
CORE_SCAN = M7 | MEGA_HINT

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
                                "vol_ratio": vr, "src": scr}
    except Exception as e:
        errors.append(f"screener {scr}: {e}")

for s in sorted(CORE_SCAN):
    if s in out:
        continue
    try:
        d = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{s}?range=10d&interval=1d")
        r = d["chart"]["result"][0]
        m = r["meta"]
        # 당일 일봉이 아직 null인 시간대(장 마감 직후)가 있어 종가 배열만 믿으면 '전일 세션'을 집계하게 된다.
        # 확정 종가에 날짜를 붙여, 실시간가(regularMarketTime)가 더 최신이면 그 값을 당일 종가로 쓴다.
        bars = [(datetime.datetime.utcfromtimestamp(t).date(), c)
                for t, c in zip(r.get("timestamp") or [], r["indicators"]["quote"][0]["close"])]
        valid = [(dt, c) for dt, c in bars if c]
        last_px, rmt = m.get("regularMarketPrice"), m.get("regularMarketTime")
        rmt_date = datetime.datetime.utcfromtimestamp(rmt).date() if rmt else None
        if last_px and valid and rmt_date and rmt_date > valid[-1][0]:
            pct = (last_px / valid[-1][1] - 1) * 100
        elif len(valid) >= 2:
            pct = (valid[-1][1] / valid[-2][1] - 1) * 100
        else:
            continue
        if abs(pct) < 2.0:
            continue
        out[s] = {"symbol": s, "name": r["meta"].get("shortName") or s,
                  "pct": round(pct, 2), "mktcap_b": cnbc_cap_b(s), "vol_ratio": None,
                  "src": "core"}
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
