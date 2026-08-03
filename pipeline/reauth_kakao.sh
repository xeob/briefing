#!/usr/bin/env bash
# 카카오 재인증 1회용 — refresh_token 재발급 → 로컬 .env + briefing-secrets(main) 반영까지 한 번에.
# 사용자가 직접 실행한다(카카오 로그인·동의는 사람만 가능).
#   실행:  cd ~/Downloads/claude/briefing && ./reauth_kakao.sh
#
# 선행 조건: PAT에 briefing-secrets Contents R/W 권한(없으면 저장 단계에서 알려준다).
set -uo pipefail
cd "$(dirname "$0")"
[ -f .env ] && { set -a; source .env; set +a; }
: "${KAKAO_REST_KEY:?.env에 KAKAO_REST_KEY 없음}"; : "${KAKAO_CLIENT_SECRET:?.env에 KAKAO_CLIENT_SECRET 없음}"
REDIRECT="https://localhost:3000/oauth"
SECREPO="${GH_SECRETS_REPO:-xeob/briefing-secrets}"

echo "────────────────────────────────────────────────"
echo " 카카오 재인증 (1) 아래 주소를 브라우저에 붙여넣고 로그인·동의"
echo "────────────────────────────────────────────────"
echo "https://kauth.kakao.com/oauth/authorize?client_id=${KAKAO_REST_KEY}&redirect_uri=${REDIRECT}&response_type=code&scope=talk_message"
echo
echo "  → 동의 후 'localhost 연결 실패' 페이지로 이동합니다(정상)."
echo "    그 주소창의  code=XXXXX  값만 복사하세요."
echo
read -r -p "붙여넣을 code: " CODE
[ -z "$CODE" ] && { echo "❌ code 없음"; exit 1; }

echo
echo "[1/3] 토큰 교환..."
RESP=$(curl -s -X POST "https://kauth.kakao.com/oauth/token" \
  -d grant_type=authorization_code -d client_id="${KAKAO_REST_KEY}" \
  -d client_secret="${KAKAO_CLIENT_SECRET}" -d redirect_uri="${REDIRECT}" -d code="${CODE}")
NEWRT=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('refresh_token',''))" 2>/dev/null)
ACCESS=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
if [ -z "$NEWRT" ]; then
  echo "❌ 실패: $(echo "$RESP" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('error',''),d.get('error_description',''))" 2>/dev/null)"
  echo "   code는 1회용·수명이 짧습니다. 위 주소부터 다시 받아 주세요."
  exit 1
fi
FP=$(printf '%s' "$NEWRT" | python3 -c "import hashlib,sys;print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest()[:10])")
echo "  ✓ 새 refresh_token 발급 [지문 ${FP}]"

echo "[2/3] 로컬 .env 반영..."
if grep -q "^KAKAO_REFRESH_TOKEN=" .env 2>/dev/null; then
  sed -i.bak "s|^KAKAO_REFRESH_TOKEN=.*|KAKAO_REFRESH_TOKEN=${NEWRT}|" .env && rm -f .env.bak
  echo "  ✓ .env 갱신"
else
  echo "KAKAO_REFRESH_TOKEN=${NEWRT}" >> .env; echo "  ✓ .env 추가"
fi

echo "[3/3] briefing-secrets(main) 반영 — 이게 돼야 클라우드 루틴이 씁니다..."
if [ -z "${GH_PAT:-}" ]; then echo "  ❌ GH_PAT 없음"; exit 1; fi
T=$(mktemp -d)
if ! git clone --depth 1 -q "https://x-access-token:${GH_PAT}@github.com/${SECREPO}.git" "$T/s" 2>/dev/null; then
  rm -rf "$T"
  echo "  ❌ ${SECREPO} 클론 실패 — PAT에 이 저장소 권한이 없습니다."
  echo "     GitHub → Settings → Developer settings → Fine-grained tokens → 해당 토큰"
  echo "     → Repository access 에 ${SECREPO} 추가, Permissions → Contents: Read and write"
  echo "     권한 부여 후 이 스크립트를 다시 실행하세요(위 code는 재발급 필요)."
  exit 1
fi
sed -i.bak "s|^KAKAO_REFRESH_TOKEN=.*|KAKAO_REFRESH_TOKEN=${NEWRT}|" "$T/s/.env" && rm -f "$T/s/.env.bak"
git -C "$T/s" config user.email "briefing@bot"; git -C "$T/s" config user.name "briefing-bot"
git -C "$T/s" add .env; git -C "$T/s" commit -q -m "chore: 카카오 재인증 (${FP})" 2>/dev/null
if git -C "$T/s" push -q origin HEAD:main 2>/dev/null \
   && git clone --depth 1 -q "https://x-access-token:${GH_PAT}@github.com/${SECREPO}.git" "$T/v" 2>/dev/null \
   && [ "$(grep '^KAKAO_REFRESH_TOKEN=' "$T/v/.env" | cut -d= -f2- | tr -d '\r\n' | python3 -c "import hashlib,sys;print(hashlib.sha256(sys.stdin.buffer.read().strip()).hexdigest()[:10])")" = "$FP" ]; then
  echo "  ✅ 원격 main 저장·검증 완료"
else
  echo "  ❌ push/검증 실패 — 권한(Contents: Read and write) 확인 필요"; rm -rf "$T"; exit 1
fi
rm -rf "$T"

echo
echo "🎉 재인증 완료. 이제 Claude에게 '브리핑 지금 실행해줘' 라고 하면 카톡이 정상 발송됩니다."
echo "   (이후 60일마다 자동 회전·저장되므로 재인증은 다시 필요 없습니다)"
