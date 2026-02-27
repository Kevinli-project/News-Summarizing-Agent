#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context

dist_arn=""
if [[ -f "${RUNTIME_DIR}/distribution_arn.txt" ]]; then
  dist_arn="$(cat "${RUNTIME_DIR}/distribution_arn.txt")"
fi
if [[ -z "${dist_arn}" ]]; then
  dist_arn="$(aws cloudfront get-distribution --id "${CLOUDFRONT_DISTRIBUTION_ID}" --query 'Distribution.ARN' --output text --no-cli-pager)"
fi

log "Backing up current S3 bucket policy (if any)..."
aws s3api get-bucket-policy \
  --bucket "${S3_BUCKET_NAME}" \
  --query 'Policy' \
  --output text \
  --no-cli-pager >"${RUNTIME_DIR}/bucket_policy_backup.txt" 2>/dev/null || true

log "Backing up current S3 website config (if any)..."
aws s3api get-bucket-website \
  --bucket "${S3_BUCKET_NAME}" \
  --output json \
  --no-cli-pager >"${RUNTIME_DIR}/bucket_website_backup.json" 2>/dev/null || true

policy_file="${RUNTIME_DIR}/bucket_policy_oac_private.json"
cat >"${policy_file}" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCloudFrontServicePrincipalReadOnly",
      "Effect": "Allow",
      "Principal": {
        "Service": "cloudfront.amazonaws.com"
      },
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::${S3_BUCKET_NAME}/*",
      "Condition": {
        "StringEquals": {
          "AWS:SourceArn": "${dist_arn}"
        }
      }
    }
  ]
}
EOF

log "Applying private bucket policy restricted to this CloudFront distribution..."
aws s3api put-bucket-policy \
  --bucket "${S3_BUCKET_NAME}" \
  --policy "file://${policy_file}" \
  --no-cli-pager

log "Enabling all S3 public access block settings..."
aws s3api put-public-access-block \
  --bucket "${S3_BUCKET_NAME}" \
  --public-access-block-configuration \
"BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
  --no-cli-pager

log "Disabling S3 static website hosting endpoint..."
aws s3api delete-bucket-website \
  --bucket "${S3_BUCKET_NAME}" \
  --no-cli-pager || true

log "Step 30 complete."
