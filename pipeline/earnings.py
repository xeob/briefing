#!/usr/bin/env python3
"""실적 발표 로스터 — 브리핑이 다루는 미국 세션에 실적을 낸 '화이트리스트' 종목 + 컨센서스 → out/earnings.json

★ 실측 제약(2026-07-29 확인): Nasdaq은 실적 actual(EPS)을 T+1에야 채운다.
  (7/22~7/27 전량 채움 ↔ 7/28·7/29 0건 — 발표 8시간 뒤에도 없음)
  또 Nasdaq EPS는 GAAP이라 언론이 쓰는 조정(Non-GAAP) EPS와 다르다(TSLA GAAP 0.04 vs 조정 0.33).
  조정 EPS·매출·가이던스는 회사 보도자료(8-K EX-99.1) 고유 값이라 무료 API로 당일 확정이 불가능하다.
  → 이 스크립트는 **결정론적으로 확정 가능한 것만** 제공한다:
     ① 누가 발표했는가(로스터 — verify가 누락 차단)  ② EPS 컨센서스  ③ 시총·분기·발표시점
     실제 수치(매출·조정 EPS·가이던스·특이사항)는 모델이 2소스 웹 리서치로 채운다(RUN.md).

출력: must_cover(반드시 브리핑에 실릴 종목 — src: 나스닥·야후·예고, unconfirmed=발표 미확인) /
      deep(컨콜·특이사항 심화 대상: M7·반도체) / ah_watch(시간외 감시용 이 세션 발표 $10B+) / errors / notes
부산물: earnings_expected.json(실적 예고 장부 — publish.sh가 저장소에 커밋, 다음 실행이 대조)"""
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
INCLUDE_CAP_B = 100  # 실적 편입 시총 문턱(2026-08-21: 200→100. TJX $160B·로우스 $123B가 빠지던 문제 해소)
MEGA_CAP_B = 200     # "메가캡" 라벨 기준(편입 문턱과 별개)
UPCOMING_DAYS = 7    # 일정 표에 실을 "실적 예정" 조회 창(일). 12일로 넓히면 성수기 누적 행이 급증(실측 84행)
AH_CAP_B = 10        # 시간외 감시용 '그 세션 실적 발표 종목' 시총 하한 — 특징주 수집 문턱($10B)과 같다
EXPECTED_FILE = "earnings_expected.json"  # 실적 예고 장부 — publish.sh가 매일 저장소에 커밋(다음 실행이 대조)
EXPECTED_KEEP_DAYS = 10                   # 지난 예고를 남겨 두는 기간(주말·휴일·발송 실패일을 건너도 대조 가능)

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
      "CSCO": "시스코", "T": "AT&T", "VZ": "버라이즌", "NEE": "넥스트에라",
      "CRWD": "크라우드스트라이크", "PDD": "핀둬둬", "BABA": "알리바바", "TJX": "TJX", "LOW": "로우스",
      "TGT": "타깃", "ROST": "로스스토어", "EL": "에스티로더", "NTES": "넷이즈",
      "RY": "캐나다왕립은행", "TD": "토론토도미니언", "BMO": "몬트리올은행",
      "BNS": "노바스코샤은행", "CM": "CIBC"}


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
       "must_cover": [], "upcoming": [], "deep": [], "errors": []}

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
    if not (is_m7 or is_semi or is_gauge or cb >= INCLUDE_CAP_B):
        continue  # 화이트리스트 밖 + 문턱 미달은 제외
    tier = ("M7" if is_m7 else "반도체" if is_semi
            else "메가캡" if cb >= MEGA_CAP_B else "대형주" if cb >= INCLUDE_CAP_B else "가늠자")
    rec = {"symbol": sym, "name_ko": KO.get(sym, clean(r.get("name"))), "name_en": clean(r.get("name")),
           "cap_b": round(cb, 1), "tier": tier,
           "eps_forecast": clean(r.get("epsForecast")),   # 컨센서스(결정론) — 발표 전에도 제공됨
           "eps_actual_gaap": clean(r.get("eps")),        # GAAP·T+1 반영. 조정 EPS와 다름 → 표시용 아님
           "fiscal_q": clean(r.get("fiscalQuarterEnding")), "timing": clean(r.get("time")),
           "deep": is_m7 or is_semi}                      # 컨콜·특이사항 심화 대상
    out["must_cover"].append(rec)
    if rec["deep"]:
        out["deep"].append(sym)

