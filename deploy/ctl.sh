#!/usr/bin/env bash
# deploy/ctl.sh — the Eden Milestone-B deploy entrypoint (ADR-0022 #2). It selects a PLANE
# (local = docker-compose, production = Helm) and drives the supporting stack + the live demo.
#
#   bash deploy/ctl.sh local up        # supporting stack (Vault+NATS+Postgres) + seed Vault from .env.development
#   bash deploy/ctl.sh local down       # tear the supporting stack down (-v removes volumes)
#   bash deploy/ctl.sh local seed       # (re)seed Vault from .env.development only
#   bash deploy/ctl.sh local verify     # confirm a `kv get` returns the seeded ref WITHOUT printing the value
#   bash deploy/ctl.sh demo             # THE ONE COMMAND: stack up + seed + agentgateway-live + frontend → live UI
#   bash deploy/ctl.sh demo down        # reap the demo (gateway + frontend + stack)
#   bash deploy/ctl.sh production render # render the Helm chart from the typed ServiceSpec
#
# Two-axis (ADR-0022 #2): `deploy/<plane>/{local,production}`; one typed Go ServiceSpec renders to
# BOTH compose and Helm; the supporting stack stands up out-of-band; `local` loads .env.development
# into the env AND seeds the local REAL Vault from it.
#
# SECRET SAFETY: this script and vault-seed.sh NEVER echo a credential value. .env.development is
# sourced into the env (values stay in env vars) but never printed; only key NAMES are logged.
set -Eeuo pipefail
set +x # SECRET SAFETY: never trace.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOCAL_DIR="${SCRIPT_DIR}/plane/local"
STATE_DIR="${LOCAL_DIR}/.state"
ENV_FILE="${EDEN_ENV_FILE:-${REPO_ROOT}/.env.development}"
COMPOSE_FILE="${LOCAL_DIR}/docker-compose.yaml"

# SUBSTRATE_HOST is the hostname the demo processes reach the supporting stack's PUBLISHED ports on.
# On the host shell that is 127.0.0.1 (the loopback the compose publishes to). Inside the
# devcontainer (a bridge-network container over docker-out-of-docker), 127.0.0.1 is the container's
# OWN loopback, so the host's published ports are reached via host.docker.internal. Detected by the
# presence of the /workspace mount + the host gateway alias; override with EDEN_SUBSTRATE_HOST.
detect_substrate_host() {
  if [ -n "${EDEN_SUBSTRATE_HOST:-}" ]; then printf '%s' "${EDEN_SUBSTRATE_HOST}"; return; fi
  if [ -f /.dockerenv ] && getent hosts host.docker.internal >/dev/null 2>&1; then
    printf '%s' "host.docker.internal"
  else
    printf '%s' "127.0.0.1"
  fi
}
SUBSTRATE_HOST="$(detect_substrate_host)"

# Bind addresses for the demo processes.
GATEWAY_ADDRESS="${EDEN_GATEWAY_ADDRESS:-127.0.0.1:8080}"
FRONTEND_PORT="${EDEN_FRONTEND_PORT:-5173}"

log()  { printf '\033[1;36m[deploy]\033[0m %s\n' "$*" >&2; }
warn() { printf '\033[1;33m[deploy]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[deploy] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

compose() { docker compose -f "${COMPOSE_FILE}" "$@"; }

# load_env sources .env.development into the environment WITHOUT echoing any value, and derives
# the local defaults the seed + gateway need (VAULT_PASSWORD, POSTGRES_*). It exports each var so
# child processes (vault-seed.sh, agentgateway-live) inherit them. Key NAMES only are logged.
load_env() {
  [ -f "${ENV_FILE}" ] || die "env file not found: ${ENV_FILE} (copy .env.example → .env.development and fill it in)"
  log "loading ${ENV_FILE} (values stay in the env; names only logged) ..."
  # Export every KEY=VALUE line; `set -a` auto-exports. The file is the .env standard (no `export`).
  set -a
  # shellcheck disable=SC1090
  . "${ENV_FILE}"
  set +a
  # Defaults for the local supporting stack (a real Vault still needs a userpass password; if the
  # operator did not set one in .env.development we derive a stable local one — never committed).
  # VAULT_ADDR / NATS point at SUBSTRATE_HOST so the demo processes reach the PUBLISHED ports both
  # from the host (127.0.0.1) and from inside the devcontainer (host.docker.internal).
  export VAULT_ADDR="http://${SUBSTRATE_HOST}:8200"
  export EDEN_NATS_URL="${EDEN_NATS_URL:-nats://${SUBSTRATE_HOST}:4222}"
  export VAULT_USERNAME="${VAULT_USERNAME:-eden}"
  export VAULT_PASSWORD="${VAULT_PASSWORD:-${VAULT_DEV_PASSWORD:-eden-local-dev-password}}"
  export POSTGRES_USER="${POSTGRES_USER:-eden}"
  export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-eden}"
  export POSTGRES_DB="${POSTGRES_DB:-eden}"
  log "env loaded; harness credential keys present: $(present_keys)"
}

