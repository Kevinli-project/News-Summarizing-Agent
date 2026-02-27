# Cache prewarm cron job

The backend keeps news in an **in-memory cache**. After a restart (or before the first request of the day), the cache is empty and the first user waits ~20s. A **cron job** can prewarm the cache by calling `/api/news` for both languages so that doesn’t happen.

## Local setup (this repo)

- Script: `scripts/prewarm_cache.sh` (default `BASE_URL=http://localhost:8000`).
- **Install 7am daily cron** (same machine as backend):
  ```bash
  chmod +x scripts/install_cron.sh
  ./scripts/install_cron.sh
  ```
  This adds one crontab entry and appends output to `scripts/prewarm.log`. Safe to run multiple times (skips if already present).

## What the cron does

- Runs once per day (e.g. 7:00).
- Calls `GET /api/news?lang=en` and `GET /api/news?lang=zh`.
- Each request triggers a full fetch if the cache is empty and fills it; if the cache is already warm, the request still returns quickly.

## Option A: Cron on the same server as the backend (recommended)

**Assumption:** Backend runs on the same machine (e.g. a VPS) and is reachable at `http://localhost:8000` (or a local URL).

### 1. Make the script executable

```bash
chmod +x scripts/prewarm_cache.sh
```

### 2. Test once

```bash
# Backend must be running (e.g. uvicorn)
./scripts/prewarm_cache.sh
```

If the backend is on another host or port:

```bash
BASE_URL=http://127.0.0.1:8000 ./scripts/prewarm_cache.sh
```

### 3. Add a crontab entry

```bash
crontab -e
```

Add one line (run at 7:00 every day; adjust timezone by changing `7` or using `TZ=...` if needed):

```cron
0 7 * * * BASE_URL=http://localhost:8000 /path/to/NewsFeedProject/scripts/prewarm_cache.sh >> /var/log/news-prewarm.log 2>&1
```

Replace `/path/to/NewsFeedProject` with the real path to the project. Example with a user project dir:

```cron
0 7 * * * BASE_URL=http://localhost:8000 /home/me/NewsFeedProject/scripts/prewarm_cache.sh >> /home/me/news-prewarm.log 2>&1
```

### 4. (Optional) Use a virtualenv or project env

If the backend uses a virtualenv and you want to ensure the same env for any future Python prewarm script, you can wrap the call:

```cron
0 7 * * * cd /path/to/NewsFeedProject && BASE_URL=http://localhost:8000 ./scripts/prewarm_cache.sh >> /var/log/news-prewarm.log 2>&1
```

The provided script is plain bash + `curl`, so no Python env is required.

---

## Option B: Hosted cron (backend has a public URL)

If the backend is deployed and has a public URL (e.g. `https://your-api.example.com`), you can use an external cron service to hit it.

### 1. Use a “cron as a service” provider

Examples:

- [cron-job.org](https://cron-job.org) (free)
- [EasyCron](https://www.easycron.com)
- Or a small scheduled job on another cloud (e.g. AWS Lambda on a schedule, GitHub Actions scheduled workflow).

### 2. Configure two daily requests

- **URL 1:** `https://your-api.example.com/api/news?lang=en`
- **URL 2:** `https://your-api.example.com/api/news?lang=zh`
- **Schedule:** Once per day (e.g. 7:00 in your target timezone).

No script to install; the provider just does HTTP GET to those URLs.

---

## Option C: Python script (alternative to shell)

If you prefer Python and are on the same server:

```python
# scripts/prewarm_cache.py
import os
import urllib.request
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
for lang in ("en", "zh"):
    url = f"{BASE_URL}/api/news?lang={lang}"
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            print(r.status, lang)
    except Exception as e:
        print("FAIL", lang, e)
```

Run daily the same way (cron or hosted cron calling the URLs). Cron example:

```cron
0 7 * * * cd /path/to/NewsFeedProject && BASE_URL=http://localhost:8000 python scripts/prewarm_cache.py >> /var/log/news-prewarm.log 2>&1
```

---

## Summary

| Where backend runs        | How to prewarm |
|---------------------------|----------------|
| Same server (e.g. VPS)    | Option A: `prewarm_cache.sh` in crontab at 7am. |
| Public URL (e.g. cloud)   | Option B: Hosted cron hitting `.../api/news?lang=en` and `.../api/news?lang=zh` once per day. |
| Either                   | Option C: Python script in crontab if you prefer. |

The cache is in-memory, so prewarm must run **after** the backend process has started (e.g. after a reboot, wait for the app to be up, or run prewarm a few minutes after the service starts).
