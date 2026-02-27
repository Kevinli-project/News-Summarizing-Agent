#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context

trust_policy_file="${RUNTIME_DIR}/apprunner-ecr-trust-policy.json"

cat >"${trust_policy_file}" <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "build.apprunner.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON

log "Ensuring IAM role exists: ${APP_RUNNER_ECR_ROLE_NAME}"
aws iam get-role --role-name "${APP_RUNNER_ECR_ROLE_NAME}" >/dev/null 2>&1 || \
aws iam create-role \
  --role-name "${APP_RUNNER_ECR_ROLE_NAME}" \
  --assume-role-policy-document "file://${trust_policy_file}" >/dev/null

log "Attaching ECR access policy to role..."
aws iam attach-role-policy \
  --role-name "${APP_RUNNER_ECR_ROLE_NAME}" \
  --policy-arn "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess" >/dev/null

role_arn="$(aws iam get-role --role-name "${APP_RUNNER_ECR_ROLE_NAME}" --query 'Role.Arn' --output text)"
echo "${role_arn}" >"${RUNTIME_DIR}/apprunner_ecr_role_arn.txt"

log "Role ARN: ${role_arn}"
log "Step 30 complete."