# present_keys reports which harness credential NAMES are non-empty (never the values).
present_keys() {
  local out=""
  [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && out="${out} CLAUDE_CODE_OAUTH_TOKEN"
  [ -n "${CLAUDEADAPTER_LIVE_TOKEN:-}" ] && out="${out} CLAUDEADAPTER_LIVE_TOKEN"
  [ -n "${OPENROUTER_API_KEY:-}" ] && out="${out} OPENROUTER_API_KEY"
  printf '%s' "${out:- (none)}"
}

local_up() {
  command -v docker >/dev/null 2>&1 || die "docker is required (docker-out-of-docker in the devcontainer)"
  load_env
  log "bringing up the supporting stack (Vault + NATS + Postgres) ..."
  compose up -d
  log "waiting for Vault/NATS/Postgres health ..."
  wait_healthy eden-vault
  wait_nats
  wait_healthy eden-postgres
  local_seed
}

# wait_nats polls the NATS monitoring endpoint from the host (the nats image is distroless, so it
# has no in-container healthcheck — it is ready when /healthz answers ok).
wait_nats() {
  for _ in $(seq 1 30); do
    if curl -fsS "http://${SUBSTRATE_HOST}:8222/healthz" >/dev/null 2>&1; then
      log "  eden-nats: healthy"
      return 0
    fi
    sleep 1
  done
  die "eden-nats did not become healthy in time"
}

local_seed() {
  load_env
  log "seeding the REAL Vault from ${ENV_FILE} ..."
  # The seed runs INSIDE the vault container so the `vault` CLI + the server are co-located; it
  # mounts the repo to read .env.development and the seed script. Values cross via the env (-e),
  # never via a logged command. We pass only the NAMES' values through the environment.
  EDEN_DEPLOY_STATE_DIR="${STATE_DIR}" \
    bash "${LOCAL_DIR}/vault-seed.sh"
}

local_verify() {
  load_env
  log "verifying a kv get returns the seeded reference WITHOUT printing the value ..."
  local init_file="${STATE_DIR}/vault-init.json"
  [ -f "${init_file}" ] || die "Vault not initialized (run: deploy local up)"
  local token mount path len
  token="$(jq -r '.root_token' "${init_file}")"
  mount="${EDEN_VAULT_MOUNT:-eden}"; path="${EDEN_VAULT_PATH:-development}"
  # Run the vault CLI INSIDE the container (the host devcontainer has no vault CLI). Read the
  # field's BYTE LENGTH only — NEVER its value.
  len="$(docker exec -e "VAULT_TOKEN=${token}" -e "VAULT_ADDR=http://127.0.0.1:8200" eden-vault \
    vault kv get -field=setup-token "${mount}/${path}" 2>/dev/null | wc -c | tr -d ' ')" || die "kv get failed — is the secret seeded?"
  if [ "${len:-0}" -gt 1 ]; then
    log "OK: vault://${mount}/${path}#setup-token resolves to a ${len}-byte value (value NOT printed)."
  else
    die "the seeded setup-token field is empty or absent"
  fi
}

local_down() {
  log "tearing down the supporting stack (and volumes) ..."
  compose down -v --remove-orphans || true
  rm -rf "${STATE_DIR}" 2>/dev/null || true
}

# wait_healthy blocks until the named container reports healthy (or times out).
wait_healthy() {
  local name="$1"
  for _ in $(seq 1 60); do
    local status
    status="$(docker inspect -f '{{.State.Health.Status}}' "${name}" 2>/dev/null || echo missing)"
    case "${status}" in
      healthy) log "  ${name}: healthy"; return 0 ;;
      missing) die "container ${name} is not running" ;;
    esac
    sleep 2
  done
  die "${name} did not become healthy in time"
}

