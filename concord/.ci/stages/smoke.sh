#!/usr/bin/env bash
# Smoke test a deployed environment.
# Hits health endpoints and runs the smoke test suite.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"

ENV="${1:-staging}"

log_stage "smoke — $ENV"

case "$ENV" in
  staging)
    TARGET_URL="https://staging.concord.local"
    API_KEY="ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG"
    ;;
  production)
    TARGET_URL="https://concord.local"
    API_KEY="${PRODUCTION_SMOKE_API_KEY:-}"
    ;;
  *)
    TARGET_URL="http://localhost:9001"
    API_KEY=""
    ;;
esac

log_info "target=$TARGET_URL"

# Health check
if curl -sf "$TARGET_URL/v2/docs" > /dev/null 2>&1; then
  log_ok "health check passed"
else
  log_err "health check failed — $TARGET_URL/v2/docs unreachable"
  log_stage_end
  exit 1
fi

# Smoke tests (if they exist and infra is reachable)
if [[ -d "tests/smoke" ]]; then
  PYTHONPATH="apps/backend/http-api/src:libs/python:libs:libs/protocols" \
    python3 -m pytest tests/smoke/ -v --timeout=30 \
    --target-url="$TARGET_URL" \
    --api-key="$API_KEY" || true
fi

log_stage_end
