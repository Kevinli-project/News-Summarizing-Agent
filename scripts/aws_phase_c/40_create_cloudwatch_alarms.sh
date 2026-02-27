#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context

lambda_arn="$(aws lambda get-function --function-name "${LAMBDA_FUNCTION_NAME}" --region "${AWS_REGION}" --query 'Configuration.FunctionArn' --output text 2>/dev/null || true)"
[[ -n "${lambda_arn}" && "${lambda_arn}" != "None" ]] || fail "Lambda ${LAMBDA_FUNCTION_NAME} not found."

service_arn="$(get_apprunner_service_arn)"
[[ -n "${service_arn}" ]] || fail "App Runner service ${APP_RUNNER_SERVICE_NAME} not found."
service_id="$(get_apprunner_service_id "${service_arn}")"

put_alarm() {
  local -a args=("$@")
  if [[ -n "${SNS_TOPIC_ARN}" ]]; then
    args+=(--alarm-actions "${SNS_TOPIC_ARN}" --ok-actions "${SNS_TOPIC_ARN}")
  fi
  args+=(--region "${AWS_REGION}")
  aws cloudwatch put-metric-alarm "${args[@]}"
}

log "Creating Lambda alarms..."
put_alarm \
  --alarm-name "${CLOUDWATCH_ALARM_PREFIX}-lambda-errors" \
  --alarm-description "Newsfeed prewarm lambda errors > 0" \
  --namespace "AWS/Lambda" \
  --metric-name "Errors" \
  --dimensions "Name=FunctionName,Value=${LAMBDA_FUNCTION_NAME}" \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 0 \
  --comparison-operator GreaterThanThreshold \
  --treat-missing-data notBreaching

put_alarm \
  --alarm-name "${CLOUDWATCH_ALARM_PREFIX}-lambda-duration-high" \
  --alarm-description "Newsfeed prewarm lambda duration high (>120s average)" \
  --namespace "AWS/Lambda" \
  --metric-name "Duration" \
  --dimensions "Name=FunctionName,Value=${LAMBDA_FUNCTION_NAME}" \
  --statistic Average \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 120000 \
  --comparison-operator GreaterThanThreshold \
  --treat-missing-data notBreaching

app_runner_metric_names="$(aws cloudwatch list-metrics \
  --namespace "AWS/AppRunner" \
  --dimensions "Name=ServiceName,Value=${APP_RUNNER_SERVICE_NAME}" \
  --region "${AWS_REGION}" \
  --query 'Metrics[].MetricName' \
  --output text | tr '\t' '\n' | sort -u)"

pick_metric() {
  local metrics="$1"
  shift
  local candidate
  for candidate in "$@"; do
    if echo "${metrics}" | grep -Fxq "${candidate}"; then
      printf '%s' "${candidate}"
      return 0
    fi
  done
  printf ''
}

metric_5xx="$(pick_metric "${app_runner_metric_names}" "5xxStatusResponses" "HTTPCode5XX")"
metric_latency="$(pick_metric "${app_runner_metric_names}" "ResponseTime" "RequestLatency" "Latency")"
app_runner_dims=("Name=ServiceName,Value=${APP_RUNNER_SERVICE_NAME}")
if [[ -n "${service_id}" ]]; then
  app_runner_dims+=("Name=ServiceId,Value=${service_id}")
fi

if [[ -n "${metric_5xx}" ]]; then
  log "Creating App Runner 5xx alarm using metric ${metric_5xx}..."
  put_alarm \
    --alarm-name "${CLOUDWATCH_ALARM_PREFIX}-apprunner-5xx" \
    --alarm-description "App Runner 5xx responses > 5 in 5 minutes" \
    --namespace "AWS/AppRunner" \
    --metric-name "${metric_5xx}" \
    --dimensions "${app_runner_dims[@]}" \
    --statistic Sum \
    --period 300 \
    --evaluation-periods 1 \
    --threshold 5 \
    --comparison-operator GreaterThanThreshold \
    --treat-missing-data notBreaching
else
  log "Skipped App Runner 5xx alarm: no matching metric found in AWS/AppRunner namespace."
fi

if [[ -n "${metric_latency}" ]]; then
  log "Creating App Runner latency alarm using metric ${metric_latency}..."
  put_alarm \
    --alarm-name "${CLOUDWATCH_ALARM_PREFIX}-apprunner-latency" \
    --alarm-description "App Runner latency high (>5s average in 5 minutes)" \
    --namespace "AWS/AppRunner" \
    --metric-name "${metric_latency}" \
    --dimensions "${app_runner_dims[@]}" \
    --statistic Average \
    --period 300 \
    --evaluation-periods 1 \
    --threshold 5000 \
    --comparison-operator GreaterThanThreshold \
    --treat-missing-data notBreaching
else
  log "Skipped App Runner latency alarm: no matching metric found in AWS/AppRunner namespace."
fi

log "Step 40 complete."
