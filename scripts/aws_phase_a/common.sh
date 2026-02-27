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

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  value="${value//$'\r'/\\r}"
  value="${value//$'\t'/\\t}"
  printf '%s' "$value"
}

init_context() {
  require_cmd aws
  require_cmd docker
  require_cmd curl

  load_project_env
  validate_required_env

  AWS_REGION="${AWS_REGION:-${DEFAULT_AWS_REGION:-$(aws configure get region || true)}}"
  [[ -n "$AWS_REGION" ]] || fail "AWS region is empty. Run: aws configure"

  AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
  [[ -n "$AWS_ACCOUNT_ID" && "$AWS_ACCOUNT_ID" != "None" ]] || fail "Could not read AWS account ID."

  ECR_REPO_NAME="${ECR_REPO_NAME:-newsfeed-backend}"
  IMAGE_TAG="${IMAGE_TAG:-latest}"
  APP_RUNNER_SERVICE_NAME="${APP_RUNNER_SERVICE_NAME:-newsfeed-api}"
  APP_RUNNER_ECR_ROLE_NAME="${APP_RUNNER_ECR_ROLE_NAME:-AppRunnerECRAccessRole}"
  APP_RUNNER_CPU="${APP_RUNNER_CPU:-0.25 vCPU}"
  APP_RUNNER_MEMORY="${APP_RUNNER_MEMORY:-0.5 GB}"
  APP_RUNNER_CORS_ORIGINS="${APP_RUNNER_CORS_ORIGINS:-${CORS_ORIGINS:-http://localhost:3000,http://127.0.0.1:3000}}"

  ECR_IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:${IMAGE_TAG}"

  mkdir -p "$RUNTIME_DIR"

  export SCRIPT_DIR PROJECT_ROOT RUNTIME_DIR
  export AWS_REGION AWS_ACCOUNT_ID
  export ECR_REPO_NAME IMAGE_TAG ECR_IMAGE_URI
  export APP_RUNNER_SERVICE_NAME APP_RUNNER_ECR_ROLE_NAME APP_RUNNER_CPU APP_RUNNER_MEMORY APP_RUNNER_CORS_ORIGINS
}

print_context() {
  cat <<EOF
PROJECT_ROOT=${PROJECT_ROOT}
AWS_REGION=${AWS_REGION}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID}
ECR_REPO_NAME=${ECR_REPO_NAME}
IMAGE_TAG=${IMAGE_TAG}
ECR_IMAGE_URI=${ECR_IMAGE_URI}
APP_RUNNER_SERVICE_NAME=${APP_RUNNER_SERVICE_NAME}
APP_RUNNER_ECR_ROLE_NAME=${APP_RUNNER_ECR_ROLE_NAME}
APP_RUNNER_CPU=${APP_RUNNER_CPU}
APP_RUNNER_MEMORY=${APP_RUNNER_MEMORY}
APP_RUNNER_CORS_ORIGINS=${APP_RUNNER_CORS_ORIGINS}
EOF
}

write_context_file() {
  local context_file="${RUNTIME_DIR}/context.env"
  cat >"$context_file" <<EOF
PROJECT_ROOT=${PROJECT_ROOT}
AWS_REGION=${AWS_REGION}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID}
ECR_REPO_NAME=${ECR_REPO_NAME}
IMAGE_TAG=${IMAGE_TAG}
ECR_IMAGE_URI=${ECR_IMAGE_URI}
APP_RUNNER_SERVICE_NAME=${APP_RUNNER_SERVICE_NAME}
APP_RUNNER_ECR_ROLE_NAME=${APP_RUNNER_ECR_ROLE_NAME}
APP_RUNNER_CPU=${APP_RUNNER_CPU}
APP_RUNNER_MEMORY=${APP_RUNNER_MEMORY}
APP_RUNNER_CORS_ORIGINS=${APP_RUNNER_CORS_ORIGINS}
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

wait_for_service_running() {
  local service_arn="$1"
  local max_attempts="${2:-45}"
  local attempt status

  for ((attempt = 1; attempt <= max_attempts; attempt++)); do
    status="$(aws apprunner describe-service \
      --region "$AWS_REGION" \
      --service-arn "$service_arn" \
      --query 'Service.Status' \
      --output text)"

    log "App Runner status (attempt ${attempt}/${max_attempts}): ${status}"

    case "$status" in
      RUNNING)
        return 0
        ;;
      CREATE_FAILED | DELETE_FAILED | OPERATION_FAILED)
        fail "Service entered failure state: ${status}"
        ;;
    esac

    sleep 20
  done

  fail "Timed out waiting for App Runner service to reach RUNNING."
}
