#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context

service_arn="$(get_service_arn)"
[[ -n "${service_arn}" ]] || fail "App Runner service ${APP_RUNNER_SERVICE_NAME} was not found. Run 40_deploy_apprunner.sh first."

wait_for_service_running "${service_arn}" "${MAX_WAIT_ATTEMPTS:-45}"

service_url="$(aws apprunner describe-service \
  --region "${AWS_REGION}" \
  --service-arn "${service_arn}" \
  --query 'Service.ServiceUrl' \
  --output text)"

echo "${service_url}" >"${RUNTIME_DIR}/service_url.txt"

log "Service URL: https://${service_url}"
log "Checking health endpoint..."
curl -fsS "https://${service_url}/" | sed -n '1,5p'

log "Checking /api/news?lang=en endpoint (can take ~20-30 seconds on cold cache)..."
curl -fsS --max-time 180 "https://${service_url}/api/news?lang=en" >/dev/null

log "Verification passed."
log "Step 50 complete."
