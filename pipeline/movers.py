#!/usr/bin/env python3
"""특징주 후보 수집 + 자격(티어별 황금 등락률) 판정 → out/movers.json

깔때기:
  수집  = Yahoo 스크리너 day_gainers/losers (시총 $10B+) ∪ CORE_SCAN 상시 감시
          — 스크리너는 등락률 상위 100만 잡으므로, M7 +2%대처럼 '작지만 자격 있는' 대형주 이동은
            CORE_SCAN이 보장한다 (구 watchlist.txt는 폐지, 2026-07-04)
          — CORE_SCAN = M7 ∪ MEGA_HINT(고정) ∪ **Nasdaq $200B+ 전 종목(매 실행 자동 갱신)**.
            고정 명단만 쓰던 시절 7/10 상장한 SK하이닉스 ADR이 +4.64%·고유 재료에도 누락됐다(2026-09-18).
  자격  = M7 ±2% / 메가캡($200B+) ±3% / 그 외 ±4%
  출력  = qualified_up / qualified_down (우선순위: 티어 → |등락률|), 기본 25 — M7·메가캡·일반 7%+는 전원(초과 허용)
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

# 메가캡 감시 목록 자동 갱신 — 고정 명단(MEGA_HINT)은 2026-07-04 작성분이라 이후 상장(SK하이닉스 ADR 7/10·
# 스페이스X)과 $200B를 새로 넘은 기업을 못 잡아 조용히 누락됐다(2026-09-18 실측: $200B+ 78개 중 28개 누락).
# 매 실행 Nasdaq 스크리너에서 $200B+ 전 종목을 받아 합친다. 조회 실패 시 MEGA_HINT로 폴백.
EXCLUDE_KW = ("zones", "notes", "preferred", "warrant", "units", "debenture", "rights")

def company_key(name):
    """같은 회사의 다른 주식 클래스를 하나로 묶기 위한 키 — 'Alphabet Inc. Class C…' → 'alphabet'"""
    n = (name or "").lower()
    for cut in (" class ", " common", " american depositary", " depositary", " ordinary",
                " capital stock", " sponsored", " ads", ","):
        i = n.find(cut)
        if i > 0:
            n = n[:i]
    n = n.strip(" .")
    for suf in (" inc", " corporation", " corp", " plc", " ltd", " limited", " n.v", " s.a", " se", " ag"):
        if n.endswith(suf):
            n = n[: -len(suf)].strip(" .,")
    return n

def live_megacaps():
    """Nasdaq 스크리너 $200B+ → {Yahoo 심볼: 시총B}. 같은 회사의 다른 클래스(GOOG·GOOGM↔GOOGL,
    BRK/A↔BRK/B)는 하나만, 보통주가 아닌 상품(CCZ ZONES 등)은 제외."""
    d = get("https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=300&marketcap=mega")
    rows = ((d.get("data") or {}).get("table") or {}).get("rows") or []
    best = {}
    for x in rows:
        try:
            cap = float(str(x.get("marketCap", "0")).replace(",", "")) / 1e9
        except ValueError:
            continue
        name = x.get("name") or ""
        if cap < 200 or any(k in name.lower() for k in EXCLUDE_KW):
            continue
        sym = x["symbol"].strip().upper()
        # 같은 회사면: 기존 감시 목록에 있는 쪽 > '/' 없는 쪽 > 사전순 뒤(BRK/B > BRK/A)
        rank = (sym in (M7 | MEGA_HINT), "/" not in sym, sym)
        key = company_key(name)
        if key not in best or rank > best[key][0]:
            best[key] = (rank, sym, round(cap, 1))
    return {s.replace("/", "-"): c for _, s, c in best.values()}

def _num(v):
    s = str(v or "").replace(",", "").replace("$", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None

# 후보 수집 전수화(2026-10-23) — 야후 day_gainers/losers는 '등락률 상위 100개'만 주므로 컷오프가 매일 달라진다.
#   실측(2026-10-22 세션): 급등 컷 +5.72% · 급락 컷 −8.27% → 시총 $10B+ 자격 통과 240건 중 **161건이
#   수집조차 되지 않았다**(코닝 −8.10%/$107B · 씨게이트 −7.86%/$147B · 암페놀 −7.74%/$180B · 서던코퍼 −7.31%/$153B).
#   특히 $100~200B 구간은 상시 감시(메가캡 $200B+)에도 없어 완전 사각지대였고, 그날 록히드마틴 +6.96%가
#   자격·A급 재료(실적 상회)에도 특징주에서 빠졌다.
#   나스닥 스크리너는 시총 구간 전체를 1회 호출로 주므로($10B~$200B 약 886종목) 컷오프 개념이 사라진다.
#   등락률 정확도: 야후 일봉과 LMT·CSX·ADBE·KLAC·LDOS·INTU 6종목 모두 0.00%p 일치(2026-10-23 확인).
def nasdaq_screen(group, min_cap_b=10.0):
    """나스닥 스크리너 시총 구간 전수 → [{symbol,name,pct,mktcap_b}]. 보통주 아닌 상품은 제외."""
    d = get(f"https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=3000&marketcap={group}")
    rows = ((d.get("data") or {}).get("table") or {}).get("rows") or []
    got = []
    for x in rows:
        name = x.get("name") or ""
        if any(k in name.lower() for k in EXCLUDE_KW):
            continue
        pct, cap = _num(x.get("pctchange")), _num(x.get("marketCap"))
        if pct is None or cap is None or cap / 1e9 < min_cap_b:
            continue
        got.append({"symbol": x["symbol"].strip().upper().replace("/", "-"), "name": name,
                    "pct": round(pct, 2), "mktcap_b": round(cap / 1e9, 1)})
    if not got:
        raise ValueError("스크리너 행 0건")
    return got

out, errors = {}, []
try:
    LIVE_MEGA = live_megacaps()
except Exception as e:
    LIVE_MEGA = {}
    errors.append(f"nasdaq megacap list: {str(e)[:60]} — 고정 명단 MEGA_HINT로 폴백")

# CORE_SCAN: 스크리너와 무관하게 매일 반드시 확인하는 대형주 (M7 + 고정 메가캡 + 실시간 $200B+)
CORE_SCAN = M7 | MEGA_HINT | set(LIVE_MEGA)

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
            capb = max(round(cap / 1e9, 1), LIVE_MEGA.get(q["symbol"], 0))  # ADR 발행분 기준 과소집계 보정
            out[q["symbol"]] = {"symbol": q["symbol"], "name": q.get("shortName"),
                                "pct": round(pct, 2), "mktcap_b": capb,
                                "vol_ratio": vr, "src": scr}
    except Exception as e:
        errors.append(f"screener {scr}: {e}")

# 나스닥 전수 수집($10B~$200B) — 야후 상위 100 컷오프 밖의 자격 종목을 메운다.
# 야후 항목이 먼저 들어온 종목은 그대로 둔다(거래량비 vol_ratio가 야후에만 있다).
try:
    for r in nasdaq_screen("large"):
        if r["symbol"] in out:
            continue
        out[r["symbol"]] = {"symbol": r["symbol"], "name": r["name"], "pct": r["pct"],
                            "mktcap_b": r["mktcap_b"], "vol_ratio": None, "src": "nasdaq_large"}
except Exception as e:
    errors.append(f"nasdaq large screener: {str(e)[:60]} — 야후 상위 100만으로 수집(컷오프 아래 자격 종목 누락 가능)")

for s in sorted(CORE_SCAN):
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
                  "pct": round(pct, 2), "mktcap_b": LIVE_MEGA.get(s) or cnbc_cap_b(s), "vol_ratio": None,
                  "src": "core"}
        time.sleep(0.15)
    except Exception as e:
        errors.append(f"chart {s}: {e}")

def tier(r):
    """0=M7, 1=메가캡($200B+), 2=그 외 — 자격 기준·우선순위 겸용"""
    if r["symbol"] in M7:
        return 0
    cap = r.get("mktcap_b")
    if (cap and cap >= 200) or (cap is None and (r["symbol"] in MEGA_HINT or r["symbol"] in LIVE_MEGA)):
        return 1
    return 2

THRESH = {0: 2.0, 1: 3.0, 2: 4.0}

rows = list(out.values())
for r in rows:
    r["tier"] = tier(r)
    r["qualified"] = abs(r["pct"]) >= THRESH[r["tier"]]

qual = sorted([r for r in rows if r["qualified"]], key=lambda x: (x["tier"], -abs(x["pct"])))

def ah_roster():
    """그 세션 실적 발표 종목(earnings.json must_cover). 파일이 없으면 earnings.py를 직접 한 번 돌린다 —
    루틴의 스크립트 실행 순서에 의존하지 않기 위해(실적 발표 종목이야말로 시간외가 크게 움직이는 쪽이다).
    이미 있으면 그대로 읽고, 실패하면 빈 집합(섹션은 CORE_SCAN·자격 종목만으로 돌아간다)."""
    for attempt in (1, 2):
        try:
            if attempt == 1 and time.time() - os.path.getmtime("out/earnings.json") > 12 * 3600:
                raise ValueError("earnings.json 12시간 초과 — 어제 로스터일 수 있어 다시 수집")
            return {e["symbol"] for e in json.load(open("out/earnings.json")).get("must_cover", []) if e.get("symbol")}
        except Exception:
            if attempt == 2:
                return set()
            try:
                import sys
                subprocess.run([sys.executable, "earnings.py"], capture_output=True, timeout=180, check=False)
            except Exception:
                return set()

REPORTERS = ah_roster()   # 그 세션 실적 발표 종목 — 후보 구성·시간외 감시 공통

GEN_CAP = 20   # 일반 티어 후보 상한(방향별). 되돌리려면 이 값만 키우면 된다.

def candidates(side):
    """후보 = M7·메가캡 전원 + 그 세션 실적 발표 종목(자격 통과) 전원 + 일반 티어 |등락률| 상위 GEN_CAP.
    side는 (티어 → |등락률|) 정렬 상태로 들어온다.
    2026-10-23 변경: 수집이 전수가 되면서 구 규칙 '일반 |7%|+ 전원 강제 포함'이 역효과를 냈다 — 변동 큰 날
    7%+가 75건까지 나오는데(10/22 실측) 그날 개별 상위 10 컷오프는 −11.5%여서 7~11% 종목은 애초에 개별
    자리에 닿지 못한다. 전원 조사는 실행시간만 늘리고(한 번에 79종목) 결과는 같다.
    잘린 종목도 all[].qualified=true로 남아 **묶음 구성·감사 기록의 대상**이며, 누락이 가장 잘 숨는 두 부류
    (메가캡·실적 발표 종목)는 몇 건이든 전원 후보에 넣는다 — verify #15가 실적 쪽을 기계로 재확인한다."""
    m7mega = [r for r in side if r["tier"] <= 1]
    rep = [r for r in side if r["tier"] == 2 and r["symbol"] in REPORTERS]
    rest = [r for r in side if r["tier"] == 2 and r["symbol"] not in REPORTERS]
    return m7mega + rep + rest[:GEN_CAP]

