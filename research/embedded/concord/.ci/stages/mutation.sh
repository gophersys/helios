#!/usr/bin/env bash
# Mutation testing — verifies tests actually catch bugs, not just execute lines.
# Uses mutmut to inject small code changes and checks if tests detect them.
# Gate: ADVISORY (nightly only) — reports mutation score but doesn't block.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"

log_stage "mutation — mutation testing (mutmut)"

if ! command -v mutmut &>/dev/null; then
  log_warn "mutmut not installed — skipping mutation testing"
  log_info "Install: pip install mutmut"
  log_stage_end
  exit 0
fi

# Run mutation testing on the most critical module (build_trigger — handles all build logic)
# Full mutation testing takes hours, so we target high-value code only
TARGET="apps/backend/http-api/src/services/build_trigger.py"
TEST_CMD="cd apps/backend/http-api && PYTHONPATH=src:\$(pwd)/../../../libs/python:\$(pwd)/../../../libs:. python3 -m pytest tests/services/test_build_trigger.py -x -q --tb=no"

if [[ ! -f "$TARGET" ]]; then
  log_warn "Target $TARGET not found — skipping"
  log_stage_end
  exit 0
fi

log_info "Mutating $TARGET..."
mutmut run \
  --paths-to-mutate="$TARGET" \
  --tests-dir="apps/backend/http-api/tests/services/" \
  --runner="$TEST_CMD" \
  --no-progress \
  2>&1 | tail -20 || true

# Show results
log_info "Mutation results:"
mutmut results 2>&1 | tail -10 || true

# Report mutation score
KILLED=$(mutmut results 2>/dev/null | grep -c "Killed" || echo 0)
SURVIVED=$(mutmut results 2>/dev/null | grep -c "Survived" || echo 0)
TOTAL=$((KILLED + SURVIVED))

if [[ "$TOTAL" -gt 0 ]]; then
  SCORE=$(( KILLED * 100 / TOTAL ))
  log_info "Mutation score: ${SCORE}% ($KILLED killed / $TOTAL total)"
  if [[ "$SCORE" -lt 60 ]]; then
    log_warn "Low mutation score — tests may not catch real bugs"
  else
    log_ok "Mutation score acceptable"
  fi
else
  log_warn "No mutations generated"
fi

# Advisory — never fails the pipeline
log_stage_end
