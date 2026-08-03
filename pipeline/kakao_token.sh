#!/usr/bin/env bash
# 카카오 액세스 토큰 확보 + 회전된 refresh_token '방탄' 영구 저장.
# publish.sh / publish_calls.sh 가 공통으로 호출한다(같은 취약 로직을 두 벌 두지 않기 위함).
#
# 성공: out/.kakao_access 에 access_token 기록 후 exit 0
# 실패: exit 1 (호출자는 게시·발송을 중단해야 한다)
#
# ★ 2026-08-03 사고 배경 — 반드시 유지할 것:
#   카카오 refresh_token은 60일 만료이고 '만료 1개월 이내'에 갱신하면 새 토큰을 발급하며
#   기존 토큰을 무효화한다(슬라이딩 갱신). 7/2 발급분의 회전 시점(8/1)에 새 토큰을
#   briefing-secrets 에 되돌려 저장하지 못해(PAT 권한 없음 + 클라우드 클론의 임시 브랜치)
#   다음 날부터 invalid_grant(KOE322)로 카톡 발송이 전부 실패했다.
#   → 저장은 'PAT로 main에 직접 push', 저장 후 '원격에서 다시 읽어 검증',
#     저장 실패 시 '그 순간 살아있는 access_token으로 즉시 경보 + 실패 종료'.
set -uo pipefail
cd "$(dirname "$0")"

[ -f .env ] && { set -a; source .env; set +a; }
: "${KAKAO_REST_KEY:?}"; : "${KAKAO_CLIENT_SECRET:?}"; : "${KAKAO_REFRESH_TOKEN:?}"
SECREPO="${GH_SECRETS_REPO:-xeob/briefing-secrets}"

fp() {  # 비밀값 노출 없이 동일성만 비교하기 위한 짧은 지문(stdin 사용 — 프로세스 목록에 안 남음)
  printf '%s' "$1" | python3 -c "import hashlib,sys;print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest()[:10])"
}

alert() {  # 아직 유효한 access_token으로 즉시 경보(토큰 값은 절대 싣지 않는다)
  local msg="$1" access="$2"
  [ -z "$access" ] && return 0
  curl -s -X POST "https://kapi.kakao.com/v2/api/talk/memo/default/send" \
    -H "Authorization: Bearer ${access}" \
    --data-urlencode "template_object={\"object_type\":\"text\",\"text\":\"⚠️ 경제 브리핑 시스템 알림\n\n${msg}\",\"link\":{\"web_url\":\"${SITE_URL:-https://xeob.github.io/briefing/}\"}}" \
    >/dev/null 2>&1 || true
}

echo "[카카오] 토큰 갱신..."
RESP=$(curl -s -X POST "https://kauth.kakao.com/oauth/token" \
  -d "grant_type=refresh_token" -d "client_id=${KAKAO_REST_KEY}" \
  -d "client_secret=${KAKAO_CLIENT_SECRET}" -d "refresh_token=${KAKAO_REFRESH_TOKEN}")

ACCESS=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
NEWRT=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('refresh_token',''))" 2>/dev/null)
RTLEFT=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('refresh_token_expires_in',''))" 2>/dev/null)

if [ -z "$ACCESS" ]; then
  ERR=$(echo "$RESP" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('error',''),d.get('error_code',''),d.get('error_description',''))" 2>/dev/null)
  echo "❌ 카카오 토큰 갱신 실패: ${ERR:-응답 파싱 불가}"
  echo "   → refresh_token 무효/만료(KOE322)면 재인증 필요: 복구 매뉴얼 §4.3-E"
  exit 1
fi

mkdir -p out
printf '%s' "$ACCESS" > out/.kakao_access
chmod 600 out/.kakao_access 2>/dev/null || true
[ -n "$RTLEFT" ] && echo "  refresh_token 잔여: $((RTLEFT/86400))일"

# 새 refresh_token이 오지 않았으면(만료 1개월 초과 남음) 기존 토큰이 계속 유효 — 저장할 것 없음
if [ -z "$NEWRT" ]; then
  echo "  ✓ access_token 확보 (회전 없음)"
  exit 0
fi

echo "  ★ 새 refresh_token 발급됨(회전) — 영구 저장 시작 [지문 $(fp "$NEWRT")]"
FP_NEW=$(fp "$NEWRT")
SAVED=0

# (a) 컨테이너 내부 .env 즉시 반영 — 같은 실행 안에서의 일관성
for f in .env ../../briefing-secrets/.env ../briefing-secrets/.env ../../../briefing-secrets/.env; do
  if [ -f "$f" ] && grep -q "^KAKAO_REFRESH_TOKEN=" "$f"; then
    sed -i.bak "s|^KAKAO_REFRESH_TOKEN=.*|KAKAO_REFRESH_TOKEN=${NEWRT}|" "$f" && rm -f "$f.bak"
    echo "  ✓ 로컬 반영: $f"
  fi
done

# (b) 영구 저장: PAT로 저장소를 직접 클론해 main에 push (클라우드 클론의 remote/브랜치에 의존하지 않음)
if [ -n "${GH_PAT:-}" ]; then
  T=$(mktemp -d)
  if git clone --depth 1 -q "https://x-access-token:${GH_PAT}@github.com/${SECREPO}.git" "$T/s" 2>/dev/null \
     && [ -f "$T/s/.env" ] && grep -q "^KAKAO_REFRESH_TOKEN=" "$T/s/.env"; then
    sed -i.bak "s|^KAKAO_REFRESH_TOKEN=.*|KAKAO_REFRESH_TOKEN=${NEWRT}|" "$T/s/.env" && rm -f "$T/s/.env.bak"
    git -C "$T/s" config user.email "briefing@bot"
    git -C "$T/s" config user.name "briefing-bot"
    git -C "$T/s" add .env
    git -C "$T/s" commit -q -m "chore: kakao refresh_token 자동 갱신 (${FP_NEW})" 2>/dev/null
    if git -C "$T/s" push -q origin HEAD:main 2>/dev/null; then
      # (c) 검증 — push 성공 코드를 믿지 않고 원격에서 다시 읽어 지문 대조
      if git clone --depth 1 -q "https://x-access-token:${GH_PAT}@github.com/${SECREPO}.git" "$T/v" 2>/dev/null; then
        REMOTE_RT=$(grep "^KAKAO_REFRESH_TOKEN=" "$T/v/.env" | cut -d= -f2- | tr -d '\r\n')
        [ "$(fp "$REMOTE_RT")" = "$FP_NEW" ] && SAVED=1
      fi
    fi
  fi
  rm -rf "$T"
else
  echo "  ⚠ GH_PAT 없음 — 영구 저장 불가"
fi

if [ "$SAVED" = "1" ]; then
  echo "  ✅ 영구 저장·검증 완료 (원격 main 지문 일치) — 다음 실행에 정상 인계"
  exit 0
fi

# (d) 저장 실패 = 내일부터 확실히 죽는다. 조용히 넘기지 않고 지금 경보 + 실패 종료.
echo "❌ 새 refresh_token을 저장소에 영구 저장하지 못했습니다."
echo "   이대로 두면 다음 실행부터 invalid_grant로 카톡이 전부 실패합니다."
echo "   확인: PAT에 ${SECREPO} 접근 권한(Contents R/W)이 있는지 — 복구 매뉴얼 §4.2"
alert "카카오 새 토큰 저장 실패. 조치 없으면 내일부터 브리핑 카톡이 발송되지 않습니다. PAT의 briefing-secrets 권한(Contents R/W)을 확인해 주세요." "$ACCESS"
exit 1