q_up = candidates([r for r in qual if r["pct"] > 0])
q_down = candidates([r for r in qual if r["pct"] < 0])

# SK하이닉스 ADR 상시 블록 — 한국 하이닉스와 직결되는 종목이라 특징주 자격과 무관하게 매일 표시(2026-09-18 결정).
#   ① 20시 KST(한국 NXT 애프터마켓 마감) 시점 ADR 등락률 ② 미장 종가 등락률
#   ③ 괴리 = 20시→종가 변동 = 한국장이 끝난 뒤 미장에서 더 움직인 몫(다음 날 한국 시초가에 반영될 신호).
#   20시 KST는 미국 프리마켓(여름 07:00·겨울 06:00 ET)이라 프리·애프터 포함 5분봉에서 뽑는다 — 거래량이 0으로 잡혀
#   체결가가 아닌 호가 기준일 수 있다. 종가는 공식 일봉 종가.
KR_ADR = "SKHY"

def skhy_block():
    from zoneinfo import ZoneInfo
    ET, KST = ZoneInfo("America/New_York"), ZoneInfo("Asia/Seoul")
    now_et = datetime.datetime.now(ET)
    r = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{KR_ADR}?range=10d&interval=1d")["chart"]["result"][0]
    closes = {}
    for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]):
        day = datetime.datetime.fromtimestamp(t, ET).date()
        if c is None or (day == now_et.date() and now_et.hour < 16):
            continue  # 정규장이 아직 안 끝난 날의 미완성 봉은 제외
        closes[day] = c
    days = sorted(closes)
    if len(days) < 2:
        raise ValueError("완료된 미국 세션이 2개 미만")
    s_day, prev_day = days[-1], days[-2]
    close, prev = closes[s_day], closes[prev_day]
    # 20시 KST 시점 가격 = 세션일(KST 같은 날짜) 20:00 직전 30분 안의 마지막 5분봉 종가
    target = datetime.datetime(s_day.year, s_day.month, s_day.day, 20, 0, tzinfo=KST)
    m = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{KR_ADR}?range=10d&interval=5m&includePrePost=true")
    mr = m["chart"]["result"][0]
    p20 = t20 = None
    for t, c in zip(mr["timestamp"], mr["indicators"]["quote"][0]["close"]):
        tk = datetime.datetime.fromtimestamp(t, KST)
        if c is not None and target - datetime.timedelta(minutes=30) <= tk < target:
            p20, t20 = c, tk + datetime.timedelta(minutes=5)   # 봉 시작+5분 = 그 가격의 시각
    # 그 날 한국 정규장이 열렸는가(추석·설 등) — 휴장이면 '20시=한국 마감' 전제가 성립하지 않는다
    kr_trading = None
    try:
        kd = get("https://query1.finance.yahoo.com/v8/finance/chart/000660.KS?range=10d&interval=1d")["chart"]["result"][0]
        kr_trading = s_day in {datetime.datetime.fromtimestamp(t, KST).date() for t in kd["timestamp"]}
    except Exception:
        pass
    return {"symbol": KR_ADR, "session_et": s_day.isoformat(), "prev_session_et": prev_day.isoformat(),
            "prev_close": round(prev, 2), "close": round(close, 2),
            "p20": round(p20, 2) if p20 else None, "p20_kst": t20.strftime("%Y-%m-%d %H:%M") if t20 else None,
            "pct_20": round((p20 / prev - 1) * 100, 2) if p20 else None,
            "pct_close": round((close / prev - 1) * 100, 2),
            "gap": round((close / p20 - 1) * 100, 2) if p20 else None,
            "kr_trading": kr_trading, "side": "up" if close >= prev else "down"}