# 일정 표용 '실적 예정' 로스터 — 모델 리서치에 맡기면 누락이 반복되므로(리바이스 사고) 스크립트가 확정한다.
for off in range(0, UPCOMING_DAYS + 1):
    day = today + datetime.timedelta(days=off)
    if day.weekday() >= 5:
        continue
    try:
        d2 = curl_json(f"https://api.nasdaq.com/api/calendar/earnings?date={day.isoformat()}")
        rows2 = (d2.get("data") or {}).get("rows") or []
    except Exception as ex:
        out["errors"].append(f"nasdaq upcoming {day}: {str(ex)[:50]}")
        continue
    for r in rows2:
        sym = clean(r.get("symbol")).upper()
        if not sym:
            continue
        cb = cap_b(r.get("marketCap"))
        is_m7, is_semi, is_gauge = sym in M7, sym in SEMI, sym in GAUGE
        if not (is_m7 or is_semi or is_gauge or cb >= INCLUDE_CAP_B):
            continue
        out["upcoming"].append({
            "date": day.isoformat(), "symbol": sym,
            "name_ko": KO.get(sym, clean(r.get("name"))), "cap_b": round(cb, 1),
            "tier": ("M7" if is_m7 else "반도체" if is_semi
                     else "메가캡" if cb >= MEGA_CAP_B else "대형주" if cb >= INCLUDE_CAP_B else "가늠자"),
            "eps_forecast": clean(r.get("epsForecast")), "timing": clean(r.get("time"))})
seen_up = set()
uniq = []
for e in out["upcoming"]:                      # 같은 종목이 인접일에 중복 게재되는 사례 방지
    if e["symbol"] in seen_up:
        continue
    seen_up.add(e["symbol"])
    uniq.append(e)
out["upcoming"] = sorted(uniq, key=lambda x: (x["date"], -x["cap_b"]))

# ───────────────────────────────────────────────────────────────────────────────────────────────
# 2026-11-28 보강 — 나스닥 캘린더 한 곳만 믿다가 실적 발표를 두 번 놓쳤다.
#   · 11/26 브리핑: 디어(DE)가 11/25 개장 전 발표했는데, 06:42 조회 때 나스닥 11/25 캘린더에 없었다(전날 예고엔
#     있었고 지금도 있다). 목록이 비자 verify #11도 대조할 게 없어 통과 → 실적 섹션 통째 누락.
#   · 11/24 브리핑: 크라우드스트라이크(CRWD)가 예정(12/1)보다 앞당겨 11/23 개장 전 발표(즈스케일러 인수와 함께).
#     나스닥은 나중에야 날짜를 옮겼다 → 누락.
# 대책 ① 예고 장부: 어제까지 '이 세션에 발표 예정'이던 종목이 오늘 목록에서 사라지면 되살린다(연기 확인 시만 제외).
#      ② 2차 소스: 야후 종목 시세의 earningsTimestamp(실제 발표 시각)로 이 세션 발표 종목을 따로 잡는다.
#      ③ 시간외 감시 명단: 이 세션 발표 종목 중 시총 $10B+ 전부(ah_watch) — movers.py가 시간외 스캔에 쓴다.
#      야후 실패는 notes에만 남기고(발송 차단 안 함) 나스닥·예고 장부로 계속 간다.
from zoneinfo import ZoneInfo
ET = ZoneInfo("America/New_York")
out["notes"] = []
now_et = now.astimezone(ET)


def nasdaq_caps():
    """나스닥 스크리너 mega·large 전수 → {티커: 시총(십억$)} (야후 조회 대상 명단)."""
    caps = {}
    for grp in ("mega", "large"):
        d = curl_json(f"https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=3000&marketcap={grp}")
        for x in (((d.get("data") or {}).get("table") or {}).get("rows") or []):
            s = clean(x.get("symbol")).upper()
            if s:
                caps[s] = cap_b(x.get("marketCap"))
    return caps


def yahoo_earnings_ts(symbols, chunk=100):
    """야후 시세 → {티커: (실적 발표 시각 ET, 시총 십억$, 이름)}. 쿠키+crumb 방식(curl, 임시 쿠키 파일)."""
    import tempfile
    got = {}
    with tempfile.TemporaryDirectory() as td:
        jar = os.path.join(td, "c.txt")
        ua = ["-A", "Mozilla/5.0"]
        subprocess.run(["curl", "-s", "-m", "12", "-c", jar, *ua, "https://fc.yahoo.com"], capture_output=True)
        crumb = subprocess.run(["curl", "-s", "-m", "12", "-b", jar, *ua,
                                "https://query1.finance.yahoo.com/v1/test/getcrumb"],
                               capture_output=True, text=True).stdout.strip()
        if not crumb or len(crumb) > 40 or "<" in crumb:
            raise ValueError("야후 crumb 발급 실패")
        syms = sorted({s.replace("/", "-").replace(".", "-") for s in symbols if s})
        for i in range(0, len(syms), chunk):
            url = ("https://query1.finance.yahoo.com/v7/finance/quote?symbols=" + ",".join(syms[i:i + chunk]) +
                   "&fields=earningsTimestamp,marketCap,shortName&crumb=" + crumb)
            r = subprocess.run(["curl", "-s", "-m", "15", "-b", jar, *ua, url], capture_output=True, text=True)
            for q in (json.loads(r.stdout).get("quoteResponse") or {}).get("result") or []:
                ts = q.get("earningsTimestamp")
                if ts:
                    got[q["symbol"]] = (datetime.datetime.fromtimestamp(ts, ET),
                                        round((q.get("marketCap") or 0) / 1e9, 1), q.get("shortName") or "")
    if not got:
        raise ValueError("야후 실적 시각 0건")
    return got


