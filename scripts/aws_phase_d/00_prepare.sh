#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context
write_context_file

log "Validating CloudFront distribution exists..."
aws cloudfront get-distribution --id "${CLOUDFRONT_DISTRIBUTION_ID}" --no-cli-pager >/dev/null

log "Validating S3 bucket exists..."
aws s3api head-bucket --bucket "${S3_BUCKET_NAME}" --no-cli-pager >/dev/null

log "Checking current app health through CloudFront..."
html_sample="$(curl -fsS "https://${CLOUDFRONT_DOMAIN}/" | head -c 160)"
printf '%s\n' "${html_sample}"

api_sample="$(curl -fsS --max-time 180 "https://${CLOUDFRONT_DOMAIN}/api/news?lang=en")"
if ! echo "${api_sample}" | jq -e . >/dev/null 2>&1; then
  fail "CloudFront API check failed before migration."
fi

log "Step 00 complete."
