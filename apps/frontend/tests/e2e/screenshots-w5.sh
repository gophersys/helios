#!/usr/bin/env bash
# W5 FINAL GALLERY runner — boots the SAME real dev-serve + vite dev as run.sh, drives the
# screenshots-w5.mjs sweep against them (every screen, both themes), then tree-kills its servers (no
# orphans). One-shot; artifacts land in /tmp/ui-audit/final/.
set -Eeuo pipefail
IFS=$'\n\t'

FRONTEND_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPO_ROOT="$(git -C "$FRONTEND_ROOT" rev-parse --show-toplevel 2>/dev/null || echo "$FRONTEND_ROOT")"
DEV_BIN="${TMPDIR:-/tmp}/agentgateway-dev-shots-w5"

log() { printf '\033[0;36m[shots-w5]\033[0m %s\n' "$*"; }
err() { printf '\033[0;31m[shots-w5:error]\033[0m %s\n' "$*" >&2; }

free_port() {
  python3 - <<'PY' 2>/dev/null || node -e 'const s=require("net").createServer();s.listen(0,()=>{console.log(s.address().port);s.close()})' 2>/dev/null
import socket
s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()
PY
}

GATEWAY_PORT="$(free_port)"; PREVIEW_PORT="$(free_port)"
GATEWAY_URL="http://127.0.0.1:${GATEWAY_PORT}"; PREVIEW_URL="http://127.0.0.1:${PREVIEW_PORT}"

DEV_PID=""; PREVIEW_PID=""
cleanup() {
  local code=$?
  if [[ -n "$PREVIEW_PID" ]]; then pkill -P "$PREVIEW_PID" 2>/dev/null || true; kill "$PREVIEW_PID" 2>/dev/null || true; fi
  if [[ -n "$DEV_PID" ]]; then pkill -P "$DEV_PID" 2>/dev/null || true; kill "$DEV_PID" 2>/dev/null || true; fi
  wait 2>/dev/null || true
  log "torn down"
  exit "$code"
}
trap cleanup EXIT INT TERM

wait_http() {
  local url="$1" name="$2" i
  for i in $(seq 1 150); do
    if curl -s -o /dev/null -w '%{http_code}' "$url" 2>/dev/null | grep -qE '^[1-5][0-9][0-9]$'; then
      log "$name up ($url)"; return 0
    fi
    sleep 0.2
  done
  err "$name did not come up at $url"; return 1
}

log "building agentgateway-dev -> $DEV_BIN"
(cd "$REPO_ROOT" && go build -o "$DEV_BIN" ./apps/agentgateway/cmd/agentgateway-dev)

log "starting dev-serve on $GATEWAY_URL"
EDEN_DEV_ADDRESS="127.0.0.1:${GATEWAY_PORT}" "$DEV_BIN" >"${TMPDIR:-/tmp}/shots-w5-devserve.log" 2>&1 &
DEV_PID=$!
wait_http "${GATEWAY_URL}/healthz" "dev-serve"

log "starting vite dev on $PREVIEW_URL"
(cd "$FRONTEND_ROOT" && EDEN_GATEWAY_TARGET="$GATEWAY_URL" \
  exec bun x vite dev --host 127.0.0.1 --port "$PREVIEW_PORT" --strictPort \
  >"${TMPDIR:-/tmp}/shots-w5-preview.log" 2>&1) &
PREVIEW_PID=$!
wait_http "$PREVIEW_URL" "vite dev"

mkdir -p /tmp/ui-audit/final
log "capturing W5 gallery -> /tmp/ui-audit/final"
(cd "$FRONTEND_ROOT" && E2E_BASE_URL="$PREVIEW_URL" bun x node tests/e2e/screenshots-w5.mjs)
