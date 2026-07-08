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
#   bash deploy/ctl.sh demo ssh-editor-config  # print the ~/.ssh/config alias for the desktop ssh-remote editor
#                                              # (set EDEN_EDITOR_SSH_HOST first; opt-in — the demo is web-only without it)
#   bash deploy/ctl.sh production render # render the Helm chart from the typed ServiceSpec
#   bash deploy/ctl.sh release v<semver> # cut a stable release: tag → release.yml (build+push+promote)
#   bash deploy/ctl.sh release-status v<semver> # watch the cut: the CI runs, the infra PR, the Argo app
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
PLATFORM_ADDRESS="${EDEN_PLATFORM_ADDRESS:-127.0.0.1:8081}" # platformgateway (Eden's platform HTTP API: users + login)
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
  # The dashboard's persisted-Project store DSN (eden-postgres). Points at SUBSTRATE_HOST so the
  # gateway reaches it both from the host (127.0.0.1) and from inside the devcontainer
  # (host.docker.internal). agentgateway-live reads DATABASE_URL; unset → the /projects routes 503.
  export DATABASE_URL="${DATABASE_URL:-postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${SUBSTRATE_HOST}:5432/${POSTGRES_DB}?sslmode=disable}"
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
      EDEN_SUPERVISOR_WORKSPACE_ROOT="${REPO_ROOT}/.eden-runtime/supervisors" \
      EDEN_WORKSPACE="${REPO_ROOT}/.eden-runtime/session" \
      EDEN_EDITOR_URL_BASE="${EDEN_EDITOR_URL_BASE:-http://localhost:${CODE_SERVER_PORT}}" \
      EDEN_EDITOR_SSH_HOST="${EDEN_EDITOR_SSH_HOST:-}" \
      bash -c "cd '${REPO_ROOT}/apps/agentgateway' && exec go run ./cmd/agentgateway-live" \
      >"${STATE_DIR}/gateway.log" 2>&1 &
  echo $! > "${STATE_DIR}/gateway.pid"
  wait_gateway

  log "starting platformgateway-live (Eden's platform HTTP API: users + login) on ${PLATFORM_ADDRESS} ..."
  # platformgateway resolves its JWT signing key + Postgres DSN from the SAME local Vault (seeded by
  # vault-seed.sh as platformgateway-jwt-signing-key / platformgateway-database-dsn under
  # eden/development); it runs migrations + seeds the default user at startup against eden-postgres.
  ${launcher} env \
      GOWORK="${REPO_ROOT}/go.work" \
      EDEN_GATEWAY_ADDRESS="${PLATFORM_ADDRESS}" \
      EDEN_GATEWAY_JWT_SECRET_REF="vault://eden/development#platformgateway-jwt-signing-key" \
      EDEN_GATEWAY_DATABASE_DSN_REF="vault://eden/development#platformgateway-database-dsn" \
      bash -c "cd '${REPO_ROOT}/apps/platformgateway' && exec go run ./cmd/gateway" \
      >"${STATE_DIR}/platform.log" 2>&1 &
  echo $! > "${STATE_DIR}/platform.pid"
  wait_platform

  log "starting the SvelteKit chat UI (vite via bun) on port ${FRONTEND_PORT} ..."
  # The base devcontainer is bun-only (no node/yarn); the frontend's ctl.sh runs `bun x vite dev`.
  # The vite proxy forwards /gateway → the live gateway (EDEN_GATEWAY_TARGET), same-origin (no CORS).
  # vite binds 0.0.0.0 (NOT 127.0.0.1): the demo runs INSIDE the devcontainer, and the published-port
  # proxy sidecar (start_demo_proxy, below) reaches it over the devcontainer's bridge IP — a service
  # bound to the container's own loopback would be unreachable from that sidecar. The gateway stays
  # loopback-only (the vite proxy reaches it in-container); only the UI port is host-exposed.
  ${launcher} env \
      EDEN_GATEWAY_TARGET="http://${GATEWAY_ADDRESS}" \
      EDEN_PLATFORM_TARGET="http://${PLATFORM_ADDRESS}" \
      bash -c "cd '${REPO_ROOT}/apps/frontend' && exec bash ./ctl.sh dev --port '${FRONTEND_PORT}' --host 0.0.0.0 --strictPort" \
      >"${STATE_DIR}/frontend.log" 2>&1 &
  echo $! > "${STATE_DIR}/frontend.pid"

  # Publish the UI to the Mac host. The devcontainer itself publishes NO host ports, so a Mac browser
  # can only reach a PUBLISHED port. Once vite answers in-container, start a published-port proxy
  # sidecar (alpine/socat) over docker-out-of-docker: -p publishes FRONTEND_PORT to the Mac host
  # through Docker Desktop, forwarding to the devcontainer's bridge IP where vite now listens.
  start_demo_proxy
  start_code_server
  start_ssh_editor

  log ""
  log "  ============================================================"
  log "  LIVE: open  http://127.0.0.1:${FRONTEND_PORT}/   (login → Projects dashboard)"
  log "  gateway:    http://${GATEWAY_ADDRESS}/healthz   (agentgateway — chat/agents)"
  log "  platform:   http://${PLATFORM_ADDRESS}/healthz/live   (platformgateway — users/login)"
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

