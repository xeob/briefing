#!/usr/bin/env bash
# 실적 컨퍼런스콜 브리핑 — 08:30 KST 2차 발송. out/calls.html 을 만든 뒤 실행.
# 아침 브리핑(index.html)은 건드리지 않고 archive/<날짜>-calls.html 만 추가한다.
# 카카오는 기존 템플릿(134931)을 그대로 재사용 — WDATE에 "-calls"를 붙여 버튼 링크가 컨콜 페이지로 간다.
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] && { set -a; source .env; set +a; }
: "${GH_PAT:?GH_PAT 필요}"; : "${GH_REPO:?GH_REPO 필요}"; : "${SITE_URL:?SITE_URL 필요}"
: "${KAKAO_REST_KEY:?}"; : "${KAKAO_CLIENT_SECRET:?}"; : "${KAKAO_REFRESH_TOKEN:?}"

HTML="out/calls.html"
[ -f "$HTML" ] || { echo "ERROR: $HTML 없음 — 먼저 컨콜 브리핑 생성"; exit 1; }
TODAY=$(TZ=Asia/Seoul date +%F)

# 게이트: 내용 없는 껍데기 발송 방지(다룰 컨콜이 없으면 아예 발송하지 않는다)
if ! grep -q 'class="mv-n"' "$HTML"; then
  echo "❌ 컨콜 항목이 없음 → 발송 중단(빈 카드 금지). 다룰 실적이 없으면 실행 자체를 생략할 것."
  exit 1
fi
if ! grep -q "$(TZ=Asia/Seoul date +%Y.%m.%d)" "$HTML"; then
  echo "❌ 헤더 날짜가 오늘이 아님 → 재탕 의심, 발송 중단."
  exit 1
fi

echo "[1/2] GitHub 게시(아카이브만)..."
TMP=$(mktemp -d)
git clone --depth 1 "https://${GH_PAT}@github.com/${GH_REPO}.git" "$TMP/repo" 2>/dev/null
mkdir -p "$TMP/repo/archive"
cp "$HTML" "$TMP/repo/archive/${TODAY}-calls.html"
git -C "$TMP/repo" config user.email "briefing@bot"
git -C "$TMP/repo" config user.name "briefing-bot"
git -C "$TMP/repo" add -A
git -C "$TMP/repo" commit -m "calls ${TODAY}" >/dev/null 2>&1 || echo "  (변경 없음)"
git -C "$TMP/repo" push >/dev/null 2>&1
rm -rf "$TMP"
echo "  게시 완료 → ${SITE_URL}archive/${TODAY}-calls.html"

echo "[2/2] 카카오 발송..."
# 아침 브리핑과 동일한 단일 경로 사용(토큰 로직 중복 금지 — 두 벌이면 한쪽만 고쳐지는 사고가 난다)
./kakao_token.sh
ACCESS=$(cat out/.kakao_access)

MD=$(TZ=Asia/Seoul date +%-m/%-d)
SUMMARY=$(tr '\n' ' ' < out/calls_summary.txt 2>/dev/null)
[ -z "$SUMMARY" ] && SUMMARY="간밤 실적 컨퍼런스콜 주요 내용을 확인하세요."
TEMPLATE_ID="${KAKAO_TEMPLATE_ID:-134931}"
ARGS=$(MD="${MD} 실적 컨콜" SUMMARY="$SUMMARY" WDATE="${TODAY}-calls" python3 -c 'import json,os;print(json.dumps({"DATE":os.environ["MD"],"SUMMARY":os.environ["SUMMARY"],"WDATE":os.environ["WDATE"]},ensure_ascii=False))')
OUT=$(curl -s -X POST "https://kapi.kakao.com/v2/api/talk/memo/send" \
  -H "Authorization: Bearer ${ACCESS}" -d "template_id=${TEMPLATE_ID}" --data-urlencode "template_args=${ARGS}")
echo "  응답: $OUT"
echo "완료."