try:
    skhy = skhy_block()
except Exception as e:
    skhy = None
    errors.append(f"skhy block: {str(e)[:60]}")

# 시간외 특징주 — 정규장 종료 후 '브리핑 제작 직전까지'의 움직임(2026-10-19 결정).
#   자격 기준은 정규장과 동일(M7 ±2% / 메가캡 ±3% / 그 외 ±4%)이지만, 시간외엔 1주 단위 허수 체결이 흔해
#   그대로 쓰면 날조에 가까운 수치가 실린다. 실측(2026-09-16~10-15 22세션·메가캡 62종목):
#     · 마지막 1봉만 보면 3건 통과 — UNH +6.61%·ABT +5.96%·AAPL −2.39% (셋 다 다음 세션 시가에서 ±0.5% 복귀 = 허수)
#     · AMAT −29.0%·TSM −30.6% 같은 단발 프린트도 창 안에 찍혔다
#     · '마지막 2봉 전부 통과'로 바꾸면 위 전부 탈락(허수 0건). 3봉은 겨울 30분 창에서 갓 나온 실적 반응을 놓친다.
#   그래서 방어 3중: ① 마지막 2개 5분봉 전부 기준선 통과(+방향 동일) ② 나스닥 시간외 거래대금 하한
#   ③ 야후 봉 ↔ 나스닥 체결가 일치(표시값은 나스닥 체결가 = 2소스 합의).
#   고저폭(고가·저가)은 판단·표시 모두 금지 — 조용한 날에도 넷플릭스 고저폭이 종가의 12.8%로 찍혔다(10/15 실측).
#   거래대금은 나스닥 단일 소스라 지면에는 쓰지 않고 필터·감사용으로만 기록한다(2026-10-19 사용자 결정).
#   창은 ET로 계산해 서머타임을 자동 반영(여름 06:30 KST=17:30 ET·겨울=16:30 ET).
AH_ENABLE = True        # 문제 발생 시 이 한 줄로 즉시 중단(섹션만 사라지고 나머지는 정상)
AH_BARS = 2             # 지속성: 마지막 N개 5분봉이 전부 기준선 통과
AH_MIN_VALUE_M = 5.0    # 시간외 거래대금 하한($M) — 얇은 외국 ADR 단발 체결 차단(실측 공백대 $1.7M~$6.4M)
AH_SRC_TOL = 0.5        # 야후↔나스닥 가격 허용 오차(%)
AH_STALE_MIN = 15       # 마지막 봉이 기준시각보다 이만큼 이상 오래됐으면 제외(체결 끊긴 종목)
AH_BUDGET_S = 90        # 조회 전체 시간예산(초) — 초과분은 조회하지 않고 실패로 집계
AH_MAX_FAIL = 0.2       # 실패율이 이보다 크면 불완전 스캔으로 보고 섹션 생략

