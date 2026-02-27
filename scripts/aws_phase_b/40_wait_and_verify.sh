#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
require_cmd jq
print_context

distribution_id=""
if [[ -f "${RUNTIME_DIR}/distribution_id.txt" ]]; then
  distribution_id="$(cat "${RUNTIME_DIR}/distribution_id.txt")"
fi
if [[ -z "${distribution_id}" ]]; then
  distribution_id="$(get_distribution_id_by_comment)"
fi
[[ -n "${distribution_id}" ]] || fail "CloudFront distribution not found. Run 30_create_cloudfront.sh first."

wait_for_cloudfront_deployed "${distribution_id}" "${MAX_WAIT_ATTEMPTS:-60}"

distribution_domain="$(get_distribution_domain "${distribution_id}")"
echo "${distribution_domain}" >"${RUNTIME_DIR}/distribution_domain.txt"

log "CloudFront domain: https://${distribution_domain}"
log "Checking frontend root..."
curl -fsS "https://${distribution_domain}/" | head -c 220
echo

log "Checking API route through CloudFront..."
api_response="$(curl -fsS --max-time 180 "https://${distribution_domain}/api/news?lang=en")"
if ! echo "${api_response}" | jq -e . >/dev/null 2>&1; then
  fail "CloudFront /api/news returned non-JSON payload. API routing is likely going to S3/index.html."
fi

log "Verification passed."
log "Step 40 complete."
