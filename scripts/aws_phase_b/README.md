# AWS Phase B Scripts (Frontend to S3 + CloudFront)

These scripts deploy your frontend and route `/api/*` through CloudFront to App Runner.

## What this phase does

1. Build static frontend export from `frontend/`.
2. Upload export files to S3.
3. Create CloudFront distribution:
   - Default origin: S3 website endpoint
   - `api/*` origin: App Runner backend
4. Force-correct CloudFront API behavior (`/api/*`) on existing distributions.
5. Update App Runner `CORS_ORIGINS` to the CloudFront domain.
6. Run end-to-end checks.

## Prerequisites

1. Phase A is done and App Runner backend is running.
2. Repo root `.env` exists with:
   - `OPENAI_API_KEY`
   - `NEWS_API_KEY`
   - `BRAVE_API_KEY`
3. AWS CLI configured and authenticated.
4. Node/npm available.

## One-time permission note (important)

These scripts make the S3 bucket publicly readable **for static website hosting**.
That is expected for this setup. If your account has organization-level S3 public access restrictions, Step 20 can fail and you must relax that policy in AWS admin settings.

## Run step-by-step

```bash
chmod +x scripts/aws_phase_b/*.sh

./scripts/aws_phase_b/00_prepare.sh
./scripts/aws_phase_b/10_build_frontend.sh
./scripts/aws_phase_b/20_create_s3_and_upload.sh
./scripts/aws_phase_b/30_create_cloudfront.sh
./scripts/aws_phase_b/35_fix_cloudfront_api_routing.sh
./scripts/aws_phase_b/40_wait_and_verify.sh
./scripts/aws_phase_b/50_update_backend_cors.sh
./scripts/aws_phase_b/60_invalidate_and_final_test.sh
```

## Run all steps

```bash
./scripts/aws_phase_b/run_all.sh
```

## Optional environment overrides

- Change S3 bucket name:
```bash
S3_BUCKET_NAME=my-newsfeed-frontend-bucket ./scripts/aws_phase_b/20_create_s3_and_upload.sh
```

- Change CloudFront price class:
```bash
CLOUDFRONT_PRICE_CLASS=PriceClass_All ./scripts/aws_phase_b/30_create_cloudfront.sh
```

- Debug shell output:
```bash
DEBUG=1 ./scripts/aws_phase_b/30_create_cloudfront.sh
```

## Runtime outputs

Generated under `scripts/aws_phase_b/.runtime/`:

- `context.env`
- `service_arn.txt`
- `apprunner_service_url.txt`
- `distribution_id.txt`
- `distribution_domain.txt`
