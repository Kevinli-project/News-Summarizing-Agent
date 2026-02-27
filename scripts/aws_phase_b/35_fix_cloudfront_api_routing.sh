#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context
require_cmd jq

distribution_id=""
if [[ -f "${RUNTIME_DIR}/distribution_id.txt" ]]; then
  distribution_id="$(cat "${RUNTIME_DIR}/distribution_id.txt")"
fi
if [[ -z "${distribution_id}" ]]; then
  distribution_id="$(get_distribution_id_by_comment)"
fi
[[ -n "${distribution_id}" ]] || fail "CloudFront distribution not found. Run 30_create_cloudfront.sh first."

s3_website_domain="$(get_s3_website_domain)"
apprunner_service_url="$(get_apprunner_service_url)"

log "Fetching current CloudFront distribution config..."
current_cfg_file="${RUNTIME_DIR}/cloudfront_get_distribution_config.json"
aws cloudfront get-distribution-config --id "${distribution_id}" >"${current_cfg_file}"

etag="$(jq -r '.ETag' "${current_cfg_file}")"
[[ -n "${etag}" && "${etag}" != "null" ]] || fail "Could not read CloudFront ETag."

updated_cfg_file="${RUNTIME_DIR}/cloudfront_updated_distribution_config.json"

jq \
  --arg s3_domain "${s3_website_domain}" \
  --arg api_domain "${apprunner_service_url}" \
  '
  .DistributionConfig as $dc
  | ($dc.CacheBehaviors.Items // []) as $existing_behaviors
  | ($existing_behaviors | map(select(.PathPattern == "/api/*" or .PathPattern == "api/*")) | .[0]) as $existing_api_behavior
  | (
      $existing_api_behavior
      // (
        $dc.DefaultCacheBehavior
        + {
            "PathPattern": "/api/*"
          }
      )
    ) as $api_behavior_template
  | $api_behavior_template as $api_behavior
  | .DistributionConfig.Origins.Items = (
      .DistributionConfig.Origins.Items
      | map(
          if .Id == "s3-website-origin" then
            .DomainName = $s3_domain
            | .OriginPath = ""
            | .CustomOriginConfig.HTTPPort = 80
            | .CustomOriginConfig.HTTPSPort = 443
            | .CustomOriginConfig.OriginProtocolPolicy = "http-only"
            | .CustomOriginConfig.OriginReadTimeout = 30
            | .CustomOriginConfig.OriginKeepaliveTimeout = 5
          elif .Id == "apprunner-origin" then
            .DomainName = $api_domain
            | .OriginPath = ""
            | .CustomOriginConfig.HTTPPort = 80
            | .CustomOriginConfig.HTTPSPort = 443
            | .CustomOriginConfig.OriginProtocolPolicy = "https-only"
            | .CustomOriginConfig.OriginReadTimeout = 120
            | .CustomOriginConfig.OriginKeepaliveTimeout = 5
          else
            .
          end
        )
    )
  | .DistributionConfig.DefaultRootObject = "index.html"
  | .DistributionConfig.DefaultCacheBehavior.TargetOriginId = "s3-website-origin"
  | .DistributionConfig.CacheBehaviors.Items = (
      ($existing_behaviors | map(select(.PathPattern != "api/*" and .PathPattern != "/api/*")))
      + [
          (
            $api_behavior
            | .PathPattern = "api/*"
            | .TargetOriginId = "apprunner-origin"
            | .ViewerProtocolPolicy = "redirect-to-https"
            | .Compress = true
            | .AllowedMethods = {
                "Quantity": 7,
                "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
                "CachedMethods": {
                  "Quantity": 2,
                  "Items": ["GET", "HEAD"]
                }
              }
            | .MinTTL = 0
            | .DefaultTTL = 0
            | .MaxTTL = 0
            | .ForwardedValues = {
                "QueryString": true,
                "Cookies": { "Forward": "none" },
                "Headers": {
                  "Quantity": 0
                },
                "QueryStringCacheKeys": {
                  "Quantity": 0
                }
              }
            | .TrustedSigners = {
                "Enabled": false,
                "Quantity": 0
              }
            | .SmoothStreaming = (.SmoothStreaming // false)
          )
        ]
    )
  | .DistributionConfig.CacheBehaviors.Quantity = (.DistributionConfig.CacheBehaviors.Items | length)
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
  ' "${current_cfg_file}" >"${updated_cfg_file}"

log "Updating CloudFront distribution with explicit /api/* behavior..."
aws cloudfront update-distribution \
  --id "${distribution_id}" \
  --if-match "${etag}" \
  --distribution-config "file://${updated_cfg_file}" >/dev/null

distribution_domain="$(get_distribution_domain "${distribution_id}")"
echo "${distribution_id}" >"${RUNTIME_DIR}/distribution_id.txt"
echo "${distribution_domain}" >"${RUNTIME_DIR}/distribution_domain.txt"

log "CloudFront update submitted."
log "Distribution ID: ${distribution_id}"
log "Distribution domain: https://${distribution_domain}"
log "Step 35 complete."
