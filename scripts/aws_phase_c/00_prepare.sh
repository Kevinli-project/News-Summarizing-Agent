#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context
write_context_file

service_arn="$(get_apprunner_service_arn)"
[[ -n "$service_arn" ]] || fail "App Runner service ${APP_RUNNER_SERVICE_NAME} not found. Complete Phase A/B first."

log "Checking CloudFront API endpoint..."
api_sample="$(curl -fsS --max-time 180 "${PREWARM_URL_EN}")"
if ! echo "${api_sample}" | jq -e . >/dev/null 2>&1; then
  fail "CloudFront API did not return JSON at ${PREWARM_URL_EN}"
fi

echo "${service_arn}" >"${RUNTIME_DIR}/apprunner_service_arn.txt"

log "Preparation checks passed."
log "Step 00 complete."
