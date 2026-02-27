#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context

role_arn="$(aws iam get-role --role-name "${APP_RUNNER_ECR_ROLE_NAME}" --query 'Role.Arn' --output text 2>/dev/null || true)"
[[ -n "${role_arn}" && "${role_arn}" != "None" ]] || fail "Role ${APP_RUNNER_ECR_ROLE_NAME} not found. Run 30_prepare_iam_role.sh first."

existing_service_arn="$(get_service_arn)"

openai_key_json="$(json_escape "${OPENAI_API_KEY}")"
news_key_json="$(json_escape "${NEWS_API_KEY}")"
brave_key_json="$(json_escape "${BRAVE_API_KEY}")"
cors_json="$(json_escape "${APP_RUNNER_CORS_ORIGINS}")"

if [[ -z "${existing_service_arn}" ]]; then
  payload_file="${RUNTIME_DIR}/apprunner_create_payload.json"
  cat >"${payload_file}" <<EOF
{
  "ServiceName": "${APP_RUNNER_SERVICE_NAME}",
  "SourceConfiguration": {
    "AutoDeploymentsEnabled": false,
    "AuthenticationConfiguration": {
      "AccessRoleArn": "${role_arn}"
    },
    "ImageRepository": {
      "ImageIdentifier": "${ECR_IMAGE_URI}",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "8000",
        "RuntimeEnvironmentVariables": {
          "OPENAI_API_KEY": "${openai_key_json}",
          "NEWS_API_KEY": "${news_key_json}",
          "BRAVE_API_KEY": "${brave_key_json}",
          "CORS_ORIGINS": "${cors_json}"
        }
      }
    }
  },
  "InstanceConfiguration": {
    "Cpu": "${APP_RUNNER_CPU}",
    "Memory": "${APP_RUNNER_MEMORY}"
  },
  "HealthCheckConfiguration": {
    "Protocol": "HTTP",
    "Path": "/",
    "Interval": 20,
    "Timeout": 5,
    "HealthyThreshold": 1,
    "UnhealthyThreshold": 5
  }
}
EOF
  chmod 600 "${payload_file}"

  log "Creating App Runner service: ${APP_RUNNER_SERVICE_NAME}"
  service_arn="$(aws apprunner create-service \
    --region "${AWS_REGION}" \
    --cli-input-json "file://${payload_file}" \
    --query 'Service.ServiceArn' \
    --output text)"
else
  payload_file="${RUNTIME_DIR}/apprunner_update_payload.json"
  cat >"${payload_file}" <<EOF
{
  "ServiceArn": "${existing_service_arn}",
  "SourceConfiguration": {
    "AutoDeploymentsEnabled": false,
    "AuthenticationConfiguration": {
      "AccessRoleArn": "${role_arn}"
    },
    "ImageRepository": {
      "ImageIdentifier": "${ECR_IMAGE_URI}",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "8000",
        "RuntimeEnvironmentVariables": {
          "OPENAI_API_KEY": "${openai_key_json}",
          "NEWS_API_KEY": "${news_key_json}",
          "BRAVE_API_KEY": "${brave_key_json}",
          "CORS_ORIGINS": "${cors_json}"
        }
      }
    }
  },
  "InstanceConfiguration": {
    "Cpu": "${APP_RUNNER_CPU}",
    "Memory": "${APP_RUNNER_MEMORY}"
  },
  "HealthCheckConfiguration": {
    "Protocol": "HTTP",
    "Path": "/",
    "Interval": 20,
    "Timeout": 5,
    "HealthyThreshold": 1,
    "UnhealthyThreshold": 5
  }
}
EOF
  chmod 600 "${payload_file}"

  log "Updating existing App Runner service: ${APP_RUNNER_SERVICE_NAME}"
  service_arn="$(aws apprunner update-service \
    --region "${AWS_REGION}" \
    --cli-input-json "file://${payload_file}" \
    --query 'Service.ServiceArn' \
    --output text)"
fi

echo "${service_arn}" >"${RUNTIME_DIR}/service_arn.txt"
log "Service ARN: ${service_arn}"
log "Step 40 complete."
