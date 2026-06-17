#!/usr/bin/env bash
#
# tests/e2e/run-login.sh — the LOGIN E2E against a REAL Vault + Postgres stack (IOTEA-style: the
# dev/test loop uses real Vault, never a mock or a secrets bypass). It ensures the local supporting
# stack (Vault + Postgres) is up and seeded with platformgateway's secrets, boots the REAL
# platformgateway-live (which resolves its JWT signing key + Postgres DSN from Vault and migrates +
# seeds the default user at startup), serves the UI, and runs the login spec: /login loads the
# seeded default user from the public bootstrap and continues into the dashboard signed in as them.
#
# Unlike the live-claude arms, this lane needs NO external token — it brings up its OWN real Vault
# (EDEN_REQUIRE_HARNESS_CREDS=false seeds ONLY the platform secrets), so it is a non-skipping,
# always-green real-substrate test. The JWT/DSN values are resolved server-side from Vault and never
# read or logged by this script.
#
set -Eeuo pipefail
IFS=$'\n\t'

FRONTEND_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPO_ROOT="$(git -C "$FRONTEND_ROOT" rev-parse --show-toplevel 2>/dev/null || echo "$FRONTEND_ROOT")"
PLATFORM_BIN="${TMPDIR:-/tmp}/platformgateway-login-e2e"

log() { printf '\033[0;36m[e2e:login]\033[0m %s\n' "$*"; }
err() { printf '\033[0;31m[e2e:login:error]\033[0m %s\n' "$*" >&2; }

command -v docker >/dev/null 2>&1 || { err "docker is required (the real Vault + Postgres stack)"; exit 1; }

# ── 1. ensure the real local stack (Vault + Postgres) is up + the platform secrets are seeded ──
# deploy/ctl.sh local up is idempotent (compose up -d + the idempotent vault-seed);
# EDEN_REQUIRE_HARNESS_CREDS=false seeds ONLY the platformgateway secrets, so this lane needs no
# claude/openrouter token. The shared Vault/Postgres stack is left up afterwards (the dev Vault).
log "ensuring the real Vault + Postgres stack (deploy local up; platform secrets only) ..."
EDEN_REQUIRE_HARNESS_CREDS=false bash "${REPO_ROOT}/deploy/ctl.sh" local up

# The Vault userpass auth platformgateway resolves its secrets through (the deploy defaults; the
# password matches the 'eden' user vault-seed bound). In-container, Vault is reachable on the host's
# published port via host.docker.internal.
VAULT_ADDR="${VAULT_ADDR:-http://host.docker.internal:8200}"
VAULT_USERNAME="${VAULT_USERNAME:-eden}"
VAULT_PASSWORD="${VAULT_PASSWORD:-eden-local-dev-password}"

DEV_PID=""
PREVIEW_PID=""
cleanup() {
  local code=$?
  [[ -n "$PREVIEW_PID" ]] && kill "$PREVIEW_PID" 2>/dev/null || true
  [[ -n "$DEV_PID" ]] && kill "$DEV_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  log "torn down (platformgateway-live + preview reaped; the shared Vault/Postgres stack left up)"
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
      log "$name is up ($url) after $i tries"
      return 0
    fi
    sleep 0.2
  done
  err "$name did not come up at $url"
  return 1
}

PLATFORM_PORT="$(free_port)"
PREVIEW_PORT="$(free_port)"
[[ -n "$PLATFORM_PORT" && -n "$PREVIEW_PORT" ]] || { err "could not allocate free ports"; exit 1; }
PLATFORM_URL="http://127.0.0.1:${PLATFORM_PORT}"
PREVIEW_URL="http://127.0.0.1:${PREVIEW_PORT}"

# ── 2. build + boot platformgateway-live (real Vault) ──
log "building platformgateway-live -> $PLATFORM_BIN"
(cd "$REPO_ROOT/apps/platformgateway" && GOWORK="$REPO_ROOT/go.work" go build -o "$PLATFORM_BIN" ./cmd/gateway)

log "starting platformgateway-live on $PLATFORM_URL (JWT + DSN resolved from Vault, never logged)"
EDEN_GATEWAY_ADDRESS="127.0.0.1:${PLATFORM_PORT}" \
  EDEN_GATEWAY_JWT_SECRET_REF="vault://eden/development#platformgateway-jwt-signing-key" \
  EDEN_GATEWAY_DATABASE_DSN_REF="vault://eden/development#platformgateway-database-dsn" \
  VAULT_ADDR="$VAULT_ADDR" VAULT_USERNAME="$VAULT_USERNAME" VAULT_PASSWORD="$VAULT_PASSWORD" \
  "$PLATFORM_BIN" >"${TMPDIR:-/tmp}/e2e-login-platform.log" 2>&1 &
DEV_PID=$!
wait_http "${PLATFORM_URL}/healthz/live" "platformgateway-live"

# ── 3. serve the UI with the /platform proxy → platformgateway ──
log "starting vite dev (/platform proxy -> $PLATFORM_URL) on $PREVIEW_URL"
(cd "$FRONTEND_ROOT" && EDEN_PLATFORM_TARGET="$PLATFORM_URL" \
  bun x vite dev --host 127.0.0.1 --port "$PREVIEW_PORT" --strictPort \
  >"${TMPDIR:-/tmp}/e2e-login-preview.log" 2>&1) &
PREVIEW_PID=$!
wait_http "$PREVIEW_URL" "vite dev"

(cd "$FRONTEND_ROOT" && bun x playwright install chromium >/dev/null 2>&1) ||
  log "playwright install skipped/failed (will use a present browser)"

# ── 4. run the login spec against the real stack ──
log "running the login E2E against real Vault + Postgres + platformgateway-live"
(cd "$FRONTEND_ROOT" && E2E_BASE_URL="$PREVIEW_URL" \
  bun x playwright test tests/e2e/login.spec.ts "$@")
