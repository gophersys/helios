#!/usr/bin/env bash
# teardown.sh — Reverse of bootstrap.sh. Removes everything Concord installed.
# Leaves K3s itself intact but removes all Concord namespaces, RBAC, deps, labels.
#
# Usage:
#   bash infrastructure/clusters/office/teardown.sh              # Interactive confirm
#   bash infrastructure/clusters/office/teardown.sh --confirm    # Skip confirmation
#   bash infrastructure/clusters/office/teardown.sh --dry-run    # Preview only
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CLUSTER_YAML="${SCRIPT_DIR}/cluster.yaml"

DRY_RUN=false
CONFIRMED=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true
[[ "${1:-}" == "--confirm" ]] && CONFIRMED=true

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[teardown]${NC} $*"; }
info() { echo -e "${CYAN}[teardown]${NC} $*"; }
warn() { echo -e "${YELLOW}[teardown]${NC} $*"; }
err()  { echo -e "${RED}[teardown]${NC} $*" >&2; }

command -v kubectl >/dev/null 2>&1 || { err "kubectl not found"; exit 1; }
command -v helm >/dev/null 2>&1 || { err "helm not found"; exit 1; }
command -v yq >/dev/null 2>&1 || { err "yq not found"; exit 1; }

cluster_name=$(yq -r '.name' "${CLUSTER_YAML}")

# ── Confirmation ──────────────────────────────────────────────
if ! $DRY_RUN && ! $CONFIRMED; then
  echo ""
  err "${BOLD}WARNING: This will destroy ALL Concord resources on cluster '${cluster_name}'${NC}"
  err "  - Uninstall all Helm releases (concord in staging + production)"
  err "  - Delete all PVCs (postgres, minio, pypi DATA WILL BE LOST)"
  err "  - Uninstall cluster dependencies (cert-manager)"
  err "  - Remove RBAC, namespaces, and node labels"
  echo ""
  read -rp "Type '${cluster_name}' to confirm: " answer
  if [[ "${answer}" != "${cluster_name}" ]]; then
    err "Aborted."
    exit 1
  fi
fi

log "${BOLD}Tearing down cluster: ${cluster_name}${NC}"
$DRY_RUN && info "  Mode: DRY RUN"
echo ""

# ── Step 1: Uninstall application Helm releases ─────────────
log "Step 1/6: Uninstall application Helm releases"
while IFS= read -r ns; do
  if $DRY_RUN; then
    echo "  [dry-run] helm uninstall concord -n ${ns}"
  else
    if helm status concord -n "${ns}" >/dev/null 2>&1; then
      info "  Uninstalling concord from ${ns}..."
      helm uninstall concord -n "${ns}" --wait 2>&1 | sed 's/^/  /' || true
    else
      info "  No concord release in ${ns}"
    fi
  fi
done < <(yq -r '.namespaces[]' "${CLUSTER_YAML}" 2>/dev/null)
echo ""

# ── Step 2: Delete PVCs ─────────────────────────────────────
log "Step 2/6: Delete PVCs"
while IFS= read -r ns; do
  if $DRY_RUN; then
    echo "  [dry-run] kubectl delete pvc --all -n ${ns}"
  else
    pvcs=$(kubectl get pvc -n "${ns}" --no-headers 2>/dev/null | awk '{print $1}' || true)
    if [[ -n "${pvcs}" ]]; then
      for pvc in ${pvcs}; do
        info "  Deleting PVC ${pvc} in ${ns}..."
        kubectl delete pvc "${pvc}" -n "${ns}" --wait=false 2>/dev/null || true
      done
    else
      info "  No PVCs in ${ns}"
    fi
  fi
done < <(yq -r '.namespaces[]' "${CLUSTER_YAML}" 2>/dev/null)
echo ""

