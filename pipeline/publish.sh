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
TODAY=$(date +%F)

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
[ -n "$NEWRT" ] && echo "  ※ 새 refresh_token 발급 — .env 갱신 권장"

MD=$(date +%-m/%-d)
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