def ah_universe():
    """감시 대상 = CORE_SCAN ∪ 그날 정규장 자격 종목 ∪ 그 세션 실적 발표 로스터.
    SKHY는 전용 상시 블록이 20시→종가 괴리로 따로 다루므로 제외(중복·verify #13 충돌 방지)."""
    u = set(CORE_SCAN) | {r["symbol"] for r in qual} | set(REPORTERS)
    return sorted(s for s in u if s and s != KR_ADR)

def afterhours_block(now_et=None):
    from zoneinfo import ZoneInfo
    from concurrent.futures import ThreadPoolExecutor
    ET, KST = ZoneInfo("America/New_York"), ZoneInfo("Asia/Seoul")
    now_et = now_et or datetime.datetime.now(ET)
    syms = ah_universe()
    t0 = time.time()

    def fetch(sym):
        r = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
                f"?range=5d&interval=5m&includePrePost=true")["chart"]["result"][0]
        m = r["meta"]
        close, rmt = m.get("regularMarketPrice"), m.get("regularMarketTime")
        if not (close and rmt):
            raise ValueError("종가 메타 없음")
        return {"symbol": sym, "name": m.get("shortName") or sym, "close": close,
                "session": datetime.datetime.fromtimestamp(rmt, ET).date(),
                "bars": [(datetime.datetime.fromtimestamp(t, ET), c)
                         for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c is not None]}

    def one(sym):
        if time.time() - t0 > AH_BUDGET_S:
            return sym, None, "시간예산 초과"
        try:
            return sym, fetch(sym), None
        except Exception as e:
            return sym, None, str(e)[:40]

    data, failed = [], []
    with ThreadPoolExecutor(6) as ex:
        for sym, d, err in ex.map(one, syms):
            data.append(d) if d else failed.append(f"{sym}: {err}")
    if not data:
        return {"status": "error", "reason": "시간외 시세 전건 조회 실패 — 섹션 생략", "errors": failed[:10]}

    sess = max(d["session"] for d in data)
    open_et = datetime.datetime.combine(sess, datetime.time(16, 0), ET)
    end_et = datetime.datetime.combine(sess, datetime.time(20, 0), ET)
    next_pre = datetime.datetime.combine(sess + datetime.timedelta(days=1), datetime.time(4, 0), ET)
    if now_et >= next_pre:
        # 주말·휴일 다음 브리핑이나 낮 수동 재실행 — 이미 끝난 시간외를 '제작 직전까지'로 보여주지 않는다
        return {"status": "skipped", "session_et": sess.isoformat(),
                "reason": f"{sess} 세션 시간외 창 경과(다음 프리마켓 개시 이후 실행) — 섹션 생략"}
    cut = min(now_et, end_et)
    if len(failed) / max(1, len(syms)) > AH_MAX_FAIL:
        return {"status": "partial", "session_et": sess.isoformat(),
                "reason": f"조회 실패 {len(failed)}/{len(syms)} — 불완전 스캔이라 섹션 생략(누락 위험)",
                "errors": failed[:10]}

    cand = []
    for d in data:
        if d["session"] != sess:
            continue                        # 거래정지·상장폐지 등 세션이 다른 종목
        win = [(t, c) for t, c in d["bars"] if open_et <= t <= cut]
        if len(win) < AH_BARS or cut - win[-1][0] > datetime.timedelta(minutes=AH_STALE_MIN):
            continue                        # 봉이 부족하거나 최근 체결이 끊긴 종목
        row = out.get(d["symbol"]) or {"symbol": d["symbol"], "mktcap_b": LIVE_MEGA.get(d["symbol"])}
        th = THRESH[tier(row)]
        tail = [(c / d["close"] - 1) * 100 for _, c in win[-AH_BARS:]]
        if not all(abs(p) >= th for p in tail) or len({p > 0 for p in tail}) > 1:
            continue                        # 지속성 미달 또는 방향이 섞인 봉(허수)
        cand.append({**d, "tier": tier(row), "th": th, "y_last": win[-1][1], "y_t": win[-1][0]})

    rows_ah, dropped = [], []
    for c in cand:
        def drop(why):
            dropped.append({"symbol": c["symbol"], "yahoo_pct": round((c["y_last"] / c["close"] - 1) * 100, 2),
                            "reason": why})
        try:
            t = get(f"https://api.nasdaq.com/api/quote/{c['symbol']}/extended-trading"
                    f"?assetclass=stocks&markettype=post&time=0")["data"]["infoTable"]["rows"][0]
            n_last = float(str(t["consolidated"]).split()[0].replace("$", "").replace(",", ""))
            n_vol = float(str(t["volume"]).replace(",", ""))
        except Exception as e:
            drop(f"나스닥 시간외 조회 실패({str(e)[:30]}) — 2소스 확인 불가")
            continue
        value_m, diff = n_vol * n_last / 1e6, abs(n_last / c["y_last"] - 1) * 100
        pct = (n_last / c["close"] - 1) * 100
        if value_m < AH_MIN_VALUE_M:
            drop(f"거래대금 ${value_m:.1f}M < ${AH_MIN_VALUE_M:.0f}M")
        elif diff > AH_SRC_TOL:
            drop(f"2소스 불일치 {diff:.2f}% (야후 {c['y_last']:.2f} vs 나스닥 {n_last:.2f})")
        elif abs(pct) < c["th"]:
            drop(f"나스닥 체결가 기준 {pct:+.2f}% < 기준 {c['th']:.0f}%")
        else:
            rows_ah.append({"symbol": c["symbol"], "name": c["name"], "tier": c["tier"],
                            "close": round(c["close"], 2), "price": round(n_last, 2), "pct": round(pct, 2),
                            "yahoo_pct": round((c["y_last"] / c["close"] - 1) * 100, 2),
                            "value_m": round(value_m, 1), "src_diff": round(diff, 2),
                            "last_bar_et": c["y_t"].strftime("%H:%M")})
    rows_ah.sort(key=lambda r: -abs(r["pct"]))
    cut_kst = cut.astimezone(KST)
    return {"status": "ok", "session_et": sess.isoformat(), "window_et": f"16:00~{cut:%H:%M}",
            "cut_et_hm": f"{cut:%H:%M}", "cut_kst_hm": f"{cut_kst:%H:%M}",
            "cut_kst": cut_kst.strftime("%Y-%m-%d %H:%M"), "scanned": len(data), "failed": len(failed),
            "rows": rows_ah, "dropped": dropped[:10], "errors": failed[:5],
            "rule": f"정규장과 동일 자격(M7 ±2%/메가캡 ±3%/그외 ±4%) · 마지막 {AH_BARS}개 5분봉 전부 통과 · "
                    f"거래대금 ${AH_MIN_VALUE_M:.0f}M+ · 야후↔나스닥 {AH_SRC_TOL}% 이내 · 표시값=나스닥 체결가 "
                    f"· 거래대금·고저폭은 지면 비표시"}

