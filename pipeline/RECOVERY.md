# Market Briefing — 복구 매뉴얼 (재해 복구 · DR)
v2.0 · 2026-07-05 · **이 문서 하나 + 새 Claude 세션이면 전손 상태에서도 시스템 100% 재구축 가능** (부록에 전체 소스 코드 수록)

> **복구 실행법**: 새 Claude Code 세션에 이 문서를 주고 **"이 복구 매뉴얼대로 재구축해줘"** 라고 지시한다. 사람이 직접 해야 하는 것은 §4의 계정 작업(GitHub PAT 발급·카카오 로그인 동의)뿐이다.

---

## 1. 자산 소재 지도 (무엇이 어디에, 유일 원본은 무엇인가)
| 자산 | 위치 | 사본 |
|---|---|---|
| 파이프라인 파일 전체 | GitHub `xeob/briefing` pipeline/ ⟷ 로컬 `~/Downloads/claude/briefing/` ⟷ **이 문서 부록(§8)** | 3 |
| 운영 매뉴얼 | repo·로컬 MANUAL.md + 옵시디언 `xxeob/Market Briefing/` | 3 |
| 복구 매뉴얼(이 문서) | repo·로컬 RECOVERY.md + 옵시디언 + Claude 메모리 백업 | 4 |
| 루틴 프롬프트 전문 | 트리거 설정 + **§4.5에 전문 수록** | 2 |
| 비밀값 | 로컬 .env + `xeob/briefing-secrets`(비공개) — 값은 어디에도 추가 기록 금지, 분실 시 §4에서 재발급 | 2 |
| 카카오 앱·템플릿 | 카카오 콘솔(유일) + **재구축 스펙 §4.3** | 스펙 1 |
| 발행물 아카이브 | GitHub Pages(repo) | 1 — 손실 시 과거 브리핑 복구 불가(수용) |

## 2. 복구 시나리오 매트릭스
| 손실 대상 | 절차 | 소요 |
|---|---|---|
| 로컬 폴더 | §5-A (repo에서 클론) | 5분 |
| `xeob/briefing` repo | §4.1 → §5-B | 15분 |
| `briefing-secrets` | §4.2 | 10분 |
| 클라우드 루틴 | §4.5 | 10분 |
| 클라우드 환경 | §4.4 → §4.5 | 15분 |
| 카카오 앱/템플릿/토큰 | §4.3 | 30~60분 |
| 소스 전손(repo+로컬) | §5-C (부록에서 복원) | 30분 |
| **전부(전손)** | §4.1→4.2→4.3→4.4→§5-C→§4.5→§6 | 반나절 |

## 3. 복구 전 준비물
- GitHub 계정 `xeob` 로그인 가능 상태
- 카카오 계정 로그인 가능 상태 (developers.kakao.com)
- claude.ai 계정 (루틴·환경)
- 이 문서 (어느 사본이든)

---

## 4. 인프라 재구축 절차

### 4.1 GitHub 저장소 `xeob/briefing`
1. github.com → New repository → 이름 `briefing`, **Public**, README 없이 생성.
2. **Pages**: repo Settings → Pages → Source **"Deploy from a branch"** → Branch **main** / **/(root)** → Save. 몇 분 후 https://xeob.github.io/briefing/ 활성.
3. **PAT 발급**: GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate: Resource owner `xeob`, Repository access = **Only select repositories: `briefing`, `briefing-secrets`**, Permissions → **Contents: Read and write**. 만료 최장으로. 발급값 = `GH_PAT`.
4. 파일 push는 §5에서.

### 4.2 저장소 `briefing-secrets` + .env 전문
1. github.com → New repository → `briefing-secrets`, **Private**.
2. 루트에 `.env` 1개 커밋 — **전체 형식**:
```
GH_PAT=github_pat_...          # §4.1-3에서 발급
GH_REPO=xeob/briefing
SITE_URL=https://xeob.github.io/briefing/
KAKAO_REST_KEY=...             # §4.3-A 앱 키 > REST API 키
KAKAO_CLIENT_SECRET=...        # §4.3-C 보안 > Client Secret
KAKAO_REFRESH_TOKEN=...        # §4.3-E OAuth 재인증
# KAKAO_TEMPLATE_ID=134931     # 템플릿을 새로 만들었으면 새 ID (publish.sh 기본값 134931)
```
3. 로컬 `~/Downloads/claude/briefing/.env`에도 동일 내용 저장 (git 추적 금지 — 공개 repo에 절대 커밋 불가).

### 4.3 카카오 전체 재구축 (앱 소실 시 A→F 순서대로)
**A. 앱**: developers.kakao.com → 내 애플리케이션 → 앱 생성(이름 "경제 브리핑"). [앱 키]에서 **REST API 키** → `KAKAO_REST_KEY`.
**B. 플랫폼**: 앱 설정 → 플랫폼 → **Web 사이트 도메인 `https://xeob.github.io` 등록** (템플릿 링크 도메인으로 필요).
**C. 카카오 로그인 + Client Secret**: 제품 설정 → 카카오 로그인 **활성화 ON** → **Redirect URI `https://localhost:3000/oauth`** 등록 (⚠ '고급 > 로그아웃 리다이렉트'가 아님 — 과거 KOE006 원인). [보안]에서 **Client Secret 발급 + 활성화(사용함)** → `KAKAO_CLIENT_SECRET`.
**D. 동의항목**: 카카오 로그인 → 동의항목 → **"카카오톡 메시지 전송(talk_message)"** 이용 설정(선택 동의).
**E. refresh_token 발급 (OAuth)**:
1. 브라우저: `https://kauth.kakao.com/oauth/authorize?client_id={REST_KEY}&redirect_uri=https://localhost:3000/oauth&response_type=code&scope=talk_message` → 로그인·동의.
2. 이동된 주소(연결 실패 화면이어도 무관)의 `code=` 파라미터 복사 (1회용·수분 내 사용).
3. 교환:
```bash
curl -X POST "https://kauth.kakao.com/oauth/token" \
  -d grant_type=authorization_code -d client_id={REST_KEY} \
  -d client_secret={CLIENT_SECRET} \
  -d redirect_uri=https://localhost:3000/oauth -d code={code}
```
→ 응답 `refresh_token` → `.env` 두 곳에 저장. (이후엔 publish.sh가 슬라이딩 자동 갱신.)
**F. 메시지 템플릿**: 도구 → 메시지 템플릿 → 템플릿 추가, 타입 **피드**:
- 제목 `[경제 브리핑] ${DATE}` / 본문 `${SUMMARY}` (예: "오늘의 주요 뉴스·미국 시장을 확인하세요." 고정문 조합 가능)
- 버튼 1개 "자세히 보기"
- **링크(개별링크 설정)**: 모바일 웹·PC 웹 모두 → 도메인 `https://xeob.github.io`, **Path `/briefing/archive/${WDATE}.html`** (콘텐츠 영역·버튼에 링크 자리가 각각 있으면 **둘 다** 동일하게)
- 사용자 인자 문법 = `${KEY}` (DATE·SUMMARY·WDATE 3개 사용)
- 저장 후 **새 템플릿 ID**를 `.env`에 `KAKAO_TEMPLATE_ID=새ID`로 추가.

### 4.4 클라우드 환경 (claude.ai)
- 코드 환경 설정에서 환경의 **네트워크 액세스 = 개방** ("신뢰된 것만"이면 Yahoo·CNBC·Nasdaq·카카오 egress가 막혀 전부 실패).
- 환경 ID는 직접 입력하지 말 것("cloud_default" 문자열은 session_config_rejected) — **루틴을 탭에서 한 번 저장하면 서버가 자동 연결**.

### 4.5 루틴(트리거) 재생성
**설정값**:
| 항목 | 값 |
|---|---|
| 이름 | Market Briefing |
| 스케줄 | 매일 06:30 KST (cron `30 21 * * *` UTC) |
| 모델 | claude-fable-5 |
| 소스 | git 2개: https://github.com/xeob/briefing + https://github.com/xeob/briefing-secrets |
| 세션 유지 | 끔 |

**생성 방법**: claude.ai 루틴(자동화) 탭 → 새 루틴 → 위 설정 + 아래 프롬프트 전문 붙여넣기 → 저장(환경 자동 연결). (Claude에게 맡기면 RemoteTrigger API로도 생성 가능.)

**프롬프트 전문 (그대로 사용— 수정 시 이 문서도 동기화)**:
```
매일 아침 "경제 브리핑"을 생성해 GitHub Pages에 게시하고 카카오톡으로 발송하라. 작업 공간에 xeob/briefing(공개)·xeob/briefing-secrets(비공개) 두 저장소가 클론돼 있다.

[무인 실행 — 최우선] 사람이 안 보는 예약 실행. 절대 질문·선택지 제시하며 멈추지 말 것. 문제 시 스스로 최선 판단으로 계속(대체 소스, 확인 불가는 "미확인"). 단 publish.sh(내부 verify.py)를 통과 못 했으면 게시·발송 금지.

[★ 매번 반드시 — 과거 위반 잦음, 어기지 말 것]
A. 처음부터 새로 생성. 이전 브리핑(index.html·archive)을 복사·부분수정·재탕 금지. 뉴스·키워드·특징주·일정 전부 오늘 새로 수집·작성.
B. 뉴스 시간창 엄수: 각 뉴스 게재시각 확인 → 전일 15:20~당일 발행분만, 전일 15:20 이전·전전일(2일 전) 이전 금지. verify.py가 날짜 하한을 차단하니 걸리면 최신 기사로 교체.
C. 휴장/주말: 국내 뉴스·키워드는 시장과 무관하게 매일 새로. 미국장이 직전 휴장이면 미국 시장 섹션은 직전 개장 세션 종가 + sec-note에 "○/○ 휴장 · 수치는 직전 거래일 ○/○ 종가" 명시. 미국 수치가 그대로여도 브리핑 전체 재탕 금지.
D. template.html 세부규칙 전부 반영: 일정 표는 3열(구분/내용/일시 — 비고 칸 없음), 일시는 날짜·요일·시간 한 줄(예 7/14 (화) 21:30), 연준 발언은 발언자 이름 표기("연준 월러 발언" — events.json title 그대로), 순연·예고·변동 특이사항은 표 아래 회색 줄(.sched), 구분 색태그, 특징주 묶음행은 종목명과 % 사이 &nbsp; 결합·나열 중간 억지 <br> 금지·라벨은 실제 업종명만(순환매·테마 금지), 가늠자 실적 화이트리스트(리바이스·나이키·페덱스·델타 등) 포함·M7·초대형 실적 개별 보장.

0) 비밀값: briefing-secrets/.env에서 GH_PAT·KAKAO_REST_KEY·KAKAO_CLIENT_SECRET·KAKAO_REFRESH_TOKEN·GH_REPO·SITE_URL 확보(출력 금지). 발송 위해 export: set -a; source briefing-secrets/.env; set +a. 없으면 중단 보고.
1) briefing/pipeline/RUN.md 를 반드시 먼저 전부 읽고 그대로 따른다(특히 상단 '매 실행 필수 규칙'과 특징주 4단계).
2) briefing/pipeline 에서 python3 market.py, python3 movers.py, python3 events.py 셋 다 먼저 실행. 실패 시에만 대체 소스.
3) 지수·지표 수치 = market.json 2소스 합의값 그대로(방안 A). 일정·발표지표 = out/events.json(must_include 전부·optional 기본 포함·released 그 세션분 전부, 날짜 추측 금지). [특징주 4단계 — RUN.md 상세 따름] 1차 자격: M7 ±2%/메가캡($200B+) ±3%/그 외 ±4% (movers.json qualified·시총 전수 포함). 2차 재료 게이트(비메가캡): A급(확정 사실·공시)·B급(투자의견·보도) 통과·C급=재료 없음·$50B 이하는 A급만·재료 없으면 7%+라도 개별 제외. M7·메가캡은 게이트 면제(거시 사유 허용·출처 있는 사실만·못 찾으면 이들만 '이유 미확인'). 3차 배치: 등락률순(동률 시총순) 상위 10. 예외① M7은 10위 밖이어도 무조건 개별. 예외② 메가캡은 10위 밖이면 고유(종목 자체) 재료 A/B급 보유 시에만 개별 — 거시·섹터 사유뿐이면 개별 제외(묶음 성립 시 묶음으로, 아니면 섹터 파트·감사기록). 후보 부족 시 억지 채움 금지. 4차 동반 묶음: 같은 실제 업종에서 [메가캡 |3%|+ 또는 비메가캡 |5%|+] 5개 이상(개별 포함 집계) AND 묶음행 잔여 중 |5%|+ 3개 이상(verify 차단)일 때만 구성. 라벨 실제 업종명만, 개별 제외 잔여 전부(재료 없는 고% 종목 묶음 정당). 급등/급락 동일. 뉴스·키워드·섹터·재료·실적은 웹 리서치(2소스·시간창 엄수).
4) pipeline/template.html 구조·CSS 그대로 out/index.html 생성 + out/summary.txt 에 카드용 요약(200자) 저장.
5) 사람판단 QA: 뉴스 시간창·5분야(분야당 3~5건)·출처 실존·일정 must_include 전부·released 전부·재료 팩트체크(A/B/C 판정·$50B 이하 A급만)·메가캡 개별/묶음/제외 분류 적정성·묶음 성립조건(혼합 5개+앵커 3개)·날조 0·한글 종목명·묶음행 &nbsp; 확인.
6) [게시·발송 = publish.sh 로만] ./publish.sh 실행 — 내부 verify.py가 지수·지표·특징주·묶음 라벨 금지어·묶음행 앵커(5%+ 3개)·&nbsp;·뉴스 날짜창·헤더 날짜·일정 1순위 누락을 기계검사, 실패 시 자동 중단. 수정 후 재실행 반복, 통과 못 하면 발송 안 함.
7) 보고: 게시 URL·카카오 result_code·verify 결과 + 감사 기록(ⓐ재료 없어 제외한 7%+ ⓑ등락률 10위 밖 재료 보유 종목 ⓒ거시 사유뿐이라 개별·묶음 모두 못 실린 메가캡 — "제외: XYZ +9.2% 재료없음 / KO +3.5% 거시·단독" 형식). publish.sh가 새 refresh_token을 자동 저장·push하니 실패 경고 시에만 수동 커밋.
```

