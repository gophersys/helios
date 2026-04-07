#!/usr/bin/env bash
# Secret detection via detect-secrets.
# Gate: fails if potential secrets are found in staged/committed code.
# Uses a baseline file to suppress known false positives.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"

BASELINE=".ci/secrets-baseline.json"

log_stage "secret-scan — detect hardcoded credentials"

# Generate baseline if it doesn't exist
if [[ ! -f "$BASELINE" ]]; then
  log_info "No baseline found — creating initial baseline..."
  detect-secrets scan \
    --exclude-files '\.yarn/|node_modules/|\.venv/|site-packages/|\.coverage|\.nx/|dist/|\.git/' \
    --exclude-lines 'nosec|example|placeholder|test|dummy|fake|mock' \
    > "$BASELINE"
  log_info "Baseline created at $BASELINE — review and commit it"
fi

# Scan for new secrets not in the baseline
log_info "Scanning for secrets..."
if ! detect-secrets scan \
    --baseline "$BASELINE" \
    --exclude-files '\.yarn/|node_modules/|\.venv/|site-packages/|\.coverage|\.nx/|dist/|\.git/' \
    --exclude-lines 'nosec|example|placeholder|test|dummy|fake|mock' \
    2>&1; then
  log_error "New potential secrets detected — review with: detect-secrets audit $BASELINE"
  exit 1
fi

# Audit: check if any secrets in baseline are still marked as real
REAL_SECRETS=$(python3 -c "
import json, sys
try:
    with open('$BASELINE') as f:
        data = json.load(f)
    count = 0
    for path, secrets in data.get('results', {}).items():
        for s in secrets:
            if s.get('is_verified') is True:
                count += 1
                print(f'  VERIFIED SECRET: {path}:{s.get(\"line_number\", \"?\")} ({s.get(\"type\", \"unknown\")})', file=sys.stderr)
    print(count)
except Exception:
    print(0)
" 2>&1)

if [[ "$REAL_SECRETS" -gt 0 ]]; then
  log_error "$REAL_SECRETS verified secret(s) in baseline — remove them before committing"
  exit 1
fi

log_ok "No new secrets detected"
log_stage_end
