#!/usr/bin/env bash
# Pipeline: Pull Request
# Runs on every PR. Must pass before merge.
#
# Stage 1: env-check + secret-scan (fast safety gates)
# Stage 2: ALL quality gates in parallel (lint, typecheck, test, coverage,
#           complexity, security, dep-audit, contracts, schema-check,
#           docstrings, docs-build, typecheck-python)
# Stage 3: integration tests (real DB, real services)
# Stage 4: build (only after all gates pass)
#
# Parallel execution via background jobs — ~5min instead of ~20min sequential.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"

# ── Stage 1: Safety gates (must pass before anything else) ──
bash "$DIR/stages/env-check.sh"
bash "$DIR/stages/secret-scan.sh"

# ── Stage 2: All quality gates in parallel ──
PIDS=()
STAGES=()
FAILED=false

run_stage() {
  local name="$1"
  local script="$2"
  shift 2
  bash "$script" "$@" &
  PIDS+=($!)
  STAGES+=("$name")
}

run_stage "lint"             "$DIR/stages/lint.sh"
run_stage "typecheck"        "$DIR/stages/typecheck.sh"
run_stage "typecheck-python" "$DIR/stages/typecheck-python.sh"
run_stage "test"             "$DIR/stages/test.sh"
run_stage "coverage"         "$DIR/stages/coverage.sh"
run_stage "complexity"       "$DIR/stages/complexity.sh"
run_stage "security"         "$DIR/stages/security.sh"
run_stage "dep-audit"        "$DIR/stages/dep-audit.sh"
run_stage "contracts"        "$DIR/stages/contracts.sh"
run_stage "schema-check"     "$DIR/stages/schema-check.sh"
run_stage "docstrings"       "$DIR/stages/docstrings.sh"
run_stage "docs-build"       "$DIR/stages/docs-build.sh"
run_stage "dep-pin"          "$DIR/stages/dep-pin.sh"
run_stage "api-compat"       "$DIR/stages/api-compat.sh"
run_stage "migration-safety" "$DIR/stages/migration-safety.sh"
run_stage "proto-sync"              "$DIR/stages/proto-sync.sh"
run_stage "ai-review-completeness" "$DIR/stages/ai-review-completeness.sh"
run_stage "ai-review-security"     "$DIR/stages/ai-review-security.sh"
run_stage "ai-review-blast-radius" "$DIR/stages/ai-review-blast-radius.sh"
run_stage "ai-review-docs"         "$DIR/stages/ai-review-docs.sh"

# Wait for all and collect results
for i in "${!PIDS[@]}"; do
  if ! wait "${PIDS[$i]}"; then
    echo "FAIL: ${STAGES[$i]}"
    FAILED=true
  else
    echo "PASS: ${STAGES[$i]}"
  fi
done

if $FAILED; then
  echo ""
  echo "PR pipeline FAILED — one or more quality gates did not pass."

  # Attempt auto-fix for AI review failures
  if [[ -d "/tmp/ai-review" ]] && ls /tmp/ai-review/*.json >/dev/null 2>&1; then
    echo ""
    bash "$DIR/stages/ai-fix.sh" || true
  fi

  exit 1
fi

# ── Stage 3: Integration tests (real DB, compose stack) ──
# Only run after all unit/static gates pass — these are slower
bash "$DIR/stages/test-integration.sh"

# ── Stage 4: Build (only if everything passed) ──
bash "$DIR/stages/build.sh" staging

# ── Stage 5: Container image scanning (post-build) ──
bash "$DIR/stages/image-scan.sh"
