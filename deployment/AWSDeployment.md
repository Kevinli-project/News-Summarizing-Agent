# AWS Deployment Plan (Recommended for This Project)

## 1) Deployment choice and why

Use a **hybrid AWS setup**:

- **Backend API**: Dockerized FastAPI on **AWS App Runner** (same flow you used in `DeploymentDay5.md`).
- **Frontend**: Static Next.js export on **S3 + CloudFront** (services you already used before).
- **Daily cache prewarm**: **EventBridge Scheduler + Lambda** calling `/api/news?lang=en|zh` at 7am.

Why this fits best:

- Keeps your familiar App Runner + ECR workflow for Python backend.
- Uses your CloudFront/S3 knowledge for fast, low-cost frontend hosting.
- Avoids forcing chat SSE endpoints into API Gateway/Lambda timeouts.
- Requires only small, targeted code/config updates.

---

## 2) Target architecture

1. User opens `https://news.yourdomain.com` (CloudFront).
2. CloudFront serves static frontend files from S3.
3. Frontend calls `/api/*` on the same domain.
4. CloudFront behavior routes `/api/*` to App Runner backend origin.
5. App Runner serves:
   - `GET /api/news`
   - `POST /api/chat` (SSE)
   - `POST /api/news-search` (SSE)
6. EventBridge triggers Lambda daily at 7:00; Lambda calls:
   - `/api/news?lang=en`
   - `/api/news?lang=zh`

---

## 3) AWS services to create

1. **ECR repository**: `newsfeed-backend`
2. **App Runner service**: `newsfeed-api`
3. **S3 bucket**: `newsfeed-frontend-<account>-<region>`
4. **CloudFront distribution**:
   - Origin A: S3 bucket (default behavior)
   - Origin B: App Runner URL (`/api/*` behavior, all methods, no caching)
5. **Lambda function**: `newsfeed-prewarm`
6. **EventBridge schedule**: `newsfeed-prewarm-7am`
7. **CloudWatch logs + alarms**
8. **AWS Budgets** alerts ($1 / $5 / $10), same as Day 5

---

## 4) Minimal project changes before deploy

1. **Frontend static export**
   - In `frontend/next.config.ts`, set:
   - `output: "export"`
   - `images.unoptimized: true`
   - Remove dependency on dev-only rewrite for production.

2. **Keep frontend API calls as relative paths**
   - Keep `fetch("/api/...")` style so CloudFront path routing works.

3. **Backend CORS**
   - Set `CORS_ORIGINS` to your CloudFront/custom domain in App Runner env.
   - Example: `https://news.yourdomain.com`

4. **Add backend Dockerfile**
   - App Runner deploys backend container on port `8000`.
   - Health check path: `/`

---

## 5) Deployment steps (practical order)

## Phase A: Backend first (App Runner)

1. Build backend Docker image locally.
2. Push image to ECR `newsfeed-backend`.
3. Create App Runner service from ECR image.
4. Configure env vars in App Runner:
   - `OPENAI_API_KEY`
   - `NEWS_API_KEY`
   - `BRAVE_API_KEY`
   - `CORS_ORIGINS=https://news.yourdomain.com`
5. Verify:
   - `GET /` returns `{"status":"ok"}`
   - `GET /api/news?lang=en`
   - `POST /api/chat` streams correctly

## Phase B: Frontend (S3 + CloudFront)

1. Build frontend static files:
   - `cd frontend && npm run build`
2. Upload `frontend/out` to S3 bucket.
3. Create CloudFront distribution:
   - Default behavior -> S3
   - `/api/*` behavior -> App Runner backend origin
   - Disable caching on `/api/*`, allow `GET,HEAD,OPTIONS,PUT,POST,PATCH,DELETE`
4. Point custom domain to CloudFront (Route 53 optional).
5. Verify on CloudFront domain:
   - UI loads
   - Explain/follow-up/chat stream works
   - EN/ZH switch works

## Phase C: Prewarm and operations

1. Create Lambda (`newsfeed-prewarm`) that GETs:
   - `https://news.yourdomain.com/api/news?lang=en`
   - `https://news.yourdomain.com/api/news?lang=zh`
2. Schedule daily 7:00 with EventBridge Scheduler.
3. Add CloudWatch alarms:
   - App Runner 5xx count
   - App Runner high latency
   - Lambda errors
4. Keep min App Runner instances at `1` initially (cache behavior predictable, lower risk).

---

## 6) Why not API Gateway + Lambda for backend now

Current backend has long-running SSE endpoints (`/api/chat`, `/api/news-search`).  
App Runner handles this more naturally with less refactor. API Gateway/Lambda can be revisited later if you redesign streaming behavior.

---

## 7) Update workflow after initial launch

1. **Backend release**
   - Build new image -> push to ECR -> deploy new App Runner version.
2. **Frontend release**
   - `npm run build` -> sync `out/` to S3 -> CloudFront invalidation.
3. **Rollback**
   - Backend: redeploy previous ECR image tag.
   - Frontend: restore previous S3 artifact version and invalidate CloudFront.

---

## 8) Production checklist

1. Secrets configured only in App Runner/Lambda (not in repo).
2. `CORS_ORIGINS` set to production domain.
3. CloudFront `/api/*` behavior has caching disabled.
4. App Runner health check uses `/`.
5. 7am prewarm schedule active.
6. Budget alerts active.
7. CloudWatch alarms active.