---

## 5. 파일 복원
**A. 로컬만 소실**: `git clone https://github.com/xeob/briefing.git` → pipeline/ 내용을 `~/Downloads/claude/briefing/`로 복사 + briefing-secrets 클론해 .env 복사.
**B. repo 소실(로컬 생존)**: §4.1로 repo 재생성 후
```bash
cd ~/Downloads/claude/briefing && TMP=$(mktemp -d)
git clone https://${GH_PAT}@github.com/xeob/briefing.git $TMP/r
mkdir -p $TMP/r/pipeline $TMP/r/archive
cp RUN.md MANUAL.md RECOVERY.md template.html market.py movers.py events.py verify.py publish.sh gen_static.py events_static.json events_manual.txt $TMP/r/pipeline/
cp out/index.html $TMP/r/index.html 2>/dev/null || true
cd $TMP/r && git add -A && git commit -m restore && git push
```
**C. 전손(repo+로컬 모두)**: **이 문서 부록(§8)의 소스를 파일명 그대로 저장**해 `~/Downloads/claude/briefing/`를 재구성 → B 절차로 push. (Claude에게 "부록 소스로 파일 전부 복원해줘" 지시하면 자동.)
- events_static.json은 참고 스냅샷 — 복원 후 `python3 gen_static.py` 또는 첫 정기 실행이 자동 갱신.
- publish.sh는 복원 후 `chmod +x publish.sh`.

## 6. 복구 후 검증 체크리스트 (순서대로 — 모두 통과해야 완료)
1. `python3 market.py` → "지수 4 / 지표 6 (오류 0)" + 지수 4종 verify "일치"
2. `python3 movers.py` → 후보 수십 건, "시총 None 0건" (`python3 -c "import json;print(sum(1 for r in json.load(open('out/movers.json'))['all'] if r['mktcap_b'] is None))"` = 0)
3. `python3 events.py` → 캘리브레이션 로그("FF 앵커 n건 → 오프셋 보정") + must_include에 다음 CPI·FOMC 포함 + released에 최근 지표
4. 카카오 단독 테스트: publish.sh의 토큰·발송 부분 실행(verify 건너뛰려면 임시 정상 out/index.html 필요) 또는 Claude에게 "카카오 테스트 발송해줘" → result_code 0 + 카톡 수신 + **카드 링크가 archive/날짜.html로 열리는지**
5. 루틴 수동 실행 → 브리핑 발행 → 운영 매뉴얼 §7 기준 전 항목 검증 + 카톡 수신
6. 다음 날 정기 실행(06:30) 정상 확인 → 복구 완료

## 7. 백업 유지 규칙
- 이 복구 매뉴얼은 **4곳 유지**: repo pipeline/RECOVERY.md(정본) · 로컬 · 옵시디언 `xxeob/Market Briefing/Market Briefing 복구 매뉴얼` · Claude 메모리 백업.
- **규칙·코드·프롬프트가 바뀌면 반드시 이 문서의 §4.5 프롬프트 전문과 §8 부록 소스도 재생성**(Claude에게 "복구 매뉴얼 갱신해줘" — 부록은 실제 파일에서 자동 수록되므로 재생성이 정확성을 보장).
- 카카오 템플릿 변경 시 §4.3-F 스펙 동기화.

---

## 8. 부록 — 전체 소스 코드 (전손 대비 · 파일명 그대로 저장하면 복원 완료)
> 아래 각 코드블록을 해당 파일명으로 저장한다. 이 부록은 실제 배포 파일에서 자동 수록되어 바이트 단위로 동일하다.

### 8.RUN.md

````text
# 경제 브리핑 — 매일 실행 절차 (06:30 KST)

실행 주체: 스케줄 클라우드 루틴(A) = Claude가 정해진 시각에 아래 순서를 수행.
비밀값: `.env` 참조 (KAKAO_REST_KEY / KAKAO_CLIENT_SECRET / KAKAO_REFRESH_TOKEN / GH_PAT / GH_REPO / SITE_URL).
설계 규칙 전체는 메모리 `morning-briefing-tool.md` 참조.

## ★ 매 실행 필수 규칙 (위반 잦음 — 반드시 지킬 것)
1. **매번 처음부터 새로 생성.** 이전 브리핑(index.html·archive)을 복사·재사용·부분수정하지 말 것. 뉴스·키워드·특징주·일정 전부 오늘 새로 수집·작성한다.
2. **뉴스 시간창 엄수.** 각 뉴스는 게재시각을 확인해 **전일 15:20 ~ 당일 발행분만**. 전일 15:20 이전 기사·전전일(2일 전) 이전 기사는 포함 금지. (verify.py는 날짜 하한=전전일 이전을 확실히 차단하고, 15:20 시각 컷은 각 기사 게재시각으로 직접 확인해 적용.)
3. **휴장/주말 처리.** 국내 뉴스·키워드는 시장 상태와 무관하게 **매일 새로** 수집. 미국장이 직전에 휴장이면 미국 시장 섹션은 **직전 개장 세션 종가**를 쓰되 sec-note에 "○/○ 휴장 · 수치는 직전 거래일 ○/○ 종가"로 명시. 절대 미국 데이터가 그대로라는 이유로 브리핑 전체를 재탕하지 말 것.
4. **template.html·RUN.md 규칙을 그대로 반영.** 색태그·일정 3열(비고 없음)·일시 한 줄·연준 발언 이름 표기·묶음행 &nbsp;·묶음 성립조건(5개@5%) 등 세부 규칙을 빠짐없이 적용. 마지막에 verify.py 통과 필수(6번 게이트).

---

## 1) 데이터 수집 (전일 15:20 ~ 당일 06:30 실행시각)

> 시간 창: 루틴은 매일 **06:30 KST** 실행. 뉴스는 **전일 15:20 ~ 당일 발행분만**(전일 15:20 이전·전전일 이전 금지). 미국 시장은 **직전 개장 세션**(전일 16:00 ET 마감 = 당일 05:00 KST, 휴장이면 그 이전 개장일) 기준. 헤더 설명글은 "전일 15:20 ~ 당일 06:30"으로 유지.

- **주요 뉴스** — 5개 분야(정치·경제·세계·IT·산업), 분야당 3~5건.
  5단계 선별(수집→클러스터/중복제거→잡음 필터→점수화[영향범위·파급·신규성·보도밀도·시의성]→요약+검증). 각 헤드라인에 원문 URL. **시간창 엄수: 전일 15:20~당일만, 전일 15:20 이전·전전일 이전 기사 금지 — verify.py가 날짜 하한을 차단하니 창 밖이면 최신 기사로 교체.**
