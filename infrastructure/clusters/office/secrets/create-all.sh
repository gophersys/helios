#!/usr/bin/env bash
# create-all.sh — Create all Kubernetes secrets required for Concord app deployment.
# Reads values from .env file in this directory. Idempotent (apply, not create).
#
# Usage:
#   bash infrastructure/clusters/office/secrets/create-all.sh              # All namespaces
#   bash infrastructure/clusters/office/secrets/create-all.sh staging      # Single namespace
#   bash infrastructure/clusters/office/secrets/create-all.sh --dry-run    # Preview only
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLUSTER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CLUSTER_YAML="${CLUSTER_DIR}/cluster.yaml"
ENV_FILE="${SCRIPT_DIR}/.env"

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

# Parse args
for arg in "$@"; do
  case "${arg}" in
    --dry-run) DRY_RUN=true ;;
    *)         TARGET_NS="${arg}" ;;
  esac
done

# ── Require tools ────────────────────────────────────────────────
command -v kubectl >/dev/null 2>&1 || { err "kubectl not found"; exit 1; }
command -v yq >/dev/null 2>&1 || { err "yq not found"; exit 1; }

# ── Load .env ────────────────────────────────────────────────────
if [[ ! -f "${ENV_FILE}" ]]; then
  err ".env file not found at: ${ENV_FILE}"
  err "Copy .env.example to .env and fill in real values:"
  err "  cp ${SCRIPT_DIR}/.env.example ${SCRIPT_DIR}/.env"
  exit 1
fi

# Source .env (supports KEY=VALUE, ignores comments and empty lines)
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

# ── Determine namespaces ────────────────────────────────────────
if [[ -n "${TARGET_NS}" ]]; then
  NAMESPACES=("${TARGET_NS}")
else
  mapfile -t NAMESPACES < <(yq -r '.namespaces[]' "${CLUSTER_YAML}" 2>/dev/null)
fi

log "${BOLD}Creating secrets for: ${NAMESPACES[*]}${NC}"
$DRY_RUN && info "  Mode: DRY RUN"
echo ""