try:
    ah = afterhours_block() if AH_ENABLE else {"status": "off", "reason": "AH_ENABLE=False"}
except Exception as e:
    ah = {"status": "error", "reason": f"afterhours block: {str(e)[:60]}"}
if ah.get("status") in ("error", "partial"):
    errors.append(f"afterhours: {ah.get('reason')}")   # 비차단 — 아침 브리핑은 그대로 발행된다

os.makedirs("out", exist_ok=True)
json.dump({"generated_kst": time.strftime("%Y-%m-%d %H:%M"), "errors": errors, "skhy": skhy,
           "rule": "자격: M7 ±2% / 메가캡 ±3% / 그외 ±4% · 우선순위: 티어→|등락률| · 최종 표시는 |등락률|순",
           "qualified_up": q_up, "qualified_down": q_down, "afterhours": ah,
           "qualified_total": {"up": len([r for r in qual if r["pct"] > 0]),
                               "down": len([r for r in qual if r["pct"] < 0]),
                               "후보_up": len(q_up), "후보_down": len(q_down),
                               "note": "후보에 담기지 않은 자격 통과 종목도 all[].qualified=true로 남는다 "
                                       "— 감사 기록(RUN.md ⑦)은 '자격 통과했는데 안 실린 종목'을 모두 대상으로 한다"},
           "all": rows},
          open("out/movers.json", "w"), ensure_ascii=False, indent=1)

