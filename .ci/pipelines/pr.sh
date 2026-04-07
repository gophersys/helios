#!/usr/bin/env bash
# Pipeline: Pull Request
# Runs on every PR. Must pass before merge.
#
# Stage 1: env-check (fast, validates environment contract)
# Stage 2: ALL quality gates in parallel (lint, typecheck, test, coverage,
#           complexity, security, contracts, schema-check, docstrings, docs-build)
# Stage 3: build (only after all gates pass)
#
# Parallel execution via background jobs — ~4min instead of ~15min sequential.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"

# ── Stage 1: Environment contract (must pass before anything else) ──
bash "$DIR/stages/env-check.sh"

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

run_stage "lint"         "$DIR/stages/lint.sh"
run_stage "typecheck"    "$DIR/stages/typecheck.sh"
run_stage "test"         "$DIR/stages/test.sh"
run_stage "coverage"     "$DIR/stages/coverage.sh"
run_stage "complexity"   "$DIR/stages/complexity.sh"
run_stage "security"     "$DIR/stages/security.sh"
run_stage "contracts"    "$DIR/stages/contracts.sh"
run_stage "schema-check" "$DIR/stages/schema-check.sh"
run_stage "docstrings"   "$DIR/stages/docstrings.sh"
run_stage "docs-build"   "$DIR/stages/docs-build.sh"

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
  exit 1
fi

# ── Stage 3: Build (only if all gates passed) ──
bash "$DIR/stages/build.sh" staging
