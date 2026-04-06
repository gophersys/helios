#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────────
# Concord Infrastructure CLI
# ───────────────────────────────────────────────────────────────
# Usage:
#   ./infrastructure/ctl.sh <cluster> <action>
#
# Clusters:
#   office    — On-premise K3s HA cluster
#   eks       — AWS EKS cluster (placeholder)
#
# Actions:
#   bootstrap   — Apply all manifests: namespaces, RBAC, certs, storage
#   status      — Show cluster readiness (namespaces, RBAC, certs, storage)
#   validate    — Dry-run all manifests, report errors
#   diff        — Show what bootstrap would change vs live state
# ───────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLUSTERS_DIR="${SCRIPT_DIR}/clusters"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[infra]${NC} $*"; }
warn() { echo -e "${YELLOW}[infra]${NC} $*"; }
err()  { echo -e "${RED}[infra]${NC} $*" >&2; }
info() { echo -e "${CYAN}[infra]${NC} $*"; }

# ─── Validate cluster ────────────────────────────────────────

validate_cluster() {
  local cluster="$1"
  local cluster_dir="${CLUSTERS_DIR}/${cluster}"
  if [[ ! -d "${cluster_dir}" ]]; then
    err "Unknown cluster: ${cluster}"
    err "Available clusters:"
    for d in "${CLUSTERS_DIR}"/*/; do
      [[ -d "$d" ]] && err "  - $(basename "$d")"
    done
    exit 1
  fi
}

# ─── Bootstrap ───────────────────────────────────────────────

cmd_bootstrap() {
  local cluster="$1"
  local cluster_dir="${CLUSTERS_DIR}/${cluster}"
  local bootstrap="${cluster_dir}/bootstrap.sh"

  if [[ ! -f "${bootstrap}" ]]; then
    err "No bootstrap.sh found for cluster '${cluster}'"
    exit 1
  fi

  log "Bootstrapping cluster: ${BOLD}${cluster}${NC}"
  bash "${bootstrap}"
}

# ─── Status ──────────────────────────────────────────────────

cmd_status() {
  local cluster="$1"
  local cluster_dir="${CLUSTERS_DIR}/${cluster}"
  local cluster_yaml="${cluster_dir}/cluster.yaml"

  log "Cluster status: ${BOLD}${cluster}${NC}"
  echo ""

  # Namespaces
  echo -e "${BOLD}=== Namespaces ===${NC}"
  if command -v yq >/dev/null 2>&1 && [[ -f "${cluster_yaml}" ]]; then
    while IFS= read -r ns; do
      if kubectl get ns "${ns}" >/dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} ${ns}"
      else
        echo -e "  ${RED}✗${NC} ${ns} (missing)"
      fi
    done < <(yq -r '.namespaces[]' "${cluster_yaml}" 2>/dev/null)
  else
    kubectl get ns --no-headers 2>/dev/null | awk '{print "  "$1}'
  fi
  echo ""

  # RBAC
  echo -e "${BOLD}=== ClusterRoles ===${NC}"
  for role in concord-super-admin concord-namespace-admin concord-namespace-readonly concord-api-system-monitor; do
    if kubectl get clusterrole "${role}" >/dev/null 2>&1; then
      echo -e "  ${GREEN}✓${NC} ${role}"
    else
      echo -e "  ${RED}✗${NC} ${role} (missing)"
    fi
  done
  echo ""

  # cert-manager
  echo -e "${BOLD}=== Certificates ===${NC}"
  if kubectl get clusterissuer concord-ca-issuer >/dev/null 2>&1; then
    ready=$(kubectl get clusterissuer concord-ca-issuer -o jsonpath='{.status.conditions[0].status}' 2>/dev/null)
    echo -e "  ${GREEN}✓${NC} concord-ca-issuer (Ready=${ready})"
  else
    echo -e "  ${RED}✗${NC} concord-ca-issuer (missing)"
  fi
  echo ""

  # Storage
  echo -e "${BOLD}=== Storage ===${NC}"
  kubectl get sc --no-headers 2>/dev/null | while read -r line; do
    echo "  ${line}"
  done
  echo ""

  # Nodes
  echo -e "${BOLD}=== Nodes ===${NC}"
  kubectl get nodes -o wide --no-headers 2>/dev/null | while read -r line; do
    echo "  ${line}"
  done
}

# ─── Validate ────────────────────────────────────────────────

cmd_validate() {
  local cluster="$1"
  local cluster_dir="${CLUSTERS_DIR}/${cluster}"

  log "Validating cluster manifests: ${BOLD}${cluster}${NC}"

  # Run bootstrap in dry-run mode
  local bootstrap="${cluster_dir}/bootstrap.sh"
  if [[ -f "${bootstrap}" ]]; then
    bash "${bootstrap}" --dry-run
  else
    err "No bootstrap.sh found for cluster '${cluster}'"
    exit 1
  fi
}

# ─── Diff ────────────────────────────────────────────────────

cmd_diff() {
  local cluster="$1"
  local cluster_dir="${CLUSTERS_DIR}/${cluster}"

  log "Diffing cluster manifests: ${BOLD}${cluster}${NC}"
  echo ""

  for f in $(find "${cluster_dir}" -name '*.yaml' -type f | sort); do
    base=$(basename "$f")
    [[ "${base}" == "cluster.yaml" ]] && continue
    [[ "$f" == */nodes/* ]] && continue

    # Check if it's a valid K8s manifest
    kind=$(yq -r '.kind' "$f" 2>/dev/null | grep -v '^null$' | head -1 || true)
    [[ -z "${kind}" ]] && continue

    echo -e "${CYAN}--- ${f#${SCRIPT_DIR}/} ---${NC}"
    kubectl diff -f "$f" 2>/dev/null || true
  done
}

# ─── Help ────────────────────────────────────────────────────

usage() {
  cat <<EOF

${BOLD}Concord Infrastructure CLI${NC}

${BOLD}Usage:${NC}
  ./infrastructure/ctl.sh <cluster> <action>

${BOLD}Clusters:${NC}
$(for d in "${CLUSTERS_DIR}"/*/; do [[ -d "$d" ]] && echo "  $(basename "$d")"; done)

${BOLD}Actions:${NC}
  ${GREEN}bootstrap${NC}    Apply all manifests (namespaces, RBAC, certs, storage)
  ${GREEN}status${NC}       Show cluster readiness
  ${GREEN}validate${NC}     Dry-run all manifests
  ${GREEN}diff${NC}         Show what bootstrap would change

${BOLD}Examples:${NC}
  ./infrastructure/ctl.sh office bootstrap     # Set up the office cluster
  ./infrastructure/ctl.sh office status        # Check readiness
  ./infrastructure/ctl.sh office validate      # Preview changes
  ./infrastructure/ctl.sh eks bootstrap        # Set up EKS (placeholder)

EOF
}

# ─── Main ────────────────────────────────────────────────────

if [[ $# -eq 0 ]] || [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]] || [[ "$1" == "help" ]]; then
  usage
  exit 0
fi

CLUSTER="${1}"
ACTION="${2:-status}"

validate_cluster "${CLUSTER}"

case "${ACTION}" in
  bootstrap)  cmd_bootstrap "${CLUSTER}" ;;
  status)     cmd_status "${CLUSTER}" ;;
  validate)   cmd_validate "${CLUSTER}" ;;
  diff)       cmd_diff "${CLUSTER}" ;;
  *)
    err "Unknown action: ${ACTION}"
    usage
    exit 1
    ;;
esac
