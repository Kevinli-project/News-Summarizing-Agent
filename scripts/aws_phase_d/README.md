# AWS Phase D Scripts (CloudFront + S3 Private Bucket with OAC)

This phase migrates your frontend hosting from:

- Public S3 website bucket + CloudFront custom origin

to:

- Private S3 bucket + CloudFront OAC (recommended production setup)

## What this changes

1. Creates/reuses CloudFront Origin Access Control (OAC).
2. Updates CloudFront frontend origin to S3 REST endpoint with OAC signing.
3. Restricts S3 bucket policy so only your CloudFront distribution can read objects.
4. Enables full S3 Block Public Access.
5. Disables S3 website hosting endpoint.
6. Invalidates CloudFront and verifies app/API still work.

## Prerequisites

1. Phase B and C completed.
2. CloudFront URL is working.
3. AWS CLI configured with permissions for CloudFront + S3 + IAM read.

## Run step-by-step

```bash
chmod +x scripts/aws_phase_d/*.sh

./scripts/aws_phase_d/00_prepare.sh
./scripts/aws_phase_d/10_create_or_get_oac.sh
./scripts/aws_phase_d/20_update_cloudfront_to_oac.sh
./scripts/aws_phase_d/30_lock_s3_bucket.sh
./scripts/aws_phase_d/40_wait_invalidate_and_verify.sh
```

## Run all

```bash
./scripts/aws_phase_d/run_all.sh
```

## Optional overrides

- Explicit CloudFront values:
```bash
CLOUDFRONT_DISTRIBUTION_ID=E123ABC456 \
CLOUDFRONT_DOMAIN=dvabg4443rdrf.cloudfront.net \
./scripts/aws_phase_d/run_all.sh
```

- Explicit bucket:
```bash
S3_BUCKET_NAME=newsfeed-frontend-975049984940-us-east-1 ./scripts/aws_phase_d/run_all.sh
```

## AWS Console checks after Phase D

1. CloudFront distribution:
   - Frontend origin uses S3 REST endpoint (`bucket.s3.<region>.amazonaws.com`)
   - Origin access control is attached
2. S3 bucket:
   - Block Public Access: all 4 settings enabled
   - Bucket policy principal is `cloudfront.amazonaws.com` with `AWS:SourceArn` for your distribution
   - Website hosting disabled
3. App still loads from CloudFront URL.
4. `/api/news?lang=en` still returns JSON via CloudFront.

## Rollback notes

Backups are saved to `scripts/aws_phase_d/.runtime/`:

- `bucket_policy_backup.txt`
- `bucket_website_backup.json`
- CloudFront config snapshots

You can manually restore these in AWS Console/CLI if needed.