# ── Step 3: Uninstall cluster dependencies (reverse order) ──
log "Step 3/6: Uninstall cluster dependencies"
dep_count=$(yq -r '.dependencies | length' "${CLUSTER_YAML}" 2>/dev/null || echo 0)
# Reverse order — last installed, first removed
for ((i=dep_count-1; i>=0; i--)); do
  dep_name=$(yq -r ".dependencies[${i}].name" "${CLUSTER_YAML}")
  dep_ns=$(yq -r ".dependencies[${i}].namespace" "${CLUSTER_YAML}")

  # Remove post-install manifests first
  post_count=$(yq -r ".dependencies[${i}].postInstall // [] | length" "${CLUSTER_YAML}" 2>/dev/null || echo 0)
  for ((j=post_count-1; j>=0; j--)); do
    manifest=$(yq -r ".dependencies[${i}].postInstall[${j}]" "${CLUSTER_YAML}")
    manifest_path="${SCRIPT_DIR}/${manifest}"
    if [[ -f "${manifest_path}" ]]; then
      if $DRY_RUN; then
        echo "  [dry-run] kubectl delete -f ${manifest_path}"
      else
        kubectl delete -f "${manifest_path}" --ignore-not-found 2>&1 | sed 's/^/  /' || true
      fi
    fi
  done

  # Uninstall the Helm chart
  if $DRY_RUN; then
    echo "  [dry-run] helm uninstall ${dep_name} -n ${dep_ns}"
  else
    if helm status "${dep_name}" -n "${dep_ns}" >/dev/null 2>&1; then
      info "  Uninstalling ${dep_name} from ${dep_ns}..."
      helm uninstall "${dep_name}" -n "${dep_ns}" --wait 2>&1 | sed 's/^/  /' || true
    else
      info "  ${dep_name} not installed in ${dep_ns}"
    fi
  fi
done
echo ""

# ── Step 4: Remove RBAC ─────────────────────────────────────
log "Step 4/6: Remove RBAC"
for f in "${SCRIPT_DIR}"/rbac/bindings-*.yaml; do
  [[ -f "$f" ]] || continue
  if $DRY_RUN; then
    echo "  [dry-run] kubectl delete -f ${f}"
  else
    kubectl delete -f "$f" --ignore-not-found 2>&1 | sed 's/^/  /' || true
  fi
done
if $DRY_RUN; then
  echo "  [dry-run] kubectl delete -f ${SCRIPT_DIR}/rbac/service-accounts.yaml"
  echo "  [dry-run] kubectl delete -f ${SCRIPT_DIR}/rbac/clusterroles.yaml"
else
  kubectl delete -f "${SCRIPT_DIR}/rbac/service-accounts.yaml" --ignore-not-found 2>&1 | sed 's/^/  /' || true
  kubectl delete -f "${SCRIPT_DIR}/rbac/clusterroles.yaml" --ignore-not-found 2>&1 | sed 's/^/  /' || true
fi
echo ""

# ── Step 5: Remove node labels ──────────────────────────────
log "Step 5/6: Remove node labels"
node_count=$(yq -r '.nodes | length' "${SCRIPT_DIR}/nodes/labels.yaml" 2>/dev/null || echo 0)
for ((i=0; i<node_count; i++)); do
  node_name=$(yq -r ".nodes[${i}].name" "${SCRIPT_DIR}/nodes/labels.yaml")
  if $DRY_RUN; then
    echo "  [dry-run] kubectl label node ${node_name} concord.corekinect.com/workload- concord.corekinect.com/workload-{platform,data,build,worker,edge}-"
  else
    kubectl label node "${node_name}" \
      concord.corekinect.com/workload- \
      concord.corekinect.com/workload-platform- \
      concord.corekinect.com/workload-data- \
      concord.corekinect.com/workload-build- \
      concord.corekinect.com/workload-worker- \
      concord.corekinect.com/workload-edge- \
      2>/dev/null || true
  fi
done
echo ""

# ── Step 6: Delete namespaces ───────────────────────────────
log "Step 6/6: Delete namespaces"
while IFS= read -r ns; do
  if $DRY_RUN; then
    echo "  [dry-run] kubectl delete namespace ${ns}"
  else
    if kubectl get ns "${ns}" >/dev/null 2>&1; then
      info "  Deleting namespace ${ns}..."
      kubectl delete namespace "${ns}" --wait=false 2>/dev/null || true
    else
      info "  Namespace ${ns} does not exist"
    fi
  fi
done < <(yq -r '.namespaces[]' "${CLUSTER_YAML}" 2>/dev/null)

# Also delete dependency namespaces
for ((i=0; i<dep_count; i++)); do
  dep_ns=$(yq -r ".dependencies[${i}].namespace" "${CLUSTER_YAML}")
  if $DRY_RUN; then
    echo "  [dry-run] kubectl delete namespace ${dep_ns}"
  else
    if kubectl get ns "${dep_ns}" >/dev/null 2>&1; then
      info "  Deleting namespace ${dep_ns}..."
      kubectl delete namespace "${dep_ns}" --wait=false 2>/dev/null || true
    else
      info "  Namespace ${dep_ns} does not exist"
    fi
  fi
done
echo ""

if $DRY_RUN; then
  log "${BOLD}Dry run complete.${NC}"
else
  log "${BOLD}Teardown complete: ${cluster_name}${NC}"
  info "  Cluster is back to bare K3s. Run bootstrap.sh to set up again."
fi
