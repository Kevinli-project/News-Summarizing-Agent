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

get_phase_b_domain() {
  local phase_b_domain_file="${PROJECT_ROOT}/scripts/aws_phase_b/.runtime/distribution_domain.txt"
  if [[ -f "${phase_b_domain_file}" ]]; then
    cat "${phase_b_domain_file}"
  fi
}

normalize_domain() {
  local value="$1"
  value="${value#http://}"
  value="${value#https://}"
  value="${value%%/}"
  printf '%s' "$value"
}

init_context() {
  require_cmd aws
  require_cmd jq
  require_cmd zip
  require_cmd curl

  # Prevent AWS CLI from opening an interactive pager (e.g., less) in scripts.
  export AWS_PAGER=""
  export AWS_CLI_AUTO_PROMPT=off

  load_project_env
  validate_required_env

  AWS_REGION="${AWS_REGION:-${DEFAULT_AWS_REGION:-$(aws configure get region || true)}}"
  [[ -n "$AWS_REGION" ]] || fail "AWS region is empty. Run: aws configure"

  AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
  [[ -n "$AWS_ACCOUNT_ID" && "$AWS_ACCOUNT_ID" != "None" ]] || fail "Could not read AWS account ID."

  APP_RUNNER_SERVICE_NAME="${APP_RUNNER_SERVICE_NAME:-newsfeed-api}"
  LAMBDA_FUNCTION_NAME="${LAMBDA_FUNCTION_NAME:-newsfeed-prewarm}"
  LAMBDA_ROLE_NAME="${LAMBDA_ROLE_NAME:-NewsfeedPrewarmLambdaExecutionRole}"
  SCHEDULER_ROLE_NAME="${SCHEDULER_ROLE_NAME:-NewsfeedSchedulerInvokeLambdaRole}"
  SCHEDULE_NAME="${SCHEDULE_NAME:-newsfeed-prewarm-7am}"
  PREWARM_HOUR="${PREWARM_HOUR:-7}"
  PREWARM_MINUTE="${PREWARM_MINUTE:-0}"
  PREWARM_TIMEZONE="${PREWARM_TIMEZONE:-America/New_York}"
  CLOUDWATCH_ALARM_PREFIX="${CLOUDWATCH_ALARM_PREFIX:-newsfeed}"
  SNS_TOPIC_ARN="${SNS_TOPIC_ARN:-}"

  local raw_domain
  raw_domain="${CLOUDFRONT_DOMAIN:-$(get_phase_b_domain)}"
  [[ -n "${raw_domain}" ]] || fail "Could not resolve CloudFront domain. Set CLOUDFRONT_DOMAIN=... when running scripts."
  CLOUDFRONT_DOMAIN="$(normalize_domain "${raw_domain}")"

  PREWARM_URL_EN="${PREWARM_URL_EN:-https://${CLOUDFRONT_DOMAIN}/api/news?lang=en&refresh=true}"
  PREWARM_URL_ZH="${PREWARM_URL_ZH:-https://${CLOUDFRONT_DOMAIN}/api/news?lang=zh&refresh=true}"
  SCHEDULE_EXPRESSION="${SCHEDULE_EXPRESSION:-cron(${PREWARM_MINUTE} ${PREWARM_HOUR} * * ? *)}"

  mkdir -p "$RUNTIME_DIR"

  export SCRIPT_DIR PROJECT_ROOT RUNTIME_DIR
  export AWS_REGION AWS_ACCOUNT_ID
  export APP_RUNNER_SERVICE_NAME
  export LAMBDA_FUNCTION_NAME LAMBDA_ROLE_NAME
  export SCHEDULER_ROLE_NAME SCHEDULE_NAME
  export PREWARM_HOUR PREWARM_MINUTE PREWARM_TIMEZONE
  export CLOUDWATCH_ALARM_PREFIX SNS_TOPIC_ARN
  export CLOUDFRONT_DOMAIN PREWARM_URL_EN PREWARM_URL_ZH SCHEDULE_EXPRESSION
}

print_context() {
  cat <<EOF
PROJECT_ROOT=${PROJECT_ROOT}
AWS_REGION=${AWS_REGION}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID}
APP_RUNNER_SERVICE_NAME=${APP_RUNNER_SERVICE_NAME}
LAMBDA_FUNCTION_NAME=${LAMBDA_FUNCTION_NAME}
LAMBDA_ROLE_NAME=${LAMBDA_ROLE_NAME}
SCHEDULER_ROLE_NAME=${SCHEDULER_ROLE_NAME}
SCHEDULE_NAME=${SCHEDULE_NAME}
SCHEDULE_EXPRESSION=${SCHEDULE_EXPRESSION}
PREWARM_TIMEZONE=${PREWARM_TIMEZONE}
CLOUDFRONT_DOMAIN=${CLOUDFRONT_DOMAIN}
PREWARM_URL_EN=${PREWARM_URL_EN}
PREWARM_URL_ZH=${PREWARM_URL_ZH}
CLOUDWATCH_ALARM_PREFIX=${CLOUDWATCH_ALARM_PREFIX}
EOF
}

write_context_file() {
  local context_file="${RUNTIME_DIR}/context.env"
  cat >"$context_file" <<EOF
PROJECT_ROOT=${PROJECT_ROOT}
AWS_REGION=${AWS_REGION}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID}
APP_RUNNER_SERVICE_NAME=${APP_RUNNER_SERVICE_NAME}
LAMBDA_FUNCTION_NAME=${LAMBDA_FUNCTION_NAME}
LAMBDA_ROLE_NAME=${LAMBDA_ROLE_NAME}
SCHEDULER_ROLE_NAME=${SCHEDULER_ROLE_NAME}
SCHEDULE_NAME=${SCHEDULE_NAME}
SCHEDULE_EXPRESSION=${SCHEDULE_EXPRESSION}
PREWARM_TIMEZONE=${PREWARM_TIMEZONE}
CLOUDFRONT_DOMAIN=${CLOUDFRONT_DOMAIN}
PREWARM_URL_EN=${PREWARM_URL_EN}
PREWARM_URL_ZH=${PREWARM_URL_ZH}
CLOUDWATCH_ALARM_PREFIX=${CLOUDWATCH_ALARM_PREFIX}
EOF
  chmod 600 "$context_file"
}

get_apprunner_service_arn() {
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

get_apprunner_service_id() {
  local service_arn="$1"
  if [[ -z "$service_arn" ]]; then
    printf ''
    return
  fi
  # ARN format: arn:...:service/<name>/<service-id>
  printf '%s' "$service_arn" | awk -F'/' '{print $3}'
}

alarm_action_args() {
  if [[ -n "${SNS_TOPIC_ARN}" ]]; then
    printf -- '--alarm-actions %q --ok-actions %q' "${SNS_TOPIC_ARN}" "${SNS_TOPIC_ARN}"
  fi
}
