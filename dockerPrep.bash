#!/usr/bin/env bash
set -euo pipefail

echo "dockerPrep.bash now points to the new step-based deploy scripts."
echo "Run one step at a time for easier debugging:"
echo "  ./scripts/aws_phase_a/00_prepare.sh"
echo "  ./scripts/aws_phase_a/10_build_image.sh"
echo "  ./scripts/aws_phase_a/20_push_ecr.sh"
echo "  ./scripts/aws_phase_a/30_prepare_iam_role.sh"
echo "  ./scripts/aws_phase_a/40_deploy_apprunner.sh"
echo "  ./scripts/aws_phase_a/50_wait_and_verify.sh"
echo
echo "Or run everything:"
echo "  ./scripts/aws_phase_a/run_all.sh"
echo
echo "Phase B (frontend + CloudFront) scripts are also available:"
echo "  ./scripts/aws_phase_b/00_prepare.sh ... ./scripts/aws_phase_b/60_invalidate_and_final_test.sh"
echo "  ./scripts/aws_phase_b/run_all.sh"
echo
echo "Phase C (prewarm + scheduler + alarms) scripts:"
echo "  ./scripts/aws_phase_c/00_prepare.sh ... ./scripts/aws_phase_c/50_verify_phase_c.sh"
echo "  ./scripts/aws_phase_c/run_all.sh"
echo
echo "Phase D (private S3 + CloudFront OAC hardening) scripts:"
echo "  ./scripts/aws_phase_d/00_prepare.sh ... ./scripts/aws_phase_d/40_wait_invalidate_and_verify.sh"
echo "  ./scripts/aws_phase_d/run_all.sh"
