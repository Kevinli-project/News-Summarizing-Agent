#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context

log "Checking local image exists: ${ECR_REPO_NAME}:${IMAGE_TAG}"
docker image inspect "${ECR_REPO_NAME}:${IMAGE_TAG}" >/dev/null

log "Ensuring ECR repository exists: ${ECR_REPO_NAME}"
aws ecr describe-repositories \
  --repository-names "${ECR_REPO_NAME}" \
  --region "${AWS_REGION}" >/dev/null 2>&1 || \
aws ecr create-repository \
  --repository-name "${ECR_REPO_NAME}" \
  --image-scanning-configuration scanOnPush=true \
  --region "${AWS_REGION}" >/dev/null

log "Logging Docker into ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | \
docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

log "Tagging image -> ${ECR_IMAGE_URI}"
docker tag "${ECR_REPO_NAME}:${IMAGE_TAG}" "${ECR_IMAGE_URI}"

log "Pushing image to ECR..."
docker push "${ECR_IMAGE_URI}"

digest="$(aws ecr describe-images \
  --repository-name "${ECR_REPO_NAME}" \
  --image-ids imageTag="${IMAGE_TAG}" \
  --region "${AWS_REGION}" \
  --query 'imageDetails[0].imageDigest' \
  --output text)"

log "Push complete."
log "Image URI: ${ECR_IMAGE_URI}"
log "Image digest: ${digest}"
log "Step 20 complete."
