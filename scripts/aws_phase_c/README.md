# AWS Phase C Scripts (Prewarm + Schedule + Monitoring)

These scripts complete Phase C from `AWSDeployment.md`:

1. Create/update prewarm Lambda.
2. Create/update daily EventBridge schedule (7am).
3. Create CloudWatch alarms for Lambda and App Runner.
4. Verify everything by invoking Lambda once.

## Prerequisites

1. Phase A and B are completed.
2. CloudFront URL works and `/api/news?lang=en` returns JSON.
3. AWS CLI configured.
4. Repo root `.env` exists.

By default, scripts auto-read CloudFront domain from:
`scripts/aws_phase_b/.runtime/distribution_domain.txt`

You can override explicitly:

```bash
CLOUDFRONT_DOMAIN=dvabg4443rdrf.cloudfront.net ./scripts/aws_phase_c/00_prepare.sh
```

## Run step-by-step

```bash
chmod +x scripts/aws_phase_c/*.sh

./scripts/aws_phase_c/00_prepare.sh
./scripts/aws_phase_c/10_create_lambda_role.sh
./scripts/aws_phase_c/20_create_or_update_prewarm_lambda.sh
./scripts/aws_phase_c/30_create_or_update_schedule.sh
./scripts/aws_phase_c/40_create_cloudwatch_alarms.sh
./scripts/aws_phase_c/50_verify_phase_c.sh
```

## Run all

```bash
./scripts/aws_phase_c/run_all.sh
```

## Optional overrides

- Change schedule time (24h format):
```bash
PREWARM_HOUR=7 PREWARM_MINUTE=0 PREWARM_TIMEZONE=America/Los_Angeles ./scripts/aws_phase_c/30_create_or_update_schedule.sh
```

- Use SNS for alarm notifications:
```bash
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:123456789012:my-alerts ./scripts/aws_phase_c/40_create_cloudwatch_alarms.sh
```

- Debug mode:
```bash
DEBUG=1 ./scripts/aws_phase_c/run_all.sh
```

## What gets created

- Lambda function: `newsfeed-prewarm` (default)
- Lambda IAM role: `NewsfeedPrewarmLambdaExecutionRole`
- Scheduler role: `NewsfeedSchedulerInvokeLambdaRole`
- Schedule: `newsfeed-prewarm-7am`
- CloudWatch alarms (prefix default `newsfeed-`)
