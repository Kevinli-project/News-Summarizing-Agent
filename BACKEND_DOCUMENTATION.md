# Backend Documentation (Current State)

This document describes how the backend currently works, based on:
- `backend/main.py`
- Root modules: `presenter.py`, `presenter_zh.py`, `question_answer.py`, `question_answer_zh.py`, `router.py`
- `backend/Dockerfile`, `backend/requirements.txt`, `backend/.env` variable names
- Deployment notes in `AWSDeployment.md` and `AWSDeployment2.md`

Scope: current behavior, not idealized behavior.

## 1) How Backend Works Locally

### 1.1 Runtime components and ownership

- API server: FastAPI app in `backend/main.py`
- News formatting pipeline: root `presenter.py` and `presenter_zh.py`
- Q&A/chat pipeline: root `question_answer.py` and `question_answer_zh.py`
- Legacy router: root `router.py` (reference only, not used by FastAPI routes)

`backend/main.py` adds the project root to `sys.path`, then imports the root agent modules directly.

### 1.2 Startup and initialization flow

At import time in `backend/main.py`:
- Loads `.env` via `load_dotenv(override=True)`
- Creates OpenAI client (`OpenAI()`) and sets model `gpt-4.1-mini`
- Parses CORS origins from `CORS_ORIGINS` env var (comma-separated), with localhost defaults
- Registers FastAPI CORS middleware
- Defines in-memory news cache structure:
  - `NEWS_CACHE: dict[str, dict]`
  - lock: `_cache_lock`

At import time in the root modules:
- Each module loads env vars again (`load_dotenv(override=True)`)
- Creates its own OpenAI client
- Instantiates singleton QA objects:
  - `question_answer.QA_instance`
  - `question_answer_zh.QA_instance`

### 1.3 Environment variables used by backend

Used across backend/root Python modules:
- `OPENAI_API_KEY`
- `NEWS_API_KEY`
- `BRAVE_API_KEY`
- `CORS_ORIGINS`

Behavior notes:
- Missing keys are printed in root modules, but startup is not hard-failed there.
- Real failures happen when an API call is attempted without valid credentials.

### 1.4 Public API endpoints

#### `GET /`
- Health check.
- Returns: `{"status":"ok"}`

#### `GET /api/news?lang=en|zh&refresh=true|false`
- Returns structured news card JSON (`categories -> articles`).
- `lang` must be `en` or `zh`.
- Sets anti-cache headers on every response:
  - `Cache-Control: no-store, no-cache, must-revalidate, max-age=0, s-maxage=0`
  - `Pragma: no-cache`
  - `Expires: 0`

#### `POST /api/chat` (SSE)
- Body:
  - `message` string (1..4000 chars)
  - `history` list, max 40 turns
  - `lang` in `en|zh`
- Streams SSE events with `{"delta":"..."}` chunks, then `[DONE]`.

#### `POST /api/news-search` (SSE)
- Body:
  - `query` string (1..200 chars)
  - `lang` in `en|zh`
  - `history` list (accepted but currently ignored in execution)
- Server rewrites query to `"./ {query}"`, then routes to presenter agent.
- Streams same SSE delta format as `/api/chat`.

### 1.5 `/api/news` internal pipeline (news cards)

#### Step A: Cache strategy in `backend/main.py`

Cache key is language (`en`, `zh`) with entry:
- `data`: last structured news payload
- `fetched_at`: unix timestamp
- `is_refreshing`: bool

Flow:
1. `refresh=true`:
   - Force blocking refresh via `fetch_news_cards(lang)`
   - Overwrite cache
   - Return fresh data immediately
2. Cache hit and `refresh=false`:
   - Return cached data immediately
   - If not already refreshing, schedule background refresh task
3. Cache miss:
   - Do blocking refresh
   - Store and return

Important property:
- No TTL or explicit expiration. Freshness is driven by:
  - background refresh on cache hits
  - forced refresh calls (`refresh=true`, including prewarm job)

#### Step B: `fetch_news_cards(lang)` LLM formatting

`fetch_news_cards` does:
1. Calls `presenter.get_today_news()` to fetch raw NewsAPI JSON text (always English source data)
2. Chooses prompt:
   - English card prompt (`CARD_PROMPT_EN`)
   - Chinese card prompt (`CARD_PROMPT_ZH`) for translated output
3. Calls OpenAI chat completion with strict JSON schema (`NEWS_CARD_SCHEMA`)
4. Parses model JSON into Python dict and returns it

Result shape:
- `{"categories": [{"name": ..., "articles": [...]}]}`
- Each article contains: `title`, `summary`, `image`, `url`, `source`, `published`

### 1.6 `/api/chat` internal pipeline (Q&A agent)

`/api/chat` routes by language:
- `en` -> `question_answer.chat(message, history)`
- `zh` -> `question_answer_zh.chat(message, history)`

Both modules use the same architecture:

1. Probe call:
   - LLM decides whether to call tools
   - Tools available:
     - `visit_website(url)`
     - `find_internet_articles(query)`

2. Evaluator gate:
   - Evaluator model checks tool-call decision
   - Main rule: do not use `visit_website` for paywalled sources
   - If rejected, rerun once with feedback telling agent to use internet search path