def timing_of(t_et):
    """발표 시각(ET) → 나스닥 표기와 같은 timing 문자열(verify #17이 'after' 포함 여부로 시간외 표기를 판단)."""
    hm = t_et.hour * 60 + t_et.minute
    return "time-pre-market" if hm < 9 * 60 + 30 else ("time-after-hours" if hm >= 16 * 60 else "time-during-market")


def whitelisted(sym, cb):
    return sym in M7 or sym in SEMI or sym in GAUGE or cb >= INCLUDE_CAP_B


def make_rec(sym, cb, name, timing, src):
    is_m7, is_semi = sym in M7, sym in SEMI
    return {"symbol": sym, "name_ko": KO.get(sym, name), "name_en": name, "cap_b": round(cb, 1),
            "tier": ("M7" if is_m7 else "반도체" if is_semi else "메가캡" if cb >= MEGA_CAP_B
                     else "대형주" if cb >= INCLUDE_CAP_B else "가늠자"),
            "eps_forecast": "", "eps_actual_gaap": "", "fiscal_q": "", "timing": timing,
            "deep": is_m7 or is_semi, "src": src}


mc = {e["symbol"]: e for e in out["must_cover"]}
for e in mc.values():
    e["src"] = ["나스닥"]
cal_caps = {clean(r.get("symbol")).upper(): cap_b(r.get("marketCap")) for r in rows if clean(r.get("symbol"))}
ah_watch = {s for s, cb in cal_caps.items() if cb >= AH_CAP_B}       # 나스닥 캘린더 기준 $10B+ 발표 종목

# 예고 장부(어제까지의 upcoming 누적) 읽기 — 이번 실행이 덮어쓰기 전에
try:
    prev_items = json.load(open(EXPECTED_FILE)).get("items", [])
except Exception:
    prev_items = []
    out["notes"].append(f"{EXPECTED_FILE} 없음 — 예고 대조 생략(첫 실행이거나 파일 유실)")

# ② 야후 2차 소스
ytab = {}
try:
    caps = nasdaq_caps()
    universe = {s for s, cb in caps.items() if cb >= AH_CAP_B} | set(cal_caps) | M7 | SEMI | GAUGE \
        | {i["symbol"] for i in prev_items}
    ytab = yahoo_earnings_ts(universe)
except Exception as ex:
    out["notes"].append(f"야후 실적 시각 조회 실패({str(ex)[:50]}) — 나스닥 캘린더·예고 장부만으로 진행")

y_session = {}                                   # 이 세션(ET 날짜)에 이미 발표한 종목
for ysym, (t_et, ycap, yname) in ytab.items():
    if t_et.date() == session and t_et <= now_et:
        y_session[ysym.replace("-", ".") if ysym.replace("-", ".") in cal_caps else ysym] = (t_et, ycap, yname)
for sym, (t_et, ycap, yname) in y_session.items():
    cb = cal_caps.get(sym) or ycap
    if cb >= AH_CAP_B:
        ah_watch.add(sym)
    if sym in mc:
        mc[sym]["src"].append("야후")
        if not mc[sym]["timing"] or "not-supplied" in mc[sym]["timing"]:
            mc[sym]["timing"] = timing_of(t_et)
    elif whitelisted(sym, cb):
        mc[sym] = make_rec(sym, cb, yname, timing_of(t_et), ["야후"])
        out["notes"].append(f"{sym}: 나스닥 캘린더엔 {session} 발표가 없지만 야후 발표 시각 "
                            f"{t_et:%m/%d %H:%M} ET → 실적 대상에 추가")

