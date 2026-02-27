# Frontend Documentation (Current State)

This document describes how the frontend currently works, based on:
- `frontend/app/`
- `frontend/components/`
- `frontend/lib/sse.ts`
- `frontend/types.ts`
- `frontend/next.config.ts`
- Frontend build/deploy behavior used by AWS scripts

Scope: current behavior, not planned behavior.

## 1) How Frontend Works Locally

### 1.1 Runtime stack and boundaries

- Framework: Next.js App Router (`next` 16.1.6)
- UI runtime: React 19 client components
- Styling: Tailwind CSS v4 + utility classes
- Markdown rendering for streamed answers: `react-markdown` + `remark-gfm`
- Frontend talks to backend only through relative `/api/*` paths

Key boundary:
- Frontend never calls OpenAI/NewsAPI/Brave directly.
- All model/search/news logic is backend-owned.

### 1.2 Core file map

- App shell:
  - `frontend/app/layout.tsx`
  - `frontend/app/page.tsx`
  - `frontend/app/globals.css`
- Main feed and cards:
  - `frontend/components/NewsFeed.tsx`
  - `frontend/components/NewsCard.tsx`
  - `frontend/components/InlineExplain.tsx`
- Chatbot area:
  - `frontend/components/ChatbotCard.tsx`
  - `frontend/components/ToolSelector.tsx`
  - `frontend/components/FollowUpBar.tsx`
  - `frontend/components/StreamedResponse.tsx`
- SSE parser:
  - `frontend/lib/sse.ts`
- Shared types:
  - `frontend/types.ts`

### 1.3 Top-level state model (`app/page.tsx`)

The page owns shared cross-component state:
- `lang`: `"en"` or `"zh"`
- `expandedArticleIndex`: which news card is expanded
- `isStreaming`: global stream lock across explain/chat flows
- `history`: shared conversation history sent to backend
- `followUpMessage`: queued follow-up text for inline explain

Important behavior:
- Language switch resets:
  - `history`
  - `expandedArticleIndex`
  - `followUpMessage`
  - `isStreaming`
- `onComplete` appends user+assistant turns to shared `history`.

### 1.4 News loading flow (`NewsFeed.tsx`)

When `lang` changes, frontend fetches:
- `GET /api/news?lang=${lang}&_ts=${Date.now()}`
- fetch option: `{ cache: "no-store" }`

UI states handled:
- loading skeleton
- error + retry button (full page reload)
- empty categories message
- normal category/article rendering

Article indexing:
- `articleIndex` is flattened across all categories.
- Expand/collapse uses this flattened index (`expandedArticleIndex`), not per-category index.

### 1.5 News card interaction (`NewsCard.tsx`)

Each card shows:
- category label
- title/summary
- published + source link
- image (or fallback icon)
- “Explain” circular button

Explain click behavior:
1. Capture current card top position.
2. Trigger parent `onExplain`.
3. On next frame, calculate vertical shift and scroll by delta.

Purpose:
- keeps clicked card visually anchored when inline explanation expands and layout shifts.

### 1.6 Inline explanation flow (`InlineExplain.tsx`)

When mounted for an expanded card:
1. Builds message:
   - `Tell me more about this article: {title}. URL: {url}`
2. `POST /api/chat` with:
   - `message`
   - shared `history`
   - `lang`
3. Parses SSE stream using `streamSseDeltas`.
4. Renders streamed markdown in `StreamedResponse`.
5. On finish, pushes turn pair into shared global history via `onComplete`.

Follow-up flow:
- Follow-up bar submits text to parent (`onFollowUpSubmit`).
- Parent sets `followUpMessage`.
- `InlineExplain` listens for that value and sends another `POST /api/chat`.
- It prefixes the visible output with a quoted follow-up block, then appends streamed answer.
- On completion, adds follow-up turn pair to shared history and clears queued follow-up.

Streaming coordination:
- Uses both local streaming state and parent global streaming state.
- Aborts fetch on unmount with `AbortController`.
- Ensures `onStreamEnd` is called exactly once per stream via guard ref.

