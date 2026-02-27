#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
require_cmd jq
print_context

distribution_domain=""
if [[ -f "${RUNTIME_DIR}/distribution_domain.txt" ]]; then
  distribution_domain="$(cat "${RUNTIME_DIR}/distribution_domain.txt")"
fi
if [[ -z "${distribution_domain}" ]]; then
  distribution_id="$(get_distribution_id_by_comment)"
  [[ -n "${distribution_id}" ]] || fail "CloudFront distribution not found. Run 30_create_cloudfront.sh first."
  distribution_domain="$(get_distribution_domain "${distribution_id}")"
fi

new_cors_origin="https://${distribution_domain}"
log "Updating App Runner CORS_ORIGINS to ${new_cors_origin}"

APP_RUNNER_CORS_ORIGINS="${new_cors_origin}" "${PROJECT_ROOT}/scripts/aws_phase_a/40_deploy_apprunner.sh"
"${PROJECT_ROOT}/scripts/aws_phase_a/50_wait_and_verify.sh"

log "Re-checking API through CloudFront after CORS update..."
api_response="$(curl -fsS --max-time 180 "https://${distribution_domain}/api/news?lang=en")"
if ! echo "${api_response}" | jq -e . >/dev/null 2>&1; then
  fail "CloudFront /api/news returned non-JSON payload after CORS update."
fi

log "CORS update complete."
log "Step 50 complete."
