#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context

oac_id="$(aws cloudfront list-origin-access-controls \
  --query "OriginAccessControlList.Items[?OriginAccessControlConfig.Name=='${OAC_NAME}'] | [0].Id" \
  --output text \
  --no-cli-pager 2>/dev/null || true)"

if [[ -n "${oac_id}" && "${oac_id}" != "None" ]]; then
  log "Reusing existing OAC: ${oac_id}"
else
  oac_cfg="${RUNTIME_DIR}/oac_config.json"
  cat >"${oac_cfg}" <<EOF
{
  "Name": "${OAC_NAME}",
  "Description": "OAC for private S3 access via CloudFront (${S3_BUCKET_NAME})",
  "SigningProtocol": "sigv4",
  "SigningBehavior": "always",
  "OriginAccessControlOriginType": "s3"
}
EOF

  log "Creating new OAC..."
  oac_id="$(aws cloudfront create-origin-access-control \
    --origin-access-control-config "file://${oac_cfg}" \
    --query 'OriginAccessControl.Id' \
    --output text \
    --no-cli-pager)"
fi

echo "${oac_id}" >"${RUNTIME_DIR}/oac_id.txt"
log "OAC ID: ${oac_id}"
log "Step 10 complete."