- **핫한 키워드 Top 3** — 기간: **실행 시점(06:30) 기준 최근 24시간** 급상승 이슈. 경제 전반 최다 검색 이슈(구글 트렌드 급상승 + 포털 경제면 '많이 본 뉴스' + 실검 집계). 급등폭·중요도·교차등장·이유명확성으로 채점. (주의: 한국은 2021년 이후 단일 공식 실시간 검색어 서비스가 없어 근사치 — 이 파트만 스크립트 검증 대상 아님.)
- **전일 미국 시장**:
  - 지수 4종(다우·나스닥·S&P·필라 반도체): 종가 + 등락폭 + 등락률
  - **수치 = 스크립트 2소스 교차검증 (방안 A, 신뢰가 생명)**: `python3 market.py` 로 `out/market.json` 생성. 지수 4종·지표 6종이 **Yahoo + CNBC 2소스 교차검증**(국채금리 3자리, 지표는 CNBC realtime 1차). **두 독립 소스가 일치하면 그게 확정값 — market.json 값을 그대로 쓴다.** 달러인덱스처럼 investing.com과 소수 둘째 자리에서 미세하게 달라도 **2소스 합의값을 유지**한다(investing.com은 Cloudflare로 스크립트 불가라 강제 참조 대상 아님). market.json의 errors·notes에 불일치·이상치가 있을 때만 웹으로 재확인. market.json 값이 상식 밖(지수 하루 ±10%)이거나 스크립트 완전 실패 시에만 웹 대체. **요약 기사 속 수치 사용 금지**(오차 실증: 7/1 SOX 기사 13,478 vs 실제 13,353).
  - **일정·발표지표 데이터 = `python3 events.py` (→ out/events.json)**: 실제 캘린더(Nasdaq 경제캘린더 + IPO + events_manual.txt)에서 수집. **모델이 날짜를 추측하지 말고 이 값을 쓴다.** 구조: `must_include`(1순위·반드시 일정 표에 포함 — 누락 시 verify.py가 게시 차단), `optional`(2순위·자리 남으면), `released`(직전 세션 발표지표: 지표명·actual·forecast). 미국 관련이 아닌 특수 이벤트(한국 상장 등)는 events_manual.txt에 수동 추가.
  - 시장 지표 **6종 고정, 2행×3열 그리드(가로 스크롤 금지)**: 윗줄 美10년물·달러인덱스·원/달러 / 아랫줄 WTI·비트코인·금 (값은 out/market.json의 indicators 그대로)
  - 섹터 강세/약세: **강세는 강한 순, 약세는 약한 순**으로 나열. 색 태그(강세=초록 t-strong, 약세=빨강 t-weak) + 이유 설명은 회색 노트(sector-note)
  - **특징주(핵심!) — 확정 규칙 (2026-07-02 사용자와 합의)**: 먼저 `python3 movers.py` 실행 → `out/movers.json`의 `qualified_up`/`qualified_down`(각 최대 25, M7·메가캡 전원 + 일반 티어 |7%|+ 전원 강제 포함 — 메가캡이 많아도 큰 이동 일반주가 잘리지 않음).
    - **① 수집**: Yahoo 스크리너 급등/급락 상위(시총 $10B+) ∪ **CORE_SCAN(M7+주요 메가캡 ~58종, movers.py 내장)** 상시 감시 — 스크리너가 못 잡는 'M7 +2%대' 같은 작지만 자격 있는 대형주 이동을 보장 (구 watchlist.txt 폐지)
    - **② 자격 (황금 등락률)**: M7 ±2% / 메가캡($200B+) ±3% / 그 외 ±4%
    - **③ 2차 재료 게이트 (비메가캡 전원 적용 — 재료 없으면 등락률 불문 개별 제외)**: 후보 전 종목을 철저히 조사(수집·검토·팩트체크)해 재료를 찾는다. **재료 등급**: **A급(확정 사실·1차 정보)** = 실적/가이던스 발표·M&A 확정/공식 제안·규제/FDA/판결 결과·대형 계약·수주 공시·파산/신용등급·지수 편입/제외·CEO 교체·사고/리콜·자사주/배당/증자 공시·공매도 리포트 등 / **B급(2차 정보·의견)** = 투자의견·목표가 변경·애널 리포트·단독 보도/루머·간접 수혜/피해 보도 / **C급(막연한 서술)** = "업황 기대감"·"AI 수혜"·"차익실현"·"저가 매수"·섹터 동반 — **C급은 재료 없음으로 취급.**
      - **통과 기준**: A·B급 통과. **시총 $50B 이하는 A급만 통과.** 재료 없으면(C급 포함) **|7%| 이상이라도 개별 제외** — 예외 없음(정말 핵심 특징주만). 지어내기 절대 금지.
      - **★ M7·메가캡은 게이트 면제(재료 없어도 후보 유지·거시 사유 서술 허용)하되 사유 조사는 필수**: 거시·섹터 사유도 **반드시 출처 있는 사실 기반**(예: "고용 쇼크 보도에 금리인하 기대 — 대형기술주 동반 강세"). 근거 없는 "시장 따라 상승"류 서술 금지. 끝내 못 찾으면 M7·메가캡에 한해서만 "이유 미확인" 표기 허용(날조 방지 최후 폴백). 단 **배치 단계에서 M7과 메가캡의 대우가 다름** — ⑤ 참조.
      - **감사 기록(브리핑에는 미게재)**: ⓐ재료가 없어 개별 제외된 |7%| 이상 종목 ⓑ등락률순 10위 밖으로 잘린 재료 보유 종목 ⓒ**거시 사유뿐이라 개별·묶음 어디에도 못 실린 메가캡**을 **루틴 실행 보고에 한 줄로 기록**(예: "제외: XYZ +9.2% 재료없음 / KO +3.5% 거시·단독") — 소리 없는 소멸 방지, 사후 검증 가능.
      - 제외 종목의 행선지: **업종 동반 이동의 일부면 묶음행으로 수용**(업종 동반이 그 종목의 이유 — 재료 없는 고등락률 종목도 묶음엔 정당하게 들어감) / 동반도 아니면 완전 제외.
      - **촉매 "명확" 판정 기준**: **본질 = ⓐ그 종목 자체의 구체적 사건 + ⓑ기사·공시 출처로 확인 가능 — 이 두 조건을 충족하면 아래 예시에 없는 유형이라도 명확으로 분류한다.** 예시: 실적·가이던스 발표, 투자의견/목표가 변경, M&A·인수설(보도 확인), 대형 계약·수주(취소 포함), 규제·소송·FDA 결과, 신제품/기술 발표, 지수 편입/제외, 증자/자사주, CEO 교체·내부자 매매, 사고·리콜·해킹, 감원·구조조정, 공매도 리포트, 파산·신용등급 변경, 경쟁사 사건의 직접 수혜/피해(해당 종목 특정 보도 시) 등. **"불명확"** = 종목 자체 사건이 아닌 막연한 서술 — "업황 기대감", "AI 수혜", "차익실현", "저가 매수" 등 근거 기사 없이 붙일 수 있는 말. 업종 동반 이동은 개별 촉매가 아니라 **묶음 사유**다.
    - **⑤ 3차 배치 (단순·재현 가능)**: 2차 통과 종목을 **등락률순(동률은 시총순)으로 정렬해 상위 10개**를 개별 특징주로 배치. 예외 규정:
      - **M7 = 무조건 개별 포함** (10위 밖이어도 — 시장 그 자체, 최대 +7행 감수)
      - **메가캡 = 조건부**: 10위 밖 메가캡은 **고유(종목 자체) 재료 A/B급 보유 시에만** 개별 포함(예: D램 담합 당사자 마이크론). **거시·섹터 사유뿐이면 개별 제외** → 묶음 성립 시 묶음행으로(% 보존), 아니면 섹터 파트·시장 해설이 커버 + 감사 기록 (거시 사유 메가캡 7개가 비슷한 서술로 도배되는 잡음 방지 — 2026-07-04 실측: 무조건 예외였다면 개별 34행).
      - 후보가 10개 미만이면 **억지로 채우지 않는다.**
    - **④ 4차 동반 묶음 (개별 배치 '이후' 잔여분만)**: **묶음 성립 조건 (2026-07-04 확정)** — 같은 '실제 업종'에서 ⓐ**[메가캡 |3%|+ 또는 비메가캡 |5%|+] 종목 5개 이상**(개별 게재분 포함 집계) **AND** ⓑ**묶음행에 실제로 남는(개별 제외한) |5%|+ 종목 3개 이상** — 두 조건을 모두 충족할 때만 묶음행을 만든다(급등·급락 동일). ⓑ는 verify.py가 기계 차단(묶음행에 5%+ 3개 미만이면 게시 불가). 메가캡 3% 혼합 문턱 덕에 완만한 섹터 로테이션(헬스케어 3%대 등)의 메가캡도 묶음으로 수치가 보존되고, ⓑ 앵커 덕에 밋밋한 3%대 일제 이동만으로는 묶음이 생기지 않는다. 라벨은 실제 업종명만(반도체·은행·방산·항공·에너지·헬스케어 등) — **"순환매"·"낙폭과대"·"테마"·"수혜" 같은 시장 현상·테마 라벨 금지(verify.py가 라벨 금지어 차단).** 조건 미달이면 묶음 없이 개별만. **묶음 멤버 = 티어 충족(±4%+) 업종 동반 종목 중 개별에 든 종목을 제외한 잔여 전부** — **재료가 없어 개별에서 제외된 고등락률(7%+ 포함) 종목도 묶음에 정당하게 들어간다**(업종 동반이 그 종목의 이유). 각 종목 %를 up/down 색과 함께 병기. **줄바꿈: 종목명과 % 사이는 반드시 `&nbsp;`(예: `테라다인&nbsp;<span class="down">−13.6%</span>`), 나열 중간 억지 `<br>` 금지, `<br>`는 종목 나열과 '업종 공통 이유' 사이 딱 하나.**
    - **⑥ 표시**: 급등은 상승률 큰 순, 급락은 하락폭 큰 순. **종목명은 반드시 한글**(티커 병기, 예: 샌디스크 (SNDK)). 태그·라벨 없이 종목명+등락률+촉매
    - 완결성 자가검증: qualified 목록과 페이지 대조, 큰 이동 누락 없는지 확인
    - 스크립트 실패 시(fallback): stockanalysis.com/markets/gainers·losers WebFetch로 대체
  - 발표된 지표: **out/events.json의 `released`에서 그 미국장 세션 날짜에 발표된 지표를 빠짐없이** (지표명·actual·forecast 값 그대로, 다른 날 금지). **포함 대상 = 등록부(events.py CANON)의 High+Medium만** — High: CPI·PCE·PPI·비농업고용·실업률·시간당임금·FOMC·연준의장발언·ISM제조업·ISM서비스업·소매판매·GDP / Medium: 신규실업수당·ADP·CB소비자신뢰·미시간심리·JOLTS·내구재·연준위원발언·주택착공/건축허가·기존주택판매·신규주택판매·산업생산. **Low(공장주문·도매재고·무역수지·모기지·원유재고·GDPNow·U-6·지역연은지수 등)는 제외.** released의 해당 세션 날짜 항목은 전부 표에(매 실행 일관성). 당일 발표가 없으면 표 대신 "· 당일 발표된 주요 지표 없음" 한 줄. **표 형식**(지표/결과/예상 3열). 결과 색: **예상 대비 시장에 긍정적 서프라이즈면 up(초록), 부정적이면 down(빨강), 부합·중립이면 무색** (예: 물가 예상 상회=빨강, 실업수당청구 예상 하회=초록)
  - 미국장 주요 일정(한국시간) — 섹션 제목도 이 이름 사용: **통합 표 1개, 3열(구분/내용/일시) — 비고 칸 없음**. 구분 셀 색 태그: 지표=`tag s-ind`(파랑)·연준=`tag s-fed`(보라)·실적=`tag s-earn`(주황)·IPO=`tag s-ipo`(초록)·기타=`tag s-etc`(회색). 날짜순 정렬, 오늘 일정은 일시에 "오늘(0/0)". **일시는 날짜·요일·시간 한 줄**(`7/14 (화) 21:30`, 시간 미정이면 날짜만). **연준 발언은 발언자 이름 표기**("연준 월러 발언"·"연준 의장 워시 발언" — events.json title 그대로). 내용 칸엔 짧은 꼬리표만 허용(예: "JP모건 등 대형은행 — 어닝 개막"). **표 목표 8~12행(비어닝시즌 기준). 단 1순위(지표·IPO)와 대상 실적(아래)이 많은 날은 12행을 넘겨서라도 전부 개별 게재 — 정보손실 최소화가 우선.** 잘리는 건 화이트리스트 밖 소형 실적·저우선 2순위뿐.
    - **★ 포함 우선순위 (반드시 이 순서로 채운다)**:
      - **1순위 = 무조건 포함(상한 없음·절대 누락 금지)** = **out/events.json의 `must_include` 전부** + 판단 기준 "이 일정이 시장(지수·환율·금리·유가·업종)을 움직일 수 있는가 → 그렇다면 목록에 없어도 포함". 핵심 지표(CPI·PCE·NFP·FOMC·GDP·소매판매·ISM·PPI), 정책·거시(관세/무역·중앙은행·OPEC+·국채입찰·쿼드위칭·부채한도), 대형·한국 IPO(SK하이닉스 ADR), 어닝 개막 대형은행, 대형 M&A·규제. **must_include는 12행을 넘겨서라도 전부 넣는다**(verify.py가 누락 시 게시 차단). FOMC·대형은행 개막·초대형 IPO는 1주 밖이어도 "예고" 허용.
      - **2순위 = 기본 포함(중요 정보로 취급)**: events.json `optional`(Medium 지표·대형 IPO 등). 1순위 다 넣은 뒤 2순위도 넣는다 — 표가 길어져도(정보손실 최소화 우선) 포함하고, 정말 넘칠 때만 그 안에서 최저우선(예: 중복성 연준위원 발언)만 컷.
    - **실적 대상 = 아래 셋을 개별 포함(상한 없음)**: ① **M7**(애플·MS·아마존·구글·메타·엔비디아·테슬라) ② **메가캡($200B+)** ③ **경기 가늠자 화이트리스트(시총 작아도 경기 신호라 포함)** — 소비=리바이스·나이키·룰루레몬·스타벅스·맥도날드, 물류·항공=페덱스·UPS·델타·유나이티드, 산업=캐터필러·디어, 반도체(한국 관심)=마이크론·ASML·TSMC, 미디어=넷플릭스 등. 해당 종목이 in-window 실적 발표 시 **개별 행**으로 (역할 설명이 필요하면 내용 칸에 짧은 꼬리표 — 예: "리바이스 (LEVI) — 소비 가늠자"). **실적 상한 없음 — 몰리는 날은 12행 넘겨도 전부 개별 게재(요약 '그 외 다수'로 뭉개지 말 것).** 화이트리스트 밖 소형·비주력 실적만 제외. (화이트리스트는 상황 따라 RUN.md에서 갱신.)
    - **누락 금지(엄수)**: **1순위·대상 실적(M7·메가캡·화이트리스트)·2순위를 행 수 아끼려고 빼지 말 것 — 정보손실 최소화가 행 수보다 우선.** 형식(색태그 등)을 바꿔 재작성할 때도 기존 자격 행 삭제 금지.
    - **특이사항 줄(표 아래 회색 `.sched`)**: 휴장으로 인한 순연·일정 변경·1주 밖 "예고"·내용 없는 구분("IPO: 오늘 대형 IPO 없음") 등 **변동·특수 상황만** 여기에 기재 (예: "· ISM 서비스업 PMI: 7/3 휴장으로 7/6로 순연"). 화제성 IPO의 상장 첫날 결과는 다음 날 특징주에도 반영.
  - **모바일 가독성(아이폰 기준 ~390px)**: 템플릿에 미디어쿼리 적용됨. 생성 시 텍스트 규칙 — 특징주 이유·키워드 설명은 **한 줄당 40자 이내**로 간결히, 뉴스 헤드라인은 35자 내외로 다듬기, '·'로 긴 나열을 만들지 않기(3개 이하 권장)

## 2) HTML 생성

