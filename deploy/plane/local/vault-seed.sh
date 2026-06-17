#!/usr/bin/env bash
# vault-seed.sh — initialize/unseal the REAL local Vault and seed the harness credentials from
# `.env.development` into a KV v2 mount, then enable userpass auth for the agent's bootstrap role.
#
# ADR-0022 #1/#2: local runs a REAL `hashicorp/vault` (server mode, NOT -dev), with a thin one-shot
# init/unseal bootstrap. `deploy local` loads `.env.development` into the env AND seeds those values
# into this Vault, from which the spawned agents resolve their credentials (the secrets/vaultadapter
# `vault://<mount>/<path>#<key>` path) — never loose files reaching the harness.
#
# The host devcontainer is bun/go-only (no `vault` CLI), so every `vault` invocation runs INSIDE the
# already-running `eden-vault` container via `docker exec` (the hashicorp/vault image carries the
# CLI). Values cross via the container's env (-e), never via a traced/logged command.
#
# ── SECRET SAFETY (the cardinal rule of this script) ──────────────────────────────────────────────
#   * `set +x` is forced ON and never disabled: no command (and so no value) is ever traced.
#   * No credential VALUE is ever echo'd, printed, or written to a tracked file. Values live only in
#     shell variables and the `vault kv put key=value` argv inside the container, which is NOT
#     logged. Keys are referenced by NAME only.
#   * The unseal key + root token ARE captured once at init to the gitignored deploy state dir
#     (`.state/vault-init.json`, mode 600) — never to a tracked path, never to stdout.
#   * This script READS `.env.development` at runtime; it embeds nothing. The file stays gitignored.
set -Eeuo pipefail
set +x # SECRET SAFETY: never trace — a traced `vault kv put k=$V` would leak V.

# ── Configuration (all overridable; defaults match `.env.example`) ────────────────────────────────
VAULT_CONTAINER="${EDEN_VAULT_CONTAINER:-eden-vault}"
VAULT_MOUNT="${EDEN_VAULT_MOUNT:-eden}"            # the KV v2 mount the vault:// references name
VAULT_SECRET_PATH="${EDEN_VAULT_PATH:-development}" # the KV v2 path under the mount
VAULT_USERNAME="${VAULT_USERNAME:-eden}"          # the userpass bootstrap role the agent logs in as
VAULT_POLICY="${EDEN_VAULT_POLICY:-eden-agent}"   # the least-privilege read policy
STATE_DIR="${EDEN_DEPLOY_STATE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.state}"
INIT_FILE="${STATE_DIR}/vault-init.json"

# repo root (this file lives at deploy/plane/local/) → for locating .env.development
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENV_FILE="${EDEN_ENV_FILE:-${REPO_ROOT}/.env.development}"

