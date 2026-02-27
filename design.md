# Design Review

Scope: Is the current backend and frontend code in decent shape to learn from as-is, or does it need structural fixes first?

Short answer: **Yes, it's worth learning from. The core patterns are real and well-applied. There are a handful of genuine design flaws, but none that would mislead you about how the pieces fit together.**

---

## Backend

### What is genuinely well-designed

**1. Clear module boundaries**

Three distinct concerns, three distinct modules:
- `backend/main.py` — HTTP routing, request validation, cache management, SSE emission
- `question_answer.py` — QA agent logic (probe, evaluate, rerun, tool execution, streaming)
- `presenter.py` — News fetching and formatting agent

Each module does one job. The FastAPI layer calls into the agents; the agents don't know about HTTP. That's a clean separation.

**2. Input validation at the API boundary**

`main.py` uses Pydantic to reject bad inputs before any LLM call runs:
- Per-role content length limits (`user` max 4000 chars, `assistant` max 16000)
- History capped at 40 turns
- Empty/whitespace strings rejected and stripped
- Extra fields forbidden (`extra="forbid"`)

This is the right place to validate. The agents themselves don't need to defensively re-check these.

**3. Stale-while-revalidate cache pattern**

The `/api/news` cache works like this: if a cached entry exists, return it immediately and schedule a background refresh. If nothing is cached, block and fetch. This is a real production pattern — users pay the wait cost only on cold start, not on every request. The `is_refreshing` flag correctly prevents parallel refreshes from piling up.

**4. Two-phase LLM agent pattern (probe → act)**

The QA agent doesn't go straight to streaming. It first makes a non-streaming "probe" call to decide if tools are needed, then either:
- Skips tools and streams directly (fast path)
- Runs the evaluator gate, possibly reruns, executes tools, then streams

This probe → evaluate → act → stream structure is a standard pattern for tool-using LLM agents. Understanding it here translates directly to production agentic systems.

**5. Evaluator gate**

The evaluator is a separate LLM call with a focused job: check whether the main agent's tool call decision violates a specific rule (don't use `visit_website` for paywalled sources). Using a structured output (`Evaluation(is_acceptable, feedback)`) and a one-shot rerun is a practical pattern — not a full multi-agent framework, but enough to catch a defined class of errors. The `rerun` injects the failure reason into the system prompt so the agent can self-correct.

**6. Parallel async scraping**

`find_internet_articles` fetches multiple URLs concurrently with `asyncio.gather`. This cuts wall-clock time roughly in proportion to the number of URLs. The error handling wraps each individual fetch so one failure doesn't abort the whole batch.

**7. Structured outputs for news cards**

Using OpenAI's strict JSON schema mode (`response_format: json_schema, strict: true`) for the news card LLM call is the right approach. It guarantees the model produces valid JSON matching the exact shape the frontend expects, without needing post-processing guards. The schema itself is well-typed (nullable image field handled with `anyOf`).

---

### Where the design has real problems

**1. Module-level mutable `today_news` dict — race condition**

In `presenter.py`:
```python
today_news = {}  # shared mutable module-level state

def extract_news(urls):
    today_news.clear()  # <-- dangerous with concurrent requests
    for category, url in urls.items():
        ...
        today_news[category] = formatted_json
```

If two requests call `custom_domain_search` at the same time, both call `today_news.clear()` and overwrite each other's entries. One request could read the other's data. For a low-traffic personal project this rarely triggers, but it's a real bug worth knowing about. The fix would be to make `today_news` a local variable returned from `extract_news` rather than a global.

**2. `asyncio.run()` inside a FastAPI request**

`lookup_news` calls `asyncio.run(_lookup_news_async(url))`. FastAPI's async endpoints run inside an existing event loop. Normally, calling `asyncio.run()` from inside an already-running event loop raises a `RuntimeError`. This works here only because `event_generator()` is a **synchronous** generator, which FastAPI runs in a thread pool (not directly on the event loop). So it accidentally works, but it's fragile: if the execution context ever changes (e.g., if the generator becomes async), it silently breaks. The cleaner fix would be to use `asyncio.get_event_loop().run_until_complete()` or restructure the generator to be async from the start.

