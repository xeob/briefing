#!/usr/bin/env python3
"""실적 발표 로스터 — 브리핑이 다루는 미국 세션에 실적을 낸 '화이트리스트' 종목 + 컨센서스 → out/earnings.json

★ 실측 제약(2026-07-29 확인): Nasdaq은 실적 actual(EPS)을 T+1에야 채운다.
  (7/22~7/27 전량 채움 ↔ 7/28·7/29 0건 — 발표 8시간 뒤에도 없음)
  또 Nasdaq EPS는 GAAP이라 언론이 쓰는 조정(Non-GAAP) EPS와 다르다(TSLA GAAP 0.04 vs 조정 0.33).
  조정 EPS·매출·가이던스는 회사 보도자료(8-K EX-99.1) 고유 값이라 무료 API로 당일 확정이 불가능하다.
  → 이 스크립트는 **결정론적으로 확정 가능한 것만** 제공한다:
     ① 누가 발표했는가(로스터 — verify가 누락 차단)  ② EPS 컨센서스  ③ 시총·분기·발표시점
     실제 수치(매출·조정 EPS·가이던스·특이사항)는 모델이 2소스 웹 리서치로 채운다(RUN.md).

출력: must_cover(반드시 브리핑에 실릴 종목) / deep(컨콜·특이사항 심화 대상: M7·반도체) / errors"""
import json, os, subprocess, datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))
KST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(KST)
today = now.date()

M7 = {"AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META", "TSLA"}
# 반도체(한국 시장 관심 — 컨콜·특이사항 심화 대상)
SEMI = {"NVDA", "AVGO", "TSM", "ASML", "AMD", "INTC", "QCOM", "TXN", "MU", "AMAT",
        "LRCX", "KLAC", "ADI", "ARM", "NXPI", "MRVL", "SMCI", "STX", "WDC", "MPWR"}
# 경기 가늠자(시총 작아도 경기 신호라 포함 — RUN.md 화이트리스트와 동일)
GAUGE = {"LEVI", "NKE", "LULU", "SBUX", "MCD", "FDX", "UPS", "DAL", "UAL", "CAT", "DE", "NFLX"}
MEGA_CAP_B = 200  # 메가캡 기준 $200B+

KO = {"AAPL": "애플", "MSFT": "마이크로소프트", "NVDA": "엔비디아", "GOOGL": "알파벳", "GOOG": "알파벳",
      "AMZN": "아마존", "META": "메타", "TSLA": "테슬라", "AVGO": "브로드컴", "TSM": "TSMC",
      "ASML": "ASML", "AMD": "AMD", "INTC": "인텔", "QCOM": "퀄컴", "TXN": "텍사스인스트루먼트",
      "MU": "마이크론", "AMAT": "어플라이드머티어리얼즈", "LRCX": "램리서치", "KLAC": "KLA",
      "ADI": "아나로그디바이스", "ARM": "ARM", "MRVL": "마벨", "SMCI": "슈퍼마이크로",
      "NXPI": "NXP반도체", "MPWR": "모놀리식파워", "INTU": "인튜이트", "AMGN": "암젠",
      "STX": "씨게이트", "WDC": "웨스턴디지털", "NFLX": "넷플릭스", "LEVI": "리바이스",
      "NKE": "나이키", "LULU": "룰루레몬", "SBUX": "스타벅스", "MCD": "맥도날드", "FDX": "페덱스",
      "UPS": "UPS", "DAL": "델타항공", "UAL": "유나이티드항공", "CAT": "캐터필러", "DE": "디어",
      "JPM": "JP모건", "V": "비자", "MA": "마스터카드", "UNH": "유나이티드헬스", "XOM": "엑슨모빌",
      "WMT": "월마트", "ORCL": "오라클", "LLY": "일라이릴리", "KO": "코카콜라", "PEP": "펩시코",
      "BAC": "뱅크오브아메리카", "WFC": "웰스파고", "GS": "골드만삭스", "MS": "모건스탠리",
      "C": "씨티그룹", "IBM": "IBM", "NOW": "서비스나우", "BA": "보잉", "DIS": "디즈니",
      "PG": "P&G", "JNJ": "존슨앤드존슨", "ABBV": "애브비", "MRK": "머크", "PFE": "화이자",
      "CVX": "셰브론", "COST": "코스트코", "HD": "홈디포", "CRM": "세일즈포스", "ADBE": "어도비",
      "PM": "필립모리스", "RTX": "RTX", "AXP": "아메리칸익스프레스", "GE": "GE에어로스페이스",
      "LIN": "린데", "ISRG": "인튜이티브서지컬", "UBER": "우버", "COIN": "코인베이스",
      "SPGI": "S&P글로벌", "GLW": "코닝", "GSK": "GSK", "TMO": "써모피셔", "ABT": "애보트",
      "CSCO": "시스코", "T": "AT&T", "VZ": "버라이즌", "NEE": "넥스트에라"}