- `template.html` 구조·CSS 그대로, 내용만 채워 `out/index.html` 로 저장.
- 색: 수치에만 (상승 초록 up / 하락 빨강 down). 소제목·강세/약세 단어는 회색.
- 한글 줄바꿈 `word-break:keep-all` (템플릿에 이미 적용).
- **키워드 설명은 키워드 아래 줄에** (kw-t 아래 kw-d, 인라인 " · 설명" 금지).
- **시장 지표 칩 6개, 2행×3열 그리드** (윗줄 10년물·달러인덱스·원/달러, 아랫줄 WTI·BTC·금 — 가로 스크롤 없음).
- **특징주 이유가 2개 이상이면 이유별로 `<br>` 줄바꿈** (긴 한 문장으로 어색하게 감싸지 말 것).

## 3) 최종 재검토(QA) — 게시 전 필수

**(A) 기계 검증 — `python3 verify.py` 를 반드시 실행한다.**
완성한 out/index.html의 지수 종가·등락률·특징주 등락률을 out/market.json·out/movers.json 원본과 자동 대조하고, 내부 정합성(등락폭↔등락률)·날짜·market.py 교차검증(야후 vs CNBC) 결과까지 확인한다. **"❌ 검증 실패"가 나오면 그 항목을 반드시 수정하고 다시 verify.py를 돌려 "✅ 검증 통과"가 될 때까지 반복**한다. 통과 전에는 게시 금지.

**(B) 사람 판단 검증 — 스크립트가 못 잡는 것:** 뉴스 5분야 채움(분야당 3~5건)/시간창/출처 실존/중복 없음 · 키워드 근거 · 특징주 재료의 사실 여부와 **A/B/C급 판정 적정성**(C급을 재료로 올리지 않았는지, $50B 이하에 B급을 통과시키지 않았는지) · **묶음 안에 재료 있는(개별 자격) 종목이 남아있지 않은지**(있으면 개별로 — 기계 판단 불가 영역) · M7·메가캡 거시 사유의 출처 존재 · **감사 기록**(재료 없어 제외한 7%+·10위 밖 잘린 재료 보유 종목을 실행 보고에 기재했는지) · 날조 0. 문제 있으면 재수집·수정.

## 4) 게시·발송 — `./publish.sh` 로만 (수동 git push·수동 카카오 전송 금지)

`out/index.html`(+`out/summary.txt` 카드용 요약 200자)을 만든 뒤 **반드시 `./publish.sh` 하나로** 게시·발송한다. publish.sh가 순서대로:
1. **[게이트] `python3 verify.py`** — 실패(exit 1) 시 게시·발송을 **기계적으로 중단**. 지적 항목 수정 후 다시 ./publish.sh, "✅ 검증 통과"까지 반복. 통과 못 하면 발송하지 않는다(잘못된 브리핑보다 미발송이 낫다).
2. **GitHub 게시** — index.html 교체 + `archive/YYYY-MM-DD.html`(KST) 추가 → main push → GitHub Pages가 1~2분 내 `$SITE_URL` 갱신.
3. **카카오 발송** — refresh_token으로 access_token 갱신 → `talk/memo/send`(커스텀 템플릿 **134931**, `template_args={"DATE":"M/D","SUMMARY":summary.txt,"WDATE":"YYYY-MM-DD"}`). `WDATE`는 그날 아카이브 영구링크용(카드가 항상 그날 자료를 가리킴). 성공 = `{"result_code":0}`.
- 응답에 새 refresh_token이 오면 안내가 출력됨 → briefing-secrets/.env 갱신 커밋.
- 비밀값은 .env(로컬) 또는 briefing-secrets/.env(클라우드, `set -a; source ...; set +a`로 export).

---

## 실패/예외 처리
- 데이터 소스 실패 → 재시도 후 대체 소스, 그래도 없으면 명확히 '미확인' 표기(날조 금지).
- 미국 휴장일 → 해당 파트 '휴장' 표기.
- Kakao `invalid_grant` → refresh_token 만료(약 2개월). 재발급 후 .env 갱신.
- 각 수치에 데이터 기준 시각 기록.
````

### 8.template.html

````html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>경제 브리핑</title>
<style>
:root{
  --bg:#f6f6f4; --card:#ffffff; --text:#1a1a19; --sub:#63625d; --muted:#9a9992;
  --border:#e6e5e1; --up:#0a7d33; --down:#d21c1c; --accent:#2f6fd0;
}
@media (prefers-color-scheme: dark){
  :root{ --bg:#181817; --card:#242422; --text:#f0efec; --sub:#a7a6a0; --muted:#77766f;
    --border:#38372f; --up:#3fb950; --down:#f5564a; --accent:#5a9bf0; }
}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",sans-serif;
  word-break:keep-all;-webkit-text-size-adjust:100%;}
.wrap{max-width:520px;margin:0 auto;padding:20px 16px 24px;}
a{color:inherit;text-decoration:none;}

.head{padding-bottom:14px;border-bottom:1px solid var(--border);margin-bottom:18px;}
.head-row{display:flex;justify-content:space-between;align-items:baseline;}
.head-title{font-size:20px;font-weight:600;}
.head-date{font-size:13px;color:var(--muted);}
.head-sub{margin:6px 0 0;font-size:12px;color:var(--muted);}

.card{background:var(--card);border:0.5px solid var(--border);border-radius:12px;padding:13px 15px;margin-bottom:12px;}
.sec{display:flex;align-items:center;gap:7px;margin-bottom:11px;}
.sec-title{font-size:13px;font-weight:600;color:var(--sub);}
.sec-note{font-size:11px;color:var(--muted);}

