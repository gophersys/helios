#!/usr/bin/env bash
#
# tests/e2e/run-create-product-live.sh — the LIVE arm of the "create a new product" E2E. It boots the
# REAL agentgateway-live (the real claude harness over the local Vault) and the UI, then runs the
# create-product LIVE describe: the wizard's propose hits REAL claude (a real one-shot ProductConfig
# turn), the created agent is REAL, and its first response streams over real SSE. It is the honest
# counterpart to run-create-product.sh (the deterministic dev-serve FAKE arm).
#
# The token NEVER touches a log. It is provided as CLAUDEADAPTER_LIVE_TOKEN in /workspace/.env.development
# (or CLAUDE_CODE_OAUTH_TOKEN). When present and Vault is reachable, this runner seeds the credential
# into the local Vault at $EDEN_CREDENTIAL_REF (the same path agentgateway-live resolves server-side)
# — so the token is read ONCE here, piped to Vault over the API, and is never echoed. agentgateway-live
# then resolves it server-side via Secret.Use and injects it into the harness child env only (REQ-0021).
#
# PRECONDITIONS (all required; an honest SKIP otherwise — never a false green):
#   - CREATE_PRODUCT_LIVE intent: a CLAUDEADAPTER_LIVE_TOKEN/CLAUDE_CODE_OAUTH_TOKEN in /workspace/.env.development,
#   - the pinned claude harness on PATH (agentgateway-live spawns it),
#   - a local Vault reachable at $VAULT_ADDR with VAULT_PASSWORD set (to seed + resolve the token).
# When a precondition is absent this prints a clear SKIP line and exits 0.
#
set -Eeuo pipefail
IFS=$'\n\t'

FRONTEND_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPO_ROOT="$(git -C "$FRONTEND_ROOT" rev-parse --show-toplevel 2>/dev/null || echo "$FRONTEND_ROOT")"
LIVE_BIN="${TMPDIR:-/tmp}/agentgateway-live-create-product-e2e"
ENV_FILE="${EDEN_ENV_FILE:-/workspace/.env.development}"

VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
EDEN_CREDENTIAL_REF="${EDEN_CREDENTIAL_REF:-vault://eden/development#setup-token}"

log() { printf '\033[0;36m[e2e:create-product:live]\033[0m %s\n' "$*"; }
err() { printf '\033[0;31m[e2e:create-product:live:error]\033[0m %s\n' "$*" >&2; }
skip() {
  printf '\033[0;33m[e2e:create-product:live:skip]\033[0m %s\n' "$*" >&2
  printf '\033[0;33m[e2e:create-product:live:skip]\033[0m LIVE arm skipped (run-create-product.sh is the non-vacuous FAKE gate).\n' >&2
  exit 0
}

# ── read the token from .env.development ONCE (never logged) ──
LIVE_TOKEN=""
if [[ -f "$ENV_FILE" ]]; then
  # Source in a subshell-safe way: read only the two accepted keys, never echo their values.
  LIVE_TOKEN="$(grep -E '^(CLAUDEADAPTER_LIVE_TOKEN|CLAUDE_CODE_OAUTH_TOKEN)=' "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"'"'"'' )"
fi
[[ -n "$LIVE_TOKEN" ]] || skip "no CLAUDEADAPTER_LIVE_TOKEN/CLAUDE_CODE_OAUTH_TOKEN in $ENV_FILE"
command -v claude >/dev/null 2>&1 || skip "the claude harness is not on PATH"
[[ -n "${VAULT_PASSWORD:-}" ]] || skip "VAULT_PASSWORD is unset (no Vault auth to seed/resolve the token)"
if ! curl -fsS -o /dev/null --max-time 3 "${VAULT_ADDR}/v1/sys/health" 2>/dev/null; then
  skip "Vault is not reachable at ${VAULT_ADDR}"
fi

# ── ensure the credential RESOLVES at the reference path (this runner never WRITES it) ──
# The local Vault's agent userpass policy (eden-agent) is READ-ONLY by design — it grants `read` on
# eden/data/development and nothing else (deploy/plane/local/vault-seed.sh §7). So this runner cannot
# (and must not) write the secret via userpass: a POST 403s. The credential is OWNED by the Vault
# lifecycle — `deploy/ctl.sh local up|seed` seeds it from .env.development using the root token. Here
# we only VERIFY the ref resolves via the SAME userpass read path agentgateway-live uses server-side;
# if it is absent we delegate the seed to deploy/ctl.sh (root path) and re-verify — never writing via
# the read-only userpass token. No credential value is logged at any step.
# Parse vault://<mount>/<path>#<key> -> mount, kv path, field.
REF_BODY="${EDEN_CREDENTIAL_REF#vault://}"
REF_PATH="${REF_BODY%%#*}"
REF_KEY="${REF_BODY##*#}"
VAULT_MOUNT="${REF_PATH%%/*}"
VAULT_KV_PATH="${REF_PATH#*/}"

