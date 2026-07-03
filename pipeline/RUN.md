# 경제 브리핑 — 매일 실행 절차 (06:45 KST)

실행 주체: 스케줄 클라우드 루틴(A) = Claude가 정해진 시각에 아래 순서를 수행.
비밀값: `.env` 참조 (KAKAO_REST_KEY / KAKAO_CLIENT_SECRET / KAKAO_REFRESH_TOKEN / GH_PAT / GH_REPO / SITE_URL).
설계 규칙 전체는 메모리 `morning-briefing-tool.md` 참조.

---

## 1) 데이터 수집 (전일 22:00 ~ 실행시각)

- **주요 뉴스** — 5개 분야(정치·경제·세계·IT·산업), 분야당 3~5건.
  5단계 선별(수집→클러스터/중복제거→잡음 필터→점수화[영향범위·파급·신규성·보도밀도·시의성]→요약+검증). 각 헤드라인에 원문 URL.
- **핫한 키워드 Top 3** — 경제 전반 최다 검색 이슈(구글 트렌드 급상승 + 포털 경제면 '많이 본 뉴스' + 실검 집계). 급등폭·중요도·교차등장·이유명확성으로 채점.
- **전일 미국 시장**:
  - 지수 4종(다우·나스닥·S&P·필라 반도체): 종가 + 등락폭 + 등락률
  - **수치 = 스크립트 1차 소스 (필수)**: `python3 market.py` 를 실행해 `out/market.json` 을 생성한다. 여기에 지수 4종(다우·나스닥·S&P·SOX 종가+등락폭+등락률)과 지표 6종(美10년물·달러인덱스·원/달러·WTI·BTC·금)이 Yahoo 일봉 종가 기반으로 들어 있다. **브리핑 수치는 이 값을 그대로 쓴다.** 요약 기사 속 수치 사용 금지(오차 실증: 7/1 SOX 기사 13,478 vs 실제 13,353). market.json 값이 상식 밖(예: 지수 하루 ±10%)이거나 오류가 있으면 그때만 investing.com historical-data로 교차확인·보정: SOX=investing.com/indices/phlx-semiconductor-historical-data, 원/달러=.../currencies/usd-krw-historical-data, BTC=.../crypto/bitcoin/historical-data. market.py 실패 시에도 investing.com으로 대체.
  - 시장 지표 **6종 고정, 2행×3열 그리드(가로 스크롤 금지)**: 윗줄 美10년물·달러인덱스·원/달러 / 아랫줄 WTI·비트코인·금 (값은 out/market.json의 indicators 그대로)
  - 섹터 강세/약세: **강세는 강한 순, 약세는 약한 순**으로 나열. 색 태그(강세=초록 t-strong, 약세=빨강 t-weak) + 이유 설명은 회색 노트(sector-note)
  - **특징주(핵심!) — 확정 규칙 (2026-07-02 사용자와 합의)**: 먼저 `python3 movers.py` 실행 → `out/movers.json`의 `qualified_up`/`qualified_down`(각 최대 25, M7·메가캡 전원 + 일반 티어 |7%|+ 전원 강제 포함 — 메가캡이 많아도 큰 이동 일반주가 잘리지 않음).
    - **① 수집**: 전 종목 (Yahoo 스크리너 시총 $10B+ ∪ watchlist.txt 전수 — 지수 밖 핫종목·ADR·신규상장 커버)
    - **② 자격 (황금 등락률)**: M7 ±2% / 메가캡($200B+) ±3% / 그 외 ±4%
    - **③ 이유 검증 (엄격)**: 후보를 우선순위 순서로 철저히 조사 — 수집·조사·검토·팩트체크를 다해 반드시 이유를 찾으려 노력. 그럼에도 못 찾으면: |등락률| 7% 미만 → **제외** / 7% 이상 → 유지하되 **"상승 이유 미확인"(급등) / "하락 이유 미확인"(급락)** 표기. 제외로 빈 슬롯은 다음 후보로 채움(backfill). 지어내기 절대 금지
    - **④ 업종 동반 예외**: 개별 뉴스 없어도 동일 업종 동반 강세/약세면 포함, "업종 전반 강세/약세"로 설명. 같은 업종이 5개를 넘으면 대표 4개만 개별 게재하고 나머지는 **별도 묶음 행**("그 외 ○○ 동반 하락")으로 — 각 종목 %를 up/down 색과 함께 병기. **대표 4개는 등락률순이 아니라 중요도 기준**(사건 당사자·메가캡·스토리 중심 — 예: D램 담합 소송일엔 당사자 마이크론은 등락률이 작아도 개별 게재)
    - **⑤ 선별**: 초과 시 우선순위 = M7·메가캡 → 뉴스 촉매 명확 → |등락률| 순으로 급등 10 · 급락 10
    - **⑥ 표시**: 급등은 상승률 큰 순, 급락은 하락폭 큰 순. **종목명은 반드시 한글**(티커 병기, 예: 샌디스크 (SNDK)). 태그·라벨 없이 종목명+등락률+촉매
    - 완결성 자가검증: qualified 목록과 페이지 대조, 큰 이동 누락 없는지 확인
    - 스크립트 실패 시(fallback): stockanalysis.com/markets/gainers·losers WebFetch로 대체
    - watchlist.txt는 핫섹터 변화에 따라 주기적으로 갱신 (새 핫테마 종목 추가)
  - 발표 지표: **표 형식**(지표/결과/예상 3열). 결과 색 기준: **예상 대비 시장에 긍정적 서프라이즈면 up(초록), 부정적이면 down(빨강), 예상 부합·중립이면 무색** (예: 물가 예상 상회=빨강, 실업수당청구 예상 하회=초록)
  - 미국장 주요 일정(한국시간) — 섹션 제목도 이 이름 사용: **통합 표 1개(구분/내용/일시/비고)**, 지표·연준·실적·IPO 모두 행으로. **범위 = 오늘부터 1주일**, 날짜순 정렬, 오늘 일정은 일시에 "오늘(0/0)" 표기. 중요도 필터(지표는 시장 영향 큰 것만, 실적은 메가캡·주요 반도체·화제 기업만) + **최대 8행**. 예외: FOMC·대형은행 실적 개막·스페이스X급 IPO는 1주 밖이어도 1~2행 "예고"로 허용. **내용이 있는 구분만 행으로, 내용이 없는 구분만 표 아래 텍스트 줄로**("IPO: 오늘 대형 IPO 없음" 식). IPO 캘린더를 확인해 대형 IPO 상장일이면 반드시 기재, 화제성 IPO의 상장 첫날 결과는 다음 날 특징주에도 반영
  - **모바일 가독성(아이폰 기준 ~390px)**: 템플릿에 미디어쿼리 적용됨. 생성 시 텍스트 규칙 — 특징주 이유·키워드 설명은 **한 줄당 40자 이내**로 간결히, 뉴스 헤드라인은 35자 내외로 다듬기, '·'로 긴 나열을 만들지 않기(3개 이하 권장)

