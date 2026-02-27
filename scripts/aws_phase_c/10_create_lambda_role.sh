#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context

trust_policy_file="${RUNTIME_DIR}/lambda_trust_policy.json"
cat >"${trust_policy_file}" <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON

log "Ensuring Lambda execution role exists: ${LAMBDA_ROLE_NAME}"
aws iam get-role --role-name "${LAMBDA_ROLE_NAME}" >/dev/null 2>&1 || \
aws iam create-role \
  --role-name "${LAMBDA_ROLE_NAME}" \
  --assume-role-policy-document "file://${trust_policy_file}" >/dev/null

log "Attaching AWSLambdaBasicExecutionRole policy..."
aws iam attach-role-policy \
  --role-name "${LAMBDA_ROLE_NAME}" \
  --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" >/dev/null

role_arn="$(aws iam get-role --role-name "${LAMBDA_ROLE_NAME}" --query 'Role.Arn' --output text)"
echo "${role_arn}" >"${RUNTIME_DIR}/lambda_role_arn.txt"

log "Lambda role ARN: ${role_arn}"
log "Step 10 complete."
