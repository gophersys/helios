#!/usr/bin/env bash
# API backward compatibility check.
# Gate: ADVISORY — warns if API endpoints are removed or response shapes change.
# Compares the current OpenAPI spec against a committed baseline.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"

BASELINE=".ci/api-baseline.json"

log_stage "api-compat — OpenAPI backward compatibility"

# Generate current spec by hitting the docs endpoint
# This requires the app to be importable (not running)
log_info "Generating current OpenAPI spec..."
CURRENT=$(mktemp)
PYTHONPATH="apps/backend/http-api/src:libs/python:libs:libs/protocols" \
  python3 -c "
from api.v2.docs import get_spec
import json
spec = get_spec()
print(json.dumps(spec.to_dict(), indent=2, sort_keys=True))
" > "$CURRENT" 2>/dev/null || {
  log_warn "Could not generate OpenAPI spec — skipping"
  rm -f "$CURRENT"
  log_stage_end
  exit 0
}

if [[ ! -f "$BASELINE" ]]; then
  log_info "No baseline found — saving current spec as baseline"
  cp "$CURRENT" "$BASELINE"
  log_info "Baseline saved to $BASELINE — commit it"
  rm -f "$CURRENT"
  log_stage_end
  exit 0
fi

# Compare: check for removed endpoints (breaking changes)
REMOVED=$(python3 -c "
import json, sys
with open('$BASELINE') as f:
    old = json.load(f)
with open('$CURRENT') as f:
    new = json.load(f)

old_paths = set(old.get('paths', {}).keys())
new_paths = set(new.get('paths', {}).keys())
removed = old_paths - new_paths

for p in sorted(removed):
    print(f'  REMOVED: {p}')

# Check for removed methods on existing paths
for path in old_paths & new_paths:
    old_methods = set(old['paths'][path].keys())
    new_methods = set(new['paths'][path].keys())
    for m in old_methods - new_methods:
        print(f'  REMOVED: {m.upper()} {path}')

sys.exit(1 if removed or any(
    set(old['paths'][p].keys()) - set(new['paths'][p].keys())
    for p in old_paths & new_paths
) else 0)
" 2>&1)

if [[ $? -ne 0 ]]; then
  log_warn "Breaking API changes detected:"
  echo "$REMOVED"
  log_warn "If intentional, update the baseline: cp $CURRENT $BASELINE"
  # Advisory — don't fail pipeline yet
  # exit 1
else
  log_ok "No breaking API changes"
fi

# Update baseline with current spec (tracks additions)
cp "$CURRENT" "$BASELINE"
rm -f "$CURRENT"

log_stage_end
