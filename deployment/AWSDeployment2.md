# AWS Deployment Delta (Executed)

This file records what was actually deployed for the bug-fix release, based on `AWSDeployment.md`.

## Architecture (unchanged)

- Frontend: **S3 + CloudFront**
- Backend: **App Runner** (`newsfeed-api`)
- Prewarm: **Lambda** (`newsfeed-prewarm`) + **EventBridge** (`newsfeed-prewarm-7am`)

## Scope deployed

1. Bug 1 (stale news): deployed
- `/api/news` anti-cache headers + `refresh=true`
- Prewarm URLs updated to include `refresh=true`

2. Bug 2 (Explain This scroll jump): deployed
- Frontend card anchor-based scroll correction

3. Bug 3 (inline LLM summary text size): deployed
- Larger proportional typography in inline markdown response

Note:
- Search Topics placeholder copy update was intentionally not included in deployment scope.

## Scripts used

1. Phase A (backend update)
```bash
./scripts/aws_phase_a/10_build_image.sh
./scripts/aws_phase_a/20_push_ecr.sh
APP_RUNNER_CORS_ORIGINS="https://dvabg4443rdrf.cloudfront.net" ./scripts/aws_phase_a/40_deploy_apprunner.sh
./scripts/aws_phase_a/50_wait_and_verify.sh
```

2. Phase B (frontend update, Phase D-safe path)
```bash
./scripts/aws_phase_b/10_build_frontend.sh
CLOUDFRONT_DOMAIN="dvabg4443rdrf.cloudfront.net" ./scripts/aws_phase_b/25_sync_private_s3_and_invalidate.sh
```

3. Phase C (prewarm Lambda update)
```bash
CLOUDFRONT_DOMAIN="dvabg4443rdrf.cloudfront.net" ./scripts/aws_phase_c/20_create_or_update_prewarm_lambda.sh
CLOUDFRONT_DOMAIN="dvabg4443rdrf.cloudfront.net" ./scripts/aws_phase_c/50_verify_phase_c.sh
```

Operational note:
- `scripts/aws_phase_c/20_create_or_update_prewarm_lambda.sh` was updated to handle Lambda `ResourceConflictException` (wait/retry between code and config updates).

## Verification results

1. CloudFront API headers verified
- `cache-control: no-store, no-cache, must-revalidate, max-age=0, s-maxage=0`
- `pragma: no-cache`
- `expires: 0`

2. Forced refresh endpoint verified
- `GET /api/news?lang=en&refresh=true` returns `200`

3. Backend contract verified (App Runner OpenAPI)
- `/api/news` includes `refresh` query parameter

4. Prewarm Lambda verified
- `PREWARM_URL_EN` and `PREWARM_URL_ZH` include `refresh=true`
- Manual invoke returned `success: true` for both `en` and `zh`

5. UI manual checks verified
- Bug 2 fixed (no viewport jump)
- Bug 3 fixed (larger inline summary text)

## No teardown required

- No AWS service was taken down.
- Existing App Runner, CloudFront, S3, Lambda, and EventBridge resources were updated in place.
