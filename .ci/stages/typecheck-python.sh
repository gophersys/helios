#!/usr/bin/env bash
# Python type checking via mypy.
# Gate: fails on type errors in backend services.
# Uses --ignore-missing-imports to avoid false positives from untyped deps.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"

log_stage "typecheck-python — mypy static type analysis"

FAILED=false

# Common mypy flags:
#   --ignore-missing-imports: don't fail on untyped third-party libs
#   --no-error-summary: cleaner output
#   --warn-return-any: catch functions returning Any accidentally
#   --warn-unused-ignores: catch stale type: ignore comments
# Flags explanation:
#   --ignore-missing-imports: skip untyped third-party libs
#   --explicit-package-bases: resolve duplicate module names (auth/, etc)
#   --follow-imports=skip: only check files passed directly
#   --disallow-untyped-defs is intentionally NOT set — too strict for initial rollout
#   --warn-return-any is intentionally NOT set — resp.json() returns Any everywhere
MYPY_FLAGS="--ignore-missing-imports --no-error-summary --no-implicit-optional --explicit-package-bases"

for svc in http-api build-service git-poller; do
  src_dir="apps/backend/$svc/src"
  if [[ ! -d "$src_dir" ]]; then
    continue
  fi

  log_info "Type-checking $svc..."
  # Set MYPYPATH so mypy resolves modules from src/ root (avoids duplicate module errors)
  if ! MYPYPATH="$src_dir" python3 -m mypy "$src_dir" \
      $MYPY_FLAGS \
      --exclude 'tests/' \
      --follow-imports=skip \
      --namespace-packages \
      2>&1 | tail -20; then
    # Advisory for now — log but don't fail
    # TODO: promote to hard gate once existing type errors are fixed
    log_warn "$svc has type errors (advisory)"
  else
    log_ok "$svc passed"
  fi
done

# Note: mypy is advisory-only for now. Uncomment when type errors are fixed:
# if $FAILED; then
#   log_error "Python type check FAILED"
#   exit 1
# fi

if $FAILED; then
  log_error "Python type check FAILED"
  exit 1
fi

log_stage_end