# wait_platform blocks until platformgateway answers its liveness probe (it migrates + seeds the
# default user on startup, so a slightly longer budget covers the first-boot schema work).
wait_platform() {
  log "waiting for platformgateway /healthz/live ..."
  for _ in $(seq 1 60); do
    if curl -fsS "http://${PLATFORM_ADDRESS}/healthz/live" >/dev/null 2>&1; then
      log "  platformgateway: healthy"
      return 0
    fi
    sleep 1
  done
  warn "platformgateway did not answer /healthz/live in time; check ${STATE_DIR}/platform.log"
}

# DEMO_PROXY_NAME is the published-port proxy sidecar that bridges the Mac host to the in-container
# vite dev server. It is unique to the demo, so demo_down reaps it by this fixed name.
DEMO_PROXY_NAME="eden-demo-proxy"

# The LOCAL (docker) read-only VS Code editor workload. CODE_SERVER_PORT is the Mac-host port the
# editor is published on; the gateway hands the UI per-project URLs (…/?folder=<worktree>) under it.
CODE_SERVER_NAME="eden-codeserver"
CODE_SERVER_PORT="${EDEN_EDITOR_PORT:-8500}"
CODE_SERVER_IMAGE="${EDEN_EDITOR_IMAGE:-codercom/code-server:latest}"
# The devcontainer name whose /workspace mount the editor shares READ-ONLY (--volumes-from). The
# project worktrees live under /workspace/.eden-runtime (set in demo_up), so the editor sees them live.
EDEN_DEVCONTAINER_NAME="${EDEN_DEVCONTAINER_NAME:-base-devcontainer}"

# ── The DESKTOP ssh-remote read-only editor (Workstream C) ────────────────────────────────────────.
# A SECOND, OPTIONAL editor surface for the NATIVE VS Code path. When EDEN_EDITOR_SSH_HOST is set, the
# gateway returns it as the editor `sshHost`, and the desktop app opens
# `vscode://vscode-remote/ssh-remote+<host><worktreePath>` so the user's own VS Code attaches over SSH.
# That requires a real sshd reachable at <host>; this builds + runs a SIBLING container (the docker
# adapter exposes NO container ports, so it cannot live in the agent container) that mounts the
# devcontainer /workspace READ-ONLY (the EROFS read-only guarantee, OD-EDITOR-2) with a SEPARATE
# writable home volume for the VS Code Server bootstrap. The host alias <EDEN_EDITOR_SSH_HOST> is
# resolved by an ~/.ssh/config block (deploy/ssh-editor/ssh-config-snippet, emitted by `ssh-editor-config`)
# to 127.0.0.1:SSH_EDITOR_PORT with the matching key — a CONFIG alias, never a credential on the wire.
#
# GATING: EDEN_EDITOR_SSH_HOST is UNSET by default → start_ssh_editor SKIPS and the gateway returns an
# empty sshHost → the UI stays on today's WEB code-server path. The demo is unchanged unless an operator
# opts in by exporting EDEN_EDITOR_SSH_HOST (the host alias) before `deploy demo`.
SSH_EDITOR_NAME="eden-ssh-editor"
SSH_EDITOR_PORT="${EDEN_EDITOR_SSH_PORT:-2222}"
SSH_EDITOR_IMAGE="${EDEN_SSH_EDITOR_IMAGE:-eden/ssh-editor:local}"
SSH_EDITOR_HOME_VOLUME="${EDEN_SSH_EDITOR_HOME_VOLUME:-eden-ssh-editor-home}"
# The key pair the desktop client presents. The PRIVATE half stays on the host (~/.ssh); only the
# PUBLIC half is handed to the sibling container at start. Generated on first run by start_ssh_editor.
SSH_EDITOR_KEY_DIR="${EDEN_SSH_EDITOR_KEY_DIR:-${STATE_DIR}/ssh-editor}"
SSH_EDITOR_KEY="${SSH_EDITOR_KEY_DIR}/id_ed25519"
SSH_EDITOR_DOCKERFILE_DIR="${SCRIPT_DIR}/ssh-editor"

