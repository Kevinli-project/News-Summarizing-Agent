#!/usr/bin/env bash
# Prewarm the news cache by calling /api/news for both en and zh.
# Run this daily (e.g. 7am) so the first user of the day doesn't hit a cold cache.
#
# Usage:
#   ./prewarm_cache.sh                    # uses BASE_URL=http://localhost:8000
#   BASE_URL=https://api.example.com ./prewarm_cache.sh

set -e
BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] Prewarming cache at $BASE_URL (forced refresh)"
curl -sS -o /dev/null -w "%{http_code}" "$BASE_URL/api/news?lang=en&refresh=true" && echo " en" || echo " en FAILED"
curl -sS -o /dev/null -w "%{http_code}" "$BASE_URL/api/news?lang=zh&refresh=true" && echo " zh" || echo " zh FAILED"
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] Prewarm done"
