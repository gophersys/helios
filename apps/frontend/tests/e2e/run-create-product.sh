#!/usr/bin/env bash
#
# tests/e2e/run-create-product.sh — the FAKE arm of the "create a new product" E2E (the regression
# gate). It mirrors run.sh: it boots a REAL agentgateway dev-serve (deterministic propose + a real
# agentsession.Pool + the verdict-aware fake adapter) and serves the UI through `vite dev` (so the
# same-origin /gateway proxy is active), then runs the create-product journey over real REST + SSE
# (no mocked fetch/SSE) on BOTH Chromium and WebKit, and tears down only what it started.
#
# Devcontainer-first: bun + go + the playwright browsers are present in the base devcontainer. Run
# from there (docker exec -u dev -w /workspace/apps/frontend base-devcontainer bash -lc './tests/e2e/run-create-product.sh').
#
set -Eeuo pipefail
IFS=$'\n\t'

FRONTEND_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPO_ROOT="$(git -C "$FRONTEND_ROOT" rev-parse --show-toplevel 2>/dev/null || echo "$FRONTEND_ROOT")"
DEV_BIN="${TMPDIR:-/tmp}/agentgateway-dev-create-product-e2e"

log() { printf '\033[0;36m[e2e:create-product]\033[0m %s\n' "$*"; }
err() { printf '\033[0;31m[e2e:create-product:error]\033[0m %s\n' "$*" >&2; }

free_port() {
  python3 - <<'PY' 2>/dev/null || node -e 'const s=require("net").createServer();s.listen(0,()=>{console.log(s.address().port);s.close()})' 2>/dev/null
import socket
s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()
PY
}

GATEWAY_PORT="$(free_port)"; PREVIEW_PORT="$(free_port)"
[[ -n "$GATEWAY_PORT" && -n "$PREVIEW_PORT" ]] || { err "could not allocate free ports"; exit 1; }
GATEWAY_URL="http://127.0.0.1:${GATEWAY_PORT}"
PREVIEW_URL="http://127.0.0.1:${PREVIEW_PORT}"

DEV_PID=""; PREVIEW_PID=""
cleanup() {
  local code=$?
  [[ -n "$PREVIEW_PID" ]] && kill "$PREVIEW_PID" 2>/dev/null || true
  [[ -n "$DEV_PID" ]] && kill "$DEV_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  log "torn down (dev-serve + preview reaped)"
  exit "$code"
}
trap cleanup EXIT INT TERM

wait_http() {
  local url="$1" name="$2" i
  for i in $(seq 1 150); do
    if curl -s -o /dev/null -w '%{http_code}' "$url" 2>/dev/null | grep -qE '^[1-5][0-9][0-9]$'; then
      log "$name is up ($url) after $i tries"; return 0
    fi
    sleep 0.2
  done
  err "$name did not come up at $url"; return 1
}

# ── 1. build the real dev-serve (workspace mode) ──
log "building agentgateway-dev (real REST+SSE backend) -> $DEV_BIN"
(cd "$REPO_ROOT" && go build -o "$DEV_BIN" ./apps/agentgateway/cmd/agentgateway-dev)

# ── 2. boot the dev-serve ──
log "starting dev-serve on $GATEWAY_URL"
EDEN_DEV_ADDRESS="127.0.0.1:${GATEWAY_PORT}" "$DEV_BIN" >"${TMPDIR:-/tmp}/e2e-create-product-devserve.log" 2>&1 &
DEV_PID=$!
wait_http "${GATEWAY_URL}/healthz" "dev-serve"

# ── 3. serve the UI via `vite dev` (same-origin /gateway proxy -> the dev-serve) ──
log "starting vite dev (same-origin /gateway proxy -> $GATEWAY_URL) on $PREVIEW_URL"
(cd "$FRONTEND_ROOT" && EDEN_GATEWAY_TARGET="$GATEWAY_URL" \
  bun x vite dev --host 127.0.0.1 --port "$PREVIEW_PORT" --strictPort \
  >"${TMPDIR:-/tmp}/e2e-create-product-preview.log" 2>&1) &
PREVIEW_PID=$!
wait_http "$PREVIEW_URL" "vite dev"

# ── ensure both browsers are present (idempotent) ──
log "ensuring Playwright chromium + webkit are installed"
(cd "$FRONTEND_ROOT" && bun x playwright install chromium webkit >/dev/null 2>&1) ||
  log "playwright install skipped/failed (will use the present browsers)"

# ── 4. run the create-product journey on BOTH engines against the real substrates ──
log "running the create-product E2E (base=$PREVIEW_URL, engines=chromium+webkit)"
(cd "$FRONTEND_ROOT" && E2E_BASE_URL="$PREVIEW_URL" E2E_BROWSERS="chromium,webkit" \
  bun x playwright test tests/e2e/create-product.spec.ts "$@")
