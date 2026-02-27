#!/usr/bin/env bash
set -euo pipefail

if [[ "${DEBUG:-0}" == "1" ]]; then
  set -x
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
RUNTIME_DIR="${SCRIPT_DIR}/.runtime"

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

get_phase_b_distribution_id() {
  local file="${PROJECT_ROOT}/scripts/aws_phase_b/.runtime/distribution_id.txt"
  if [[ -f "$file" ]]; then
    cat "$file"
  fi
}

get_phase_b_distribution_domain() {
  local file="${PROJECT_ROOT}/scripts/aws_phase_b/.runtime/distribution_domain.txt"
  if [[ -f "$file" ]]; then
    cat "$file"
  fi
}

init_context() {
  require_cmd aws
  require_cmd jq
  require_cmd curl

  export AWS_PAGER=""
  export AWS_CLI_AUTO_PROMPT=off

  AWS_REGION="${AWS_REGION:-${DEFAULT_AWS_REGION:-$(aws configure get region || true)}}"
  [[ -n "$AWS_REGION" ]] || fail "AWS region is empty. Run: aws configure"

  AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
  [[ -n "$AWS_ACCOUNT_ID" && "$AWS_ACCOUNT_ID" != "None" ]] || fail "Could not read AWS account ID."

  CLOUDFRONT_DISTRIBUTION_ID="${CLOUDFRONT_DISTRIBUTION_ID:-$(get_phase_b_distribution_id)}"
  [[ -n "$CLOUDFRONT_DISTRIBUTION_ID" ]] || fail "Missing CLOUDFRONT_DISTRIBUTION_ID and no Phase B runtime value found."

  CLOUDFRONT_DOMAIN="${CLOUDFRONT_DOMAIN:-$(get_phase_b_distribution_domain)}"
  [[ -n "$CLOUDFRONT_DOMAIN" ]] || fail "Missing CLOUDFRONT_DOMAIN and no Phase B runtime value found."
  CLOUDFRONT_DOMAIN="$(normalize_domain "$CLOUDFRONT_DOMAIN")"

  S3_BUCKET_NAME="${S3_BUCKET_NAME:-newsfeed-frontend-${AWS_ACCOUNT_ID}-${AWS_REGION}}"
  OAC_NAME="${OAC_NAME:-newsfeed-s3-oac-${AWS_ACCOUNT_ID}}"

  mkdir -p "$RUNTIME_DIR"

  export SCRIPT_DIR PROJECT_ROOT RUNTIME_DIR
  export AWS_REGION AWS_ACCOUNT_ID
  export CLOUDFRONT_DISTRIBUTION_ID CLOUDFRONT_DOMAIN
  export S3_BUCKET_NAME OAC_NAME
}

print_context() {
  cat <<EOF
PROJECT_ROOT=${PROJECT_ROOT}
AWS_REGION=${AWS_REGION}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID}
CLOUDFRONT_DISTRIBUTION_ID=${CLOUDFRONT_DISTRIBUTION_ID}
CLOUDFRONT_DOMAIN=${CLOUDFRONT_DOMAIN}
S3_BUCKET_NAME=${S3_BUCKET_NAME}
OAC_NAME=${OAC_NAME}
EOF
}

write_context_file() {
  local context_file="${RUNTIME_DIR}/context.env"
  cat >"${context_file}" <<EOF
PROJECT_ROOT=${PROJECT_ROOT}
AWS_REGION=${AWS_REGION}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID}
CLOUDFRONT_DISTRIBUTION_ID=${CLOUDFRONT_DISTRIBUTION_ID}
CLOUDFRONT_DOMAIN=${CLOUDFRONT_DOMAIN}
S3_BUCKET_NAME=${S3_BUCKET_NAME}
OAC_NAME=${OAC_NAME}
EOF
  chmod 600 "${context_file}"
}

wait_for_cloudfront_deployed() {
  local max_attempts="${1:-60}"
  local attempt status
  for ((attempt=1; attempt<=max_attempts; attempt++)); do
    status="$(aws cloudfront get-distribution --id "${CLOUDFRONT_DISTRIBUTION_ID}" --query 'Distribution.Status' --output text)"
    log "CloudFront status (attempt ${attempt}/${max_attempts}): ${status}"
    if [[ "${status}" == "Deployed" ]]; then
      return 0
    fi
    sleep 20
  done
  fail "Timed out waiting for CloudFront distribution to deploy."
}
