#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context
write_context_file

service_arn="$(get_service_arn)"
[[ -n "$service_arn" ]] || fail "Phase A backend service not found. Run scripts/aws_phase_a first."

service_status="$(aws apprunner describe-service --region "$AWS_REGION" --service-arn "$service_arn" --query 'Service.Status' --output text)"
service_url="$(get_apprunner_service_url)"
s3_website_domain="$(get_s3_website_domain)"

echo "$service_arn" >"${RUNTIME_DIR}/service_arn.txt"
echo "$service_url" >"${RUNTIME_DIR}/apprunner_service_url.txt"

log "App Runner service ARN: ${service_arn}"
log "App Runner service status: ${service_status}"
log "App Runner service URL: https://${service_url}"
log "S3 website endpoint (origin only): http://${s3_website_domain}"
log "Step 00 complete."
