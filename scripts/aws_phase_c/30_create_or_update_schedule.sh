#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context

lambda_arn="$(aws lambda get-function --function-name "${LAMBDA_FUNCTION_NAME}" --region "${AWS_REGION}" --query 'Configuration.FunctionArn' --output text 2>/dev/null || true)"
[[ -n "${lambda_arn}" && "${lambda_arn}" != "None" ]] || fail "Lambda ${LAMBDA_FUNCTION_NAME} not found. Run 20_create_or_update_prewarm_lambda.sh first."

scheduler_trust_policy="${RUNTIME_DIR}/scheduler_trust_policy.json"
cat >"${scheduler_trust_policy}" <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "scheduler.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON

log "Ensuring scheduler invoke role exists: ${SCHEDULER_ROLE_NAME}"
aws iam get-role --role-name "${SCHEDULER_ROLE_NAME}" >/dev/null 2>&1 || \
aws iam create-role \
  --role-name "${SCHEDULER_ROLE_NAME}" \
  --assume-role-policy-document "file://${scheduler_trust_policy}" >/dev/null

scheduler_policy="${RUNTIME_DIR}/scheduler_invoke_lambda_policy.json"
cat >"${scheduler_policy}" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "${lambda_arn}"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name "${SCHEDULER_ROLE_NAME}" \
  --policy-name "InvokeNewsfeedPrewarmLambda" \
  --policy-document "file://${scheduler_policy}" >/dev/null

scheduler_role_arn="$(aws iam get-role --role-name "${SCHEDULER_ROLE_NAME}" --query 'Role.Arn' --output text)"
echo "${scheduler_role_arn}" >"${RUNTIME_DIR}/scheduler_role_arn.txt"

target_json="${RUNTIME_DIR}/scheduler_target.json"
cat >"${target_json}" <<EOF
{
  "Arn": "${lambda_arn}",
  "RoleArn": "${scheduler_role_arn}",
  "Input": "{\"source\":\"newsfeed-prewarm\"}"
}
EOF

log "Creating or updating EventBridge schedule ${SCHEDULE_NAME}..."
if aws scheduler get-schedule --name "${SCHEDULE_NAME}" --group-name default --region "${AWS_REGION}" >/dev/null 2>&1; then
  aws scheduler update-schedule \
    --name "${SCHEDULE_NAME}" \
    --group-name default \
    --schedule-expression "${SCHEDULE_EXPRESSION}" \
    --schedule-expression-timezone "${PREWARM_TIMEZONE}" \
    --flexible-time-window '{"Mode":"OFF"}' \
    --target "file://${target_json}" \
    --state ENABLED \
    --region "${AWS_REGION}" >/dev/null
else
  aws scheduler create-schedule \
    --name "${SCHEDULE_NAME}" \
    --group-name default \
    --schedule-expression "${SCHEDULE_EXPRESSION}" \
    --schedule-expression-timezone "${PREWARM_TIMEZONE}" \
    --flexible-time-window '{"Mode":"OFF"}' \
    --target "file://${target_json}" \
    --state ENABLED \
    --region "${AWS_REGION}" >/dev/null
fi

schedule_arn="$(aws scheduler get-schedule --name "${SCHEDULE_NAME}" --group-name default --region "${AWS_REGION}" --query 'Arn' --output text)"
echo "${schedule_arn}" >"${RUNTIME_DIR}/schedule_arn.txt"

log "Schedule ARN: ${schedule_arn}"
log "Step 30 complete."
