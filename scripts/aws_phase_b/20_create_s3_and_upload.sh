#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context

[[ -d "${FRONTEND_OUT_DIR}" ]] || fail "Missing ${FRONTEND_OUT_DIR}. Run 10_build_frontend.sh first."

log "Ensuring S3 bucket exists: ${S3_BUCKET_NAME}"
if aws s3api head-bucket --bucket "${S3_BUCKET_NAME}" >/dev/null 2>&1; then
  log "S3 bucket already exists."
else
  if [[ "${AWS_REGION}" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "${S3_BUCKET_NAME}" >/dev/null
  else
    aws s3api create-bucket \
      --bucket "${S3_BUCKET_NAME}" \
      --create-bucket-configuration "LocationConstraint=${AWS_REGION}" >/dev/null
  fi
  log "Created S3 bucket."
fi

log "Configuring static website hosting..."
aws s3api put-bucket-website \
  --bucket "${S3_BUCKET_NAME}" \
  --website-configuration '{"IndexDocument":{"Suffix":"index.html"},"ErrorDocument":{"Key":"index.html"}}'

log "Allowing public read access for website objects (bucket-level settings)..."
aws s3api put-public-access-block \
  --bucket "${S3_BUCKET_NAME}" \
  --public-access-block-configuration \
"BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

policy_file="${RUNTIME_DIR}/s3_public_read_policy.json"
cat >"${policy_file}" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowPublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::${S3_BUCKET_NAME}/*"
    }
  ]
}
EOF

aws s3api put-bucket-policy \
  --bucket "${S3_BUCKET_NAME}" \
  --policy "file://${policy_file}"

log "Uploading static files to S3..."
aws s3 sync "${FRONTEND_OUT_DIR}/" "s3://${S3_BUCKET_NAME}/" --delete

s3_website_domain="$(get_s3_website_domain)"
echo "${s3_website_domain}" >"${RUNTIME_DIR}/s3_website_domain.txt"

log "S3 upload complete."
log "Website endpoint (origin only): http://${s3_website_domain}"
log "Step 20 complete."