# start_code_server runs a SINGLE read-only code-server (VS Code in the browser) that mounts the
# devcontainer's /workspace READ-ONLY via --volumes-from — so every project's live worktree (under
# /workspace/.eden-runtime/supervisors/…) is VIEWABLE but never editable. It is published to the Mac
# host at 127.0.0.1:CODE_SERVER_PORT (the same docker-out-of-docker publish the UI proxy uses); the
# gateway returns per-project URLs http://localhost:CODE_SERVER_PORT/?folder=<worktree>. The reusable
# browser tab re-points to a new ?folder when you open a different project. In KUBERNETES this LOCAL
# adapter is replaced by a per-project code-server Deployment+Service+Ingress mounting the project's
# workspace PVC read-only (the gateway's editor URL contract is identical, only the base URL differs).
# Skipped outside the devcontainer or if the image is unavailable.
start_code_server() {
  command -v docker >/dev/null 2>&1 || { warn "docker absent; skipping the code-server editor"; return 0; }
  if [ ! -f /.dockerenv ]; then return 0; fi
  log "starting the read-only VS Code (code-server) editor on 127.0.0.1:${CODE_SERVER_PORT} ..."
  docker rm -f "${CODE_SERVER_NAME}" >/dev/null 2>&1 || true
  if docker run -d --rm --name "${CODE_SERVER_NAME}" --label eden.demo=codeserver \
      --volumes-from "${EDEN_DEVCONTAINER_NAME}:ro" \
      -p "127.0.0.1:${CODE_SERVER_PORT}:8080" \
      "${CODE_SERVER_IMAGE}" --auth none --bind-addr 0.0.0.0:8080 /workspace \
      >/dev/null 2>&1; then
    log "  ${CODE_SERVER_NAME}: read-only VS Code at http://localhost:${CODE_SERVER_PORT}/ (opened per-project from the UI)"
  else
    warn "failed to start ${CODE_SERVER_NAME}; the 'Open in VS Code' button is unavailable (is ${CODE_SERVER_IMAGE} pulled? is ${EDEN_DEVCONTAINER_NAME} the devcontainer name?)"
  fi
}

# ensure_ssh_editor_key generates the desktop client's ed25519 key pair under the deploy state dir on
# first run. The PRIVATE half NEVER leaves the host; only the PUBLIC half is provisioned into the
# sibling sshd at start. Idempotent: an existing key is reused. The bytes are never echoed.
ensure_ssh_editor_key() {
  if [ -f "${SSH_EDITOR_KEY}" ] && [ -f "${SSH_EDITOR_KEY}.pub" ]; then return 0; fi
  mkdir -p "${SSH_EDITOR_KEY_DIR}"
  chmod 700 "${SSH_EDITOR_KEY_DIR}"
  log "generating the desktop ssh-editor key pair (${SSH_EDITOR_KEY}) ..."
  # -N '' (no passphrase) so the desktop client attaches non-interactively; the key is loopback-scoped
  # and lives only in the gitignored deploy state. -q keeps the public-key bytes off the log.
  ssh-keygen -t ed25519 -N '' -C 'eden-ssh-editor' -f "${SSH_EDITOR_KEY}" -q
  chmod 600 "${SSH_EDITOR_KEY}"
}

