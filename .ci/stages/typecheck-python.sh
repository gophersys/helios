#!/usr/bin/env bash
# Python type checking via mypy.
# Gate: FAILS on type errors in build-service and git-poller (clean).
#       Advisory for http-api (347 existing errors — needs incremental cleanup).
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"

log_stage "typecheck-python — mypy static type analysis"

FAILED=false

# Flags:
#   --ignore-missing-imports: skip untyped third-party libs
#   --explicit-package-bases: resolve duplicate module names
#   --no-implicit-optional: require explicit Optional[X] for = None defaults
#   --follow-imports=skip: only check files passed directly
MYPY_FLAGS="--ignore-missing-imports --no-error-summary --no-implicit-optional --explicit-package-bases"

# Hard gate: all 3 backend services (0 errors each)
for svc in http-api build-service git-poller; do
  src_dir="apps/backend/$svc/src"
  log_info "Type-checking $svc (hard gate)..."
  if ! MYPYPATH="$src_dir" python3 -m mypy "$src_dir" \
      $MYPY_FLAGS \
      --exclude 'tests/' \
      --follow-imports=skip \
      --namespace-packages \
      2>&1 | tail -20; then
    log_error "$svc has type errors"
    FAILED=true
  else
    log_ok "$svc passed"
  fi
done

if $FAILED; then
  log_error "Python type check FAILED"
  exit 1
fi

log_stage_end
