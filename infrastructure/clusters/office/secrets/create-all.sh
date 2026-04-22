#!/usr/bin/env bash
# create-all.sh — Create ALL Kubernetes secrets required for Concord.
# Single source of truth for secrets management. Reads from:
#   shared.env     — secrets common across all environments
#   {namespace}.env — per-environment secrets (staging.env, production.env)
#
# Usage:
#   bash infrastructure/clusters/office/secrets/create-all.sh              # All namespaces
#   bash infrastructure/clusters/office/secrets/create-all.sh staging      # Single namespace
#   bash infrastructure/clusters/office/secrets/create-all.sh --dry-run    # Preview only
#
# Nx shortcuts:
#   nx run platform:sync-secrets -c staging
#   nx run platform:sync-secrets -c production
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLUSTER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CLUSTER_YAML="${CLUSTER_DIR}/cluster.yaml"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[secrets]${NC} $*"; }
info() { echo -e "${CYAN}[secrets]${NC} $*"; }
warn() { echo -e "${YELLOW}[secrets]${NC} $*"; }
err()  { echo -e "${RED}[secrets]${NC} $*" >&2; }

PASS=0
FAIL=0
DRY_RUN=false
TARGET_NS=""

for arg in "$@"; do
  case "${arg}" in
    --dry-run) DRY_RUN=true ;;
    *)         TARGET_NS="${arg}" ;;
  esac
done

# ── Require tools ────────────────────────────────────────────────
command -v kubectl >/dev/null 2>&1 || { err "kubectl not found"; exit 1; }
command -v yq >/dev/null 2>&1 || { err "yq not found"; exit 1; }

# ── Load env files ───────────────────────────────────────────────
SHARED_ENV="${SCRIPT_DIR}/shared.env"

if [[ ! -f "${SHARED_ENV}" ]]; then
  err "shared.env not found at: ${SHARED_ENV}"
  err "Copy from .env.example and fill in values:"
  err "  cp ${SCRIPT_DIR}/.env.example ${SHARED_ENV}"
  exit 1
fi

