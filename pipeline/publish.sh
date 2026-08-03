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
# 토큰 갱신 + 회전 시 영구 저장(검증 포함)은 kakao_token.sh 단일 경로. 실패하면 여기서 중단된다.
# (조용히 넘기면 다음 날부터 invalid_grant로 전부 실패 — 2026-08-03 사고)
./kakao_token.sh
ACCESS=$(cat out/.kakao_access)

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
