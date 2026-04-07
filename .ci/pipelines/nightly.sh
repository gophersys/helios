#!/usr/bin/env bash
# Pipeline: Nightly
# Full sweep — not affected-only. Catches upstream drift, dep rot, image staleness.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$DIR/lib/log.sh"

# Force NX_BASE to a very old commit so `affected` means "everything"
export NX_BASE="HEAD~100"

bash "$DIR/stages/env-check.sh"

log_stage "nightly — full lint"
npx nx run-many -t lint --all 2>&1 || true
log_stage_end

log_stage "nightly — full typecheck"
npx nx run-many -t typecheck --all 2>&1 || true
log_stage_end

log_stage "nightly — full test"
npx nx run-many -t test --all 2>&1 || true
log_stage_end

log_stage "nightly — full build"
npx nx run-many -t build --all -c staging 2>&1 || true
log_stage_end

log_stage "nightly — npm audit"
cd apps/frontend/app && npm audit --omit=dev 2>&1 || true
cd -
log_stage_end

log_stage "nightly — Python dependency audit"
bash "$DIR/stages/dep-audit.sh" 2>&1 || true
log_stage_end

log_stage "nightly — secret scan"
bash "$DIR/stages/secret-scan.sh" 2>&1 || true
log_stage_end

log_stage "nightly — container image scan"
bash "$DIR/stages/image-scan.sh" 2>&1 || true
log_stage_end

log_stage "nightly — Python type check"
bash "$DIR/stages/typecheck-python.sh" 2>&1 || true
log_stage_end

log_stage "nightly — dependency pinning check"
bash "$DIR/stages/dep-pin.sh" 2>&1 || true
log_stage_end

log_stage "nightly — integration tests"
bash "$DIR/stages/test-integration.sh" 2>&1 || true
log_stage_end

log_stage "nightly — devcontainer rebuild"
npx nx run devcontainer:build-all 2>&1 || true
log_stage_end
