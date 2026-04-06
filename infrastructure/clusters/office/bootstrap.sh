#!/usr/bin/env bash
# bootstrap.sh — Idempotent setup for the office K3s cluster.
# Takes the cluster from 0 → ready for Helm deploys.
#
# Usage:
#   bash infrastructure/clusters/office/bootstrap.sh           # Apply all
#   bash infrastructure/clusters/office/bootstrap.sh --dry-run  # Preview only
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[bootstrap]${NC} $*"; }
info() { echo -e "${CYAN}[bootstrap]${NC} $*"; }
warn() { echo -e "${RED}[bootstrap]${NC} $*"; }

kube_apply() {
  local file="$1"
  local desc="${2:-$(basename "$file")}"
  if $DRY_RUN; then
    echo "  [dry-run] kubectl apply -f ${file}"
  else
    if kubectl apply -f "${file}" 2>&1 | grep -v "^$"; then
      true
    fi
  fi
}

kube_label_node() {
  local node="$1"
  shift
  local labels="$*"
  if $DRY_RUN; then
    echo "  [dry-run] kubectl label node ${node} ${labels} --overwrite"
  else
    kubectl label node "${node}" ${labels} --overwrite 2>/dev/null || true
  fi
}

# ── Header ────────────────────────────────────────────────────
log "Office K3s Cluster Bootstrap"
$DRY_RUN && info "  Mode: DRY RUN (no changes will be made)"
echo ""

# ── Step 1: Namespaces ───────────────────────────────────────
log "Step 1/6: Namespaces"
for f in "${SCRIPT_DIR}"/namespaces/*.yaml; do
  [[ -f "$f" ]] && kube_apply "$f" "namespace $(basename "$f" .yaml)"
done
echo ""

# ── Step 2: Node labels ─────────────────────────────────────
log "Step 2/6: Node labels"
if command -v yq >/dev/null 2>&1 && [[ -f "${SCRIPT_DIR}/nodes/labels.yaml" ]]; then
  node_count=$(yq -r '.nodes | length' "${SCRIPT_DIR}/nodes/labels.yaml" 2>/dev/null || echo 0)
  for ((i=0; i<node_count; i++)); do
    node_name=$(yq -r ".nodes[${i}].name" "${SCRIPT_DIR}/nodes/labels.yaml")
    # Build label string from the labels map
    label_str=""
    while IFS= read -r key; do
      val=$(yq -r ".nodes[${i}].labels.\"${key}\"" "${SCRIPT_DIR}/nodes/labels.yaml")
      label_str="${label_str} ${key}=${val}"
    done < <(yq -r ".nodes[${i}].labels | keys | .[]" "${SCRIPT_DIR}/nodes/labels.yaml" 2>/dev/null)
    if [[ -n "${label_str}" ]]; then
      kube_label_node "${node_name}" ${label_str}
    fi
  done
else
  info "  Skipping node labels (yq not available or labels.yaml missing)"
fi
echo ""

# ── Step 3: RBAC — ClusterRoles ─────────────────────────────
log "Step 3/6: RBAC — ClusterRoles"
kube_apply "${SCRIPT_DIR}/rbac/clusterroles.yaml" "ClusterRoles"
echo ""

# ── Step 4: RBAC — RoleBindings + ServiceAccounts ───────────
log "Step 4/6: RBAC — Bindings & ServiceAccounts"
kube_apply "${SCRIPT_DIR}/rbac/service-accounts.yaml" "ServiceAccount bindings"
for f in "${SCRIPT_DIR}"/rbac/bindings-*.yaml; do
  [[ -f "$f" ]] && kube_apply "$f" "bindings $(basename "$f" .yaml)"
done
echo ""

# ── Step 5: Networking — cert-manager + TLS ─────────────────
log "Step 5/6: Networking — cert-manager CA + certificates"
if [[ -f "${SCRIPT_DIR}/networking/cert-manager-ca.yaml" ]]; then
  kube_apply "${SCRIPT_DIR}/networking/cert-manager-ca.yaml" "cert-manager CA"
fi
for f in "${SCRIPT_DIR}"/networking/certificates/*.yaml; do
  [[ -f "$f" ]] && kube_apply "$f" "certificate $(basename "$f" .yaml)"
done
echo ""

# ── Step 6: Storage ─────────────────────────────────────────
log "Step 6/6: Storage"
if [[ -f "${SCRIPT_DIR}/storage/storage-classes.yaml" ]]; then
  info "  StorageClass 'local-path' ships with K3s — verifying exists"
  if $DRY_RUN; then
    echo "  [dry-run] kubectl get sc local-path"
  else
    if kubectl get sc local-path >/dev/null 2>&1; then
      info "  ✓ local-path StorageClass exists"
    else
      warn "  ✗ local-path StorageClass not found — applying"
      kube_apply "${SCRIPT_DIR}/storage/storage-classes.yaml"
    fi
  fi
fi
echo ""

# ── Summary ─────────────────────────────────────────────────
if $DRY_RUN; then
  log "${BOLD}Dry run complete.${NC} No changes were made."
else
  log "${BOLD}Bootstrap complete.${NC}"
  info "  Namespaces, RBAC, certificates, and storage are configured."
  info "  The cluster is ready for: deploy/production/ctl.sh <env> deploy"
fi
