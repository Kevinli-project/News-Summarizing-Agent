#!/usr/bin/env bash
set -euo pipefail

if [[ "${DEBUG:-0}" == "1" ]]; then
  set -x
fi

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

normalize_domain() {
  local value="$1"
  value="${value#http://}"
  value="${value#https://}"
  value="${value%%/}"
  printf '%s' "$value"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
FRONTEND_OUT_DIR="${FRONTEND_OUT_DIR:-${PROJECT_ROOT}/frontend/out}"

require_cmd aws
require_cmd jq
require_cmd curl

[[ -d "${FRONTEND_OUT_DIR}" ]] || fail "Missing ${FRONTEND_OUT_DIR}. Run scripts/aws_phase_b/10_build_frontend.sh first."

raw_domain="${CLOUDFRONT_DOMAIN:-}"
if [[ -z "${raw_domain}" && -f "${SCRIPT_DIR}/.runtime/distribution_domain.txt" ]]; then
  raw_domain="$(cat "${SCRIPT_DIR}/.runtime/distribution_domain.txt")"
fi
[[ -n "${raw_domain}" ]] || fail "Set CLOUDFRONT_DOMAIN (e.g. dvabg4443rdrf.cloudfront.net)."

CLOUDFRONT_DOMAIN="$(normalize_domain "${raw_domain}")"

log "Resolving CloudFront distribution for domain ${CLOUDFRONT_DOMAIN}..."
distribution_id="$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?DomainName=='${CLOUDFRONT_DOMAIN}'] | [0].Id" \
  --output text)"
[[ -n "${distribution_id}" && "${distribution_id}" != "None" ]] || \
  fail "Could not find CloudFront distribution with domain ${CLOUDFRONT_DOMAIN}."

cfg_json="$(aws cloudfront get-distribution-config --id "${distribution_id}")"
target_origin_id="$(echo "${cfg_json}" | jq -r '.DistributionConfig.DefaultCacheBehavior.TargetOriginId')"
[[ -n "${target_origin_id}" && "${target_origin_id}" != "null" ]] || fail "Could not read DefaultCacheBehavior.TargetOriginId."

front_origin_domain="$(echo "${cfg_json}" | jq -r --arg id "${target_origin_id}" '.DistributionConfig.Origins.Items[] | select(.Id==$id) | .DomainName' | head -n1)"
[[ -n "${front_origin_domain}" && "${front_origin_domain}" != "null" ]] || fail "Could not resolve default origin domain."

# Works for both S3 REST and S3 website origin forms.
s3_bucket="$(printf '%s' "${front_origin_domain}" | sed -E 's/\.s3[.-].*amazonaws\.com$//')"
[[ -n "${s3_bucket}" && "${s3_bucket}" != "${front_origin_domain}" ]] || \
  fail "Could not parse S3 bucket from origin domain: ${front_origin_domain}"

log "Syncing frontend assets to s3://${s3_bucket}/ ..."
aws s3 sync "${FRONTEND_OUT_DIR}/" "s3://${s3_bucket}/" --delete

log "Creating CloudFront invalidation for /* ..."
invalidation_id="$(aws cloudfront create-invalidation \
  --distribution-id "${distribution_id}" \
  --paths '/*' \
  --query 'Invalidation.Id' \
  --output text)"

aws cloudfront wait invalidation-completed \
  --distribution-id "${distribution_id}" \
  --id "${invalidation_id}"

log "Running quick checks..."
curl -fsS "https://${CLOUDFRONT_DOMAIN}/" | head -c 220
echo
api_response="$(curl -fsS --max-time 180 "https://${CLOUDFRONT_DOMAIN}/api/news?lang=en")"
echo "${api_response}" | jq -e . >/dev/null 2>&1 || fail "CloudFront /api/news did not return JSON."

echo "${distribution_id}" >"${SCRIPT_DIR}/.runtime/distribution_id.txt"
echo "${CLOUDFRONT_DOMAIN}" >"${SCRIPT_DIR}/.runtime/distribution_domain.txt"

log "Done."
log "Distribution ID: ${distribution_id}"
log "CloudFront domain: https://${CLOUDFRONT_DOMAIN}"
log "S3 bucket: ${s3_bucket}"
log "Invalidation ID: ${invalidation_id}"
