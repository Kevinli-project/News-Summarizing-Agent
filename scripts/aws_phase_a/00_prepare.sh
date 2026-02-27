#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context

log "Loaded deployment context."
print_context
write_context_file

log "Checking AWS caller identity..."
aws sts get-caller-identity --output table

log "Step 00 complete."
