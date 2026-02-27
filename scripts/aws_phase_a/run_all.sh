#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/00_prepare.sh"
"${SCRIPT_DIR}/10_build_image.sh"
"${SCRIPT_DIR}/20_push_ecr.sh"
"${SCRIPT_DIR}/30_prepare_iam_role.sh"
"${SCRIPT_DIR}/40_deploy_apprunner.sh"
"${SCRIPT_DIR}/50_wait_and_verify.sh"

echo "All Phase A steps completed."
