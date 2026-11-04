#!/usr/bin/env bash
# Flutter Web 빌드 → frontend/build/web (nginx 가 서빙)
#
# API_BASE_URL 을 비워 두면 같은 도메인의 /api 를 쓴다 (nginx 가 Django 로 넘김).
# Firebase 로그인을 쓰려면 FIREBASE_* 값을 환경변수로 넘기거나
# DART_DEFINES_FILE=frontend/.dart-defines.local.json 처럼 파일을 지정한다.
#
#   ./infra/build-frontend.sh                    # 운영 (실제 API)
#   ARTLOG_DEMO=true ./infra/build-frontend.sh   # 서버 없이 미리보기
set -euo pipefail

cd "$(dirname "$0")/../frontend"

args=(
  --release
  "--dart-define=ARTLOG_DEMO=${ARTLOG_DEMO:-false}"
  "--dart-define=AUTH_PROVIDER=${AUTH_PROVIDER:-auto}"
  "--dart-define=API_BASE_URL=${API_BASE_URL:-}"
)
for key in FIREBASE_API_KEY FIREBASE_APP_ID FIREBASE_MESSAGING_SENDER_ID FIREBASE_PROJECT_ID FIREBASE_AUTH_DOMAIN; do
  if [ -n "${!key:-}" ]; then
    args+=("--dart-define=${key}=${!key}")
  fi
done
if [ -n "${DART_DEFINES_FILE:-}" ]; then
  args+=("--dart-define-from-file=$(cd .. && realpath "$DART_DEFINES_FILE")")
fi

flutter pub get
flutter build web "${args[@]}"
echo "빌드 완료: frontend/build/web"
