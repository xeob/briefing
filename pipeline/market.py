#!/usr/bin/env python3
"""시장 지표를 한 번에 수집 → out/market.json
지수 4종(종가+등락폭+등락률) + 지표 6종(레벨). Yahoo 일봉 종가 배열 기반(휴장일에도 정확).
브리핑 수치의 1차 소스. 값이 이상하면(예: 급변) 생성 단계에서 investing.com으로 교차확인."""
import json, os, subprocess, time, urllib.parse

os.chdir(os.path.dirname(os.path.abspath(__file__)))

def get(sym):
    enc = urllib.parse.quote(sym)
    r = subprocess.run(["curl", "-s", "-m", "15", "-H", "User-Agent: Mozilla/5.0",
                        f"https://query1.finance.yahoo.com/v8/finance/chart/{enc}?range=7d&interval=1d"],
                       capture_output=True, text=True, check=True)
    res = json.loads(r.stdout)["chart"]["result"][0]
    closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
    return closes  # 마지막이 최근 종가

INDICES = [("다우", "^DJI"), ("나스닥", "^IXIC"), ("S&P 500", "^GSPC"), ("필라델피아 반도체", "^SOX")]
CNBC = {"다우": ".DJI", "나스닥": ".IXIC", "S&P 500": ".SPX", "필라델피아 반도체": ".SOX"}

def cnbc_quote(sym):
    """CNBC 시세 — 레벨·등락률·전일종가를 **한 소스로** 받는다(2026-10-27).
    지표 6종은 24시간·FX 자산이라 야후 일봉은 경계가 흔들린다(실측: 원/달러는 10/23 봉이,
    BTC는 10/26 봉이 없다). 레벨만 CNBC에서 받고 등락률을 야후로 계산하면 둘이 어긋나므로
    change_pct·previous_day_closing을 같이 받아 쓴다. 실패 시 None → 야후 일봉 폴백."""
    try:
        r = subprocess.run(["curl", "-s", "-m", "12", "-H", "User-Agent: Mozilla/5.0",
                            f"https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols={sym}&requestMethod=itv&noform=1&partnerId=2&output=json"],
                           capture_output=True, text=True, check=True)
        q = json.loads(r.stdout)["FormattedQuoteResult"]["FormattedQuote"][0]
        f = lambda k: float(str(q[k]).replace(",", "").replace("%", ""))
        return {"last": f("last"), "pct": f("change_pct"), "prev": f("previous_day_closing")}
    except Exception:
        return None

def cnbc_close(sym):
    """CNBC 2차 소스 종가 (지수 교차검증용). 실패 시 None."""
    q = cnbc_quote(sym)
    return q["last"] if q else None
# 지표: (라벨, 야후심볼, 포맷함수, CNBC심볼, 교차검증 허용오차)
# 국채금리는 소수 3자리, CNBC(realtime)를 1차로 채택(투자닷컴과 더 근접)
IND = [
    ("美10년물", "^TNX", lambda v: f"{v:.3f}%", "US10Y", 0.03),
    ("달러인덱스", "DX-Y.NYB", lambda v: f"{v:.2f}", ".DXY", 0.2),
    ("원/달러", "KRW=X", lambda v: f"{v:,.1f}", "KRW=", 3),
    ("WTI", "CL=F", lambda v: f"${v:.2f}", "@CL.1", 0.4),
    ("BTC", "BTC-USD", lambda v: f"${v:,.0f}", "BTC.CM=", 500),
    ("금", "GC=F", lambda v: f"${v:,.1f}", "@GC.1", 12),
]

out = {"generated_kst": time.strftime("%Y-%m-%d %H:%M"), "indices": {}, "indicators": {},
       "indicator_chg": {}, "errors": [], "notes": []}

for name, sym in INDICES:
    try:
        cl = get(sym)
        close, prev = cl[-1], cl[-2]
        chg = close - prev
        rec = {"close": round(close, 2), "chg": round(chg, 2), "pct": round(chg / prev * 100, 2)}
        # 교차검증: CNBC 2차 소스 종가와 대조
        c2 = cnbc_close(CNBC[name])
        if c2 is None:
            rec["verify"] = "2차소스 없음"
        elif abs(c2 - close) / close <= 0.002:  # 0.2% 이내 = 일치
            rec["verify"] = "일치"
        else:
            rec["verify"] = f"불일치(야후 {close:,.2f} vs CNBC {c2:,.2f}) — investing.com 재확인 필요"
            out["errors"].append(f"{name} 교차검증 불일치: {rec['verify']}")
        # 이상치 감지
        if abs(rec["pct"]) >= 10:
            out["errors"].append(f"{name} 이상 변동 {rec['pct']:+.2f}% — 값 재확인 권장")
        out["indices"][name] = rec
        time.sleep(0.1)
    except Exception as e:
        out["errors"].append(f"{name}({sym}): {e}")

for name, sym, fmt, csym, tol in IND:
    try:
        ys = get(sym)
        yv = ys[-1]
        ypct = round((ys[-1] / ys[-2] - 1) * 100, 2) if len(ys) >= 2 and ys[-2] else None
        q = cnbc_quote(csym)  # CNBC realtime (투자닷컴과 근접) = 1차
        if q is None:
            chosen, pct, prev, src = yv, ypct, (ys[-2] if len(ys) >= 2 else None), "야후 일봉"
            out["notes"].append(f"{name} CNBC 실패 → 야후 {fmt(yv)} 사용, 투자닷컴 웹 재확인 권장")
        else:
            chosen, pct, prev, src = q["last"], round(q["pct"], 2), q["prev"], "CNBC"
            if abs(q["last"] - yv) > tol:
                out["notes"].append(f"{name} 야후 {fmt(yv)} vs CNBC {fmt(q['last'])} 차이 → CNBC 채택, 투자닷컴 웹 재확인 권장")
            if ypct is not None and abs(pct - ypct) > 0.5:
                out["notes"].append(f"{name} 등락률 CNBC {pct:+.2f}% vs 야후 일봉 {ypct:+.2f}% 차이 "
                                    "→ CNBC 채택(24시간·FX 자산은 일봉 경계가 다르다)")
        out["indicators"][name] = fmt(chosen)
        out["indicator_chg"][name] = {"pct": pct, "prev": fmt(prev) if prev is not None else None, "src": src}
        time.sleep(0.1)
    except Exception as e:
        out["errors"].append(f"{name}({sym}): {e}")

os.makedirs("out", exist_ok=True)
json.dump(out, open("out/market.json", "w"), ensure_ascii=False, indent=1)
print(f"지수 {len(out['indices'])} / 지표 {len(out['indicators'])} (오류 {len(out['errors'])}) → out/market.json")
for n, d in out["indices"].items():
    print(f"  {n}: {d['close']:,} ({d['chg']:+,.2f}, {d['pct']:+.2f}%)")
print("  " + " · ".join(f"{n} {v} ({out['indicator_chg'].get(n, {}).get('pct', 0):+.2f}%)"
                            for n, v in out["indicators"].items()))
for n in out["notes"]:
    print("  교차검증:", n)
for e in out["errors"]:
    print("  오류:", e)