/* 뉴스 */
.field{margin-bottom:11px;}
.tag{display:inline-block;font-size:11px;padding:1px 8px;border-radius:20px;}
.t-pol{color:#d21c1c;background:rgba(210,28,28,.12);}
.t-eco{color:#0a7d33;background:rgba(10,125,51,.13);}
.t-wor{color:#2f6fd0;background:rgba(47,111,208,.13);}
.t-it{color:#7a4fd0;background:rgba(122,79,208,.14);}
.t-ind{color:#c1660f;background:rgba(193,102,15,.13);}
.s-ind{color:#2f6fd0;background:rgba(47,111,208,.13);}
.s-fed{color:#7a4fd0;background:rgba(122,79,208,.14);}
.s-earn{color:#c1660f;background:rgba(193,102,15,.13);}
.s-ipo{color:#0a7d33;background:rgba(10,125,51,.13);}
.s-etc{color:var(--muted);background:var(--bg);}
.heads{margin-top:5px;font-size:13.5px;line-height:1.85;}

/* 키워드 (설명은 키워드 아래 줄바꿈) */
.kw{display:flex;gap:10px;align-items:baseline;margin-bottom:9px;}
.kw-n{font-size:13px;font-weight:600;color:var(--sub);width:13px;flex-shrink:0;}
.kw-t{font-size:14px;font-weight:600;}
.kw-d{font-size:12px;color:var(--muted);margin-top:2px;line-height:1.5;}

/* 미국시장 */
.sum{margin:0 0 6px;font-size:13.5px;font-weight:600;line-height:1.5;}
.cmt{margin:0;font-size:12.5px;color:var(--sub);line-height:1.55;}
.divide{border-top:0.5px solid var(--border);margin:11px 0;}
.idx-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
.idx{background:var(--bg);border:0.5px solid var(--border);border-radius:10px;padding:10px 12px;}
.idx-name{font-size:12px;color:var(--sub);margin-bottom:3px;}
.idx-val{font-size:17px;font-weight:600;}
.idx-chg{font-size:12px;font-weight:600;margin-top:3px;white-space:nowrap;}
.up{color:var(--up);} .down{color:var(--down);}
.lbl{font-size:11px;color:var(--muted);margin-bottom:5px;}
.chips{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;}
.chip{font-size:11px;white-space:nowrap;text-align:center;background:var(--bg);border:0.5px solid var(--border);padding:3px 4px;border-radius:20px;}
.t-strong{color:#0a7d33;background:rgba(10,125,51,.13);}
.t-weak{color:#d21c1c;background:rgba(210,28,28,.12);}
.sector-names{margin-top:5px;font-size:13.5px;line-height:1.6;}
.sector-note{font-size:12px;color:var(--muted);margin-top:2px;line-height:1.5;}
.mv{margin-bottom:9px;}
.mv-h{display:flex;align-items:baseline;gap:8px;}
.mv-n{font-size:14px;font-weight:600;}
.mv-p{font-size:13px;font-weight:600;}
.mv-r{font-size:12px;color:var(--sub);line-height:1.5;}
.sched{font-size:12.5px;color:var(--sub);line-height:1.75;}
.tbl{width:100%;border-collapse:collapse;font-size:12.5px;}
.tbl th{text-align:left;font-size:11px;color:var(--muted);font-weight:600;padding:2px 8px 6px 0;border-bottom:0.5px solid var(--border);}
.tbl td{padding:7px 8px 7px 0;border-bottom:0.5px solid var(--border);}
.tbl tr:last-child td{border-bottom:none;}
.tbl .num{font-weight:600;}
.foot{text-align:center;font-size:11px;color:var(--muted);margin-top:14px;}
@media (max-width:430px){
  .wrap{padding:16px 12px 20px;}
  .heads{font-size:13px;}
  .idx-val{font-size:15px;}
  .idx-chg{font-size:10.5px;}
  .tbl{font-size:11px;}
  .tbl td{padding:6px 6px 6px 0;}
  .mv-r{font-size:11.5px;}
  .cmt{font-size:12px;}
  .sum{font-size:13px;}
  .sched{font-size:12px;}
  .kw-d{font-size:11.5px;}
}
</style>
</head>
<body>
<div class="wrap">

  <!-- ===== 헤더 (매일: 날짜) ===== -->
  <div class="head">
    <div class="head-row">
      <span class="head-title">경제 브리핑</span>
      <span class="head-date">2026.07.02 (목)</span>
    </div>
    <p class="head-sub">전일 15:20 ~ 당일 06:30 자료를 바탕으로 제작되었습니다.</p>
  </div>

  <!-- ===== 주요 뉴스 (매일: 5개 분야, 헤드라인 href=원문) ===== -->
  <div class="card">
    <div class="sec"><span class="sec-title">주요 뉴스</span></div>
    <div class="field"><span class="tag t-pol">정치</span>
      <div class="heads">
        · <a href="#">헤드라인 1</a><br>
        · <a href="#">헤드라인 2</a>
      </div>
    </div>
    <div class="field"><span class="tag t-eco">경제</span>
      <div class="heads">
        · <a href="#">헤드라인 1</a><br>
        · <a href="#">헤드라인 2</a>
      </div>
    </div>
    <div class="field"><span class="tag t-wor">세계</span>
      <div class="heads">
        · <a href="#">헤드라인 1</a><br>
        · <a href="#">헤드라인 2</a>
      </div>
    </div>
    <div class="field"><span class="tag t-it">IT</span>
      <div class="heads">
        · <a href="#">헤드라인 1</a><br>
        · <a href="#">헤드라인 2</a>
      </div>
    </div>
    <div class="field" style="margin-bottom:0;"><span class="tag t-ind">산업</span>
      <div class="heads">
        · <a href="#">헤드라인 1</a><br>
        · <a href="#">헤드라인 2</a>
      </div>
    </div>
  </div>

  <!-- ===== 핫한 키워드 Top 3 (매일 / 설명은 키워드 아래 줄에) ===== -->
  <div class="card">
    <div class="sec"><span class="sec-title">핫한 키워드 Top 3</span></div>
    <div class="kw"><span class="kw-n">1</span><div><div class="kw-t">키워드</div><div class="kw-d">배경 설명</div></div></div>
    <div class="kw"><span class="kw-n">2</span><div><div class="kw-t">키워드</div><div class="kw-d">배경 설명</div></div></div>
    <div class="kw" style="margin-bottom:0;"><span class="kw-n">3</span><div><div class="kw-t">키워드</div><div class="kw-d">배경 설명</div></div></div>
  </div>

  <!-- ===== 전일 미국 시장 (매일) ===== -->
  <div class="card">
    <div class="sec"><span class="sec-title">미국 시장</span><span class="sec-note">전일 마감</span></div>
    <p class="sum">한 줄 요약.</p>
    <p class="cmt">2~3줄 원인 해설.</p>

    <div class="divide"></div>
    <div class="idx-grid">
      <div class="idx"><div class="idx-name">다우</div><div class="idx-val">0,000.00</div><div class="idx-chg up">▲ +0.00 (+0.00%)</div></div>
      <div class="idx"><div class="idx-name">나스닥</div><div class="idx-val">0,000.00</div><div class="idx-chg up">▲ +0.00 (+0.00%)</div></div>
      <div class="idx"><div class="idx-name">S&amp;P 500</div><div class="idx-val">0,000.00</div><div class="idx-chg up">▲ +0.00 (+0.00%)</div></div>
      <div class="idx"><div class="idx-name">필라델피아 반도체</div><div class="idx-val">0,000.00</div><div class="idx-chg up">▲ +0.00 (+0.00%)</div></div>
    </div>

    <div class="divide"></div>
    <div class="lbl">시장 지표</div>
    <!-- 6개 고정, 2행×3열 그리드(가로 스크롤 없음): 윗줄 10년물·달러인덱스·원/달러, 아랫줄 WTI·BTC·금 -->
    <div class="chips">
      <span class="chip">美10년물 0.00%</span><span class="chip">달러인덱스 000</span><span class="chip">원/달러 0,000</span>
      <span class="chip">WTI $00</span><span class="chip">BTC $00,000</span><span class="chip">금 $0,000</span>
    </div>

    <div class="divide"></div>
    <div class="lbl">섹터</div>
    <!-- 강세는 강한 순, 약세는 약한 순으로 나열. 이유 설명은 회색 노트(sector-note) -->
    <div class="field"><span class="tag t-strong">강세</span>
      <div class="sector-names">섹터1 · 섹터2 · 섹터3</div>
      <div class="sector-note">강했던 이유 한 줄 (40자 이내)</div>
    </div>
    <div class="field" style="margin-bottom:0;"><span class="tag t-weak">약세</span>
      <div class="sector-names">섹터1 · 섹터2 · 섹터3</div>
      <div class="sector-note">약했던 이유 한 줄 (40자 이내)</div>
    </div>

    <div class="divide"></div>
    <div class="lbl">특징주 · 급등</div>
    <!-- 종목명은 반드시 한글 (티커 병기). 급등은 상승률 큰 순, 급락은 하락폭 큰 순.
         이유는 한 줄당 40자 이내로 간결히, 2개 이상이면 <br> 줄바꿈.
         이유 못 찾으면(7%+만 유지) 급등 "상승 이유 미확인" / 급락 "하락 이유 미확인".
         업종 묶음은 아래처럼 별도 행으로, 각 종목 %를 색과 함께 병기.
         ★ 종목명과 % 사이에는 일반 공백이 아니라 &nbsp; 를 넣어 "종목명+%"가 줄바꿈으로 갈라지지 않게 한다(줄바꿈은 종목 사이 ' · '에서만 자동으로). 종목 나열 중간에 억지 <br>를 넣지 말고 자연스럽게 흐르게 두되, 종목 나열과 '공통 이유' 사이에만 <br> 하나:
         <div class="mv"><div class="mv-h"><span class="mv-n">그 외 ○○ 동반 하락</span></div>
           <div class="mv-r">종목A&nbsp;<span class="down">−0.0%</span> · 종목B&nbsp;<span class="down">−0.0%</span><br>업종 공통 이유</div></div> -->
    <div class="mv"><div class="mv-h"><span class="mv-n">종목명 (TICKER)</span><span class="mv-p up">+0.00%</span></div><div class="mv-r">이유 1<br>이유 2 (있을 때만)</div></div>
    <!-- 급등 최대 10개 반복 -->

    <div class="divide"></div>
    <div class="lbl">특징주 · 급락</div>
    <div class="mv"><div class="mv-h"><span class="mv-n">종목명 (TICKER)</span><span class="mv-p down">−0.00%</span></div><div class="mv-r">촉매(이유)</div></div>
    <!-- 급락 최대 10개 반복 (movers.json selected_down 순서) -->

    <div class="divide"></div>
    <div class="lbl">발표된 지표</div>
    <!-- ★ 브리핑이 다루는 미국장 세션 '당일'에 실제 발표된 지표만 넣는다(예: 7/2 세션 기준이면 7/2 발표분만). 다른 날 발표 지표 금지. 당일 발표가 없으면 이 표 대신 "· 당일 발표된 주요 지표 없음" 한 줄.
         표 형식. 결과 색: 시장에 부정적(예상 대비 악화)이면 down, 긍정적이면 up, 중립이면 색 없음 -->
    <table class="tbl">
      <tr><th>지표</th><th>결과</th><th>예상</th></tr>
      <tr><td>지표명 (월)</td><td class="num">0.0</td><td class="num">0.0</td></tr>
    </table>

    <div class="divide"></div>
    <div class="lbl">미국장 주요 일정 (한국시간)</div>
    <!-- 통합 표 1개(구분/내용/일시/비고): 지표·연준·실적·IPO 모두 행으로.
         범위: 오늘~1주일. 날짜순 정렬, 오늘 일정은 일시에 "오늘(0/0)" 표기.
         중요도 필터: 지표는 시장 영향 큰 것만·실적은 메가캡/화제 기업만, 최대 8행.
         예외: FOMC·대형은행 실적 개막·스페이스X급 IPO는 1주 밖이어도 1~2행 "예고" 허용.
         내용 없는 구분(예: IPO 없음)만 아래 텍스트 줄로. 대형 IPO·상장 첫날 데뷔 필수 포함 -->
    <table class="tbl" style="margin-bottom:8px;">
      <tr><th>구분</th><th>내용</th><th>일시</th></tr>
      <!-- 3열(비고 없음). 구분 색 태그: 지표=s-ind, 연준=s-fed, 실적=s-earn, IPO=s-ipo, 기타=s-etc.
           일시는 날짜·요일·시간을 한 줄로(예: 7/14 (화) 21:30), 시간 미정이면 날짜만.
           연준 발언은 반드시 발언자 이름 표기: "연준 월러 발언" / "연준 의장 워시 발언" (events.json title 그대로).
           내용 칸엔 짧은 꼬리표만 허용(예: "JP모건 등 대형은행 — 어닝 개막"). -->
      <tr><td><span class="tag s-ind">지표</span></td><td>지표명(월)</td><td>0/0 (요일) 00:00</td></tr>
      <tr><td><span class="tag s-fed">연준</span></td><td>연준 ○○ 발언</td><td>0/0 (요일) 00:00</td></tr>
      <tr><td><span class="tag s-earn">실적</span></td><td>기업명 (TICKER)</td><td>0/0 (요일)</td></tr>
      <tr><td><span class="tag s-ipo">IPO</span></td><td>기업명 상장</td><td>0/0 (요일)</td></tr>
    </table>
    <div class="sched">
      <!-- 특이사항 줄(회색): 휴장 순연·일정 변경·1주 밖 "예고"·내용 없는 구분 등 -->
      · 예: ISM 서비스업 PMI: 7/3 휴장으로 7/6로 순연<br>
      · 예: 대형은행 실적 개막(7/14~)은 다음 주 — 예고
    </div>
  </div>

  <div class="foot">경제 브리핑 · 매일 오전 7시</div>
</div>
</body>
</html>
````

### 8.market.py

````python
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

def cnbc_close(sym):
    """CNBC 2차 소스 종가 (교차검증용). 실패 시 None."""
    try:
        r = subprocess.run(["curl", "-s", "-m", "12", "-H", "User-Agent: Mozilla/5.0",
                            f"https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols={sym}&requestMethod=itv&noform=1&partnerId=2&output=json"],
                           capture_output=True, text=True, check=True)
        q = json.loads(r.stdout)["FormattedQuoteResult"]["FormattedQuote"][0]
        return float(str(q["last"]).replace(",", "").replace("%", ""))
    except Exception:
        return None
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

out = {"generated_kst": time.strftime("%Y-%m-%d %H:%M"), "indices": {}, "indicators": {}, "errors": [], "notes": []}

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
        yv = get(sym)[-1]
        cv = cnbc_close(csym)  # CNBC realtime (투자닷컴과 근접) = 1차
        if cv is None:
            chosen = yv  # CNBC 실패 → 야후 폴백
            out["notes"].append(f"{name} CNBC 실패 → 야후 {fmt(yv)} 사용, 투자닷컴 웹 재확인 권장")
        else:
            chosen = cv  # CNBC 채택
            if abs(cv - yv) > tol:
                out["notes"].append(f"{name} 야후 {fmt(yv)} vs CNBC {fmt(cv)} 차이 → CNBC 채택, 투자닷컴 웹 재확인 권장")
        out["indicators"][name] = fmt(chosen)
        time.sleep(0.1)
    except Exception as e:
        out["errors"].append(f"{name}({sym}): {e}")

os.makedirs("out", exist_ok=True)
json.dump(out, open("out/market.json", "w"), ensure_ascii=False, indent=1)
print(f"지수 {len(out['indices'])} / 지표 {len(out['indicators'])} (오류 {len(out['errors'])}) → out/market.json")
for n, d in out["indices"].items():
    print(f"  {n}: {d['close']:,} ({d['chg']:+,.2f}, {d['pct']:+.2f}%)")
print("  " + " · ".join(f"{n} {v}" for n, v in out["indicators"].items()))
for n in out["notes"]:
    print("  교차검증:", n)
for e in out["errors"]:
    print("  오류:", e)
````

### 8.movers.py

````python
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
import json, time, os, subprocess

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
````

### 8.events.py

````python
#!/usr/bin/env python3
"""미국 주요 일정·발표지표를 실제 캘린더에서 수집 → out/events.json  (모든 날짜·시각 = 한국시간 KST)
소스: Nasdaq 경제캘린더(날짜별) + Nasdaq IPO + events_manual.txt(수동, KST로 기입).
★ Nasdaq 날짜는 실측상 실제 ET 날짜보다 +1일 어긋남 → 매 실행 Forex Factory(공식 ET 날짜) 앵커와
  대조해 오프셋을 자동 캘리브레이션한 뒤 보정하고, ET→KST로 변환해 저장한다.
  (검증 앵커 5건: NFP·신규실업수당 실제7/2→Nasdaq7/3, ISM제조 7/1→7/2, ISM서비스 7/6→7/7, FOMC 7/8→7/9)

- must_include: 1순위(반드시 일정 표에 포함 — 누락 시 verify.py가 게시 차단)
- optional    : 2순위(자리 남으면)
- released    : 최근 발표 지표(date=미국 세션 ET 날짜, kst=한국시간) — 발표된 지표 표에 빠짐없이"""
import json, os, subprocess, datetime, collections

os.chdir(os.path.dirname(os.path.abspath(__file__)))
try:
    from zoneinfo import ZoneInfo
    ET, KSTZ = ZoneInfo("America/New_York"), ZoneInfo("Asia/Seoul")
except Exception:
    ET = KSTZ = None
KST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(KST)
today = now.date()

# 정규화: (id, 순위, [매치], [제외], 한글제목, [verify 키워드], FF제목(캘리브레이션용))
CANON = [
    ("CPI",     1, ["cpi", "consumer price index"], ["expectation", "cleveland", "nowcast"], "소비자물가지수(CPI)", ["CPI", "소비자물가"], "cpi m/m"),
    ("PCE",     1, ["pce"], ["nowcast"], "PCE 물가지수", ["PCE"], "core pce price index m/m"),
    ("PPI",     1, ["ppi", "producer price"], [], "생산자물가지수(PPI)", ["PPI", "생산자물가"], "ppi m/m"),
    ("NFP",     1, ["nonfarm", "non-farm", "employment change"], ["adp", "weekly", "trends"], "고용보고서(비농업)", ["고용", "NFP", "비농업"], "non-farm employment change"),
    ("UNRATE",  1, ["unemployment rate"], ["u6", "u-6", "underemployment"], "실업률", ["실업률"], "unemployment rate"),
    ("AHE",     1, ["average hourly earnings"], [], "시간당 평균임금", ["시간당", "임금"], "average hourly earnings m/m"),
    ("FOMC",    1, ["fomc", "federal funds", "fed interest rate", "interest rate decision"], ["member"], "FOMC", ["FOMC", "의사록", "연준", "금리"], "fomc meeting minutes"),
    ("FEDCHAIR",1, ["powell", "fed chair", "fed chairman"], [], "연준 의장 발언", ["연준", "의장"], "fed chairman warsh speaks"),
    ("ISM_MFG", 1, ["ism manufacturing pmi"], [], "ISM 제조업 PMI", ["ISM", "제조업"], "ism manufacturing pmi"),
    ("ISM_SVC", 1, ["ism non-manufacturing pmi", "ism services pmi"], [], "ISM 서비스업 PMI", ["ISM", "서비스업"], "ism services pmi"),
    ("RETAIL",  1, ["retail sales"], [], "소매판매", ["소매판매"], "core retail sales m/m"),
    ("GDP",     1, ["gdp"], ["gdpnow", "now"], "GDP", ["GDP", "성장률"], "advance gdp q/q"),
    ("JOBLESS", 2, ["initial jobless claims"], [], "신규 실업수당청구", ["실업수당", "신규 실업"], "unemployment claims"),
    ("ADP",     2, ["adp employment"], ["weekly"], "ADP 고용", ["ADP"], "adp non-farm employment change"),
    ("CONF",    2, ["consumer confidence", "cb consumer"], [], "소비자신뢰지수", ["소비자신뢰"], "cb consumer confidence"),
    ("MICH",    2, ["michigan"], [], "미시간 소비심리", ["미시간", "소비심리"], "prelim uom consumer sentiment"),
    ("JOLTS",   2, ["jolts"], [], "JOLTS 구인", ["JOLTS", "구인"], "jolts job openings"),
    ("DURABLE", 2, ["durable goods"], [], "내구재 주문", ["내구재"], "core durable goods orders m/m"),
    ("HOUSING", 2, ["housing starts", "building permits"], [], "주택착공·건축허가", ["주택착공", "건축허가"], "housing starts"),
    ("EXHOME",  2, ["existing home sales"], [], "기존주택판매", ["기존주택"], "existing home sales"),
    ("NEWHOME", 2, ["new home sales"], [], "신규주택판매", ["신규주택"], "new home sales"),
    ("INDPROD", 2, ["industrial production"], [], "산업생산", ["산업생산"], "industrial production m/m"),
    ("FEDSPK",  2, ["speaks"], ["chair", "powell", "chairman"], "연준 위원 발언", ["연준"], None),
]

# 연준 인사 영→한 (발언자 이름 표기용; 미등록은 영문 성 그대로)
FED_KO = {"powell": "파월", "warsh": "워시", "williams": "윌리엄스", "waller": "월러",
          "jefferson": "제퍼슨", "barr": "바", "bowman": "보먼", "cook": "쿡", "kugler": "쿠글러",
          "goolsbee": "굴스비", "musalem": "무살렘", "schmid": "슈미드", "logan": "로건",
          "kashkari": "카슈카리", "daly": "데일리", "bostic": "보스틱", "collins": "콜린스",
          "harker": "하커", "hammack": "해맥"}

def fed_name(event_name):
    """'Fed Waller Speaks' / 'FOMC Member Williams Speaks' → 한글 이름"""
    words = [w.strip(".,") for w in event_name.split()]
    for i, w in enumerate(words):
        if w.lower().startswith("speak") and i > 0:
            nm = words[i - 1]
            return FED_KO.get(nm.lower(), nm)
    return ""

def classify(name):
    t = name.lower()
    for cid, tier, inc, exc, ko, kws, ff in CANON:
        if any(s in t for s in inc) and not any(s in t for s in exc):
            return cid, tier, ko, kws
    return None

def curl_json(url, retries=3):
    """재시도 포함(클라우드에서 Nasdaq이 연속 호출 제한으로 간헐 실패한 사례 — 2026-07-04 CPI 누락 사고)"""
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

def clean(v):
    return str(v or "").replace("&nbsp;", "").strip()

def to_kst(et_day, hhmm):
    """ET 날짜+시각 → (KST 'YYYY-MM-DD', 'HH:MM'). 시각 없으면 ET 날짜 그대로(주간 이벤트는 날짜 동일)."""
    if not hhmm or ":" not in hhmm:
        return et_day.isoformat(), ""
    try:
        h, m = (int(x) for x in hhmm.split(":")[:2])
    except ValueError:
        return et_day.isoformat(), ""
    if ET:
        dt = datetime.datetime(et_day.year, et_day.month, et_day.day, h, m, tzinfo=ET).astimezone(KSTZ)
    else:  # zoneinfo 없을 때 EDT 고정 +13h
        dt = datetime.datetime(et_day.year, et_day.month, et_day.day, h, m) + datetime.timedelta(hours=13)
    return dt.date().isoformat(), dt.strftime("%H:%M")

out = {"generated_kst": now.strftime("%Y-%m-%d %H:%M"), "timezone": "KST(한국시간) — released.date만 미국 세션(ET) 날짜",
       "must_include": [], "optional": [], "released": [], "errors": []}

# 1) Nasdaq 원시 수집 (query 날짜 그대로, 이후 보정) — 호출 간격으로 제한 회피
import time as _time
raw = {}
for off in range(-3, 14):
    ds = (today + datetime.timedelta(days=off)).isoformat()
    _time.sleep(0.3)
    try:
        d = curl_json(f"https://api.nasdaq.com/api/calendar/economicevents?date={ds}")
    except Exception as ex:
        out["errors"].append(f"nasdaq econ {ds}: {str(ex)[:50]}")
        continue
    for r in (d.get("data") or {}).get("rows") or []:
        if "United States" not in str(r.get("country", "")):
            continue
        ename = str(r.get("eventName", ""))
        cl = classify(ename)
        if not cl:
            continue
        cid, tier, ko, kws = cl
        if cid in ("FEDSPK", "FEDCHAIR"):  # 발언자 이름 표기 + 발언자별 구분
            nm = fed_name(ename)
            if nm:
                ko = f"연준 의장 {nm} 발언" if cid == "FEDCHAIR" else f"연준 {nm} 발언"
                kws = ["연준", nm]
                cid = f"{cid}:{nm}"
        key = (ds, cid)
        actual = clean(r.get("actual"))
        rec = {"nasdaq_date": ds, "time_et": clean(r.get("gmt")), "cid": cid, "tier": tier,
               "title": ko, "keywords": kws}
        if actual:
            rec.update(actual=actual, forecast=clean(r.get("consensus")), previous=clean(r.get("previous")))
        def score(x):  # 중복 시 우선순위: 발표값 있음 > 예상치 있음
            return (("actual" in x), bool(x.get("forecast")))
        if key not in raw or score(rec) > score(raw[key]):
            raw[key] = rec

# 2) 캘리브레이션: Forex Factory(공식 ET 날짜) 앵커와 대조 → Nasdaq 날짜 오프셋 산출
offset = None
try:
    ff = curl_json("https://nfs.faireconomy.media/ff_calendar_thisweek.json")
    ffmap = {}
    for e in ff:
        if e.get("country") == "USD":
            ffmap[e.get("title", "").strip().lower()] = e.get("date", "")[:10]
    fftitle = {cid: t for cid, _, _, _, _, _, t in CANON if t}
    diffs = []
    for (ds, cid), rec in raw.items():
        t = fftitle.get(cid)
        if t and t in ffmap:
            d1 = datetime.date.fromisoformat(ds)
            d2 = datetime.date.fromisoformat(ffmap[t])
            if abs((d1 - d2).days) <= 2:  # 같은 이벤트로 볼 수 있는 범위만
                diffs.append((d1 - d2).days)
    if diffs:
        offset = collections.Counter(diffs).most_common(1)[0][0]
        out["calibration"] = f"FF 앵커 {len(diffs)}건 → Nasdaq 오프셋 {offset:+d}일 보정"
except Exception as ex:
    out["errors"].append(f"calibration: {str(ex)[:50]}")
if offset is None:
    offset = 1  # 실측 기본값: Nasdaq = 실제 ET + 1일 (2026-07-04 앵커 5건 검증)
    out["calibration"] = "FF 앵커 없음 → 실측 기본 오프셋 +1일 적용"

# 3) 보정·KST 변환·분류
for (ds, cid), rec in raw.items():
    et_day = datetime.date.fromisoformat(ds) - datetime.timedelta(days=offset)
    kst_date, kst_time = to_kst(et_day, rec["time_et"])
    tier1 = rec["tier"] == 1
    base = {"date": kst_date, "time": kst_time, "date_et": et_day.isoformat(),
            "title": rec["title"], "impact": "High" if tier1 else "Medium",
            "cat": "지표", "src": "nasdaq", "keywords": rec["keywords"]}
    if "actual" in rec and today - datetime.timedelta(days=3) <= et_day <= today:
        out["released"].append({**base, "date": et_day.isoformat(), "kst": f"{kst_date} {kst_time}",
                                "actual": rec["actual"], "forecast": rec.get("forecast", ""),
                                "previous": rec.get("previous", "")})
    d0 = datetime.date.fromisoformat(kst_date)
    if today <= d0 <= today + datetime.timedelta(days=(12 if tier1 else 7)):
        (out["must_include"] if tier1 else out["optional"]).append(base)

# 4) Nasdaq 대형 IPO($500M+) → optional
try:
    for mon in {today.strftime("%Y-%m"), (today + datetime.timedelta(days=12)).strftime("%Y-%m")}:
        d = curl_json(f"https://api.nasdaq.com/api/ipo/calendar?date={mon}")
        for r in ((d.get("data") or {}).get("upcoming") or {}).get("upcomingTable", {}).get("rows") or []:
            val = clean(r.get("dollarValueOfSharesOffered")).replace("$", "").replace(",", "")
            try:
                big = float(val) >= 500_000_000
            except ValueError:
                big = False
            if big and r.get("companyName"):
                nm = r["companyName"].strip()
                pd = clean(r.get("expectedPriceDate"))
                try:  # m/d/Y → ISO
                    mth, dy, yr = pd.split("/")
                    pd = f"{yr}-{int(mth):02d}-{int(dy):02d}"
                except (ValueError, AttributeError):
                    pass
                out["optional"].append({"date": pd, "time": "", "title": f"{nm} 상장",
                                        "impact": "IPO", "cat": "IPO", "src": "nasdaq", "keywords": [nm]})
except Exception as ex:
    out["errors"].append(f"nasdaq ipo: {str(ex)[:50]}")

# 5) 수동 목록(KST 기입): in-window(향후 12일)면 must_include
if os.path.exists("events_manual.txt"):
    for line in open("events_manual.txt", encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "|" not in line:
            continue
        p = [x.strip() for x in line.split("|")]
        try:
            d0 = datetime.date.fromisoformat(p[0])
        except (ValueError, IndexError):
            continue
        if len(p) < 3:
            continue
        kws = [k.strip() for k in p[3].split(",")] if len(p) > 3 and p[3] else [p[2]]
        if today <= d0 <= today + datetime.timedelta(days=12):
            out["must_include"].append({"date": p[0], "time": "", "title": p[2], "impact": "수동",
                                        "cat": p[1], "src": "manual", "keywords": kws,
                                        "note": p[4] if len(p) > 4 else ""})

# 6) 정적 폴백 병합 (events_static.json — 로컬에서 미리 생성한 1순위 일정, KST 보정 완료본):
#    클라우드에서 Nasdaq 일부 날짜 조회가 실패해도 CPI·FOMC 같은 핵심 일정이 비지 않게 보장.
if os.path.exists("events_static.json"):
    try:
        st = json.load(open("events_static.json"))
        have = {(e["date"], e["title"]) for e in out["must_include"]}
        filled = []
        for e in st.get("events", []):
            try:
                d0 = datetime.date.fromisoformat(e["date"])
            except (ValueError, KeyError):
                continue
            if today <= d0 <= today + datetime.timedelta(days=12) and (e["date"], e["title"]) not in have:
                out["must_include"].append(e)
                filled.append(f"{e['date']} {e['title']}")
        if filled:
            out["errors"].append(f"⚠ Nasdaq 실시간 조회에 빠진 1순위를 static으로 보충: {', '.join(filled)} — 시각은 static 기준, 웹으로 재확인 권장")
        gen = datetime.date.fromisoformat(st.get("generated", "2000-01-01"))
        static_fresh = (today - gen).days <= 14
        if not static_fresh:
            out["errors"].append(f"⚠ events_static.json 생성 {(today-gen).days}일 경과 — 로컬에서 재생성 필요")
        # 소스 노이즈 중재: Nasdaq이 같은 지표를 인접 날짜에 중복 게재하는 사례(실측: CPI가 7/14·7/15 양쪽) —
        # static(검증 스냅샷)이 신선하면 static 날짜와 어긋난 live 지표 항목(±4일 내)을 제거
        if static_fresh:
            st_dates = {}
            for e in st.get("events", []):
                st_dates.setdefault(e["title"], set()).add(e["date"])
            cleaned, dropped = [], []
            for e in out["must_include"]:
                t, d = e.get("title"), e.get("date")
                if e.get("cat") == "지표" and e.get("src") == "nasdaq" and t in st_dates and d not in st_dates[t]:
                    near = any(abs((datetime.date.fromisoformat(d) - datetime.date.fromisoformat(sd)).days) <= 4
                               for sd in st_dates[t])
                    if near:
                        dropped.append(f"{t} {d}")
                        continue
                cleaned.append(e)
            if dropped:
                out["must_include"] = cleaned
                out["errors"].append(f"⚠ 소스 중복날짜 정리(static 기준 채택): {', '.join(dropped)} 제거")
        # 완전 중복(같은 날짜·제목) 제거
        uniq, seen2 = [], set()
        for e in out["must_include"]:
            k = (e.get("date"), e.get("title"))
            if k not in seen2:
                seen2.add(k)
                uniq.append(e)
        out["must_include"] = uniq
    except Exception as ex:
        out["errors"].append(f"static merge: {str(ex)[:50]}")

# 7) 정적 캘린더 자동 재갱신: 라이브 조회가 전부 성공한 날은 static을 오늘 데이터로 재생성
#    (수동 2주 재생성 불필요 — publish.sh가 갱신본을 저장소에 함께 push해 다음 날 클론에 반영)
query_errs = [e for e in out["errors"] if e.startswith("nasdaq econ")]
if not query_errs:
    try:
        old = json.load(open("events_static.json")) if os.path.exists("events_static.json") else {"events": []}
        horizon = (today + datetime.timedelta(days=13)).isoformat()
        keep_far = [e for e in old.get("events", []) if e.get("date", "") > horizon]  # 창 밖(예: 3주 뒤 FOMC) 보존
        near = [{"date": e["date"], "time": e.get("time", ""), "title": e["title"], "impact": "High",
                 "cat": "지표", "src": "static", "keywords": e.get("keywords", [])}
                for e in out["must_include"] if e.get("src") in ("nasdaq", "static") and e.get("cat") == "지표"]
        seen3, evs = set(), []
        for e in near + keep_far:
            k = (e["date"], e["title"])
            if k not in seen3:
                seen3.add(k)
                evs.append(e)
        evs.sort(key=lambda x: (x["date"], x.get("time", "")))
        json.dump({"generated": str(today), "offset_used": offset, "coverage_days": 13,
                   "auto_refreshed": True, "events": evs},
                  open("events_static.json", "w"), ensure_ascii=False, indent=1)
        out["static_refresh"] = f"자동 갱신 완료 ({len(evs)}건)"
    except Exception as ex:
        out["errors"].append(f"static refresh: {str(ex)[:50]}")

for k in ("must_include", "optional", "released"):
    out[k].sort(key=lambda x: (x["date"], x.get("time", "")))

os.makedirs("out", exist_ok=True)
json.dump(out, open("out/events.json", "w"), ensure_ascii=False, indent=1)
print(f"must_include {len(out['must_include'])} / optional {len(out['optional'])} / released {len(out['released'])} (오류 {len(out['errors'])}) → out/events.json")
print(" ", out.get("calibration", ""))
print("  [반드시 포함 · 1순위 · 한국시간]")
for e in out["must_include"]:
    print(f"    {e['date']} {e.get('time','')} · {e['cat']} · {e['title']}")
print("  [발표된 지표 · date=미국 세션일]")
for e in out["released"]:
    print(f"    {e['date']} · {e['title']}: {e.get('actual','')} (예상 {e.get('forecast','')})")
for er in out["errors"]:
    print("  오류:", er)
````

### 8.verify.py

````python
#!/usr/bin/env python3
"""최종 검증기 — 생성된 out/index.html의 숫자가 원본 데이터와 일치하는지 기계적으로 대조.
모델의 전사 오류(숫자 잘못 옮김)·산술 오류·날짜 오류를 잡는다.
불일치가 있으면 목록 출력 + exit 1. 통과면 exit 0. 게시 전에 반드시 실행."""
import json, os, re, sys, datetime, html as _html

os.chdir(os.path.dirname(os.path.abspath(__file__)))
html = open("out/index.html", encoding="utf-8").read()
mk = json.load(open("out/market.json"))
mv = json.load(open("out/movers.json"))
issues = []

def num(s):
    return float(str(s).replace(",", "").replace("−", "-").replace("+", "").replace("%", "").strip())

# 1) 지수 카드: 이름/종가/등락률 대조
for m in re.finditer(r'idx-name">(.*?)</div>\s*<div class="idx-val">(.*?)</div>\s*<div class="idx-chg[^"]*">(.*?)</div>', html):
    name, val, chg = _html.unescape(m.group(1).strip()), m.group(2), m.group(3)
    ref = mk["indices"].get(name)
    if not ref:
        issues.append(f"[지수] '{name}' market.json에 없음 (이름 확인)")
        continue
    if abs(num(val) - ref["close"]) > max(1, ref["close"] * 0.0005):
        issues.append(f"[지수] {name} 종가 HTML {val} ≠ 원본 {ref['close']:,}")
    pm = re.search(r'\(([-+−][\d.]+)%\)', chg)
    if pm and abs(num(pm.group(1)) - ref["pct"]) > 0.06:
        issues.append(f"[지수] {name} 등락률 HTML {pm.group(1)}% ≠ 원본 {ref['pct']:+.2f}%")
    cm = re.search(r'([-+−][\d,]+\.?\d*)\s*\(', chg)
    if cm and pm:  # 내부 정합성: 등락폭/종가 ↔ 등락률
        close, ch = num(val), num(cm.group(1))
        if close - ch != 0:
            calc = ch / (close - ch) * 100
            if abs(calc - num(pm.group(1))) > 0.1:
                issues.append(f"[지수] {name} 내부 불일치: 등락폭 {cm.group(1)}·종가 {val} → {calc:+.2f}% 인데 표기 {pm.group(1)}%")

# 2) 특징주: (티커) + 등락률 → movers.json 대조
allmv = {r["symbol"]: r["pct"] for r in mv.get("all", [])}
for m in re.finditer(r'mv-n">[^<(]*\(([A-Z]{1,6})\)</span><span class="mv-p[^"]*">([-+−][\d.]+)%', html):
    tk, pct = m.group(1), num(m.group(2))
    if tk in allmv and abs(pct - allmv[tk]) > 0.15:
        issues.append(f"[특징주] {tk} 등락률 HTML {pct:+.2f}% ≠ 원본 {allmv[tk]:+.2f}%")

# 2b) 시장 지표 6종 칩: HTML 값 ↔ market.json 대조 (전사 오류 검출)
chips = re.findall(r'class="chip">([^<]+)</span>', html)
for name, val in mk.get("indicators", {}).items():
    hit = [c.strip() for c in chips if c.strip().startswith(name)]
    if not hit:
        issues.append(f"[지표] '{name}' 칩이 HTML에 없음")
        continue
    hv = hit[0][len(name):].strip()
    try:
        if abs(num(hv) - num(val)) > max(abs(num(val)) * 0.001, 0.005):
            issues.append(f"[지표] {name} HTML '{hv}' ≠ 원본 '{val}'")
    except Exception:
        if hv.replace(" ", "") != str(val).replace(" ", ""):
            issues.append(f"[지표] {name} HTML '{hv}' ≠ 원본 '{val}'")

# 3) 날짜: 헤더에 오늘 날짜(현지) 포함 여부
today = datetime.datetime.now()
ymd = f"{today.year}.{today.month:02d}.{today.day:02d}"
hm = re.search(r'head-date">(.*?)<', html)
if hm and ymd not in hm.group(1):
    issues.append(f"[날짜] 헤더 '{hm.group(1).strip()}' 에 오늘({ymd}) 없음")

# 4) market.py 자체 오류(교차검증 불일치·이상치) 전달
for e in mk.get("errors", []):
    issues.append(f"[market.py] {e}")

# 5) 주요 뉴스 날짜창: 링크 URL의 날짜 토큰이 창 밖(전일 이전)이면 구뉴스로 간주
#    창 = 전일 00:00 ~ 당일(관대). 전일보다 이전 날짜면 위반(예: 7/4 발행에 7/2·6/25 기사).
win_start = (today - datetime.timedelta(days=1)).date()
news_html = html.split("핫한 키워드")[0]  # 주요 뉴스 영역만
seen = set()
for m in re.finditer(r'href="([^"]+)"', news_html):
    url = m.group(1)
    dm = re.search(r'(?:^|[/A])(20\d{2})[/\-]?(\d{2})[/\-]?(\d{2})(?:\D|\d{2,}|$)', url)
    if not dm:
        continue
    try:
        d = datetime.date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
    except ValueError:
        continue
    if not (today.date() - datetime.timedelta(days=120) <= d <= today.date()):
        continue  # 날짜로 보기 어려운 토큰(먼 과거/미래)은 무시
    if d < win_start and url not in seen:
        seen.add(url)
        issues.append(f"[뉴스] 창 밖 구뉴스 의심({d}): {url[:70]} — 전일 15:20~발행 창 기사로 교체")

# 6) 특징주 묶음행: 종목명+% 결합(&nbsp;) 및 억지 <br> 검사
for m in re.finditer(r'그 외[^<]*동반[^<]*</span></div><div class="mv-r">(.*?)</div>', html):
    body = m.group(1)
    if re.search(r'[가-힣A-Za-z0-9] <span class="(?:up|down)">', body):
        issues.append("[특징주] 묶음행 종목명과 %가 &nbsp;로 결합되지 않음 — 줄바꿈이 종목명/%를 가름")
    if body.count("<br>") > 1:
        issues.append("[특징주] 묶음행에 <br> 과다 — 공통이유 앞 1개만 허용(종목 나열 중간 <br> 금지)")

# 7) 특징주 묶음 라벨 금지어: 묶음은 실제 업종명만 — 시장 현상·테마 라벨 차단.
#    (구 검사 "개별<10 & 묶음 7%+ 차단"은 2026-07-04 규칙 개편으로 폐기: 재료 없는 종목은
#     등락률이 높아도 개별 제외 → 묶음 잔류가 정당하므로. 재료 유무는 사람 QA 영역.)
BAN_LABELS = ["순환매", "낙폭과대", "테마", "수혜", "관련주", "동반 반등", "저가 매수"]
for m in re.finditer(r'mv-n">(그 외[^<]*동반[^<]*)</span>', html):
    label = m.group(1)
    hits = [b for b in BAN_LABELS if b in label]
    if hits:
        issues.append(f"[특징주] 묶음 라벨 '{label.strip()}'에 금지어({','.join(hits)}) — 실제 업종명(반도체·은행·방산 등)으로만 묶을 것")

# 7b) 묶음행 실속(앵커) 검사: 각 묶음행에는 |5%| 이상 종목이 3개 이상 있어야 함(성립 조건 ⓑ)
for m in re.finditer(r'mv-n">(그 외[^<]*동반[^<]*)</span></div><div class="mv-r">(.*?)</div>', html):
    label, body = m.group(1).strip(), m.group(2)
    pcts = [abs(num(x)) for x in re.findall(r'class="(?:up|down)">([+\-−][\d.]+)%', body)]
    big = sum(1 for p in pcts if p >= 5)
    if pcts and big < 3:
        issues.append(f"[특징주] 묶음 '{label}'의 |5%|+ 종목이 {big}개(<3) — 성립 조건 미달, 묶음 해체(멤버는 섹터 파트·감사기록으로) 또는 재구성")

# 8) 일정 1순위 누락 차단: events.json의 must_include가 미국장 주요 일정 표에 있는지(키워드 매칭)
try:
    ev = json.load(open("out/events.json"))
except Exception:
    ev = None
if ev:
    sm = re.search(r'미국장 주요 일정.*?</table>', html, re.S)
    sched = sm.group(0) if sm else html
    for e in ev.get("must_include", []):
        if not any(kw and kw in sched for kw in e.get("keywords", [])):
            issues.append(f"[일정] 1순위 '{e['title']}'({e['date']}) 누락 — 미국장 주요 일정에 반드시 포함(events.json)")

if issues:
    print(f"❌ 검증 실패 {len(issues)}건 — 수정 후 재검증:")
    for i in issues:
        print("  •", i)
    sys.exit(1)
print("✅ 검증 통과 — 지수·시장지표·특징주 수치가 원본과 일치, 날짜 정상")
````

### 8.publish.sh

````bash
#!/usr/bin/env bash
# 경제 브리핑 — 게시(GitHub) + 발송(카카오). out/index.html 을 만든 뒤 실행.
set -euo pipefail
cd "$(dirname "$0")"

# .env가 있으면 로드, 없으면 이미 export된 환경변수 사용(클라우드: briefing-secrets/.env를 미리 source)
[ -f .env ] && { set -a; source .env; set +a; }
: "${GH_PAT:?GH_PAT 필요}"; : "${GH_REPO:?GH_REPO 필요}"; : "${SITE_URL:?SITE_URL 필요}"
: "${KAKAO_REST_KEY:?}"; : "${KAKAO_CLIENT_SECRET:?}"; : "${KAKAO_REFRESH_TOKEN:?}"

HTML="out/index.html"
[ -f "$HTML" ] || { echo "ERROR: $HTML 없음 — 먼저 브리핑 생성"; exit 1; }
TODAY=$(TZ=Asia/Seoul date +%F)

# ★ 게시 게이트: verify.py 통과 못 하면 게시·발송을 기계적으로 중단(모델 성실성과 무관)
echo "[검증] verify.py..."
if ! python3 verify.py; then
  echo "❌ 검증 실패 → 게시·발송 중단. 위 항목을 수정하고 다시 실행하세요."
  exit 1
fi

echo "[1/2] GitHub 게시..."
TMP=$(mktemp -d)
git clone --depth 1 "https://${GH_PAT}@github.com/${GH_REPO}.git" "$TMP/repo" 2>/dev/null
cp "$HTML" "$TMP/repo/index.html"
mkdir -p "$TMP/repo/archive"
cp "$HTML" "$TMP/repo/archive/${TODAY}.html"
# events.py가 자동 갱신한 정적 캘린더를 함께 반영(다음 실행의 클론에 최신본 전달)
[ -f events_static.json ] && cp events_static.json "$TMP/repo/pipeline/events_static.json" 2>/dev/null || true
git -C "$TMP/repo" config user.email "briefing@bot"
git -C "$TMP/repo" config user.name "briefing-bot"
git -C "$TMP/repo" add -A
git -C "$TMP/repo" commit -m "briefing ${TODAY}" >/dev/null 2>&1 || echo "  (변경 없음)"
git -C "$TMP/repo" push >/dev/null 2>&1
rm -rf "$TMP"
echo "  게시 완료 → ${SITE_URL}"

echo "[2/2] 카카오 발송..."
RESP=$(curl -s -X POST "https://kauth.kakao.com/oauth/token" \
  -d "grant_type=refresh_token" -d "client_id=${KAKAO_REST_KEY}" \
  -d "client_secret=${KAKAO_CLIENT_SECRET}" -d "refresh_token=${KAKAO_REFRESH_TOKEN}")
ACCESS=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
NEWRT=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('refresh_token',''))")
# 새 refresh_token 자동 영속화: 카카오는 만료 1개월 전부터 갱신 호출 시 새 토큰을 주므로,
# 매일 실행 + 아래 자동 저장이 유지되는 한 토큰은 영구 슬라이딩 갱신됨(수동 재인증 불필요)
if [ -n "$NEWRT" ]; then
  for f in .env ../../briefing-secrets/.env ../briefing-secrets/.env ../../../briefing-secrets/.env; do
    if [ -f "$f" ] && grep -q "^KAKAO_REFRESH_TOKEN=" "$f"; then
      sed -i.bak "s|^KAKAO_REFRESH_TOKEN=.*|KAKAO_REFRESH_TOKEN=${NEWRT}|" "$f" && rm -f "$f.bak"
      echo "  ✓ 새 refresh_token 자동 저장: $f"
      d=$(dirname "$f")
      if [ -d "$d/.git" ]; then
        (cd "$d" && git add .env && git commit -m "chore: kakao refresh_token 자동 갱신" >/dev/null 2>&1 \
          && git push >/dev/null 2>&1 && echo "  ✓ briefing-secrets push 완료") \
          || echo "  ⚠ secrets push 실패 — 보고에 명시하고 수동 커밋 필요"
      fi
      break
    fi
  done
fi

MD=$(TZ=Asia/Seoul date +%-m/%-d)
SUMMARY=$(tr '\n' ' ' < out/summary.txt 2>/dev/null)
[ -z "$SUMMARY" ] && SUMMARY="오늘의 주요 뉴스와 미국 시장을 확인하세요."
TEMPLATE_ID="${KAKAO_TEMPLATE_ID:-134931}"
# WDATE=그날의 영구 아카이브 날짜(YYYY-MM-DD). 카카오 템플릿 버튼 링크를
# https://xeob.github.io/briefing/archive/#{WDATE}.html 로 두면 카드마다 그날 자료로 고정됨.
WDATE="$TODAY"
ARGS=$(MD="$MD" SUMMARY="$SUMMARY" WDATE="$WDATE" python3 -c 'import json,os;print(json.dumps({"DATE":os.environ["MD"],"SUMMARY":os.environ["SUMMARY"],"WDATE":os.environ["WDATE"]},ensure_ascii=False))')
OUT=$(curl -s -X POST "https://kapi.kakao.com/v2/api/talk/memo/send" \
  -H "Authorization: Bearer ${ACCESS}" -d "template_id=${TEMPLATE_ID}" --data-urlencode "template_args=${ARGS}")
echo "  응답: $OUT"
echo "완료."
````

### 8.gen_static.py

````python
#!/usr/bin/env python3
"""향후 45일 미국 1순위(tier-1) 경제 일정을 Nasdaq에서 수집해 events_static.json 생성 (KST 보정 포함).
클라우드에서 Nasdaq이 막혔을 때 events.py가 쓰는 폴백. 로컬(Mac)에서 주기적으로 재생성."""
import json, subprocess, datetime, time, sys

OFFSET = 1  # Nasdaq 날짜 = 실제 ET +1 (2026-07-04 FF 앵커 6건 실측)
try:
    from zoneinfo import ZoneInfo
    ET, KSTZ = ZoneInfo("America/New_York"), ZoneInfo("Asia/Seoul")
except Exception:
    ET = KSTZ = None

CANON = [
    ("CPI", ["cpi", "consumer price index"], ["expectation", "cleveland", "nowcast"], "소비자물가지수(CPI)", ["CPI", "소비자물가"]),
    ("PCE", ["pce"], ["nowcast"], "PCE 물가지수", ["PCE"]),
    ("PPI", ["ppi", "producer price"], [], "생산자물가지수(PPI)", ["PPI", "생산자물가"]),
    ("NFP", ["nonfarm", "non-farm", "employment change"], ["adp", "weekly", "trends"], "고용보고서(비농업)", ["고용", "NFP", "비농업"]),
    ("UNRATE", ["unemployment rate"], ["u6", "u-6", "underemployment"], "실업률", ["실업률"]),
    ("FOMC", ["fomc", "federal funds", "fed interest rate", "interest rate decision"], ["member"], "FOMC", ["FOMC", "의사록", "연준", "금리"]),
    ("ISM_MFG", ["ism manufacturing pmi"], [], "ISM 제조업 PMI", ["ISM", "제조업"]),
    ("ISM_SVC", ["ism non-manufacturing pmi", "ism services pmi"], [], "ISM 서비스업 PMI", ["ISM", "서비스업"]),
    ("RETAIL", ["retail sales"], [], "소매판매", ["소매판매"]),
    ("GDP", ["gdp"], ["gdpnow", "now"], "GDP", ["GDP", "성장률"]),
]

def classify(name):
    t = name.lower()
    for cid, inc, exc, ko, kws in CANON:
        if any(s in t for s in inc) and not any(s in t for s in exc):
            return cid, ko, kws
    return None

def to_kst(et_day, hhmm):
    if not hhmm or ":" not in hhmm:
        return et_day.isoformat(), ""
    try:
        h, m = (int(x) for x in hhmm.split(":")[:2])
    except ValueError:
        return et_day.isoformat(), ""
    if ET:
        dt = datetime.datetime(et_day.year, et_day.month, et_day.day, h, m, tzinfo=ET).astimezone(KSTZ)
    else:
        dt = datetime.datetime(et_day.year, et_day.month, et_day.day, h, m) + datetime.timedelta(hours=13)
    return dt.date().isoformat(), dt.strftime("%H:%M")

today = datetime.date.today()
seen, events, fails = {}, [], 0
for off in range(0, 46):
    ds = (today + datetime.timedelta(days=off)).isoformat()
    ok = False
    for attempt in range(3):
        try:
            r = subprocess.run(["curl", "-s", "-m", "12", "-H", "User-Agent: Mozilla/5.0",
                                "-H", "Accept: application/json",
                                f"https://api.nasdaq.com/api/calendar/economicevents?date={ds}"],
                               capture_output=True, text=True)
            d = json.loads(r.stdout)
            ok = True
            break
        except Exception:
            time.sleep(1 + attempt)
    if not ok:
        fails += 1
        continue
    for row in (d.get("data") or {}).get("rows") or []:
        if "United States" not in str(row.get("country", "")):
            continue
        cl = classify(str(row.get("eventName", "")))
        if not cl:
            continue
        cid, ko, kws = cl
        et_day = datetime.date.fromisoformat(ds) - datetime.timedelta(days=OFFSET)
        kd, kt = to_kst(et_day, str(row.get("gmt", "")).replace("&nbsp;", "").strip())
        key = (kd, cid)
        if key in seen:
            continue
        seen[key] = True
        events.append({"date": kd, "time": kt, "title": ko, "impact": "High", "cat": "지표",
                       "src": "static", "keywords": kws})
    time.sleep(0.35)

events.sort(key=lambda x: (x["date"], x["time"]))
out = {"generated": today.isoformat(), "offset_used": OFFSET, "coverage_days": 45, "events": events}
json.dump(out, open("/Users/xeob/Downloads/claude/briefing/events_static.json", "w"), ensure_ascii=False, indent=1)
print(f"1순위 {len(events)}건 (조회실패 {fails}일) → events_static.json")
for e in events:
    print(f"  {e['date']} {e['time']} {e['title']}")
````

### 8.events_manual.txt

````text
# 수동 중요 일정 — 미국 캘린더(Forex Factory·Nasdaq)가 놓치는 한국 관련·특수 이벤트를 여기에 추가.
# 형식:  YYYY-MM-DD | 구분(지표/연준/실적/IPO/기타) | 제목 | 매칭키워드(쉼표, 선택) | 비고(선택)
# 날짜가 오늘~7일 안이면 events.py가 must_include(반드시 일정에 포함)로 넣고, verify.py가 누락 시 게시를 막는다.
# 예시(실제 상장일 확정되면 날짜 수정):
2026-07-10 | IPO | SK하이닉스 ADR 나스닥 상장 | SK하이닉스,하이닉스,ADR | 나스닥·최대 45조
````

### 8.events_static.json

````json
{
 "generated": "2026-07-04",
 "offset_used": 1,
 "coverage_days": 13,
 "auto_refreshed": true,
 "events": [
  {
   "date": "2026-07-06",
   "time": "23:00",
   "title": "ISM 서비스업 PMI",
   "impact": "High",
   "cat": "지표",
   "src": "static",
   "keywords": [
    "ISM",
    "서비스업"
   ]
  },
  {
   "date": "2026-07-09",
   "time": "03:00",
   "title": "FOMC",
   "impact": "High",
   "cat": "지표",
   "src": "static",
   "keywords": [
    "FOMC",
    "의사록",
    "연준",
    "금리"
   ]
  },
  {
   "date": "2026-07-14",
   "time": "21:30",
   "title": "소비자물가지수(CPI)",
   "impact": "High",
   "cat": "지표",
   "src": "static",
   "keywords": [
    "CPI",
    "소비자물가"
   ]
  },
  {
   "date": "2026-07-15",
   "time": "21:30",
   "title": "생산자물가지수(PPI)",
   "impact": "High",
   "cat": "지표",
   "src": "static",
   "keywords": [
    "PPI",
    "생산자물가"
   ]
  },
  {
   "date": "2026-07-16",
   "time": "21:30",
   "title": "소매판매",
   "impact": "High",
   "cat": "지표",
   "src": "static",
   "keywords": [
    "소매판매"
   ]
  },
  {
   "date": "2026-07-30",
   "time": "03:00",
   "title": "FOMC",
   "impact": "High",
   "cat": "지표",
   "src": "static",
   "keywords": [
    "FOMC",
    "의사록",
    "연준",
    "금리"
   ]
  }
 ]
}
````

_부록 수록 시각: 2026-07-05 00:47 KST — 파일 변경 시 '복구 매뉴얼 갱신해줘'로 재수록_
