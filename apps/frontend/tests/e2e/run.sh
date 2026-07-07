#!/usr/bin/env bash
#
# tests/e2e/run.sh — the chat-slice Playwright forced-CRUD harness. It boots a REAL agentgateway
# dev-serve and serves the production build, runs the E2E against them over real REST + SSE (no
# mocks), then tears down ONLY what it started. Devcontainer-first: bun + go are present here.
#
# Flow:
#   1. build the agentgateway-dev binary (workspace mode) and the frontend production build,
#   2. pick two free loopback ports (dev-serve + vite preview),
#   3. start the dev-serve, wait on /healthz; start vite preview, wait on its root,
#   4. run `playwright test` with E2E_BASE_URL + E2E_GATEWAY_URL pointing at them,
#   5. ALWAYS reap both child processes on exit (trap), leaving nothing running.
#
set -Eeuo pipefail
IFS=$'\n\t'

FRONTEND_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPO_ROOT="$(git -C "$FRONTEND_ROOT" rev-parse --show-toplevel 2>/dev/null || echo "$FRONTEND_ROOT")"
DEV_BIN="${TMPDIR:-/tmp}/agentgateway-dev-e2e"

log() { printf '\033[0;36m[e2e]\033[0m %s\n' "$*"; }
err() { printf '\033[0;31m[e2e:error]\033[0m %s\n' "$*" >&2; }

# free_port asks the kernel for an unused TCP port (bind :0) via python or a bash fallback.
free_port() {
  python3 - <<'PY' 2>/dev/null || node -e 'const s=require("net").createServer();s.listen(0,()=>{console.log(s.address().port);s.close()})' 2>/dev/null
import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
PY
}

GATEWAY_PORT="$(free_port)"
PREVIEW_PORT="$(free_port)"
[[ -n "$GATEWAY_PORT" && -n "$PREVIEW_PORT" ]] || { err "could not allocate free ports"; exit 1; }
GATEWAY_URL="http://127.0.0.1:${GATEWAY_PORT}"
PREVIEW_URL="http://127.0.0.1:${PREVIEW_PORT}"

DEV_PID=""
PREVIEW_PID=""

cleanup() {
  local code=$?
  # Tree-kill: `bun x` spawns vite as a CHILD, so killing only the tracked pid orphans a live
  # vite that keeps watching the tree and re-running svelte-kit sync — renumbering route chunks
  # under any LATER run's open pages (the failed-dynamic-import 500 flake). Reap descendants first.
  if [[ -n "$PREVIEW_PID" ]]; then pkill -P "$PREVIEW_PID" 2>/dev/null || true; kill "$PREVIEW_PID" 2>/dev/null || true; fi
  if [[ -n "$DEV_PID" ]]; then pkill -P "$DEV_PID" 2>/dev/null || true; kill "$DEV_PID" 2>/dev/null || true; fi
  wait 2>/dev/null || true
  log "torn down (dev-serve + preview reaped)"
  exit "$code"
}
trap cleanup EXIT INT TERM

# wait_http polls a URL until it answers 2xx/3xx or the attempt budget is exhausted.
wait_http() {
  local url="$1" name="$2" i
  for i in $(seq 1 150); do
    # Any HTTP response (even a redirect/404) means the listener is up; we are probing liveness,
    # not asserting a status. -f would false-negative on a non-2xx root, so we drop it here.
    if curl -s -o /dev/null -w '%{http_code}' "$url" 2>/dev/null | grep -qE '^[1-5][0-9][0-9]$'; then
      log "$name is up ($url) after $((i)) tries"
      return 0
    fi
    sleep 0.2
  done
  err "$name did not come up at $url"
  return 1
}

# ── 1. build the real dev-serve (workspace mode — honors go.work replace directives) ──
log "building agentgateway-dev (real REST+SSE backend) -> $DEV_BIN"
(cd "$REPO_ROOT" && go build -o "$DEV_BIN" ./apps/agentgateway/cmd/agentgateway-dev)

# ── 2. boot the dev-serve ──
log "starting dev-serve on $GATEWAY_URL"
EDEN_DEV_ADDRESS="127.0.0.1:${GATEWAY_PORT}" "$DEV_BIN" >"${TMPDIR:-/tmp}/e2e-devserve.log" 2>&1 &
DEV_PID=$!
wait_http "${GATEWAY_URL}/healthz" "dev-serve"

# ── 3. serve the UI through `vite dev` so the SAME-ORIGIN /gateway proxy is active ──
# The dev-serve sends no CORS headers (loopback dev backend), so the browser reaches it via the
# vite proxy (vite.config.ts: /gateway -> EDEN_GATEWAY_TARGET). `vite dev` is what honors the
# proxy (preview serves the adapter output, which does not); the production build is validated
# separately by `ctl.sh build`. The SSE the UI streams is 100% real — vite is a raw pipe, the
# events come straight off the dev-serve.
log "starting vite dev (same-origin /gateway proxy -> $GATEWAY_URL) on $PREVIEW_URL"
(cd "$FRONTEND_ROOT" && EDEN_GATEWAY_TARGET="$GATEWAY_URL" \
  exec bun x vite dev --host 127.0.0.1 --port "$PREVIEW_PORT" --strictPort \
  >"${TMPDIR:-/tmp}/e2e-preview.log" 2>&1) &
PREVIEW_PID=$!
wait_http "$PREVIEW_URL" "vite dev"

# ── ensure the Playwright browser is present (idempotent; installs chromium on first run) ──
log "ensuring Playwright chromium is installed"
(cd "$FRONTEND_ROOT" && bun x playwright install chromium >/dev/null 2>&1) ||
  log "playwright install skipped/failed (will use a present browser)"

# ── 4. run the forced-CRUD E2E against the real substrates (same-origin proxy) ──
log "running Playwright forced-CRUD (base=$PREVIEW_URL gateway via /gateway -> $GATEWAY_URL)"
(cd "$FRONTEND_ROOT" && E2E_BASE_URL="$PREVIEW_URL" \
  bun x playwright test "$@")