**3. System prompt built by string concatenation**

The QA system prompt (`question_answer.py:218–390`) is built by 30+ lines of `+=` appends. It works, but it's hard to read, hard to edit without breaking something, and mixes structural instructions with multi-paragraph examples. A docstring or f-string template would be easier to maintain. This is not a bug — it's a maintainability issue.

**4. `print()` instead of `logging` in agent modules**

`main.py` correctly uses `logging.getLogger(__name__)`. The agent modules (`question_answer.py`, `presenter.py`) use bare `print()` calls. In production, `print()` output doesn't show timestamps, log levels, or module names, and can't be routed to log aggregators. Not wrong, just inconsistent and something to change if you ever need to debug in production.

**5. Multiple independent OpenAI clients**

`main.py`, `question_answer.py`, `question_answer_zh.py`, `presenter.py`, and `presenter_zh.py` each create their own `OpenAI()` client at module load time. This is five separate connection pools. Functionally fine, but wasteful. A single shared client passed in (or a module-level singleton in one place) would be cleaner.

**6. `router.py` is dead code**

`router.py` contains an older intent-routing design. It is not imported or called by `main.py`. It's safe to ignore completely — treat it as a historical artifact.

---

### Backend design verdict

The core patterns — request validation, cache strategy, probe/evaluate/act/stream flow, structured outputs — are solid and real. The race condition in `presenter.py` is the one genuine architectural flaw, but it only matters under concurrent load. You can learn the patterns confidently. Just know that the `today_news` global is a bug waiting to surface.

---

## Frontend

### What is genuinely well-designed

**1. State lifted to the right level**

`page.tsx` owns the cross-component shared state:
- `lang` — drives both feed and chat
- `history` — shared context sent to the backend for all AI calls
- `isStreaming` — global lock to prevent overlapping streams
- `expandedArticleIndex` — which card is open
- `followUpMessage` — queued follow-up text

Components receive exactly what they need. Neither `NewsFeed` nor `InlineExplain` nor `ChatbotCard` own state that should be shared. This is React's "lift state up" principle applied correctly.

**2. `useRef` for history capture**

Both `InlineExplain` and `ChatbotCard` use:
```typescript
const historyRef = useRef(history);
useEffect(() => { historyRef.current = history; }, [history]);
```
Then they read `historyRef.current` inside fetch calls. This avoids a stale closure problem: if the component captured `history` from its render closure, it would send the history as it was when the effect mounted, not as it is when the fetch fires. The ref always holds the latest value without causing the effect to re-run. This is a non-obvious React pattern and it's used correctly here.

**3. `AbortController` + `streamEndedRef` guard in `InlineExplain`**

When `InlineExplain` unmounts (e.g., user collapses the card), the cleanup function aborts the in-flight fetch. The `streamEndedRef` flag ensures `onStreamEnd()` is called exactly once — either when the stream completes or when the component unmounts, never both. This prevents the parent's `isStreaming` from getting stuck in a wrong state.

**4. SSE parsing extracted to `lib/sse.ts`**

The streaming parser is a pure function that takes a `Response` and returns a `Promise<{accumulated, receivedDone}>`. It has no React dependencies and is independently testable — which is exactly why the frontend tests can test it in isolation without a browser. Good separation.

**5. `types.ts` as shared contracts**

All data shapes used across components (`Article`, `Category`, `NewsResponse`, `ChatMessage`, `Lang`, `ToolType`) are defined once in `types.ts`. No duplication, no implicit type inference from API responses. Clean.

**6. Language reset**

`handleLangChange` in `page.tsx` resets history, streaming state, expanded card, and follow-up in one atomic operation. This prevents stale state leaking across language switches (e.g., an English conversation history being sent to the Chinese backend).