# start_ssh_editor runs the SIBLING sshd the DESKTOP "Open in VS Code" path attaches to (the native
# VS Code ssh-remote). It is GATED on EDEN_EDITOR_SSH_HOST: unset → skip (today's web-only behaviour,
# the demo unchanged). When set, it builds the deploy/ssh-editor image (if absent), ensures the client
# key, then runs the container with /workspace READ-ONLY (--volumes-from :ro → EROFS, OD-EDITOR-2) plus
# a SEPARATE writable home volume for the VS Code Server bootstrap, publishing :22 to
# 127.0.0.1:SSH_EDITOR_PORT (loopback-only, like the code-server). The eden PUBLIC key is handed in via
# EDEN_SSH_EDITOR_AUTHORIZED_KEY (entrypoint installs it as the only authorized key). In KUBERNETES this
# LOCAL adapter is replaced by a per-project sshd Deployment+Service mounting the workspace PVC read-only
# (the desktop ssh-remote+<host><path> URI contract is identical). Skipped outside the devcontainer.
start_ssh_editor() {
  # GATE: the desktop ssh-remote editor is opt-in. Unset host → the gateway returns an empty sshHost →
  # the UI uses the web code-server path. This keeps the default demo exactly as it is today.
  if [ -z "${EDEN_EDITOR_SSH_HOST:-}" ]; then
    log "EDEN_EDITOR_SSH_HOST unset — skipping the desktop ssh-remote editor (web code-server only)"
    return 0
  fi
  command -v docker >/dev/null 2>&1 || { warn "docker absent; skipping the ssh-remote editor"; return 0; }
  if [ ! -f /.dockerenv ]; then return 0; fi

  ensure_ssh_editor_key

  # Build the minimal openssh image once (idempotent; docker layer-caches). The Dockerfile + sshd_config
  # + entrypoint live in deploy/ssh-editor.
  if ! docker image inspect "${SSH_EDITOR_IMAGE}" >/dev/null 2>&1; then
    log "building the ssh-editor image (${SSH_EDITOR_IMAGE}) from ${SSH_EDITOR_DOCKERFILE_DIR} ..."
    if ! docker build -t "${SSH_EDITOR_IMAGE}" "${SSH_EDITOR_DOCKERFILE_DIR}" >"${STATE_DIR}/ssh-editor-build.log" 2>&1; then
      warn "failed to build ${SSH_EDITOR_IMAGE}; the desktop ssh-remote editor is unavailable (see ${STATE_DIR}/ssh-editor-build.log)"
      return 0
    fi
  fi

  log "starting the read-only ssh-remote editor (${SSH_EDITOR_NAME}) on 127.0.0.1:${SSH_EDITOR_PORT} ..."
  docker rm -f "${SSH_EDITOR_NAME}" >/dev/null 2>&1 || true
  # --volumes-from …:ro mounts /workspace READ-ONLY (worktree un-writable, EROFS). The SEPARATE
  # writable named volume at /home/eden lets VS Code Server bootstrap (~/.vscode-server) succeed while
  # the source tree stays immutable. The PUBLIC key is passed via env (a public key is not a secret).
  if docker run -d --rm --name "${SSH_EDITOR_NAME}" --label eden.demo=ssheditor \
      --volumes-from "${EDEN_DEVCONTAINER_NAME}:ro" \
      -v "${SSH_EDITOR_HOME_VOLUME}:/home/eden" \
      -e "EDEN_SSH_EDITOR_AUTHORIZED_KEY=$(cat "${SSH_EDITOR_KEY}.pub")" \
      -p "127.0.0.1:${SSH_EDITOR_PORT}:22" \
      "${SSH_EDITOR_IMAGE}" \
      >/dev/null 2>&1; then
    log "  ${SSH_EDITOR_NAME}: read-only ssh-remote editor at 127.0.0.1:${SSH_EDITOR_PORT} (user 'eden', key-only)"
    write_ssh_editor_config
    log "  ssh alias '${EDEN_EDITOR_SSH_HOST}' written to ${SSH_EDITOR_KEY_DIR}/ssh-config-snippet"
    log "  enable it once with: cat '${SSH_EDITOR_KEY_DIR}/ssh-config-snippet' >> ~/.ssh/config"
  else
    warn "failed to start ${SSH_EDITOR_NAME}; the desktop 'Open in VS Code' (ssh-remote) path is unavailable"
  fi
}

