#!/usr/bin/env bash
#
# tests/e2e/run-live-permission.sh — the LIVE arm of the permission-flow E2E. It boots the REAL
# agentgateway-live (the real claude/omp harness over the local Vault) and the production UI, then
# runs the permission-flow LIVE arm against them: a REAL agent requests an OUT-OF-GRANT tool, the
# @eden/primitives PermissionRequest card renders, Allow flows the resolve round-trip, and the agent
# proceeds. It is the honest counterpart to run.sh (which uses the deterministic dev-serve fake).
#
# PRECONDITIONS (all required; an honest SKIP otherwise — never a false green):
#   - a local Vault reachable at $VAULT_ADDR (default http://127.0.0.1:8200) with VAULT_PASSWORD set,
#   - the setup-token resolvable at $EDEN_CREDENTIAL_REF (default vault://eden/development#setup-token),
#   - the pinned claude harness on PATH (the agentgateway-live composition spawns it).
# The token is NEVER read or logged by this script — agentgateway-live resolves it server-side from
# Vault and injects it into the harness child env via Secret.Use (REQ-0021).
#
# When a precondition is absent this script prints a clear SKIP line and exits 0 (the lane is
# honest-skipped, exactly as the spec's test.skip guard documents). When all are present it exports
# E2E_LIVE_PERMISSION=1 so the spec's LIVE describe runs.
#
set -Eeuo pipefail
IFS=$'\n\t'

FRONTEND_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPO_ROOT="$(git -C "$FRONTEND_ROOT" rev-parse --show-toplevel 2>/dev/null || echo "$FRONTEND_ROOT")"
LIVE_BIN="${TMPDIR:-/tmp}/agentgateway-live-e2e"

VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"

log() { printf '\033[0;36m[e2e:live]\033[0m %s\n' "$*"; }
skip() {
  printf '\033[0;33m[e2e:live:skip]\033[0m %s\n' "$*" >&2
  printf '\033[0;33m[e2e:live:skip]\033[0m LIVE permission arm skipped (the FAKE arm in run.sh is the non-vacuous gate).\n' >&2
  exit 0
}

# ── precondition probes (honest SKIP, never a false green) ──
command -v claude >/dev/null 2>&1 || skip "the claude harness is not on PATH"
[[ -n "${VAULT_PASSWORD:-}" ]] || skip "VAULT_PASSWORD is unset (no Vault auth to resolve the setup-token)"
if ! curl -fsS -o /dev/null --max-time 3 "${VAULT_ADDR}/v1/sys/health" 2>/dev/null; then
  skip "Vault is not reachable at ${VAULT_ADDR}"
fi

DEV_PID=""
PREVIEW_PID=""
cleanup() {
  local code=$?
  [[ -n "$PREVIEW_PID" ]] && kill "$PREVIEW_PID" 2>/dev/null || true
  [[ -n "$DEV_PID" ]] && kill "$DEV_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  log "torn down (agentgateway-live + preview reaped)"
  exit "$code"
}
trap cleanup EXIT INT TERM

free_port() {
  python3 - <<'PY' 2>/dev/null || node -e 'const s=require("net").createServer();s.listen(0,()=>{console.log(s.address().port);s.close()})' 2>/dev/null
import socket
s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()
PY
}

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
err() { printf '\033[0;31m[e2e:live:error]\033[0m %s\n' "$*" >&2; }

GATEWAY_PORT="$(free_port)"; PREVIEW_PORT="$(free_port)"
[[ -n "$GATEWAY_PORT" && -n "$PREVIEW_PORT" ]] || { err "could not allocate free ports"; exit 1; }
GATEWAY_URL="http://127.0.0.1:${GATEWAY_PORT}"
PREVIEW_URL="http://127.0.0.1:${PREVIEW_PORT}"

log "building agentgateway-live (REAL harness + Vault) -> $LIVE_BIN"
(cd "$REPO_ROOT" && go build -o "$LIVE_BIN" ./apps/agentgateway/cmd/agentgateway-live)

log "starting agentgateway-live on $GATEWAY_URL (token resolved server-side from Vault, never logged)"
EDEN_GATEWAY_ADDRESS="127.0.0.1:${GATEWAY_PORT}" VAULT_ADDR="$VAULT_ADDR" \
  "$LIVE_BIN" >"${TMPDIR:-/tmp}/e2e-live.log" 2>&1 &
DEV_PID=$!
wait_http "${GATEWAY_URL}/healthz" "agentgateway-live"

log "starting vite dev (same-origin /gateway proxy -> $GATEWAY_URL) on $PREVIEW_URL"
(cd "$FRONTEND_ROOT" && EDEN_GATEWAY_TARGET="$GATEWAY_URL" \
  bun x vite dev --host 127.0.0.1 --port "$PREVIEW_PORT" --strictPort \
  >"${TMPDIR:-/tmp}/e2e-live-preview.log" 2>&1) &
PREVIEW_PID=$!
wait_http "$PREVIEW_URL" "vite dev"

(cd "$FRONTEND_ROOT" && bun x playwright install chromium >/dev/null 2>&1) || true

log "running the LIVE permission arm against the REAL claude agent"
(cd "$FRONTEND_ROOT" && E2E_BASE_URL="$PREVIEW_URL" E2E_LIVE_PERMISSION=1 \
  bun x playwright test tests/e2e/permission-flow.spec.ts --grep "LIVE arm")
