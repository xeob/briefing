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

# 코스피200 야간선물 (2026-11-23) — KIS(한국투자증권) Open API는 9443 포트라 클라우드 루틴에서 직접 못 부른다.
# 그래서 briefing-secrets의 kis-night 워크플로(GitHub Actions)를 실행해 결과(night.json 아티팩트)를 받아 온다.
# ★ 실패해도 브리핑은 나가야 한다 → errors(=verify #4 발송 차단)가 아니라 notes에 남기고 night_futures를 비운다
#   (템플릿 규칙: night_futures가 없으면 div.nf 줄 전체 삭제).
# 필드 의미는 2026-11-23 20:26 야간장 실측으로 확정: 야간(CM) futs_prdy_vrss·futs_prdy_ctrt = **직전 주간장 종가 대비**
#   (736.25 − 9.60 = 726.65 = 그날 주간 종가). 야간 쪽 futs_prdy_clpr(700.00)은 '지난밤 종가'라 쓰지 않는다.
NF_REPO, NF_WF, NF_BUDGET_S = "xeob/briefing-secrets", "kis-night.yml", 150

def gh_token():
    """GH_PAT: 환경변수 → 로컬 .env → 클라우드 briefing-secrets/.env 순으로 찾는다.
    클라우드 루틴은 명령마다 셸이 새로 떠서, 앞 단계에서 export한 값이 이 스크립트까지 안 올 수 있다."""
    t = os.environ.get("GH_PAT")
    for p in (".env", "../../briefing-secrets/.env", "../briefing-secrets/.env"):
        if t:
            break
        if os.path.exists(p):
            for line in open(p, encoding="utf-8"):
                if line.startswith("GH_PAT="):
                    t = line.split("=", 1)[1].strip().strip('"').strip("'")
    return t

def gh(token, path, method="GET", body=None, out_file=None):
    """GitHub API 호출(curl). 토큰은 argv가 아니라 stdin 설정으로 넘긴다. (HTTP 코드, 본문) 반환."""
    cmd = ["curl", "-s", "-m", "30", "-K", "-", "-H", "Accept: application/vnd.github+json",
           "-w", "\n%{http_code}", "-X", method, "https://api.github.com/repos/" + NF_REPO + path]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
    if out_file:   # 아티팩트 zip: 저장소(blob)로 리다이렉트된다. curl은 다른 호스트로 인증 헤더를 넘기지 않는다.
        cmd[1:1] = ["-L", "-o", out_file]
    r = subprocess.run(cmd, input='header = "Authorization: Bearer %s"\n' % token,
                       capture_output=True, text=True)
    text, _, code = r.stdout.rpartition("\n")
    return int(code or 0), text

def nf_validate(j):
    """night.json → (기록, None) 또는 (None, 사유). 숫자는 KIS 값 그대로, 서로 맞는지만 검사한다."""
    if not j.get("ok"):
        return None, "조회 실패: %s" % (j.get("error") or (j.get("night") or {}).get("error"))
    n, d = j.get("night") or {}, j.get("day") or {}
    f = lambda o, k: float(str(o.get(k)).replace(",", ""))
    try:
        val, chg, pct, vol = f(n, "futs_prpr"), f(n, "futs_prdy_vrss"), f(n, "futs_prdy_ctrt"), f(n, "acml_vol")
        day_close, day_prev = f(d, "futs_prpr"), f(d, "futs_prdy_clpr")
    except Exception:
        return None, "필드 해석 실패: %s" % str(n)[:120]
    base = round(val - chg, 2)
    if vol <= 0:
        return None, "야간 거래량 0 — 막 끝난 야간장 값이 아님(초기화 상태)"
    if base <= 0 or abs(chg / base * 100 - pct) > 0.02:
        return None, "등락률 산술 불일치: %+.2f / %.2f ≠ %+.2f%%" % (chg, base, pct)
    if min(abs(base - day_close), abs(base - day_prev)) > 0.005:
        return None, "야간 기준가 %.2f가 주간 종가(%.2f/%.2f)와 다름" % (base, day_close, day_prev)
    sign = str(n.get("prdy_vrss_sign"))   # KIS: 1 상한·2 상승·3 보합·4 하한·5 하락
    if (chg > 0 and sign not in "12") or (chg < 0 and sign not in "45") or (chg == 0 and sign != "3"):
        return None, "등락 부호 불일치: 대비 %+.2f · sign %s" % (chg, sign)
    return {"val": round(val, 2), "chg": round(chg, 2), "pct": round(pct, 2), "base": base,
            "vol": int(vol), "contract": j.get("contract"), "fetched_kst": j.get("fetched_kst"),
            "src": "KIS Open API 야간(CM) 최근월물 · 직전 주간장 종가 대비"}, None

