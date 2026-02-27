#!/usr/bin/env bash
# Add the 7am cache-prewarm cron job for this project.
# Run from the project root or from scripts/. Safe to run multiple times (skips if already present).
#
# Usage: ./scripts/install_cron.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CRON_LINE="0 7 * * * BASE_URL=http://localhost:8000 ${PROJECT_ROOT}/scripts/prewarm_cache.sh >> ${PROJECT_ROOT}/scripts/prewarm.log 2>&1"

if crontab -l 2>/dev/null | grep -Fq "prewarm_cache.sh"; then
  echo "Cron entry for prewarm_cache.sh already exists. Nothing to do."
  exit 0
fi

(crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
echo "Added 7am daily prewarm cron job. Log: ${PROJECT_ROOT}/scripts/prewarm.log"
echo "To remove later: crontab -e and delete the prewarm_cache.sh line."
