# AWS Deployment Handoff (Past + Future)

This document is the single handoff for how this project was deployed on AWS in the past, and how deployment should be done going forward.

Context sources used:
- `PLAN.md`
- `FRONTEND_DOCUMENTATION.md`
- `BACKEND_DOCUMENTATION.md`
- `AWSDeployment.md` (initial recommended plan)
- `AWSDeployment2.md` (executed delta release)
- `scripts/` (phase automation and helper scripts)

## 0) Concise Service Summary (What each service does and how they connect)

| Service | Purpose | Connected to |
|---|---|---|
| CloudFront | Public entrypoint/domain for UI + API routing | Sends UI paths to S3 frontend origin and `/api/*` to App Runner |
| S3 | Stores static frontend export (`frontend/out`) | Frontend origin behind CloudFront |
| App Runner | Runs backend FastAPI container on port 8000 | Receives `/api/news`, `/api/chat`, `/api/news-search` via CloudFront |
| ECR | Stores backend Docker images | App Runner pulls image from ECR |
| Lambda (`newsfeed-prewarm`) | Daily warm-up of backend news cache | Calls CloudFront `/api/news?lang=en|zh&refresh=true` |
| EventBridge Scheduler | Triggers Lambda on schedule | Invokes prewarm Lambda daily |
| CloudWatch Alarms | Monitors Lambda/App Runner failures and latency | Optional SNS notifications |
| IAM Roles/Policies | Permissions for App Runner pull, Lambda execute, Scheduler invoke | Used by App Runner, Lambda, Scheduler |

Request flow:
1. User opens CloudFront domain.
2. CloudFront serves frontend static files from S3.
3. Frontend calls relative `/api/*`.
4. CloudFront forwards `/api/*` to App Runner backend.
5. Backend handles news/chat/search and streams SSE responses for chat endpoints.
6. Scheduler invokes prewarm Lambda daily so cache is ready before users arrive.

## 1) How deployment was done in the past

## Past Deployment #1 (initial architecture rollout)

The first deployment strategy (documented in `AWSDeployment.md` and implemented via scripts) used a phased rollout:

1. Phase A: backend on App Runner from ECR image.
2. Phase B: frontend static export to S3 + CloudFront routing `/api/*` to App Runner.
3. Phase C: prewarm Lambda + daily EventBridge schedule + alarms.
4. Phase D (later hardening): move from public S3 website origin to private S3 + CloudFront OAC.

Important implementation details from scripts:
- Backend image build, smoke test, push, and App Runner create/update are automated in `scripts/aws_phase_a/`.
- Initial frontend setup in `scripts/aws_phase_b/20_create_s3_and_upload.sh` uses public S3 website hosting.
- CloudFront `/api/*` behavior is explicitly repaired by `scripts/aws_phase_b/35_fix_cloudfront_api_routing.sh` to avoid API requests being routed to S3.
- App Runner CORS is updated after CloudFront creation via `scripts/aws_phase_b/50_update_backend_cors.sh`.
- Phase C defaults prewarm URLs to `refresh=true` for both `en` and `zh`.

## Past Deployment #2 (executed bug-fix release)

`AWSDeployment2.md` records the delta release that updated existing resources in place.

Scope deployed:
1. News anti-cache + forced refresh path.
2. Explain-card scroll anchoring fix.
3. Inline summary typography adjustment.

Scripts actually used:
1. Phase A update:
   - `scripts/aws_phase_a/10_build_image.sh`
   - `scripts/aws_phase_a/20_push_ecr.sh`
   - `scripts/aws_phase_a/40_deploy_apprunner.sh`
   - `scripts/aws_phase_a/50_wait_and_verify.sh`
2. Phase B update (Phase D-safe):
   - `scripts/aws_phase_b/10_build_frontend.sh`
   - `scripts/aws_phase_b/25_sync_private_s3_and_invalidate.sh`
3. Phase C update:
   - `scripts/aws_phase_c/20_create_or_update_prewarm_lambda.sh`
   - `scripts/aws_phase_c/50_verify_phase_c.sh`

Operational notes from this release:
- Lambda update script was hardened to handle `ResourceConflictException` with wait/retry.
- Prewarm Lambda env values were verified to include `refresh=true` URLs.
- No teardown/recreation; App Runner, CloudFront, S3, Lambda, and schedule were updated in place.

## 2) How deployment should be done in the future

Use this as the default future standard.

## A. First-time environment bootstrap

1. Run Phase A fully:
   - `scripts/aws_phase_a/run_all.sh`
2. Run Phase B fully:
   - `scripts/aws_phase_b/run_all.sh`
3. Run Phase C fully:
   - `scripts/aws_phase_c/run_all.sh`