# write_ssh_editor_config emits the ~/.ssh/config block that resolves the host alias EDEN_EDITOR_SSH_HOST
# to 127.0.0.1:SSH_EDITOR_PORT with the matching private key. This is a CONFIG alias — the gateway/UI only
# ever hand the OS the bare alias in the vscode://…ssh-remote+<alias> URI; the credential (the key path)
# stays in the user's local ssh config, never on the wire. The operator appends this once to ~/.ssh/config.
write_ssh_editor_config() {
  local snippet="${SSH_EDITOR_KEY_DIR}/ssh-config-snippet"
  mkdir -p "${SSH_EDITOR_KEY_DIR}"
  cat > "${snippet}" <<EOF
# Eden read-only ssh-remote editor — generated by deploy/ctl.sh start_ssh_editor.
# Append once to ~/.ssh/config so VS Code's vscode://…ssh-remote+${EDEN_EDITOR_SSH_HOST} resolves here.
Host ${EDEN_EDITOR_SSH_HOST}
  HostName 127.0.0.1
  Port ${SSH_EDITOR_PORT}
  User eden
  IdentityFile ${SSH_EDITOR_KEY}
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
  UserKnownHostsFile ${SSH_EDITOR_KEY_DIR}/known_hosts
EOF
  chmod 600 "${snippet}"
}

# ssh_editor_config prints the ~/.ssh/config alias block on demand (the `ssh-editor-config` verb) so an
# operator can wire the alias WITHOUT a running demo (e.g. before `deploy demo` with EDEN_EDITOR_SSH_HOST
# set). It requires the host alias so the block is concrete; the key is generated if absent.
ssh_editor_config() {
  [ -n "${EDEN_EDITOR_SSH_HOST:-}" ] || die "set EDEN_EDITOR_SSH_HOST (the host alias) first — it names the ssh config block"
  ensure_ssh_editor_key
  write_ssh_editor_config
  log "ssh-editor alias '${EDEN_EDITOR_SSH_HOST}' → 127.0.0.1:${SSH_EDITOR_PORT}; append this to ~/.ssh/config:"
  cat "${SSH_EDITOR_KEY_DIR}/ssh-config-snippet"
}

# start_demo_proxy publishes the in-container vite UI to the Mac host. The demo runs INSIDE the
# devcontainer, which publishes no host ports of its own, so a Mac browser cannot reach a service
# bound only on the container. The proven fix: once vite answers in-container, start an alpine/socat
# sidecar over docker-out-of-docker whose -p publishes FRONTEND_PORT to 127.0.0.1 on the Mac host
# (through Docker Desktop) and forwards it to the devcontainer's bridge IP (`hostname -i`) where vite
# listens on 0.0.0.0. On the bare host (no devcontainer) vite is already reachable at 127.0.0.1, so
# the sidecar is skipped. Idempotent: any prior sidecar is reaped first.
start_demo_proxy() {
  command -v docker >/dev/null 2>&1 || { warn "docker absent; skipping the host-reachability proxy"; return 0; }
  # Only needed inside the devcontainer (bridge-network container over docker-out-of-docker); on the
  # bare host vite's 0.0.0.0 bind is already reachable at 127.0.0.1.
  if [ ! -f /.dockerenv ]; then return 0; fi

  local bridge_ip
  bridge_ip="$(hostname -i 2>/dev/null | awk '{print $1}')"
  if [ -z "${bridge_ip}" ]; then
    warn "could not determine the devcontainer bridge IP; the UI may be reachable only in-container"
    return 0
  fi

  wait_frontend || warn "vite did not answer in time; starting the proxy anyway (it forks per-connection)"

  log "publishing the UI to the Mac host via ${DEMO_PROXY_NAME} (127.0.0.1:${FRONTEND_PORT} -> ${bridge_ip}:${FRONTEND_PORT}) ..."
  docker rm -f "${DEMO_PROXY_NAME}" >/dev/null 2>&1 || true
  if docker run -d --rm --name "${DEMO_PROXY_NAME}" \
      -p "127.0.0.1:${FRONTEND_PORT}:${FRONTEND_PORT}" \
      alpine/socat "TCP-LISTEN:${FRONTEND_PORT},fork,reuseaddr" "TCP:${bridge_ip}:${FRONTEND_PORT}" \
      >/dev/null 2>&1; then
    log "  ${DEMO_PROXY_NAME}: publishing 127.0.0.1:${FRONTEND_PORT} to the Mac host"
  else
    warn "failed to start ${DEMO_PROXY_NAME}; the UI is reachable in-container but maybe not from the Mac host"
  fi
}

