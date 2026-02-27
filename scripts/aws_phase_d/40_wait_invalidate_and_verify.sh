#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context

wait_for_cloudfront_deployed 60

log "Creating CloudFront invalidation for /* ..."
invalidation_id="$(aws cloudfront create-invalidation \
  --distribution-id "${CLOUDFRONT_DISTRIBUTION_ID}" \
  --paths '/*' \
  --query 'Invalidation.Id' \
  --output text \
  --no-cli-pager)"

for attempt in $(seq 1 30); do
  inv_status="$(aws cloudfront get-invalidation \
    --distribution-id "${CLOUDFRONT_DISTRIBUTION_ID}" \
    --id "${invalidation_id}" \
    --query 'Invalidation.Status' \
    --output text \
    --no-cli-pager)"
  log "Invalidation status (attempt ${attempt}/30): ${inv_status}"
  [[ "${inv_status}" == "Completed" ]] && break
  sleep 10
done

log "Verifying frontend through CloudFront..."
html_sample="$(curl -fsS "https://${CLOUDFRONT_DOMAIN}/" | head -c 220)"
printf '%s\n' "${html_sample}"

log "Verifying API through CloudFront..."
api_response="$(curl -fsS --max-time 180 "https://${CLOUDFRONT_DOMAIN}/api/news?lang=en")"
if ! echo "${api_response}" | jq -e . >/dev/null 2>&1; then
  fail "CloudFront API check failed after OAC migration."
fi

s3_rest_domain="${S3_BUCKET_NAME}.s3.${AWS_REGION}.amazonaws.com"
direct_s3_code="$(curl -s -o /dev/null -w "%{http_code}" "https://${s3_rest_domain}/index.html")"
log "Direct S3 REST status code for /index.html: ${direct_s3_code}"
if [[ "${direct_s3_code}" == "200" ]]; then
  fail "Direct S3 access is still public (expected non-200)."
fi

log "Step 40 complete."
