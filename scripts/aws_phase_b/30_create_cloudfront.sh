#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context

s3_website_domain="$(get_s3_website_domain)"
apprunner_service_url="$(get_apprunner_service_url)"

distribution_id_file="${RUNTIME_DIR}/distribution_id.txt"
distribution_domain_file="${RUNTIME_DIR}/distribution_domain.txt"

distribution_id=""
if [[ -f "${distribution_id_file}" ]]; then
  distribution_id="$(cat "${distribution_id_file}")"
  if ! aws cloudfront get-distribution --id "${distribution_id}" >/dev/null 2>&1; then
    distribution_id=""
  fi
fi

if [[ -z "${distribution_id}" ]]; then
  distribution_id="$(get_distribution_id_by_comment)"
fi

if [[ -n "${distribution_id}" ]]; then
  distribution_domain="$(get_distribution_domain "${distribution_id}")"
  echo "${distribution_id}" >"${distribution_id_file}"
  echo "${distribution_domain}" >"${distribution_domain_file}"
  log "Found existing CloudFront distribution."
  log "Distribution ID: ${distribution_id}"
  log "Distribution domain: https://${distribution_domain}"
  log "Step 30 complete."
  exit 0
fi

distribution_config_file="${RUNTIME_DIR}/cloudfront_distribution_config.json"
caller_reference="newsfeed-${AWS_ACCOUNT_ID}-$(date +%s)"

cat >"${distribution_config_file}" <<EOF
{
  "CallerReference": "${caller_reference}",
  "Comment": "${CLOUDFRONT_COMMENT}",
  "Enabled": true,
  "DefaultRootObject": "index.html",
  "Origins": {
    "Quantity": 2,
    "Items": [
      {
        "Id": "s3-website-origin",
        "DomainName": "${s3_website_domain}",
        "OriginPath": "",
        "CustomHeaders": {
          "Quantity": 0
        },
        "CustomOriginConfig": {
          "HTTPPort": 80,
          "HTTPSPort": 443,
          "OriginProtocolPolicy": "http-only",
          "OriginSslProtocols": {
            "Quantity": 1,
            "Items": ["TLSv1.2"]
          },
          "OriginReadTimeout": 30,
          "OriginKeepaliveTimeout": 5
        }
      },
      {
        "Id": "apprunner-origin",
        "DomainName": "${apprunner_service_url}",
        "OriginPath": "",
        "CustomHeaders": {
          "Quantity": 0
        },
        "CustomOriginConfig": {
          "HTTPPort": 80,
          "HTTPSPort": 443,
          "OriginProtocolPolicy": "https-only",
          "OriginSslProtocols": {
            "Quantity": 1,
            "Items": ["TLSv1.2"]
          },
          "OriginReadTimeout": 120,
          "OriginKeepaliveTimeout": 5
        }
      }
    ]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "s3-website-origin",
    "ViewerProtocolPolicy": "redirect-to-https",
    "AllowedMethods": {
      "Quantity": 2,
      "Items": ["GET", "HEAD"],
      "CachedMethods": {
        "Quantity": 2,
        "Items": ["GET", "HEAD"]
      }
    },
    "Compress": true,
    "ForwardedValues": {
      "QueryString": false,
      "Cookies": { "Forward": "none" },
      "Headers": {
        "Quantity": 0
      },
      "QueryStringCacheKeys": {
        "Quantity": 0
      }
    },
    "TrustedSigners": {
      "Enabled": false,
      "Quantity": 0
    },
    "MinTTL": 0
  },
  "CacheBehaviors": {
    "Quantity": 1,
    "Items": [
      {
        "PathPattern": "api/*",
        "TargetOriginId": "apprunner-origin",
        "ViewerProtocolPolicy": "redirect-to-https",
        "AllowedMethods": {
          "Quantity": 7,
          "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
          "CachedMethods": {
            "Quantity": 2,
            "Items": ["GET", "HEAD"]
          }
        },
        "Compress": true,
        "ForwardedValues": {
          "QueryString": true,
          "Cookies": { "Forward": "none" },
          "Headers": {
            "Quantity": 0
          },
          "QueryStringCacheKeys": {
            "Quantity": 0
          }
        },
        "TrustedSigners": {
          "Enabled": false,
          "Quantity": 0
        },
        "MinTTL": 0,
        "DefaultTTL": 0,
        "MaxTTL": 0
      }
    ]
  },
  "CustomErrorResponses": {
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
  },
  "PriceClass": "${CLOUDFRONT_PRICE_CLASS}",
  "ViewerCertificate": {
    "CloudFrontDefaultCertificate": true
  },
  "Restrictions": {
    "GeoRestriction": {
      "RestrictionType": "none",
      "Quantity": 0
    }
  },
  "HttpVersion": "http2",
  "IsIPV6Enabled": true
}
EOF

log "Creating CloudFront distribution..."
distribution_id="$(aws cloudfront create-distribution \
  --distribution-config "file://${distribution_config_file}" \
  --query 'Distribution.Id' \
  --output text)"

distribution_domain="$(get_distribution_domain "${distribution_id}")"

echo "${distribution_id}" >"${distribution_id_file}"
echo "${distribution_domain}" >"${distribution_domain_file}"

log "Created CloudFront distribution."
log "Distribution ID: ${distribution_id}"
log "Distribution domain: https://${distribution_domain}"
log "Step 30 complete."
