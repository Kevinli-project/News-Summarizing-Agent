#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/00_prepare.sh"
"${SCRIPT_DIR}/10_build_frontend.sh"
"${SCRIPT_DIR}/20_create_s3_and_upload.sh"
"${SCRIPT_DIR}/30_create_cloudfront.sh"
"${SCRIPT_DIR}/35_fix_cloudfront_api_routing.sh"
"${SCRIPT_DIR}/40_wait_and_verify.sh"
"${SCRIPT_DIR}/50_update_backend_cors.sh"
"${SCRIPT_DIR}/60_invalidate_and_final_test.sh"

echo "All Phase B steps completed."