def night_futures():
    import tempfile, zipfile
    token = gh_token()
    if not token:
        return None, "GH_PAT 없음"
    t0 = time.time()
    code, text = gh(token, "/actions/workflows/%s/runs?per_page=5" % NF_WF)
    if code != 200:
        return None, "실행 목록 조회 HTTP %d" % code
    before = {x["id"] for x in json.loads(text)["workflow_runs"]}
    code, _ = gh(token, "/actions/workflows/%s/dispatches" % NF_WF, "POST", {"ref": "main"})
    if code != 204:
        return None, "워크플로 실행 요청 HTTP %d" % code
    run = None
    while time.time() - t0 < NF_BUDGET_S:
        time.sleep(5)
        code, text = gh(token, "/actions/workflows/%s/runs?per_page=5" % NF_WF)
        new = [x for x in json.loads(text).get("workflow_runs", []) if x["id"] not in before] if code == 200 else []
        if new and new[0]["status"] == "completed":
            run = new[0]
            break
    if not run:
        return None, "워크플로 %d초 안에 끝나지 않음" % NF_BUDGET_S
    code, text = gh(token, "/actions/runs/%d/artifacts" % run["id"])
    arts = json.loads(text).get("artifacts", []) if code == 200 else []
    if not arts:
        return None, "결과 파일 없음(실행 결과 %s)" % run.get("conclusion")
    zp = os.path.join(tempfile.mkdtemp(), "night.zip")
    code, _ = gh(token, "/actions/artifacts/%d/zip" % arts[0]["id"], out_file=zp)
    try:
        j = json.loads(zipfile.ZipFile(zp).read("night.json"))
    except Exception as e:
        return None, "결과 파일 해석 실패(HTTP %d): %s" % (code, str(e)[:60])
    return nf_validate(j)

try:
    nf, why = night_futures()
except Exception as e:
    nf, why = None, "예외: %s" % str(e)[:100]
if nf:
    out["night_futures"] = nf
else:
    out["notes"].append("코스피200 야간선물 미수록 — %s (브리핑에서 div.nf 줄 삭제)" % why)

os.makedirs("out", exist_ok=True)
json.dump(out, open("out/market.json", "w"), ensure_ascii=False, indent=1)
print(f"지수 {len(out['indices'])} / 지표 {len(out['indicators'])} (오류 {len(out['errors'])}) → out/market.json")
for n, d in out["indices"].items():
    print(f"  {n}: {d['close']:,} ({d['chg']:+,.2f}, {d['pct']:+.2f}%)")
print("  " + " · ".join(f"{n} {v} ({out['indicator_chg'].get(n, {}).get('pct', 0):+.2f}%)"
                            for n, v in out["indicators"].items()))
if out.get("night_futures"):
    nf = out["night_futures"]
    print(f"  코스피200 야간선물: {nf['val']:.2f} ({nf['chg']:+.2f}, {nf['pct']:+.2f}%) · 기준 주간 종가 {nf['base']:.2f} · {nf['contract']}")
for n in out["notes"]:
    print("  교차검증:", n)
for e in out["errors"]:
    print("  오류:", e)