# ① 예고 장부 대조 — 이 세션 발표 예정이던 종목이 목록에 없으면 되살린다
later = {e["symbol"]: e["date"] for e in out["upcoming"]}
for it in prev_items:
    sym = it.get("symbol")
    if it.get("date") != session.isoformat() or not sym or sym in mc:
        continue
    yt = ytab.get(sym.replace(".", "-"))
    if sym in later:
        out["notes"].append(f"{sym}: {session} 예고였으나 {later[sym]}로 연기(나스닥) — 실적 대상 제외")
        continue
    if yt and yt[0].date() > session:
        out["notes"].append(f"{sym}: {session} 예고였으나 야후 발표 예정 {yt[0]:%m/%d} — 연기로 보고 제외")
        continue
    rec = make_rec(sym, it.get("cap_b") or 0, it.get("name_ko") or sym, "", ["예고"])
    rec["name_ko"] = it.get("name_ko") or KO.get(sym, sym)
    rec["eps_forecast"] = it.get("eps_forecast", "")
    rec["unconfirmed"] = True                    # 두 캘린더 어디서도 발표가 확인되지 않음 → 리서치로 확인
    mc[sym] = rec
    out["notes"].append(f"{sym}: {session} 발표 예고({it.get('date')})가 있었는데 오늘 캘린더 두 곳에서 확인 안 됨 "
                        f"— 실적 대상에 유지(발표 여부를 2소스로 확인, 미발표면 '발표 미확인' 한 줄)")
for sym, e in mc.items():
    pi = next((i for i in prev_items if i.get("symbol") == sym and i.get("date") == session.isoformat()), None)
    if pi and "예고" not in e["src"]:
        e["src"].append("예고")
    if pi and not e.get("eps_forecast"):
        e["eps_forecast"] = pi.get("eps_forecast", "")   # 야후로 되살린 종목도 컨센서스는 예고 장부에서
    if e["cap_b"] >= AH_CAP_B:
        ah_watch.add(sym)

out["must_cover"] = list(mc.values())
out["deep"] = sorted({e["symbol"] for e in out["must_cover"] if e.get("deep")})
out["ah_watch"] = sorted(ah_watch)               # ③ movers.py 시간외 감시 명단에 합류

# 예고 장부 갱신: 앞으로의 예정 = 오늘 upcoming(나스닥이 정본), 지난 예정은 EXPECTED_KEEP_DAYS일 보존
keep_from = (today - datetime.timedelta(days=EXPECTED_KEEP_DAYS)).isoformat()
new_syms = {e["symbol"] for e in out["upcoming"]}
items = [i for i in prev_items if keep_from <= i.get("date", "") < today.isoformat() and i.get("symbol") not in new_syms]
items += [{k: e[k] for k in ("date", "symbol", "name_ko", "cap_b", "tier", "eps_forecast")} for e in out["upcoming"]]
items.sort(key=lambda x: (x["date"], x["symbol"]))
json.dump({"generated_kst": now.strftime("%Y-%m-%d %H:%M"),
           "note": "earnings.py가 매 실행 갱신하는 실적 예고 장부 — 손으로 고치지 말 것(publish.sh가 커밋)",
           "items": items}, open(EXPECTED_FILE, "w"), ensure_ascii=False, indent=1)

out["must_cover"].sort(key=lambda x: (-x["cap_b"], x["symbol"]))
os.makedirs("out", exist_ok=True)
json.dump(out, open("out/earnings.json", "w"), ensure_ascii=False, indent=1)

print(f"세션 {session} 실적 · 대상 {len(out['must_cover'])}건 (심화 {len(out['deep'])}) → out/earnings.json")
for e in out["must_cover"]:
    print(f"   {e['symbol']:6} {e['name_ko']:12} {e['tier']:5} 시총 ${e['cap_b']:.0f}B "
          f"· EPS 예상 {e['eps_forecast'] or '—'} · 출처 {'+'.join(e.get('src', []))}"
          f"{'  [심화]' if e['deep'] else ''}{'  [발표 미확인 — 리서치로 확인]' if e.get('unconfirmed') else ''}")
print(f"  [시간외 감시용 · 이 세션 발표 · ${AH_CAP_B}B+] {len(out['ah_watch'])}건: {' '.join(out['ah_watch']) or '없음'}")
print(f"  [일정 표용 실적 예정 · 향후 {UPCOMING_DAYS}일 · ${INCLUDE_CAP_B}B+] {len(out['upcoming'])}건")
for e in out["upcoming"]:
    print(f"   {e['date']}  {e['symbol']:6} {e['name_ko']:12} {e['tier']:5} ${e['cap_b']:.0f}B")
if not out["must_cover"]:
    print("   (이 세션 화이트리스트 실적 없음 — 실적 섹션 생략)")
for er in out["errors"]:
    print("  오류:", er)
for nt in out["notes"]:
    print("  참고:", nt)
