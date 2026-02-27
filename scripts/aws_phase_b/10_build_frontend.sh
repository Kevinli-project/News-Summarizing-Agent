#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

init_context
print_context

[[ -d "${FRONTEND_DIR}" ]] || fail "Frontend directory not found: ${FRONTEND_DIR}"

cd "${FRONTEND_DIR}"

if [[ ! -d node_modules ]]; then
  log "frontend/node_modules not found. Running npm ci..."
  npm ci
fi

log "Building static frontend export with webpack (NEXT_STATIC_EXPORT=1)..."
NEXT_STATIC_EXPORT=1 npm run build -- --webpack

[[ -f "${FRONTEND_OUT_DIR}/index.html" ]] || fail "Static export missing ${FRONTEND_OUT_DIR}/index.html"

file_count="$(find "${FRONTEND_OUT_DIR}" -type f | wc -l | tr -d ' ')"
log "Static export complete. File count: ${file_count}"
log "Step 10 complete."
