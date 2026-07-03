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
# 지표: (라벨, 심볼, 포맷함수)
IND = [
    ("美10년물", "^TNX", lambda v: f"{v:.2f}%"),
    ("달러인덱스", "DX-Y.NYB", lambda v: f"{v:.2f}"),
    ("원/달러", "KRW=X", lambda v: f"{v:,.1f}"),
    ("WTI", "CL=F", lambda v: f"${v:.2f}"),
    ("BTC", "BTC-USD", lambda v: f"${v:,.0f}"),
    ("금", "GC=F", lambda v: f"${v:,.1f}"),
]

out = {"generated_kst": time.strftime("%Y-%m-%d %H:%M"), "indices": {}, "indicators": {}, "errors": []}

for name, sym in INDICES:
    try:
        cl = get(sym)
        close, prev = cl[-1], cl[-2]
        chg = close - prev
        out["indices"][name] = {"close": round(close, 2), "chg": round(chg, 2),
                                "pct": round(chg / prev * 100, 2)}
        time.sleep(0.1)
    except Exception as e:
        out["errors"].append(f"{name}({sym}): {e}")

for name, sym, fmt in IND:
    try:
        cl = get(sym)
        out["indicators"][name] = fmt(cl[-1])
        time.sleep(0.1)
    except Exception as e:
        out["errors"].append(f"{name}({sym}): {e}")

os.makedirs("out", exist_ok=True)
json.dump(out, open("out/market.json", "w"), ensure_ascii=False, indent=1)
print(f"지수 {len(out['indices'])} / 지표 {len(out['indicators'])} (오류 {len(out['errors'])}) → out/market.json")
for n, d in out["indices"].items():
    print(f"  {n}: {d['close']:,} ({d['chg']:+,.2f}, {d['pct']:+.2f}%)")
print("  " + " · ".join(f"{n} {v}" for n, v in out["indicators"].items()))
for e in out["errors"]:
    print("  오류:", e)