log() { printf '[vault-seed] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

command -v docker >/dev/null 2>&1 || die "docker is required (to exec the vault CLI in the ${VAULT_CONTAINER} container)"
command -v jq >/dev/null 2>&1 || die "the 'jq' CLI is required to parse the init output"
docker inspect "${VAULT_CONTAINER}" >/dev/null 2>&1 || die "the ${VAULT_CONTAINER} container is not running (run: deploy local up)"

mkdir -p "${STATE_DIR}"; chmod 700 "${STATE_DIR}"

# vault runs the CLI inside the vault container against its local 127.0.0.1:8200. Extra `-e KEY=VAL`
# pairs may be passed BEFORE the `--` to inject env (e.g. a token) without it ever touching a host
# log. Written bash-3.2-safe (the macOS host bash errors on an empty-array expansion under `set -u`)
# by seeding the args array with the always-present VAULT_ADDR `-e` pair.
vault() {
  local env_args
  env_args=(-e "VAULT_ADDR=http://127.0.0.1:8200")
  while [ "$#" -gt 0 ] && [ "${1:-}" != "--" ]; do env_args+=(-e "$1"); shift; done
  shift || true # drop the --
  docker exec "${env_args[@]}" "${VAULT_CONTAINER}" vault "$@"
}

# status_json captures `vault status -format=json` output, tolerating its non-zero exit (vault
# exits 2 when sealed, 1 on error) WITHOUT pipefail double-appending. It echoes the JSON (or "{}").
status_json() {
  local out
  out="$(docker exec -e "VAULT_ADDR=http://127.0.0.1:8200" "${VAULT_CONTAINER}" vault status -format=json 2>/dev/null)" || true
  [ -n "${out}" ] && printf '%s' "${out}" || printf '%s' '{}'
}

# ── 1. Wait for Vault to answer ───────────────────────────────────────────────────────────────────
log "waiting for Vault in ${VAULT_CONTAINER} ..."
for _ in $(seq 1 60); do
  [ "$(status_json | jq -r '.type // empty')" != "" ] && break
  sleep 1
done

# ── 2. Initialize (one-shot) if not already initialized ───────────────────────────────────────────
initialized="$(status_json | jq -r '.initialized // false')"
if [ "${initialized}" != "true" ]; then
  log "initializing Vault (1 key share, threshold 1 — local single-node bootstrap) ..."
  # The init output (unseal key + root token) is captured to the gitignored state file ONLY.
  ( umask 077; vault -- operator init -key-shares=1 -key-threshold=1 -format=json > "${INIT_FILE}" )
  chmod 600 "${INIT_FILE}"
  jq -e '.root_token' "${INIT_FILE}" >/dev/null 2>&1 || die "init did not produce a root token"
  log "Vault initialized; unseal key + root token written to ${INIT_FILE} (gitignored, mode 600)."
else
  log "Vault already initialized; reusing ${INIT_FILE}."
  [ -f "${INIT_FILE}" ] || die "Vault is initialized but ${INIT_FILE} is missing — cannot recover the unseal key/root token"
fi

# ── 3. Unseal if sealed (values stay in shell vars; never printed) ────────────────────────────────
sealed="$(status_json | jq -r '.sealed // true')"
if [ "${sealed}" = "true" ]; then
  log "unsealing Vault ..."
  UNSEAL_KEY="$(jq -r '.unseal_keys_b64[0]' "${INIT_FILE}")"
  vault -- operator unseal "${UNSEAL_KEY}" >/dev/null 2>&1 || die "unseal failed"
  unset UNSEAL_KEY
  log "Vault unsealed."
fi

# ── 4. Root token for the seeding steps (stays in the container env via -e; never printed) ────────
ROOT_TOKEN="$(jq -r '.root_token' "${INIT_FILE}")"

# ── 5. Enable the KV v2 mount (idempotent) ────────────────────────────────────────────────────────
if ! vault "VAULT_TOKEN=${ROOT_TOKEN}" -- secrets list -format=json 2>/dev/null | jq -e --arg m "${VAULT_MOUNT}/" '.[$m]' >/dev/null; then
  log "enabling KV v2 mount '${VAULT_MOUNT}' ..."
  vault "VAULT_TOKEN=${ROOT_TOKEN}" -- secrets enable -path="${VAULT_MOUNT}" -version=2 kv >/dev/null 2>&1 || die "failed to enable KV v2 mount"
else
  log "KV v2 mount '${VAULT_MOUNT}' already enabled."
fi

# ── 6. Read `.env.development` and seed each NAMED key as a KV field (NEVER echoing a value) ───────
[ -f "${ENV_FILE}" ] || die "env file not found: ${ENV_FILE} (copy .env.example → .env.development and fill it in)"

read_env() {
  # $1 = key name. Returns the value on stdout (captured by the caller); empty if absent.
  grep -E "^${1}=" "${ENV_FILE}" 2>/dev/null | head -n1 | cut -d= -f2- || true
}

CLAUDE_TOKEN="$(read_env CLAUDE_CODE_OAUTH_TOKEN)"
[ -n "${CLAUDE_TOKEN}" ] || CLAUDE_TOKEN="$(read_env CLAUDEADAPTER_LIVE_TOKEN)"
OPENROUTER_KEY="$(read_env OPENROUTER_API_KEY)"

declare -a kv_pairs=() seeded_keys=()
if [ -n "${CLAUDE_TOKEN}" ]; then kv_pairs+=("setup-token=${CLAUDE_TOKEN}"); seeded_keys+=("setup-token"); fi
if [ -n "${OPENROUTER_KEY}" ]; then kv_pairs+=("openrouter-api-key=${OPENROUTER_KEY}"); seeded_keys+=("openrouter-api-key"); fi
[ "${#kv_pairs[@]}" -gt 0 ] || die "no harness credentials found in ${ENV_FILE} (need CLAUDE_CODE_OAUTH_TOKEN and/or OPENROUTER_API_KEY)"

# platformgateway (Eden's platform HTTP API) resolves its JWT signing key + Postgres DSN from Vault
# (EDEN_GATEWAY_JWT_SECRET_REF / EDEN_GATEWAY_DATABASE_DSN_REF). The DSN points at the same eden
# postgres the rest of the demo uses; the signing key is a FRESH local dev key (generated, never
# committed — the public login bootstrap needs no token, so a per-seed key is fine).
PLATFORM_JWT_KEY="$(openssl rand -hex 32 2>/dev/null || echo 'eden-platformgateway-local-dev-signing-key-32bytes')"
kv_pairs+=("platformgateway-jwt-signing-key=${PLATFORM_JWT_KEY}")
seeded_keys+=("platformgateway-jwt-signing-key")
if [ -n "${DATABASE_URL:-}" ]; then
  kv_pairs+=("platformgateway-database-dsn=${DATABASE_URL}")
  seeded_keys+=("platformgateway-database-dsn")
fi
unset PLATFORM_JWT_KEY

log "seeding ${#kv_pairs[@]} credential field(s) into ${VAULT_MOUNT}/${VAULT_SECRET_PATH}: ${seeded_keys[*]} (NAMES only) ..."
# `vault kv put` runs inside the container; the value is in the argv there, NOT on any host log.
# Redirect its stdout/stderr anyway (defense in depth — its metadata table has no value).
vault "VAULT_TOKEN=${ROOT_TOKEN}" -- kv put "${VAULT_MOUNT}/${VAULT_SECRET_PATH}" "${kv_pairs[@]}" >/dev/null 2>&1 || die "kv put failed"
unset CLAUDE_TOKEN OPENROUTER_KEY kv_pairs

# ── 7. Least-privilege read policy + userpass role the agent bootstraps with ──────────────────────
log "writing the least-privilege policy '${VAULT_POLICY}' (read ${VAULT_MOUNT}/data/${VAULT_SECRET_PATH}) ..."
POLICY_HCL="path \"${VAULT_MOUNT}/data/${VAULT_SECRET_PATH}\" { capabilities = [\"read\"] }"
printf '%s\n' "${POLICY_HCL}" | docker exec -i -e "VAULT_TOKEN=${ROOT_TOKEN}" -e "VAULT_ADDR=http://127.0.0.1:8200" "${VAULT_CONTAINER}" vault policy write "${VAULT_POLICY}" - >/dev/null 2>&1 || die "policy write failed"

if ! vault "VAULT_TOKEN=${ROOT_TOKEN}" -- auth list -format=json 2>/dev/null | jq -e '."userpass/"' >/dev/null; then
  log "enabling userpass auth ..."
  vault "VAULT_TOKEN=${ROOT_TOKEN}" -- auth enable userpass >/dev/null 2>&1 || die "failed to enable userpass auth"
fi

[ -n "${VAULT_PASSWORD:-}" ] || die "VAULT_PASSWORD must be set in the environment (deploy local exports it; never committed)"
log "binding userpass user '${VAULT_USERNAME}' to policy '${VAULT_POLICY}' ..."
vault "VAULT_TOKEN=${ROOT_TOKEN}" -- write "auth/userpass/users/${VAULT_USERNAME}" \
  password="${VAULT_PASSWORD}" policies="${VAULT_POLICY}" token_ttl=1h token_max_ttl=4h >/dev/null 2>&1 || die "userpass user bind failed"
unset ROOT_TOKEN

log "DONE — Vault seeded. The agent resolves vault://${VAULT_MOUNT}/${VAULT_SECRET_PATH}#setup-token via userpass '${VAULT_USERNAME}'."
log "(No credential value was printed by this script. ${INIT_FILE} holds the operator unseal key/root token — gitignored.)"