4. Immediately harden frontend origin (recommended production baseline):
   - `scripts/aws_phase_d/run_all.sh`

Why:
- This sequence creates a working stack first, then hardens S3 access with OAC.
- It aligns with existing, tested repo automation and avoids manual AWS console drift.

## B. Routine release (most common)

1. Backend changes only:
   - `scripts/aws_phase_a/10_build_image.sh`
   - `scripts/aws_phase_a/20_push_ecr.sh`
   - `scripts/aws_phase_a/40_deploy_apprunner.sh`
   - `scripts/aws_phase_a/50_wait_and_verify.sh`
2. Frontend changes only:
   - `scripts/aws_phase_b/10_build_frontend.sh`
   - `scripts/aws_phase_b/25_sync_private_s3_and_invalidate.sh`
3. Prewarm/ops changes:
   - `scripts/aws_phase_c/20_create_or_update_prewarm_lambda.sh`
   - `scripts/aws_phase_c/30_create_or_update_schedule.sh` (if schedule changed)
   - `scripts/aws_phase_c/40_create_cloudwatch_alarms.sh` (if alarms changed)
   - `scripts/aws_phase_c/50_verify_phase_c.sh`

## C. Guardrails to follow every time

1. Keep frontend API calls as relative `/api/*`; CloudFront owns routing split.
2. Keep API caching disabled at CloudFront behavior and backend response headers.
3. Keep prewarm URLs as:
   - `.../api/news?lang=en&refresh=true`
   - `.../api/news?lang=zh&refresh=true`
4. Treat Phase D as default security posture (private S3 + OAC), not optional.
5. Prefer script-driven updates instead of console edits to reduce config drift.

## 3) Useful scripts (quick index)

## Build and deploy backend

- `scripts/aws_phase_a/run_all.sh`: full backend deployment.
- `scripts/aws_phase_a/10_build_image.sh`: build and local smoke test container.
- `scripts/aws_phase_a/20_push_ecr.sh`: push image to ECR.
- `scripts/aws_phase_a/40_deploy_apprunner.sh`: create/update App Runner service.
- `scripts/aws_phase_a/50_wait_and_verify.sh`: wait for RUNNING and endpoint checks.

## Build and deploy frontend

- `scripts/aws_phase_b/run_all.sh`: full frontend + CloudFront routing setup.
- `scripts/aws_phase_b/10_build_frontend.sh`: static export build (`NEXT_STATIC_EXPORT=1`).
- `scripts/aws_phase_b/20_create_s3_and_upload.sh`: initial public S3 website setup.
- `scripts/aws_phase_b/25_sync_private_s3_and_invalidate.sh`: fast sync for existing private-S3/OAC deployments.
- `scripts/aws_phase_b/35_fix_cloudfront_api_routing.sh`: force-correct `/api/*` behavior.
- `scripts/aws_phase_b/50_update_backend_cors.sh`: sync App Runner `CORS_ORIGINS` with CloudFront domain.

## Prewarm, schedule, monitoring

- `scripts/aws_phase_c/run_all.sh`: full prewarm/schedule/alarm rollout.
- `scripts/aws_phase_c/20_create_or_update_prewarm_lambda.sh`: update Lambda code/config.
- `scripts/aws_phase_c/30_create_or_update_schedule.sh`: update EventBridge schedule/timezone.
- `scripts/aws_phase_c/40_create_cloudwatch_alarms.sh`: create/update alarms.
- `scripts/aws_phase_c/50_verify_phase_c.sh`: invoke Lambda and validate state.

## Security hardening

- `scripts/aws_phase_d/run_all.sh`: migrate/confirm private S3 + OAC posture.
- `scripts/aws_phase_d/20_update_cloudfront_to_oac.sh`: switch frontend origin to S3 REST + OAC.
- `scripts/aws_phase_d/30_lock_s3_bucket.sh`: restrict bucket policy to CloudFront and block public access.

## Local-only prewarm helpers

- `scripts/prewarm_cache.sh`: prewarm local backend cache.
- `scripts/install_cron.sh`: install local 7am cron job.
- `scripts/README_CRON.md`: local cron operating notes.

## 4) Recommended operating model for humans and LLMs

1. Identify change type first: backend, frontend, prewarm/ops, or security.
2. Use the smallest matching script set from Section 3.
3. Preserve runtime artifacts in `scripts/aws_phase_*/.runtime/` during a run.
4. Verify via CloudFront URL, not only direct App Runner URL.
5. If API routing breaks, run `scripts/aws_phase_b/35_fix_cloudfront_api_routing.sh` and re-verify.

This repo now has a clear separation:
- Architecture intent in docs.
- Actual deployment automation in scripts.
- This handoff file as the bridge between past execution and future standard practice.