### 1.7 Chatbot flow (`ChatbotCard.tsx`)

Chatbot has three modes via `ToolSelector`:

- Default (`selectedTool = null`)
  - endpoint: `POST /api/chat`
  - payload message: raw user text

- Internet search (`selectedTool = "web_search"`)
  - endpoint: `POST /api/chat`
  - payload message: `Search the web: {userText}`

- Search topics (`selectedTool = "show_news"`)
  - endpoint: `POST /api/news-search`
  - payload: `{ query, lang, history }`

Common behavior:
- Disables submit while global/local stream is active.
- Shows user bubble immediately.
- Streams assistant response into temporary `streamingContent`.
- On completion:
  - appends assistant message to local chatbot transcript
  - appends user+assistant pair to shared global history via `onComplete`

Important separation:
- Chatbot stores its own visible transcript (`messages`) locally.
- Backend context uses shared page-level `history`.

### 1.8 SSE parsing contract (`lib/sse.ts`)

`streamSseDeltas(response, onDelta)`:
- Validates HTTP status and body presence.
- Reads stream incrementally from `response.body.getReader()`.
- Processes lines prefixed by `data: `.
- Handles payloads:
  - `[DONE]` -> stop and return
  - `{"delta":"..."}` -> append delta and call callback
  - `{"error":"..."}` -> throw error
- Ignores malformed partial JSON chunks safely.

### 1.9 Markdown rendering (`StreamedResponse.tsx`)

- Renders assistant content through `ReactMarkdown`.
- Supports GFM tables/lists/etc via `remark-gfm`.
- Applies custom styled components for headings, text, links, blockquotes, images.
- Shows:
  - localized loading label when stream started but no content yet
  - trailing pulse cursor while streaming

### 1.10 Type contracts (`types.ts`)

Shared frontend contracts:
- `Article`, `Category`, `NewsResponse`
- `Lang = "en" | "zh"`
- `ChatMessage = { role: "user" | "assistant"; content: string }`
- `ToolType = "show_news" | "web_search"`

### 1.11 Local API proxy and runtime config (`next.config.ts`)

Two modes:

- Default local dev mode (`NEXT_STATIC_EXPORT` not `1`):
  - rewrites `/api/:path*` -> `http://localhost:8000/api/:path*`

- Static export mode (`NEXT_STATIC_EXPORT=1`):
  - `output: "export"`
  - images unoptimized
  - no local rewrite

Also enabled in config:
- `experimental.proxyTimeout = 120000` for long backend calls.

### 1.12 Local run shape

Typical local run:
1. Start backend on `:8000`
2. Run frontend:
   - `cd frontend`
   - `npm run dev`
3. Browser uses Next dev server on `:3000`
4. Next rewrites frontend `/api/*` calls to backend `:8000`

### 1.13 Current frontend constraints/caveats

- Frontend does not trim history/message sizes before sending.
  - Backend validation limits can return HTTP 422 for oversized payloads.
- Chatbot local transcript is component-local state and not synchronized from global `history`.
- `layout.tsx` metadata is still default (`Create Next App` title/description).
- Dark mode styles exist in many classes, but theme is system-CSS driven (`prefers-color-scheme`) rather than explicit app toggle.

## 2) How Frontend Works in AWS (Short Version)

### 2.1 Hosting translation

- Frontend is built as static export (`NEXT_STATIC_EXPORT=1 npm run build -- --webpack`).
- Output is `frontend/out/`.
- Static assets/pages are uploaded to S3 and served through CloudFront.

### 2.2 API routing in production

- Frontend code still uses relative `/api/*`.
- In AWS, Next dev rewrite is not used.
- CloudFront behavior routes `/api/*` to App Runner backend origin.
- Non-API routes stay on S3 origin.

### 2.3 Practical result

Frontend runtime logic (state, components, streaming parser) remains the same.  
Main production difference is edge routing:
- Local: Next.js rewrite proxies API to `localhost:8000`
- AWS: CloudFront routes API paths to App Runner