3. Tool execution:
   - `visit_website`:
     - Fetches page HTML (aiohttp)
     - Strips scripts/styles/images/inputs
     - Returns page title + extracted text
   - `find_internet_articles`:
     - Uses Brave News Search API
     - Filters to `news_result` items
     - Uses LLM to select 3 best non-paywalled links
     - Fetches selected links in parallel (async gather)
     - Returns combined article content payload

4. Final answer generation:
   - LLM generates final response using tool results
   - Streaming output is emitted as accumulated text chunks from module generator

5. SSE conversion in FastAPI:
   - Backend computes delta from accumulated chunks
   - Emits SSE `data: {"delta":"..."}` records
   - Emits `data: [DONE]` at completion

Language differences:
- English QA prompt uses Cleo Abram style instructions
- Chinese QA prompt uses XiaoLin-style Chinese explanation instructions
- Tool/evaluator mechanics are otherwise the same

### 1.7 `/api/news-search` internal pipeline (topic news mode)

`/api/news-search` is separate from `/api/chat` and intentionally routes to presenter modules:
- `en` -> `presenter.chat("./ {query}", [])`
- `zh` -> `presenter_zh.chat("./ {query}", [])`

Current behavior details:
- Incoming `history` is validated but not passed through (empty history is used)
- Presenter agent flow:
  1. Probe LLM decides tool call (`custom_domain_search` expected for `./`)
  2. Tool fetches NewsAPI "everything" results for domain query
  3. Second LLM pass formats results into markdown article list
  4. Generator streams accumulated output; backend converts to deltas

Presenter tools:
- `get_today_news()` for six fixed categories
- `custom_domain_search(domain)` for topic mode

### 1.8 Validation rules at API boundary

Pydantic request models enforce:
- `message` max 4000 chars
- `query` max 200 chars
- `history` max 40 turns
- history turn roles only: `user` or `assistant`
- empty/whitespace strings rejected (normalized with `.strip()`)
- extra fields forbidden (`extra="forbid"`)

Practical impact:
- Overlong history/message/query fails with HTTP 422 before agent logic runs.

### 1.9 Local run and prewarm flow

Local backend run command (from repo root):
- `uvicorn main:app --app-dir backend --host 0.0.0.0 --port 8000`

Local frontend in dev calls `/api/*` via Next rewrite to `localhost:8000`.

Local prewarm scripts:
- `scripts/prewarm_cache.sh` calls:
  - `/api/news?lang=en&refresh=true`
  - `/api/news?lang=zh&refresh=true`
- `scripts/install_cron.sh` can install host cron for daily prewarm.

### 1.10 Legacy file status (`router.py`)

`router.py` contains an older LLM-router design that classifies intent/language and dispatches to one of four agents.  
Current FastAPI backend does not call this router. Routing is direct in endpoints:
- `/api/chat` -> QA modules
- `/api/news-search` -> presenter modules

Treat `router.py` as reference/legacy unless explicitly reintroduced.

### 1.11 Operational constraints and caveats

- In-memory cache is per process and ephemeral.
  - Restart clears it.
  - Multi-instance deployments do not share cache.
- Background refresh only runs after cache hit; no cron inside backend process itself.
- Presenter modules use module-level mutable `today_news` dict.
  - This can be shared across concurrent calls in the same process.
- Backend and root modules each create OpenAI clients independently.
- Some requests are network-heavy and can be slow:
  - NewsAPI fetch + LLM structuring
  - Brave search + multi-page scraping + final LLM generation

## 2) How It Works in AWS (Short Version)

### 2.1 Service mapping

- Backend API container (`backend/Dockerfile`) -> ECR + App Runner (`newsfeed-api`)
- Frontend static export -> S3 + CloudFront
- `/api/*` routing -> CloudFront behavior to App Runner origin
- Daily prewarm -> Lambda (`newsfeed-prewarm`) + EventBridge schedule (`newsfeed-prewarm-7am`)

### 2.2 Runtime request path

1. User loads CloudFront domain.
2. Non-API paths served from S3 static frontend.
3. API paths `/api/*` forwarded by CloudFront to App Runner.
4. App Runner runs same FastAPI app and same root agent modules as local.

### 2.3 AWS-specific points from deployment docs

- App Runner env vars include:
  - `OPENAI_API_KEY`, `NEWS_API_KEY`, `BRAVE_API_KEY`, `CORS_ORIGINS`
- CORS is set to CloudFront/custom domain in App Runner config.
- CloudFront API behavior is configured with caching disabled for API paths.
- Deployed prewarm URLs include `refresh=true` for both languages.
- Phase structure in repo scripts:
  - Phase A: backend build/push/deploy
  - Phase B: frontend build/upload/CloudFront routing + CORS update
  - Phase C: prewarm Lambda + schedule + alarms
  - Phase D: optional private S3 + OAC hardening

### 2.4 Production parity with local

Backend logic is the same code in both environments.  
Major difference is network edge/routing:
- Local: Next dev rewrite proxies `/api/*` to FastAPI
- AWS: CloudFront path behavior routes `/api/*` to App Runner

