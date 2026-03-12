#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# teardown.sh — Destroy the entire K3s cluster and OCI infrastructure
#
# This script removes all Kubernetes resources, Helm releases, Terraform-managed
# infrastructure, and local state files. Requires interactive confirmation.
#
# Usage:
#   ./teardown.sh
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORACLE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ---------------------------------------------------------------------------
# Color output helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
die()   { echo -e "${RED}[FATAL]${NC} $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Show what will be destroyed
# ---------------------------------------------------------------------------
echo ""
echo -e "${RED}============================================================${NC}"
echo -e "${RED}  TEARDOWN — This will DESTROY the following:${NC}"
echo -e "${RED}============================================================${NC}"
echo ""
echo "  1. Helm releases: cert-manager, ingress-nginx"
echo "  2. Kubernetes namespaces and all resources within them"
echo "  3. Terraform-managed OCI infrastructure:"

if [[ -d "${ORACLE_DIR}/terraform" ]]; then
    cd "${ORACLE_DIR}/terraform"
    if terraform state list &>/dev/null 2>&1; then
        echo ""
        terraform state list 2>/dev/null | sed 's/^/     /' || echo "     (unable to list state)"
        echo ""
    else
        echo "     (no Terraform state found)"
    fi
    cd "${ORACLE_DIR}"
else
    echo "     (terraform directory not found)"
fi

echo "  4. Local files: kubeconfig, generated inventory, SSH keys"
echo ""
echo -e "${RED}  This action is IRREVERSIBLE.${NC}"
echo ""

# ---------------------------------------------------------------------------
# Require interactive confirmation
# ---------------------------------------------------------------------------
echo -n "Type 'destroy' to confirm: "
read -r confirmation

if [[ "${confirmation}" != "destroy" ]]; then
    info "Teardown cancelled."
    exit 0
fi

echo ""
info "Teardown confirmed. Proceeding..."

# ---------------------------------------------------------------------------
# Step 1: Remove Kubernetes resources (best-effort — cluster may be gone)
# ---------------------------------------------------------------------------
KUBECONFIG_FILE="${ORACLE_DIR}/kubeconfig"
if [[ -f "${KUBECONFIG_FILE}" ]]; then
    export KUBECONFIG="${KUBECONFIG_FILE}"

    info "Removing Helm releases..."

    # Uninstall ingress-nginx
    if helm list -n ingress-nginx 2>/dev/null | grep -q ingress-nginx; then
        helm uninstall ingress-nginx -n ingress-nginx --wait --timeout 3m || \
            warn "Failed to uninstall ingress-nginx (may already be gone)"
    else
        info "ingress-nginx not found — skipping"
    fi

    # Uninstall cert-manager
    if helm list -n cert-manager 2>/dev/null | grep -q cert-manager; then
        helm uninstall cert-manager -n cert-manager --wait --timeout 3m || \
            warn "Failed to uninstall cert-manager (may already be gone)"
    else
        info "cert-manager not found — skipping"
    fi

    info "Deleting namespaces..."
    for ns in ingress-nginx cert-manager monitoring codectl; do
        if kubectl get namespace "${ns}" &>/dev/null 2>&1; then
            kubectl delete namespace "${ns}" --timeout=60s || \
                warn "Failed to delete namespace ${ns}"
        fi
    done

    ok "Kubernetes resources removed"
else
    warn "No kubeconfig found at ${KUBECONFIG_FILE} — skipping K8s cleanup"
fi

# ---------------------------------------------------------------------------
# Step 2: Terraform destroy
# ---------------------------------------------------------------------------
if [[ -d "${ORACLE_DIR}/terraform" ]]; then
    info "Destroying Terraform-managed infrastructure..."
    cd "${ORACLE_DIR}/terraform"

    if [[ -f "terraform.tfstate" ]] || [[ -d ".terraform" ]]; then
        terraform destroy -auto-approve -input=false
        ok "Terraform destroy complete"
    else
        warn "No Terraform state found — skipping destroy"
    fi

    cd "${ORACLE_DIR}"
else
    warn "Terraform directory not found — skipping"
fi

# ---------------------------------------------------------------------------
# Step 3: Clean up local files
# ---------------------------------------------------------------------------
info "Cleaning up local files..."

# Remove kubeconfig
if [[ -f "${ORACLE_DIR}/kubeconfig" ]]; then
    rm -f "${ORACLE_DIR}/kubeconfig"
    ok "Removed kubeconfig"
fi

# Remove generated Ansible inventory (if terraform generates one)
if [[ -f "${ORACLE_DIR}/ansible/inventory/hosts.ini" ]]; then
    rm -f "${ORACLE_DIR}/ansible/inventory/hosts.ini"
    ok "Removed generated Ansible inventory"
fi

# Remove terraform-generated files (but keep .tf files)
for artifact in "${ORACLE_DIR}/terraform/terraform.tfstate" \
                "${ORACLE_DIR}/terraform/terraform.tfstate.backup" \
                "${ORACLE_DIR}/terraform/.terraform.lock.hcl"; do
    if [[ -f "${artifact}" ]]; then
        rm -f "${artifact}"
        ok "Removed $(basename "${artifact}")"
    fi
done

if [[ -d "${ORACLE_DIR}/terraform/.terraform" ]]; then
    rm -rf "${ORACLE_DIR}/terraform/.terraform"
    ok "Removed .terraform directory"
fi

# Remove generated SSH keys (only if they live inside oracle/)
for key_file in "${ORACLE_DIR}"/ssh-key* "${ORACLE_DIR}/terraform"/ssh-key*; do
    if [[ -f "${key_file}" ]]; then
        rm -f "${key_file}"
        ok "Removed $(basename "${key_file}")"
    fi
done

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  Teardown complete.${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
info "All infrastructure has been destroyed."
info "Terraform configuration files (.tf) are preserved for re-provisioning."
echo ""
ok "Done."