userpass_token() {
  curl -fsS --max-time 5 \
    --request POST "${VAULT_ADDR}/v1/auth/userpass/login/${VAULT_USERNAME:-eden}" \
    --data "{\"password\":\"${VAULT_PASSWORD}\"}" 2>/dev/null \
    | grep -o '"client_token":"[^"]*"' | cut -d'"' -f4
}
# credential_present "$tok" -> 0 iff the KV field NAME is present (checks the name only, never the value).
credential_present() {
  curl -fsS --max-time 5 --header "X-Vault-Token: $1" \
    "${VAULT_ADDR}/v1/${VAULT_MOUNT}/data/${VAULT_KV_PATH}" 2>/dev/null \
    | grep -q "\"${REF_KEY}\""
}

log "verifying ${EDEN_CREDENTIAL_REF} resolves via userpass '${VAULT_USERNAME:-eden}' (read-only; the gateway uses the same path) ..."
VAULT_TOKEN="$(userpass_token)" || true
[[ -n "$VAULT_TOKEN" ]] || skip "could not authenticate to Vault (userpass ${VAULT_USERNAME:-eden})"

if credential_present "$VAULT_TOKEN"; then
  log "credential already present at ${EDEN_CREDENTIAL_REF}; agentgateway-live will resolve it server-side"
else
  log "credential absent; delegating the seed to 'deploy/ctl.sh local seed' (root path, reads .env.development) ..."
  unset VAULT_TOKEN
  ( cd "$REPO_ROOT" && VAULT_PASSWORD="$VAULT_PASSWORD" bash deploy/ctl.sh local seed >/dev/null 2>&1 ) \
    || skip "deploy/ctl.sh local seed failed (could not seed the credential)"
  VAULT_TOKEN="$(userpass_token)" || true
  { [[ -n "$VAULT_TOKEN" ]] && credential_present "$VAULT_TOKEN"; } \
    || skip "credential still absent after seeding via deploy/ctl.sh"
  log "credential seeded via deploy/ctl.sh; agentgateway-live will resolve it server-side"
fi
unset LIVE_TOKEN VAULT_TOKEN

DEV_PID=""; PREVIEW_PID=""
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

GATEWAY_PORT="$(free_port)"; PREVIEW_PORT="$(free_port)"
[[ -n "$GATEWAY_PORT" && -n "$PREVIEW_PORT" ]] || { err "could not allocate free ports"; exit 1; }
GATEWAY_URL="http://127.0.0.1:${GATEWAY_PORT}"
PREVIEW_URL="http://127.0.0.1:${PREVIEW_PORT}"

log "building agentgateway-live (REAL harness + Vault) -> $LIVE_BIN"
(cd "$REPO_ROOT" && go build -o "$LIVE_BIN" ./apps/agentgateway/cmd/agentgateway-live)

log "starting agentgateway-live on $GATEWAY_URL (token resolved server-side from Vault, never logged)"
EDEN_GATEWAY_ADDRESS="127.0.0.1:${GATEWAY_PORT}" VAULT_ADDR="$VAULT_ADDR" \
  EDEN_CREDENTIAL_REF="$EDEN_CREDENTIAL_REF" \
  "$LIVE_BIN" >"${TMPDIR:-/tmp}/e2e-create-product-live.log" 2>&1 &
DEV_PID=$!
wait_http "${GATEWAY_URL}/healthz" "agentgateway-live"

log "starting vite dev (same-origin /gateway proxy -> $GATEWAY_URL) on $PREVIEW_URL"
(cd "$FRONTEND_ROOT" && EDEN_GATEWAY_TARGET="$GATEWAY_URL" \
  bun x vite dev --host 127.0.0.1 --port "$PREVIEW_PORT" --strictPort \
  >"${TMPDIR:-/tmp}/e2e-create-product-live-preview.log" 2>&1) &
PREVIEW_PID=$!
wait_http "$PREVIEW_URL" "vite dev"

(cd "$FRONTEND_ROOT" && bun x playwright install chromium >/dev/null 2>&1) || true

log "running the LIVE create-product arm against the REAL claude agent"
(cd "$FRONTEND_ROOT" && E2E_BASE_URL="$PREVIEW_URL" CREATE_PRODUCT_LIVE=1 \
  bun x playwright test tests/e2e/create-product.spec.ts --grep "LIVE arm")