# ── THE DEMO: one command → live UI → real agent ─────────────────────────────────────────────────
demo_up() {
  local_up
  # setsid makes each child a session/group leader so demo_down can reap its whole process tree
  # (go run / bun x vite spawn grandchildren). Fall back to a bare subshell if setsid is absent.
  local launcher="setsid"; command -v setsid >/dev/null 2>&1 || launcher=""
  log "starting agentgateway-live (REAL ${EDEN_HARNESS:-claude-code} harness over the local Vault) on ${GATEWAY_ADDRESS} ..."
  mkdir -p "${STATE_DIR}"
  # The gateway inherits VAULT_*/EDEN_* from load_env (exported). VAULT_ADDR already points at the
  # reachable SUBSTRATE_HOST. Run it detached as a group leader; the leader pid is recorded.
  ${launcher} env \
      GOWORK="${REPO_ROOT}/go.work" \
      EDEN_GATEWAY_ADDRESS="${GATEWAY_ADDRESS}" \
      EDEN_CREDENTIAL_REF="${EDEN_CREDENTIAL_REF:-vault://eden/development#setup-token}" \
      EDEN_HARNESS="${EDEN_HARNESS:-claude-code}" \
      bash -c "cd '${REPO_ROOT}/apps/agentgateway' && exec go run ./cmd/agentgateway-live" \
      >"${STATE_DIR}/gateway.log" 2>&1 &
  echo $! > "${STATE_DIR}/gateway.pid"
  wait_gateway

  log "starting the SvelteKit chat UI (vite via bun) on port ${FRONTEND_PORT} ..."
  # The base devcontainer is bun-only (no node/yarn); the frontend's ctl.sh runs `bun x vite dev`.
  # The vite proxy forwards /gateway → the live gateway (EDEN_GATEWAY_TARGET), same-origin (no CORS).
  ${launcher} env \
      EDEN_GATEWAY_TARGET="http://${GATEWAY_ADDRESS}" \
      bash -c "cd '${REPO_ROOT}/apps/frontend' && exec bash ./ctl.sh dev --port '${FRONTEND_PORT}' --host 127.0.0.1 --strictPort" \
      >"${STATE_DIR}/frontend.log" 2>&1 &
  echo $! > "${STATE_DIR}/frontend.pid"

  log ""
  log "  ============================================================"
  log "  LIVE: open  http://127.0.0.1:${FRONTEND_PORT}/chat"
  log "  gateway:    http://${GATEWAY_ADDRESS}/healthz"
  log "  harness:    ${EDEN_HARNESS:-claude-code} (real) via vault://eden/development#setup-token"
  log "  logs:       ${STATE_DIR}/{gateway,frontend}.log"
  log "  stop:       bash deploy/ctl.sh demo down"
  log "  ============================================================"
}

wait_gateway() {
  log "waiting for the gateway /healthz ..."
  for _ in $(seq 1 60); do
    if curl -fsS "http://${GATEWAY_ADDRESS}/healthz" >/dev/null 2>&1; then
      log "  gateway: healthy"
      return 0
    fi
    sleep 1
  done
  warn "gateway did not answer /healthz in time; check ${STATE_DIR}/gateway.log"
}

demo_down() {
  log "reaping the demo (frontend + gateway + any live harness children) ..."
  for p in frontend gateway; do
    local pidfile="${STATE_DIR}/${p}.pid"
    if [ -f "${pidfile}" ]; then
      local pid; pid="$(cat "${pidfile}")"
      # Kill the whole process group (go run / bun x vite spawn children) — the children were
      # started under setsid in demo_up so the leader's group reaps the whole tree.
      kill -- "-${pid}" 2>/dev/null || kill "${pid}" 2>/dev/null || true
      rm -f "${pidfile}"
    fi
  done
  # Belt-and-suspenders: reap stray demo processes by command match (the live cmd, the vite dev
  # server, and the agentsession-spawned claude/omp harness children) — these are unique to THIS
  # demo, never an interactive harness session. A real async harness can outlive a hard gateway
  # kill, so this prevents the orphan-harness leak. `-A/--ignore-ancestors` keeps pkill from
  # signalling this very script's own process tree (so the down command itself finishes cleanly).
  for pattern in 'exe/agentgateway-live' 'cmd/agentgateway-live' 'vite dev' \
                 'claude -p --output-format stream-json --verbose --input-format stream-json' \
                 'omp .* --mode json'; do
    pkill -A -f "${pattern}" 2>/dev/null || pkill -f "${pattern}" 2>/dev/null || true
  done
  local_down
}

# ── PRODUCTION: render the Helm chart from the typed ServiceSpec ──────────────────────────────────
production_render() {
  log "rendering the Helm chart + compose from the typed ServiceSpec ..."
  ( cd "${REPO_ROOT}/deploy/servicespec" && GOWORK=off go run ./cmd/render "$@" )
  log "rendered into deploy/plane/production (Helm) — apply with: helm install eden deploy/plane/production/chart"
}

usage() {
  sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 1
}

main() {
  local plane="${1:-}"; shift || true
  case "${plane}" in
    local)
      local verb="${1:-up}"
      case "${verb}" in
        up) local_up ;;
        down) local_down ;;
        seed) local_seed ;;
        verify) local_verify ;;
        *) die "unknown 'local' verb: ${verb}" ;;
      esac
      ;;
    demo)
      local verb="${1:-up}"
      case "${verb}" in
        up|"") demo_up ;;
        down) demo_down ;;
        *) die "unknown 'demo' verb: ${verb}" ;;
      esac
      ;;
    production)
      local verb="${1:-render}"; shift || true
      case "${verb}" in
        render) production_render "$@" ;;
        *) die "unknown 'production' verb: ${verb}" ;;
      esac
      ;;
    ""|-h|--help|help) usage ;;
    *) die "unknown plane: ${plane} (local|demo|production)" ;;
  esac
}

main "$@"