TN = {0: "M7", 1: "메가캡", 2: "일반"}
print(f"상시 감시 {len(CORE_SCAN)}종목 (고정 {len(M7 | MEGA_HINT)} + 실시간 $200B+ 신규 {len(set(LIVE_MEGA) - M7 - MEGA_HINT)})")
_src = {}
for r in rows:
    _src[r.get("src", "?")] = _src.get(r.get("src", "?"), 0) + 1
print(f"수집 {len(rows)}건 {_src} → 자격 통과 급등 {len([r for r in qual if r['pct']>0])} / 급락 {len([r for r in qual if r['pct']<0])}"
      f" → 후보 급등 {len(q_up)} / 급락 {len(q_down)} (오류 {len(errors)})")
print("=== 급등 후보 (우선순위: 티어→등락률) ===")
for r in q_up:
    print(f"{r['symbol']:6} {r['pct']:+7.2f}%  [{TN[r['tier']]:3}] cap:{r.get('mktcap_b')}B  {(r.get('name') or '')[:24]}")
print("=== 급락 후보 ===")
for r in q_down:
    print(f"{r['symbol']:6} {r['pct']:+7.2f}%  [{TN[r['tier']]:3}] cap:{r.get('mktcap_b')}B  {(r.get('name') or '')[:24]}")