load_env() {
  local file="$1"
  if [[ -f "${file}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${file}"
    set +a
  fi
}

apply_secret() {
  local ns="$1"
  shift
  if $DRY_RUN; then
    echo "  [dry-run] kubectl create secret $* -n ${ns} --dry-run=client -o yaml | kubectl apply -f -"
    PASS=$((PASS + 1))
  else
    if kubectl create secret "$@" -n "${ns}" --dry-run=client -o yaml | kubectl apply -f - 2>&1 | sed 's/^/  /'; then
      PASS=$((PASS + 1))
    else
      FAIL=$((FAIL + 1))
    fi
  fi
}

# ── Process one namespace ───────────────────────────────────────
process_namespace() {
  local ns="$1"
  local ns_env="${SCRIPT_DIR}/${ns}.env"

  log "${BOLD}Namespace: ${ns}${NC}"
  echo ""

  # Load shared env, then per-namespace overrides
  load_env "${SHARED_ENV}"
  if [[ -f "${ns_env}" ]]; then
    load_env "${ns_env}"
  elif [[ "${ns}" == "staging" || "${ns}" == "production" ]]; then
    err "  ${ns}.env not found at: ${ns_env}"
    err "  Copy from .env.example and fill in values for ${ns}"
    FAIL=$((FAIL + 1))
    echo ""
    return
  fi

  # ── 1. bitbucket-ssh-key ─────────────────────────────────────
  log "  bitbucket-ssh-key"
  BITBUCKET_SSH_KEY_PATH="${BITBUCKET_SSH_KEY_PATH:-}"
  if [[ -z "${BITBUCKET_SSH_KEY_PATH}" ]]; then
    warn "    BITBUCKET_SSH_KEY_PATH not set — skipping"
  elif [[ ! -f "${BITBUCKET_SSH_KEY_PATH}" ]]; then
    err "    SSH key not found: ${BITBUCKET_SSH_KEY_PATH}"
    FAIL=$((FAIL + 1))
  else
    apply_secret "${ns}" generic bitbucket-ssh-key \
      --from-file=ssh-private-key="${BITBUCKET_SSH_KEY_PATH}"
  fi

  # ── 2. concord-build-service-secrets ─────────────────────────
  log "  concord-build-service-secrets"
  BUILD_SERVICE_API_KEY="${BUILD_SERVICE_API_KEY:-}"
  if [[ -z "${BUILD_SERVICE_API_KEY}" ]]; then
    warn "    BUILD_SERVICE_API_KEY not set — skipping"
  else
    local bs_args=(
      --from-literal=api-key="${BUILD_SERVICE_API_KEY}"
    )
    [[ -n "${BITBUCKET_EMAIL:-}" ]] && bs_args+=(--from-literal=bitbucket-email="${BITBUCKET_EMAIL}")
    [[ -n "${BITBUCKET_API_TOKEN:-}" ]] && bs_args+=(--from-literal=bitbucket-api-token="${BITBUCKET_API_TOKEN}")
    apply_secret "${ns}" generic concord-build-service-secrets "${bs_args[@]}"
  fi

  # ── 3. corecloud-validation ──────────────────────────────────
  log "  corecloud-validation"
  if [[ -z "${CORECLOUD_VALIDATION_API_KEY:-}" ]]; then
    info "    CORECLOUD_VALIDATION_API_KEY not set — skipping (optional)"
  else
    apply_secret "${ns}" generic corecloud-validation \
      --from-literal=api-key="${CORECLOUD_VALIDATION_API_KEY}"
  fi

  # ── 4. theta-mcuboot-keys ───────────────────────────────────
  log "  theta-mcuboot-keys"
  if [[ -z "${MCUBOOT_APP_KEY_PATH:-}" ]] && [[ -z "${MCUBOOT_COMMS_KEY_PATH:-}" ]]; then
    info "    MCUBOOT_*_KEY_PATH not set — skipping (optional)"
  elif [[ ! -f "${MCUBOOT_APP_KEY_PATH:-/dev/null}" ]] || [[ ! -f "${MCUBOOT_COMMS_KEY_PATH:-/dev/null}" ]]; then
    err "    MCUboot key file(s) not found"
    FAIL=$((FAIL + 1))
  else
    apply_secret "${ns}" generic theta-mcuboot-keys \
      --from-file=encryption_key.pem="${MCUBOOT_APP_KEY_PATH}" \
      --from-file=comms_encryption_key.pem="${MCUBOOT_COMMS_KEY_PATH}"
  fi

  # ── 5. concord-pypi-htpasswd ─────────────────────────────────
  if [[ "${ns}" == "staging" || "${ns}" == "production" ]]; then
    log "  concord-pypi-htpasswd"
    if [[ -n "${PYPI_HTPASSWD:-}" ]]; then
      if $DRY_RUN; then
        echo "  [dry-run] create concord-pypi-htpasswd"
        PASS=$((PASS + 1))
      else
        echo "${PYPI_HTPASSWD}" | kubectl create secret generic concord-pypi-htpasswd \
          --from-file=.htpasswd=/dev/stdin -n "${ns}" --dry-run=client -o yaml \
          | kubectl apply -f - 2>&1 | sed 's/^/  /'
        PASS=$((PASS + 1))
      fi
    else
      info "    PYPI_HTPASSWD not set — skipping (optional)"
    fi
  fi

  # ── 6. concord-infra-credentials (staging/production only) ───
  if [[ "${ns}" == "staging" || "${ns}" == "production" ]]; then
    log "  concord-infra-credentials"
    local infra_args=(
      --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-concord}"
      --from-literal=MINIO_ROOT_USER="${MINIO_ROOT_USER:-minioadmin}"
      --from-literal=MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-minioadmin}"
    )
    apply_secret "${ns}" generic concord-infra-credentials "${infra_args[@]}"
  fi

  # ── 7. concord-secrets (staging/production only) ─────────────
  if [[ "${ns}" == "staging" || "${ns}" == "production" ]]; then
    log "  concord-secrets"
    local cs_args=(
      --from-literal=DATABASE_URL="${DATABASE_URL:-}"
      --from-literal=DIRECT_DATABASE_URL="${DIRECT_DATABASE_URL:-}"
      --from-literal=STORAGE_ACCESS_KEY="${STORAGE_ACCESS_KEY:-}"
      --from-literal=STORAGE_SECRET_ACCESS_KEY="${STORAGE_SECRET_ACCESS_KEY:-}"
      --from-literal=JWT_SECRET_KEY="${JWT_SECRET_KEY:-}"
      --from-literal=BITBUCKET_API_TOKEN="${BITBUCKET_API_TOKEN:-}"
      --from-literal=AUTH_SERVER_API_KEY="${AUTH_SERVER_API_KEY:-}"
      --from-literal=DELETE_ALL_KEY="${DELETE_ALL_KEY:-}"
      --from-literal=BITBUCKET_WEBHOOK_SECRET="${BITBUCKET_WEBHOOK_SECRET:-}"
      --from-literal=COREOPS_API_KEY="${COREOPS_API_KEY:-}"
      --from-literal=COREOPS_AUTH_USER="${COREOPS_AUTH_USER:-}"
      --from-literal=COREOPS_AUTH_PASS="${COREOPS_AUTH_PASS:-}"
    )
    apply_secret "${ns}" generic concord-secrets "${cs_args[@]}"
  fi

  # ── 8. ci-minio-upload (devops only) ─────────────────────────
  if [[ "${ns}" == "devops" ]]; then
    log "  ci-minio-upload"
    if [[ -z "${CI_MINIO_USER:-}" ]] || [[ -z "${CI_MINIO_PASSWORD:-}" ]]; then
      info "    CI_MINIO_USER/PASSWORD not set — skipping (optional)"
    else
      apply_secret "${ns}" generic ci-minio-upload \
        --from-literal=MINIO_ACCESS_KEY="${CI_MINIO_USER}" \
        --from-literal=MINIO_SECRET_KEY="${CI_MINIO_PASSWORD}"
    fi

    log "  claude-code-oauth"
    CLAUDE_CREDENTIALS_PATH="${CLAUDE_CREDENTIALS_PATH:-${HOME}/.claude/.credentials.json}"
    if [[ ! -f "${CLAUDE_CREDENTIALS_PATH}" ]]; then
      info "    Claude credentials not found at ${CLAUDE_CREDENTIALS_PATH} — skipping (optional)"
    else
      apply_secret "${ns}" generic claude-code-oauth \
        --from-file=credentials.json="${CLAUDE_CREDENTIALS_PATH}"
    fi
  fi

  echo ""
}

# ── Determine namespaces ────────────────────────────────────────
if [[ -n "${TARGET_NS}" ]]; then
  NAMESPACES=("${TARGET_NS}")
else
  mapfile -t NAMESPACES < <(yq -r '.namespaces[]' "${CLUSTER_YAML}" 2>/dev/null)
fi

log "${BOLD}Creating secrets for: ${NAMESPACES[*]}${NC}"
$DRY_RUN && info "  Mode: DRY RUN"
echo ""

for ns in "${NAMESPACES[@]}"; do
  process_namespace "${ns}"
done

# ── Summary ─────────────────────────────────────────────────────
echo "=== secrets: ${PASS} applied, ${FAIL} failed ==="
if [[ ${FAIL} -gt 0 ]]; then
  exit 1
fi