## 2) HTML 생성

- `template.html` 구조·CSS 그대로, 내용만 채워 `out/index.html` 로 저장.
- 색: 수치에만 (상승 초록 up / 하락 빨강 down). 소제목·강세/약세 단어는 회색.
- 한글 줄바꿈 `word-break:keep-all` (템플릿에 이미 적용).
- **키워드 설명은 키워드 아래 줄에** (kw-t 아래 kw-d, 인라인 " · 설명" 금지).
- **시장 지표 칩 6개, 2행×3열 그리드** (윗줄 10년물·달러인덱스·원/달러, 아랫줄 WTI·BTC·금 — 가로 스크롤 없음).
- **특징주 이유가 2개 이상이면 이유별로 `<br>` 줄바꿈** (긴 한 문장으로 어색하게 감싸지 말 것).

## 3) 최종 재검토(QA) — 발송 전 필수

파트별 자가감사: 뉴스 5분야 채움/시간창/출처실존/중복 · 키워드 근거 · 지수·지표 2소스 교차검증 · 특징주 완결성 자가검증(최소 등락폭보다 큰데 빠진 종목 없나) · 촉매 사실확인 · 수치 정합성(값·등락폭·%) · 날짜 정확 · 날조 0. 실패 시 재수집/수정.

## 4) GitHub 게시

```bash
set -euo pipefail
source .env
git clone "https://${GH_PAT}@github.com/${GH_REPO}.git" repo
cp out/index.html repo/index.html
mkdir -p repo/archive
cp out/index.html "repo/archive/$(date +%F).html"
cd repo
git config user.email "briefing@bot"; git config user.name "briefing-bot"
git add .
git commit -m "briefing $(date +%F)"
git push
cd ..; rm -rf repo
```
→ GitHub Pages가 1~2분 내 `$SITE_URL` 갱신.

## 5) 카카오톡 발송 (요약 + 링크)

```bash
source .env
# 5-1) access_token 갱신 (refresh_token 사용)
ACCESS=$(curl -s -X POST "https://kauth.kakao.com/oauth/token" \
  -d "grant_type=refresh_token" \
  -d "client_id=${KAKAO_REST_KEY}" \
  -d "client_secret=${KAKAO_CLIENT_SECRET}" \
  -d "refresh_token=${KAKAO_REFRESH_TOKEN}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# (참고) 응답에 새 refresh_token 이 오면 .env 의 값을 갱신할 것

# 5-2) 요약 + 링크 전송 (text 200자 이내)
TODAY=$(date +%-m/%-d)
curl -s -X POST "https://kapi.kakao.com/v2/api/talk/memo/default/send" \
  -H "Authorization: Bearer ${ACCESS}" \
  --data-urlencode "template_object={\"object_type\":\"text\",\"text\":\"[경제 브리핑] ${TODAY}\n· 핵심 요약 3줄\n전체 보기 →\",\"link\":{\"web_url\":\"${SITE_URL}\",\"mobile_web_url\":\"${SITE_URL}\"}}"
```
→ 성공 시 `{"result_code":0}` + 카카오톡 '나와의 채팅' 도착.

---

## 실패/예외 처리
- 데이터 소스 실패 → 재시도 후 대체 소스, 그래도 없으면 명확히 '미확인' 표기(날조 금지).
- 미국 휴장일 → 해당 파트 '휴장' 표기.
- Kakao `invalid_grant` → refresh_token 만료(약 2개월). 재발급 후 .env 갱신.
- 각 수치에 데이터 기준 시각 기록.