# wait_frontend blocks until the in-container vite dev server answers on the devcontainer bridge IP
# (so the published-port sidecar has a live upstream to forward to). A non-2xx/3xx still proves the
# listener is up — we are probing liveness, not asserting a status.
wait_frontend() {
  local bridge_ip
  bridge_ip="$(hostname -i 2>/dev/null | awk '{print $1}')"
  [ -n "${bridge_ip}" ] || return 1
  log "waiting for vite to answer in-container (http://${bridge_ip}:${FRONTEND_PORT}) ..."
  for _ in $(seq 1 60); do
    if curl -s -o /dev/null "http://${bridge_ip}:${FRONTEND_PORT}/" 2>/dev/null; then
      log "  vite: up"
      return 0
    fi
    sleep 1
  done
  return 1
}

demo_down() {
  log "reaping the demo (proxy + frontend + gateway + any live harness children) ..."
  # Reap the published-port proxy sidecar FIRST so the Mac host port is released immediately (it is
  # a docker-out-of-docker container, not a process group, so the pidfile reap below never sees it).
  if command -v docker >/dev/null 2>&1; then
    docker rm -f "${DEMO_PROXY_NAME}" >/dev/null 2>&1 || true
    # Reap every read-only code-server editor sidecar by label (one shot, count-agnostic).
    docker ps -aq --filter label=eden.demo=codeserver 2>/dev/null | xargs -r docker rm -f >/dev/null 2>&1 || true
    # Reap the read-only ssh-remote editor sibling(s) by label too (the desktop "Open in VS Code" path).
    docker ps -aq --filter label=eden.demo=ssheditor 2>/dev/null | xargs -r docker rm -f >/dev/null 2>&1 || true
  fi
  for p in frontend gateway platform; do
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

# ── RELEASE: cut a stable release → tag → the release.yml build+push+promote flow ─────────────────
# `bash deploy/ctl.sh release v<semver>` validates the version, the tree, and the branch, confirms
# the harness pin is committed (the agent-runtime build needs it), then tags + pushes — the `v*` tag
# triggers .github/workflows/release.yml (multi-arch build+push of the four images to
# ghcr.io/gophersys/eden/* + the digest-pin promotion PR against gophersys/infrastructure). It NEVER
# prints a secret value; the whole cut is one verb (the AI-instrumentation seam).
EDEN_GHCR_OWNER="gophersys/eden"
EDEN_RELEASE_WORKFLOW="release.yml"

release_cut() {
  local version="${1:-}"
  command -v git >/dev/null 2>&1 || die "git is required to cut a release"
  [ -n "${version}" ] || die "usage: deploy release v<semver>  (e.g. deploy release v0.1.0)"

  # 1. The version MUST be a v-prefixed semver (the release.yml `v*` tag contract + the render drift
  # test's ghcr.io/gophersys/eden/<service>:<semver> expectation). A pre-release/build suffix is allowed.
  if ! printf '%s' "${version}" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$'; then
    die "version '${version}' is not a v-semver (want vMAJOR.MINOR.PATCH, e.g. v0.1.0)"
  fi

  # 2. The tag must not already exist (locally or on origin) — a re-tag needs an explicit delete first.
  if git -C "${REPO_ROOT}" rev-parse -q --verify "refs/tags/${version}" >/dev/null 2>&1; then
    die "tag ${version} already exists locally (delete it first: git tag -d ${version})"
  fi
  if git -C "${REPO_ROOT}" ls-remote --exit-code --tags origin "refs/tags/${version}" >/dev/null 2>&1; then
    die "tag ${version} already exists on origin (a released version is immutable)"
  fi

  # 3. The working tree must be clean (no uncommitted changes ride into a release).
  if [ -n "$(git -C "${REPO_ROOT}" status --porcelain)" ]; then
    warn "working tree is dirty:"
    git -C "${REPO_ROOT}" status --short >&2
    die "commit or stash your changes before cutting a release"
  fi

  # 4. The current branch must be up-to-date with its origin counterpart. The repo's working branch is
  # init/seed today (NOT main) — assert the CURRENT branch, whatever it is, matches origin/<branch>.
  local branch
  branch="$(git -C "${REPO_ROOT}" rev-parse --abbrev-ref HEAD)"
  [ "${branch}" != "HEAD" ] || die "detached HEAD — check out the release branch first"
  log "fetching origin to compare ${branch} with its upstream ..."
  git -C "${REPO_ROOT}" fetch --quiet origin || die "git fetch origin failed"
  if ! git -C "${REPO_ROOT}" rev-parse -q --verify "refs/remotes/origin/${branch}" >/dev/null 2>&1; then
    die "origin/${branch} does not exist — push ${branch} first"
  fi
  local head remote
  head="$(git -C "${REPO_ROOT}" rev-parse HEAD)"
  remote="$(git -C "${REPO_ROOT}" rev-parse "origin/${branch}")"
  if [ "${head}" != "${remote}" ]; then
    die "${branch} (${head:0:7}) is not up-to-date with origin/${branch} (${remote:0:7}) — push/pull first"
  fi

  # 5. The harness pin MUST be committed — the agent-runtime image build sources CLAUDE_CODE_VERSION
  # from harnesses/versions.env (ADR-0021), so an uncommitted pin would build a different harness than
  # HEAD claims. (Tree-clean already implies this; assert the file is TRACKED for a precise message.)
  if ! git -C "${REPO_ROOT}" ls-files --error-unmatch harnesses/versions.env >/dev/null 2>&1; then
    die "harnesses/versions.env is not tracked — the agent-runtime build needs the committed pin (ADR-0021)"
  fi
  local claude_pin
  claude_pin="$(grep -E '^CLAUDE_CODE_VERSION=' "${REPO_ROOT}/harnesses/versions.env" | cut -d= -f2)"
  [ -n "${claude_pin}" ] || die "CLAUDE_CODE_VERSION is empty in harnesses/versions.env"

  # 6. Tag + push. The tag push is what triggers release.yml.
  log "cutting release ${version} from ${branch} @ ${head:0:7} (Claude Code pin ${claude_pin}) ..."
  git -C "${REPO_ROOT}" tag -a "${version}" -m "eden release ${version}" || die "git tag ${version} failed"
  if ! git -C "${REPO_ROOT}" push origin "${version}"; then
    git -C "${REPO_ROOT}" tag -d "${version}" >/dev/null 2>&1 || true
    die "git push origin ${version} failed (the local tag was rolled back)"
  fi

  local origin_url actions_url
  origin_url="$(git -C "${REPO_ROOT}" remote get-url origin 2>/dev/null || echo '')"
  actions_url="$(gh_actions_url "${origin_url}")"
  log ""
  log "  ============================================================"
  log "  RELEASE ${version} TAGGED + PUSHED."
  log "  → release.yml now builds+pushes the 4 images multi-arch to ghcr.io/${EDEN_GHCR_OWNER}/*"
  log "    and opens the digest-pin PR against gophersys/infrastructure (apps/eden)."
  log "  Watch the run:   ${actions_url}"
  log "  Then poll:       bash deploy/ctl.sh release-status ${version}"
  log "  On PR merge, Argo CD reconciles apps/eden onto the home cluster."
  log "  ============================================================"
}

# gh_actions_url derives the Actions page URL from the origin remote (ssh or https form), degrading to
# a bare hint when the remote is not a recognizable GitHub URL. Never prints a credential.
gh_actions_url() {
  local url="${1:-}" slug=""
  case "${url}" in
    git@github.com:*) slug="${url#git@github.com:}" ;;
    https://github.com/*) slug="${url#https://github.com/}" ;;
    ssh://git@github.com/*) slug="${url#ssh://git@github.com/}" ;;
  esac
  slug="${slug%.git}"
  if [ -n "${slug}" ]; then
    printf 'https://github.com/%s/actions/workflows/%s' "${slug}" "${EDEN_RELEASE_WORKFLOW}"
  else
    printf '(the %s workflow run in your repo Actions tab)' "${EDEN_RELEASE_WORKFLOW}"
  fi
}

