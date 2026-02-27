# Test Plan and Run Guide

## Why these tests exist

This suite covers the highest-risk logic identified in `PLAN2.md` and `code_review.md` section 4.2:

- Backend tool orchestration in `QA.chat()`:
  - Verifies paywalled `visit_website` attempts are rejected by evaluator flow and rerouted to `find_internet_articles`.
  - Verifies happy path (`visit_website` accepted), direct no-tool path, and direct `find_internet_articles` path.
- Backend integration around structured cards:
  - Verifies `fetch_news_cards()` calls the LLM in JSON schema mode, uses correct EN/ZH prompts, and fails on invalid JSON.
- Backend cache behavior:
  - Verifies cache hit scheduling, forced refresh branch, refresh failure recovery, and EN/ZH cache isolation.
- Frontend SSE streaming parser:
  - Verifies normal deltas, malformed chunks, backend error events, multi-event chunks, non-data lines, EOF-without-DONE handling, and HTTP errors.

## Test layout

- `Tests/backend/test_qa_orchestration_unit.py`
- `Tests/backend/test_fetch_news_cards_integration.py`
- `Tests/backend/test_cache_logic.py`
- `Tests/frontend/sse.unit.test.ts`
- `Tests/frontend/vitest.config.ts`

## How to run

These tests were created but intentionally not executed.

### Backend (pytest)

1. Install backend test dependency (if not installed):
   - `pip install pytest`
2. Run backend tests from project root:
   - `pytest Tests/backend -q`

### Frontend (Vitest)

1. Install frontend test dependency inside `frontend/`:
   - `cd frontend && npm install -D vitest`
2. Run frontend unit tests from project root:
   - `cd /Users/gonghanli/Project/llm_engineering/extras/NewsFeedProject`
   - `npx vitest run --config Tests/frontend/vitest.config.ts`

## Expected output

If everything passes:

- Backend command should end with a summary similar to:
  - `8 passed`
- Frontend command should end with a summary similar to:
  - `8 passed`

If there are regressions, pytest/vitest will print failed test names and assertion diffs for the specific behavior that changed.
