# AWS Phase A Scripts (Backend to App Runner)

These scripts let you deploy backend Phase A in small debug-friendly steps.

## One-time setup

1. Put keys in repo root `.env`:
   - `OPENAI_API_KEY`
   - `NEWS_API_KEY`
   - `BRAVE_API_KEY`
2. Make sure AWS CLI is configured (`aws configure`).
3. From repo root, make scripts executable:

```bash
chmod +x scripts/aws_phase_a/*.sh
```

## Run step-by-step

```bash
./scripts/aws_phase_a/00_prepare.sh
./scripts/aws_phase_a/10_build_image.sh
./scripts/aws_phase_a/20_push_ecr.sh
./scripts/aws_phase_a/30_prepare_iam_role.sh
./scripts/aws_phase_a/40_deploy_apprunner.sh
./scripts/aws_phase_a/50_wait_and_verify.sh
```

## Run all steps

```bash
./scripts/aws_phase_a/run_all.sh
```

## Debug tips

- Verbose shell tracing:

```bash
DEBUG=1 ./scripts/aws_phase_a/20_push_ecr.sh
```

- Skip local smoke test (if local port conflict):

```bash
SKIP_SMOKE_TEST=1 ./scripts/aws_phase_a/10_build_image.sh
```

- Change smoke test port:

```bash
SMOKE_TEST_PORT=19000 ./scripts/aws_phase_a/10_build_image.sh
```

## Useful runtime files

Generated under `scripts/aws_phase_a/.runtime/`:

- `context.env` (resolved non-secret context)
- `service_arn.txt`
- `service_url.txt`
- create/update payload JSON files