if skhy:
    f = lambda v: "없음" if v is None else f"{v:+.2f}%"
    print(f"=== SK하이닉스 ADR 상시 블록 (세션 {skhy['session_et']}) — {'급등' if skhy['side']=='up' else '급락'} 파트 ===")
    print(f"  20시({skhy['p20_kst'] or '-'} KST) ${skhy['p20']} {f(skhy['pct_20'])} → 미장 종가 ${skhy['close']} {f(skhy['pct_close'])}"
          f" · 한국장 마감 후 {f(skhy['gap'])}  {'' if skhy['kr_trading'] is not False else '(한국 휴장)'}")
print(f"=== 시간외 특징주 [{ah.get('status')}] ===")
if ah.get("status") == "ok":
    print(f"  세션 {ah['session_et']} · 창 {ah['window_et']} ET ({ah['cut_kst_hm']} KST) · 감시 {ah['scanned']}종목(실패 {ah['failed']})")
    for r in ah["rows"]:
        print(f"  {r['symbol']:6} {r['pct']:+7.2f}%  [{TN[r['tier']]:3}] ${r['price']} (종가 ${r['close']})"
              f"  거래대금 ${r['value_m']}M · 2소스차 {r['src_diff']}%  {r['name'][:22]}")
    if not ah["rows"]:
        print("  자격 통과 0건 — 섹션 생략(정상)")
    for d in ah.get("dropped", []):
        print(f"  (제외) {d['symbol']:6} 야후 {d['yahoo_pct']:+.2f}% — {d['reason']}")
else:
    print(f"  {ah.get('reason')}")
