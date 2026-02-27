#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context

oac_id=""
if [[ -f "${RUNTIME_DIR}/oac_id.txt" ]]; then
  oac_id="$(cat "${RUNTIME_DIR}/oac_id.txt")"
fi
[[ -n "${oac_id}" ]] || fail "Missing OAC ID. Run 10_create_or_get_oac.sh first."

cfg_raw="${RUNTIME_DIR}/cloudfront_get_distribution_config.json"
aws cloudfront get-distribution-config \
  --id "${CLOUDFRONT_DISTRIBUTION_ID}" \
  --output json \
  --no-cli-pager >"${cfg_raw}"

etag="$(jq -r '.ETag' "${cfg_raw}")"
[[ -n "${etag}" && "${etag}" != "null" ]] || fail "Could not read CloudFront ETag."

frontend_origin_id="$(jq -r '
  .DistributionConfig.Origins.Items
  | (map(select(.Id=="s3-website-origin"))[0]
    // map(select((.DomainName|test("s3-website")) or (.DomainName|test("\\.s3\\."))))[0]
    // map(select(.Id!="apprunner-origin"))[0]
    // empty
  ) | .Id // empty
' "${cfg_raw}")"

[[ -n "${frontend_origin_id}" ]] || fail "Could not identify frontend S3 origin in CloudFront distribution."

s3_rest_domain="${S3_BUCKET_NAME}.s3.${AWS_REGION}.amazonaws.com"
patched_cfg="${RUNTIME_DIR}/cloudfront_updated_for_oac.json"

jq \
  --arg front_id "${frontend_origin_id}" \
  --arg s3_rest "${s3_rest_domain}" \
  --arg oac_id "${oac_id}" \
  '
  .DistributionConfig.Origins.Items |=
    map(
      if .Id == $front_id then
        .DomainName = $s3_rest
        | .OriginPath = ""
        | .OriginAccessControlId = $oac_id
        | .S3OriginConfig = {"OriginAccessIdentity": ""}
        | del(.CustomOriginConfig)
      else
        .
      end
    )
  | .DistributionConfig.DefaultCacheBehavior.TargetOriginId = $front_id
  | .DistributionConfig.CustomErrorResponses = {
      "Quantity": 2,
      "Items": [
        {
          "ErrorCode": 403,
          "ResponsePagePath": "/index.html",
          "ResponseCode": "200",
          "ErrorCachingMinTTL": 0
        },
        {
          "ErrorCode": 404,
          "ResponsePagePath": "/index.html",
          "ResponseCode": "200",
          "ErrorCachingMinTTL": 0
        }
      ]
    }
  | .DistributionConfig
  ' "${cfg_raw}" >"${patched_cfg}"

log "Updating CloudFront distribution to use private S3 origin + OAC..."
aws cloudfront update-distribution \
  --id "${CLOUDFRONT_DISTRIBUTION_ID}" \
  --if-match "${etag}" \
  --distribution-config "file://${patched_cfg}" \
  --no-cli-pager >/dev/null

dist_arn="$(aws cloudfront get-distribution --id "${CLOUDFRONT_DISTRIBUTION_ID}" --query 'Distribution.ARN' --output text --no-cli-pager)"
echo "${dist_arn}" >"${RUNTIME_DIR}/distribution_arn.txt"
echo "${frontend_origin_id}" >"${RUNTIME_DIR}/frontend_origin_id.txt"
echo "${s3_rest_domain}" >"${RUNTIME_DIR}/s3_rest_domain.txt"

log "Submitted CloudFront update."
log "Distribution ARN: ${dist_arn}"
log "Frontend origin ID: ${frontend_origin_id}"
log "S3 REST origin domain: ${s3_rest_domain}"
log "Step 20 complete."