def curl_json(url, retries=3):
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


def cap_b(s):
    """'$954,441,967,092' → 954.4 (십억 달러)"""
    try:
        return float(str(s or "").replace("$", "").replace(",", "").strip()) / 1e9
    except ValueError:
        return 0.0


def clean(v):
    return str(v or "").replace("&nbsp;", "").strip()


# 브리핑이 다루는 미국 세션(ET) = 전일. 주말이면 직전 평일로.
# (Nasdaq 실적 캘린더는 경제지표와 달리 날짜 오프셋이 없다 — TSLA 실제 7/22 발표 ↔ 캘린더 7/22 확인)
session = today - datetime.timedelta(days=1)
while session.weekday() >= 5:
    session -= datetime.timedelta(days=1)

out = {"generated_kst": now.strftime("%Y-%m-%d %H:%M"), "session_et": session.isoformat(),
       "note": ("must_cover = 이 세션에 실적을 낸 화이트리스트 종목(브리핑 '실적 발표' 섹션에 반드시). "
                "actual 수치는 API가 T+1에야 채우므로 매출·조정 EPS·가이던스는 2소스 리서치로 채운다."),
       "must_cover": [], "deep": [], "errors": []}

try:
    d = curl_json(f"https://api.nasdaq.com/api/calendar/earnings?date={session.isoformat()}")
    rows = (d.get("data") or {}).get("rows") or []
except Exception as ex:
    rows = []
    out["errors"].append(f"nasdaq earnings {session}: {str(ex)[:60]}")

for r in rows:
    sym = clean(r.get("symbol")).upper()
    if not sym:
        continue
    cb = cap_b(r.get("marketCap"))
    is_m7, is_semi, is_gauge = sym in M7, sym in SEMI, sym in GAUGE
    is_mega = cb >= MEGA_CAP_B
    if not (is_m7 or is_semi or is_gauge or is_mega):
        continue  # 화이트리스트 밖 소형·비주력 실적은 제외(RUN.md 실적 대상과 동일)
    tier = "M7" if is_m7 else ("반도체" if is_semi else ("메가캡" if is_mega else "가늠자"))
    rec = {"symbol": sym, "name_ko": KO.get(sym, clean(r.get("name"))), "name_en": clean(r.get("name")),
           "cap_b": round(cb, 1), "tier": tier,
           "eps_forecast": clean(r.get("epsForecast")),   # 컨센서스(결정론) — 발표 전에도 제공됨
           "eps_actual_gaap": clean(r.get("eps")),        # GAAP·T+1 반영. 조정 EPS와 다름 → 표시용 아님
           "fiscal_q": clean(r.get("fiscalQuarterEnding")), "timing": clean(r.get("time")),
           "deep": is_m7 or is_semi}                      # 컨콜·특이사항 심화 대상
    out["must_cover"].append(rec)
    if rec["deep"]:
        out["deep"].append(sym)

out["must_cover"].sort(key=lambda x: (-x["cap_b"], x["symbol"]))
os.makedirs("out", exist_ok=True)
json.dump(out, open("out/earnings.json", "w"), ensure_ascii=False, indent=1)

print(f"세션 {session} 실적 · 대상 {len(out['must_cover'])}건 (심화 {len(out['deep'])}) → out/earnings.json")
for e in out["must_cover"]:
    print(f"   {e['symbol']:6} {e['name_ko']:12} {e['tier']:5} 시총 ${e['cap_b']:.0f}B "
          f"· EPS 예상 {e['eps_forecast'] or '—'}{'  [심화]' if e['deep'] else ''}")
if not out["must_cover"]:
    print("   (이 세션 화이트리스트 실적 없음 — 실적 섹션 생략)")
for er in out["errors"]:
    print("  오류:", er)