# ── Helper: create-or-apply a secret ────────────────────────────
apply_secret() {
  local ns="$1"
  shift
  # remaining args are passed to kubectl create secret
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

# ── Secret 1: bitbucket-ssh-key ─────────────────────────────────
log "bitbucket-ssh-key"
BITBUCKET_SSH_KEY_PATH="${BITBUCKET_SSH_KEY_PATH:-}"
if [[ -z "${BITBUCKET_SSH_KEY_PATH}" ]]; then
  warn "  BITBUCKET_SSH_KEY_PATH not set — skipping"
elif [[ ! -f "${BITBUCKET_SSH_KEY_PATH}" ]]; then
  err "  SSH key not found: ${BITBUCKET_SSH_KEY_PATH}"
  FAIL=$((FAIL + 1))
else
  for ns in "${NAMESPACES[@]}"; do
    apply_secret "${ns}" generic bitbucket-ssh-key \
      --from-file=ssh-private-key="${BITBUCKET_SSH_KEY_PATH}"
  done
fi
echo ""

# ── Secret 2: concord-build-service-secrets ─────────────────────
# Used by: build-service (API auth), git-poller (API auth + Bitbucket REST)
log "concord-build-service-secrets"
BUILD_SERVICE_API_KEY="${BUILD_SERVICE_API_KEY:-}"
BITBUCKET_EMAIL="${BITBUCKET_EMAIL:-}"
BITBUCKET_API_TOKEN="${BITBUCKET_API_TOKEN:-}"
if [[ -z "${BUILD_SERVICE_API_KEY}" ]]; then
  warn "  BUILD_SERVICE_API_KEY not set — skipping"
else
  local_args=(
    --from-literal=api-key="${BUILD_SERVICE_API_KEY}"
  )
  # Bitbucket REST API credentials (optional — needed for PR monitoring)
  if [[ -n "${BITBUCKET_EMAIL}" ]]; then
    local_args+=(--from-literal=bitbucket-email="${BITBUCKET_EMAIL}")
  fi
  if [[ -n "${BITBUCKET_API_TOKEN}" ]]; then
    local_args+=(--from-literal=bitbucket-api-token="${BITBUCKET_API_TOKEN}")
  fi
  for ns in "${NAMESPACES[@]}"; do
    apply_secret "${ns}" generic concord-build-service-secrets "${local_args[@]}"
  done
fi
echo ""

# ── Secret 3: corecloud-validation ──────────────────────────────
log "corecloud-validation"
CORECLOUD_VALIDATION_API_KEY="${CORECLOUD_VALIDATION_API_KEY:-}"
if [[ -z "${CORECLOUD_VALIDATION_API_KEY}" ]]; then
  info "  CORECLOUD_VALIDATION_API_KEY not set — skipping (optional)"
else
  for ns in "${NAMESPACES[@]}"; do
    apply_secret "${ns}" generic corecloud-validation \
      --from-literal=api-key="${CORECLOUD_VALIDATION_API_KEY}"
  done
fi
echo ""

# ── Secret 4: theta-mcuboot-keys ───────────────────────────────
log "theta-mcuboot-keys"
MCUBOOT_APP_KEY_PATH="${MCUBOOT_APP_KEY_PATH:-}"
MCUBOOT_COMMS_KEY_PATH="${MCUBOOT_COMMS_KEY_PATH:-}"
if [[ -z "${MCUBOOT_APP_KEY_PATH}" ]] && [[ -z "${MCUBOOT_COMMS_KEY_PATH}" ]]; then
  info "  MCUBOOT_*_KEY_PATH not set — skipping (optional)"
elif [[ ! -f "${MCUBOOT_APP_KEY_PATH}" ]] || [[ ! -f "${MCUBOOT_COMMS_KEY_PATH}" ]]; then
  err "  MCUboot key file(s) not found"
  [[ -n "${MCUBOOT_APP_KEY_PATH}" ]] && [[ ! -f "${MCUBOOT_APP_KEY_PATH}" ]] && err "    Missing: ${MCUBOOT_APP_KEY_PATH}"
  [[ -n "${MCUBOOT_COMMS_KEY_PATH}" ]] && [[ ! -f "${MCUBOOT_COMMS_KEY_PATH}" ]] && err "    Missing: ${MCUBOOT_COMMS_KEY_PATH}"
  FAIL=$((FAIL + 1))
else
  for ns in "${NAMESPACES[@]}"; do
    apply_secret "${ns}" generic theta-mcuboot-keys \
      --from-file=encryption_key.pem="${MCUBOOT_APP_KEY_PATH}" \
      --from-file=comms_encryption_key.pem="${MCUBOOT_COMMS_KEY_PATH}"
  done
fi
echo ""

# ── Secret 5: ci-minio-upload (devops namespace only) ──────────
# Used by: CI CronJobs to upload test results to cluster MinIO.
log "ci-minio-upload"
MINIO_ROOT_USER="${MINIO_ROOT_USER:-}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-}"
if [[ -z "${MINIO_ROOT_USER}" ]] || [[ -z "${MINIO_ROOT_PASSWORD}" ]]; then
  info "  MINIO_ROOT_USER/PASSWORD not set — skipping (optional)"
else
  for ns in "${NAMESPACES[@]}"; do
    if [[ "${ns}" == "devops" ]]; then
      apply_secret "${ns}" generic ci-minio-upload \
        --from-literal=MINIO_ACCESS_KEY="${MINIO_ROOT_USER}" \
        --from-literal=MINIO_SECRET_KEY="${MINIO_ROOT_PASSWORD}"
    fi
  done
fi
echo ""

# ── Summary ─────────────────────────────────────────────────────
echo "=== secrets: ${PASS} applied, ${FAIL} failed ==="
if [[ ${FAIL} -gt 0 ]]; then
  exit 1
fi