# ── RELEASE-STATUS: watch a cut without leaving the verb ───────────────────────────────────────────
# `bash deploy/ctl.sh release-status v<semver>` reports: the release.yml runs for the tag (gh run
# list), the open infra promotion PR, and (read-only) the Argo Application on the home cluster when a
# kubeconfig is present. Every step degrades HONESTLY when its tool/credential is absent — it never
# fabricates a status and never prints a secret.
EDEN_HOME_KUBECONFIG="${EDEN_HOME_KUBECONFIG:-${HOME}/.kube/eden-clusters.yaml}"

release_status() {
  local version="${1:-}"
  [ -n "${version}" ] || die "usage: deploy release-status v<semver>"

  # 1. The release.yml runs for this tag (needs the gh CLI + auth; degrade if absent).
  log "── release.yml runs for ${version} ──"
  if command -v gh >/dev/null 2>&1; then
    if gh auth status >/dev/null 2>&1; then
      gh run list --workflow "${EDEN_RELEASE_WORKFLOW}" --branch "${version}" --limit 5 \
        2>/dev/null || warn "  gh run list failed (is ${EDEN_RELEASE_WORKFLOW} present on the remote yet?)"
    else
      warn "  gh is installed but not authenticated (run: gh auth login) — cannot list runs"
    fi
  else
    warn "  gh CLI not installed — see the Actions tab for the ${EDEN_RELEASE_WORKFLOW} run on tag ${version}"
  fi

  # 2. The open infra promotion PR (title `chore(deploy): eden -> <version>`).
  log "── infrastructure promotion PR ──"
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    local pr_json
    pr_json="$(gh pr list --repo gophersys/infrastructure --state open \
      --search "chore(deploy): eden -> ${version} in:title" --json url,title 2>/dev/null || echo '')"
    if [ -n "${pr_json}" ] && [ "${pr_json}" != "[]" ]; then
      printf '%s\n' "${pr_json}" | (jq -r '.[] | "  \(.title)\n  \(.url)"' 2>/dev/null || printf '  %s\n' "${pr_json}")
    else
      warn "  no open promotion PR for ${version} yet (the promote job opens it after all 4 builds pass)"
    fi
  else
    warn "  gh unavailable/unauthenticated — check gophersys/infrastructure PRs for 'eden -> ${version}'"
  fi

  # 3. The Argo Application on the home cluster (READ-ONLY), only if a kubeconfig is present + reachable.
  log "── Argo Application 'eden' on the home cluster (read-only) ──"
  if [ ! -f "${EDEN_HOME_KUBECONFIG}" ]; then
    warn "  no home kubeconfig at ${EDEN_HOME_KUBECONFIG} — skipping the live Argo read (set EDEN_HOME_KUBECONFIG to override)"
  elif ! command -v kubectl >/dev/null 2>&1; then
    warn "  kubectl not installed — cannot read the Argo Application"
  else
    if KUBECONFIG="${EDEN_HOME_KUBECONFIG}" kubectl --context home get application -n argocd eden \
         -o wide 2>/dev/null; then
      : # printed above
    else
      warn "  could not read Application/eden (cluster unreachable, context 'home' absent, or app not yet registered) — reporting honestly, not fabricating a status"
    fi
  fi
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
        ssh-editor-config) ssh_editor_config ;;
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
    release) release_cut "$@" ;;
    release-status) release_status "$@" ;;
    ""|-h|--help|help) usage ;;
    *) die "unknown plane: ${plane} (local|demo|production|release|release-status)" ;;
  esac
}

main "$@"
