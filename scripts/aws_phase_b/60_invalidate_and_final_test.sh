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

distribution_domain="$(get_distribution_domain "${distribution_id}")"
echo "${distribution_domain}" >"${RUNTIME_DIR}/distribution_domain.txt"

log "Creating CloudFront invalidation for /* ..."
invalidation_id="$(aws cloudfront create-invalidation \
  --distribution-id "${distribution_id}" \
  --paths '/*' \
  --query 'Invalidation.Id' \
  --output text)"

for attempt in $(seq 1 30); do
  inv_status="$(aws cloudfront get-invalidation \
    --distribution-id "${distribution_id}" \
    --id "${invalidation_id}" \
    --query 'Invalidation.Status' \
    --output text)"
  log "Invalidation status (attempt ${attempt}/30): ${inv_status}"
  if [[ "${inv_status}" == "Completed" ]]; then
    break
  fi
  sleep 10
done

log "Final frontend check..."
curl -fsS "https://${distribution_domain}/" | head -c 220
echo

log "Final API check through CloudFront..."
api_response="$(curl -fsS --max-time 180 "https://${distribution_domain}/api/news?lang=en")"
if ! echo "${api_response}" | jq -e . >/dev/null 2>&1; then
  fail "CloudFront /api/news returned non-JSON payload."
fi

log "Final deployment URL: https://${distribution_domain}"
log "Step 60 complete."
