#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/00_prepare.sh"
"${SCRIPT_DIR}/10_create_or_get_oac.sh"
"${SCRIPT_DIR}/20_update_cloudfront_to_oac.sh"
"${SCRIPT_DIR}/30_lock_s3_bucket.sh"
"${SCRIPT_DIR}/40_wait_invalidate_and_verify.sh"

echo "All Phase D steps completed."
