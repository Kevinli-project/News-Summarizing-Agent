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

load_project_env() {
  local env_file="${PROJECT_ROOT}/.env"
  [[ -f "$env_file" ]] || fail "Missing ${env_file}. Create it from .env.example first."

  # shellcheck disable=SC1090
  set -a
  source "$env_file"
  set +a
}

validate_required_env() {
  local required=(OPENAI_API_KEY NEWS_API_KEY BRAVE_API_KEY)
  local key
  for key in "${required[@]}"; do
    [[ -n "${!key:-}" ]] || fail "Missing ${key} in ${PROJECT_ROOT}/.env"
  done
}

init_context() {
  require_cmd aws
  require_cmd npm
  require_cmd curl

  load_project_env
  validate_required_env

  AWS_REGION="${AWS_REGION:-${DEFAULT_AWS_REGION:-$(aws configure get region || true)}}"
  [[ -n "$AWS_REGION" ]] || fail "AWS region is empty. Run: aws configure"

  AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
  [[ -n "$AWS_ACCOUNT_ID" && "$AWS_ACCOUNT_ID" != "None" ]] || fail "Could not read AWS account ID."

  APP_RUNNER_SERVICE_NAME="${APP_RUNNER_SERVICE_NAME:-newsfeed-api}"
  FRONTEND_DIR="${FRONTEND_DIR:-${PROJECT_ROOT}/frontend}"
  FRONTEND_OUT_DIR="${FRONTEND_OUT_DIR:-${FRONTEND_DIR}/out}"
  S3_BUCKET_NAME="${S3_BUCKET_NAME:-newsfeed-frontend-${AWS_ACCOUNT_ID}-${AWS_REGION}}"
  CLOUDFRONT_COMMENT="${CLOUDFRONT_COMMENT:-newsfeed-frontend-${AWS_ACCOUNT_ID}}"
  CLOUDFRONT_PRICE_CLASS="${CLOUDFRONT_PRICE_CLASS:-PriceClass_100}"

  mkdir -p "$RUNTIME_DIR"

  export SCRIPT_DIR PROJECT_ROOT RUNTIME_DIR
  export AWS_REGION AWS_ACCOUNT_ID
  export APP_RUNNER_SERVICE_NAME
  export FRONTEND_DIR FRONTEND_OUT_DIR
  export S3_BUCKET_NAME CLOUDFRONT_COMMENT CLOUDFRONT_PRICE_CLASS
}

print_context() {
  cat <<EOF
PROJECT_ROOT=${PROJECT_ROOT}
AWS_REGION=${AWS_REGION}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID}
APP_RUNNER_SERVICE_NAME=${APP_RUNNER_SERVICE_NAME}
FRONTEND_DIR=${FRONTEND_DIR}
FRONTEND_OUT_DIR=${FRONTEND_OUT_DIR}
S3_BUCKET_NAME=${S3_BUCKET_NAME}
CLOUDFRONT_COMMENT=${CLOUDFRONT_COMMENT}
CLOUDFRONT_PRICE_CLASS=${CLOUDFRONT_PRICE_CLASS}
EOF
}

write_context_file() {
  local context_file="${RUNTIME_DIR}/context.env"
  cat >"$context_file" <<EOF
PROJECT_ROOT=${PROJECT_ROOT}
AWS_REGION=${AWS_REGION}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID}
APP_RUNNER_SERVICE_NAME=${APP_RUNNER_SERVICE_NAME}
FRONTEND_DIR=${FRONTEND_DIR}
FRONTEND_OUT_DIR=${FRONTEND_OUT_DIR}
S3_BUCKET_NAME=${S3_BUCKET_NAME}
CLOUDFRONT_COMMENT=${CLOUDFRONT_COMMENT}
CLOUDFRONT_PRICE_CLASS=${CLOUDFRONT_PRICE_CLASS}
EOF
  chmod 600 "$context_file"
}

get_service_arn() {
  local arn
  arn="$(aws apprunner list-services \
    --region "$AWS_REGION" \
    --query "ServiceSummaryList[?ServiceName=='${APP_RUNNER_SERVICE_NAME}'] | [0].ServiceArn" \
    --output text)"
  if [[ "$arn" == "None" || -z "$arn" ]]; then
    printf ''
  else
    printf '%s' "$arn"
  fi
}

get_apprunner_service_url() {
  local service_arn
  service_arn="$(get_service_arn)"
  [[ -n "$service_arn" ]] || fail "App Runner service ${APP_RUNNER_SERVICE_NAME} not found. Run Phase A first."

  local service_url
  service_url="$(aws apprunner describe-service \
    --region "$AWS_REGION" \
    --service-arn "$service_arn" \
    --query 'Service.ServiceUrl' \
    --output text)"

  [[ -n "$service_url" && "$service_url" != "None" ]] || fail "Could not resolve App Runner service URL."
  printf '%s' "$service_url"
}

get_s3_website_domain() {
  printf '%s.s3-website-%s.amazonaws.com' "$S3_BUCKET_NAME" "$AWS_REGION"
}

wait_for_cloudfront_deployed() {
  local distribution_id="$1"
  local max_attempts="${2:-60}"
  local attempt status

  for ((attempt = 1; attempt <= max_attempts; attempt++)); do
    status="$(aws cloudfront get-distribution \
      --id "$distribution_id" \
      --query 'Distribution.Status' \
      --output text)"

    log "CloudFront status (attempt ${attempt}/${max_attempts}): ${status}"
    if [[ "$status" == "Deployed" ]]; then
      return 0
    fi
    sleep 20
  done

  fail "Timed out waiting for CloudFront distribution ${distribution_id} to reach Deployed."
}

get_distribution_id_by_comment() {
  local dist_id
  dist_id="$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?Comment=='${CLOUDFRONT_COMMENT}'] | [0].Id" \
    --output text 2>/dev/null || true)"
  if [[ -z "$dist_id" || "$dist_id" == "None" ]]; then
    printf ''
  else
    printf '%s' "$dist_id"
  fi
}

get_distribution_domain() {
  local distribution_id="$1"
  aws cloudfront get-distribution \
    --id "$distribution_id" \
    --query 'Distribution.DomainName' \
    --output text
}