**7. Two-mode config**

`next.config.ts` handles local dev (rewrite `/api/*` to `localhost:8000`) and production static export (`NEXT_STATIC_EXPORT=1`) with one env var. The proxy timeout (`proxyTimeout: 120000`) is a practical choice given how long Brave search + multi-URL scraping can take.

---

### Where the design has real problems

**1. `articleIndex++` mutation during render**

In `NewsFeed.tsx`:
```typescript
let articleIndex = 0;
return (
  <div>
    {data.categories.map((category) => (
      ...
      {category.articles.map((article) => {
        const currentIndex = articleIndex++;  // mutated during render
```

React renders can be invoked more than once (especially in Strict Mode's double-invocation for detecting side effects). Mutating a variable during render breaks the rule that renders should be pure. In this codebase it works in practice because the production build doesn't double-invoke, but it's a latent bug. The safer approach is to pre-compute a flat `{article, globalIndex}` list before the JSX return.

**2. No `AbortController` in `ChatbotCard`**

`InlineExplain` correctly aborts its fetch on unmount. `ChatbotCard` does not. If a user sends a message and then navigates away while streaming, the request continues running in the background until it completes or times out. Low impact for a personal project but worth knowing.

**3. Prop drilling through `NewsFeed`**

`page.tsx` passes 10 props to `NewsFeed`, which passes most of them down to `InlineExplain` and `ChatbotCard`. `NewsFeed` itself only uses a few of them directly (`lang`, `expandedArticleIndex`, `isStreaming`). The rest are passed through unmodified. For the current scale this is fine, but if the component tree grows it becomes a maintenance issue. Context or a custom hook could flatten this.

**4. `key={i}` for chatbot messages**

```typescript
{messages.map((msg, i) => (
  <div key={i} ...>
```

Using array index as key works here because messages only ever append (never insert or delete at earlier positions). But React's key reconciliation relies on stable keys. If the messages list ever gains a "clear history" feature, index keys would cause incorrect DOM reuse. Not a current bug, but a footgun for future changes.

**5. `layout.tsx` still has default metadata**

The page title and description are still `Create Next App`. Not a design flaw, but if this ever goes public it should be updated.

---

### Frontend design verdict

The state management design is genuinely solid — the ref-based history capture, streaming lock, abort-on-unmount, and lifted state are all correct and non-trivial patterns. The main issue is the `articleIndex` mutation during render, which is technically wrong even though it works. Everything else is either minor or cosmetic.

---

## Overall Verdict

| Area | Quality | Can you learn from it? |
|---|---|---|
| API validation (Pydantic) | Good | Yes |
| Cache strategy | Good | Yes |
| LLM agent probe/act pattern | Good | Yes |
| Evaluator gate | Good | Yes |
| Structured JSON outputs | Good | Yes |
| Async parallel scraping | Good | Yes |
| React state lifting | Good | Yes |
| `useRef` for stale closure prevention | Good | Yes |
| AbortController on unmount | Good (InlineExplain) | Yes |
| SSE parsing | Good | Yes |
| `today_news` global mutation | Bug | Know it's a flaw |
| `asyncio.run()` inside FastAPI | Fragile | Know why it works |
| `articleIndex++` during render | Technically wrong | Know it's a flaw |
| System prompt concatenation | Messy style | Just read it carefully |
| No AbortController in ChatbotCard | Minor | Note the gap |

**Bottom line:** The code is shaped by a developer who understood the domain problems (streaming, tool-using agents, caching, React state coordination) even if the implementation has rough edges. The patterns are real. The flaws are real too, but they are well-contained — none of them would cause you to mislearn a concept. You can read this code, understand it, and use it as a reference for how these pieces fit together.

The one caveat worth keeping in mind: `presenter.py`'s module-level `today_news` dict is a concurrency bug, not a stylistic choice. Don't copy that pattern.
