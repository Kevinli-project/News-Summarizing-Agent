#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/00_prepare.sh"
"${SCRIPT_DIR}/10_create_lambda_role.sh"
"${SCRIPT_DIR}/20_create_or_update_prewarm_lambda.sh"
"${SCRIPT_DIR}/30_create_or_update_schedule.sh"
"${SCRIPT_DIR}/40_create_cloudwatch_alarms.sh"
"${SCRIPT_DIR}/50_verify_phase_c.sh"

echo "All Phase C steps completed."
