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

def candidates(side):
    """후보 목록: M7·메가캡 전원 + 일반 티어 |7%|+ 전원 강제 포함, 나머지로 25까지 채움.
    (과거엔 전체를 [:25]로 잘라, 메가캡이 많은 날 일반 7%+가 잘릴 수 있었다 — 감시 대상 확대(2026-09-18)로
     그 위험이 커져 보장을 코드로 강제. 상한 25는 '일반 7% 미만'에만 적용되어 초과될 수 있다.)"""
    m7mega = [r for r in side if r["tier"] <= 1]
    gen_big = [r for r in side if r["tier"] == 2 and abs(r["pct"]) >= 7]
    gen_rest = [r for r in side if r["tier"] == 2 and abs(r["pct"]) < 7]
    return m7mega + gen_big + gen_rest[:max(0, 25 - len(m7mega) - len(gen_big))]

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

os.makedirs("out", exist_ok=True)
json.dump({"generated_kst": time.strftime("%Y-%m-%d %H:%M"), "errors": errors, "skhy": skhy,
           "rule": "자격: M7 ±2% / 메가캡 ±3% / 그외 ±4% · 우선순위: 티어→|등락률| · 최종 표시는 |등락률|순",
           "qualified_up": q_up, "qualified_down": q_down, "all": rows},
          open("out/movers.json", "w"), ensure_ascii=False, indent=1)

TN = {0: "M7", 1: "메가캡", 2: "일반"}
print(f"상시 감시 {len(CORE_SCAN)}종목 (고정 {len(M7 | MEGA_HINT)} + 실시간 $200B+ 신규 {len(set(LIVE_MEGA) - M7 - MEGA_HINT)})")
print(f"전체 {len(rows)}건 → 자격 통과 급등 {len([r for r in qual if r['pct']>0])} / 급락 {len([r for r in qual if r['pct']<0])} (오류 {len(errors)})")
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
