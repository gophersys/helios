#!/usr/bin/env bash
# bootstrap.sh — Placeholder for EKS cluster setup.
# TODO: Implement with eksctl, ALB controller, EBS CSI driver, etc.
#
# Usage:
#   bash infrastructure/clusters/eks/bootstrap.sh           # Apply all
#   bash infrastructure/clusters/eks/bootstrap.sh --dry-run  # Preview only
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[bootstrap]${NC} $*"; }
info() { echo -e "${CYAN}[bootstrap]${NC} $*"; }
warn() { echo -e "${YELLOW}[bootstrap]${NC} $*"; }

kube_apply() {
  local file="$1"
  if $DRY_RUN; then
    echo "  [dry-run] kubectl apply -f ${file}"
  else
    kubectl apply -f "${file}" 2>&1 | grep -v "^$" || true
  fi
}

log "EKS Cluster Bootstrap (placeholder)"
$DRY_RUN && info "  Mode: DRY RUN"
echo ""

# ── Step 1: Namespaces ───────────────────────────────────────
log "Step 1/4: Namespaces"
for f in "${SCRIPT_DIR}"/namespaces/*.yaml; do
  [[ -f "$f" ]] && kube_apply "$f"
done
warn "  No namespace manifests yet — create them when EKS cluster is provisioned"
echo ""

# ── Step 2: RBAC ────────────────────────────────────────────
log "Step 2/4: RBAC"
kube_apply "${SCRIPT_DIR}/rbac/clusterroles.yaml"
kube_apply "${SCRIPT_DIR}/rbac/service-accounts.yaml"
for f in "${SCRIPT_DIR}"/rbac/bindings-*.yaml; do
  [[ -f "$f" ]] && kube_apply "$f"
done
echo ""

# ── Step 3: Networking ──────────────────────────────────────
log "Step 3/4: Networking"
warn "  TODO: Install AWS Load Balancer Controller"
warn "  TODO: Install cert-manager with Let's Encrypt issuer"
echo ""

# ── Step 4: Storage ─────────────────────────────────────────
log "Step 4/4: Storage"
warn "  TODO: Install EBS CSI driver + gp3 StorageClass"
echo ""

if $DRY_RUN; then
  log "Dry run complete."
else
  log "Bootstrap complete (partial — EKS cluster is a placeholder)."
fi
