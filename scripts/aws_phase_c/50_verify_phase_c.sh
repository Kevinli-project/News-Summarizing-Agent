#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context

log "Invoking prewarm Lambda once for smoke test..."
invoke_out="${RUNTIME_DIR}/lambda_invoke_output.json"
aws lambda invoke \
  --function-name "${LAMBDA_FUNCTION_NAME}" \
  --payload '{}' \
  --cli-binary-format raw-in-base64-out \
  --no-cli-pager \
  --region "${AWS_REGION}" \
  "${invoke_out}" >/tmp/newsfeed_lambda_invoke_meta.json

status_code="$(jq -r '.StatusCode' /tmp/newsfeed_lambda_invoke_meta.json)"
function_error="$(jq -r '.FunctionError // empty' /tmp/newsfeed_lambda_invoke_meta.json)"

log "Lambda invoke status code: ${status_code}"
if [[ -n "${function_error}" ]]; then
  log "Lambda function error flag: ${function_error}"
  cat "${invoke_out}"
  fail "Lambda invoke returned FunctionError."
fi

if jq -e '.success == true' "${invoke_out}" >/dev/null 2>&1; then
  log "Lambda output indicates prewarm success."
else
  log "Lambda output:"
  cat "${invoke_out}"
  fail "Prewarm lambda output did not report success=true."
fi

log "Checking EventBridge schedule state..."
aws scheduler get-schedule \
  --name "${SCHEDULE_NAME}" \
  --group-name default \
  --no-cli-pager \
  --region "${AWS_REGION}" \
  --output table

log "Checking alarm list..."
aws cloudwatch describe-alarms \
  --alarm-name-prefix "${CLOUDWATCH_ALARM_PREFIX}" \
  --no-cli-pager \
  --region "${AWS_REGION}" \
  --query 'MetricAlarms[].{Name:AlarmName,State:StateValue,Metric:MetricName}' \
  --output table

log "Step 50 complete."
