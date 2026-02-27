#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context

DOCKER_PLATFORM="${DOCKER_PLATFORM:-linux/amd64}"
SMOKE_TEST_PORT="${SMOKE_TEST_PORT:-18000}"
SKIP_SMOKE_TEST="${SKIP_SMOKE_TEST:-0}"

log "Building Docker image ${ECR_REPO_NAME}:${IMAGE_TAG} (${DOCKER_PLATFORM})..."
docker build \
  --platform "${DOCKER_PLATFORM}" \
  -f "${PROJECT_ROOT}/backend/Dockerfile" \
  -t "${ECR_REPO_NAME}:${IMAGE_TAG}" \
  "${PROJECT_ROOT}"

if [[ "$SKIP_SMOKE_TEST" == "1" ]]; then
  log "Skipping smoke test because SKIP_SMOKE_TEST=1."
  log "Step 10 complete."
  exit 0
fi

container_name="newsfeed-local-smoke-$RANDOM"

cleanup() {
  docker rm -f "${container_name}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

log "Running smoke test container on http://127.0.0.1:${SMOKE_TEST_PORT} ..."
docker run -d \
  --platform "${DOCKER_PLATFORM}" \
  --name "${container_name}" \
  -p "${SMOKE_TEST_PORT}:8000" \
  -e OPENAI_API_KEY \
  -e NEWS_API_KEY \
  -e BRAVE_API_KEY \
  -e CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000" \
  "${ECR_REPO_NAME}:${IMAGE_TAG}" >/dev/null

healthy=0
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${SMOKE_TEST_PORT}/" >/tmp/newsfeed_smoke_health.txt 2>/dev/null; then
    healthy=1
    break
  fi

  # If container died early, show logs immediately for easier debugging.
  if ! docker ps --format '{{.Names}}' | grep -Fxq "${container_name}"; then
    log "Smoke test container exited before becoming healthy. Container logs:"
    docker logs "${container_name}" || true
    fail "Smoke test failed. Fix container startup error above and rerun."
  fi

  sleep 1
done

if [[ "${healthy}" != "1" ]]; then
  log "Smoke test health check timed out. Container logs:"
  docker logs "${container_name}" || true
  fail "Smoke test failed (timeout waiting for /)."
fi

sed -n '1,5p' /tmp/newsfeed_smoke_health.txt

log "Smoke test passed."
log "Step 10 complete."
