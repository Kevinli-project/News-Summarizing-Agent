#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context

update_with_retry() {
  local step_name="$1"
  shift

  local max_attempts=20
  local attempt
  local output

  for attempt in $(seq 1 "${max_attempts}"); do
    if output="$("$@" 2>&1)"; then
      return 0
    fi

    if echo "${output}" | grep -q "ResourceConflictException"; then
      log "${step_name} hit ResourceConflictException (attempt ${attempt}/${max_attempts}); waiting for Lambda update lock..."
      aws lambda wait function-updated-v2 \
        --function-name "${LAMBDA_FUNCTION_NAME}" \
        --region "${AWS_REGION}" >/dev/null 2>&1 || true
      sleep 3
      continue
    fi

    echo "${output}" >&2
    return 1
  done

  fail "${step_name} failed after ${max_attempts} retries due to repeated ResourceConflictException."
}

role_arn="$(aws iam get-role --role-name "${LAMBDA_ROLE_NAME}" --query 'Role.Arn' --output text 2>/dev/null || true)"
[[ -n "${role_arn}" && "${role_arn}" != "None" ]] || fail "Lambda role ${LAMBDA_ROLE_NAME} not found. Run 10_create_lambda_role.sh first."

lambda_src="${RUNTIME_DIR}/prewarm_lambda.py"
cat >"${lambda_src}" <<'PY'
import json
import os
import time
import urllib.request
import urllib.error


def _hit(url: str, timeout: int = 180) -> dict:
    started = time.time()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            elapsed_ms = int((time.time() - started) * 1000)
            return {
                "url": url,
                "ok": 200 <= resp.status < 300,
                "status": resp.status,
                "elapsed_ms": elapsed_ms,
                "content_type": resp.headers.get("content-type", ""),
                "body_prefix": body[:120],
            }
    except urllib.error.HTTPError as exc:
        elapsed_ms = int((time.time() - started) * 1000)
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return {
            "url": url,
            "ok": False,
            "status": exc.code,
            "elapsed_ms": elapsed_ms,
            "error": str(exc),
            "body_prefix": body[:120],
        }
    except Exception as exc:
        elapsed_ms = int((time.time() - started) * 1000)
        return {
            "url": url,
            "ok": False,
            "status": None,
            "elapsed_ms": elapsed_ms,
            "error": str(exc),
        }


def handler(event, context):
    url_en = os.environ["PREWARM_URL_EN"]
    url_zh = os.environ["PREWARM_URL_ZH"]
    results = [_hit(url_en), _hit(url_zh)]
    success = all(r.get("ok") for r in results)

    output = {
        "success": success,
        "results": results,
    }
    print(json.dumps(output, ensure_ascii=False))

    if not success:
        raise RuntimeError(json.dumps(output))

    return output
PY

zip_file="${RUNTIME_DIR}/prewarm_lambda.zip"
rm -f "${zip_file}"
(
  cd "${RUNTIME_DIR}"
  zip -q -j "${zip_file}" "${lambda_src}"
)

log "Creating or updating Lambda function ${LAMBDA_FUNCTION_NAME}..."
if aws lambda get-function --function-name "${LAMBDA_FUNCTION_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1; then
  update_with_retry "update-function-code" \
    aws lambda update-function-code \
      --function-name "${LAMBDA_FUNCTION_NAME}" \
      --zip-file "fileb://${zip_file}" \
      --region "${AWS_REGION}" >/dev/null

  # Lambda serializes updates: wait for code update to finish before config update.
  aws lambda wait function-updated-v2 \
    --function-name "${LAMBDA_FUNCTION_NAME}" \
    --region "${AWS_REGION}" >/dev/null

  update_with_retry "update-function-configuration" \
    aws lambda update-function-configuration \
      --function-name "${LAMBDA_FUNCTION_NAME}" \
      --role "${role_arn}" \
      --runtime "python3.12" \
      --handler "prewarm_lambda.handler" \
      --timeout 180 \
      --memory-size 128 \
      --environment "Variables={PREWARM_URL_EN=${PREWARM_URL_EN},PREWARM_URL_ZH=${PREWARM_URL_ZH}}" \
      --region "${AWS_REGION}" >/dev/null
else
  update_with_retry "create-function" \
    aws lambda create-function \
      --function-name "${LAMBDA_FUNCTION_NAME}" \
      --role "${role_arn}" \
      --runtime "python3.12" \
      --handler "prewarm_lambda.handler" \
      --timeout 180 \
      --memory-size 128 \
      --zip-file "fileb://${zip_file}" \
      --environment "Variables={PREWARM_URL_EN=${PREWARM_URL_EN},PREWARM_URL_ZH=${PREWARM_URL_ZH}}" \
      --region "${AWS_REGION}" >/dev/null
fi

aws lambda wait function-updated-v2 \
  --function-name "${LAMBDA_FUNCTION_NAME}" \
  --region "${AWS_REGION}"

lambda_arn="$(aws lambda get-function --function-name "${LAMBDA_FUNCTION_NAME}" --region "${AWS_REGION}" --query 'Configuration.FunctionArn' --output text)"
echo "${lambda_arn}" >"${RUNTIME_DIR}/lambda_function_arn.txt"

log "Lambda function ARN: ${lambda_arn}"
log "Step 20 complete."
