#!/usr/bin/env bash
# bootstrap.sh — EKS cluster setup (placeholder).
# Same lifecycle as office/bootstrap.sh — reads dependencies from cluster.yaml.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CLUSTER_YAML="${SCRIPT_DIR}/cluster.yaml"

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[bootstrap]${NC} $*"; }
info() { echo -e "${CYAN}[bootstrap]${NC} $*"; }
warn() { echo -e "${YELLOW}[bootstrap]${NC} $*"; }

command -v kubectl >/dev/null 2>&1 || { echo "kubectl not found"; exit 1; }
command -v helm >/dev/null 2>&1 || { echo "helm not found"; exit 1; }
command -v yq >/dev/null 2>&1 || { echo "yq not found"; exit 1; }

cluster_name=$(yq -r '.name' "${CLUSTER_YAML}")
log "${BOLD}Bootstrapping cluster: ${cluster_name}${NC}"
$DRY_RUN && info "  Mode: DRY RUN"
echo ""

# ── Namespaces ───────────────────────────────────────────────
log "Step 1/4: Namespaces"
for f in "${SCRIPT_DIR}"/namespaces/*.yaml; do
  if [[ -f "$f" ]]; then
    if $DRY_RUN; then
      echo "  [dry-run] kubectl apply -f ${f}"
    else
      kubectl apply -f "$f" 2>&1 | sed 's/^/  /'
    fi
  fi
done
warn "  No namespace manifests yet — create when EKS cluster is provisioned"
echo ""

# ── Dependencies ─────────────────────────────────────────────
log "Step 2/4: Cluster dependencies"
dep_count=$(yq -r '.dependencies | length' "${CLUSTER_YAML}" 2>/dev/null || echo 0)
for ((i=0; i<dep_count; i++)); do
  dep_name=$(yq -r ".dependencies[${i}].name" "${CLUSTER_YAML}")
  dep_chart=$(yq -r ".dependencies[${i}].chart" "${CLUSTER_YAML}")
  dep_ns=$(yq -r ".dependencies[${i}].namespace" "${CLUSTER_YAML}")
  dep_ver=$(yq -r ".dependencies[${i}].version" "${CLUSTER_YAML}")
  dep_repo=$(yq -r ".dependencies[${i}].repo" "${CLUSTER_YAML}" 2>/dev/null | grep -v '^null$' || true)

  values_file="${INFRA_ROOT}/dependencies/${dep_name}/values.yaml"

  if $DRY_RUN; then
    echo "  [dry-run] helm upgrade --install ${dep_name} ${dep_chart} -n ${dep_ns} --version ${dep_ver}"
    [[ -f "${values_file}" ]] && echo "            -f ${values_file}"
  else
    [[ -n "${dep_repo}" ]] && {
      repo_name=$(echo "${dep_chart}" | cut -d'/' -f1)
      helm repo add "${repo_name}" "${dep_repo}" --force-update 2>/dev/null || true
    }
    local_args=(upgrade --install "${dep_name}" "${dep_chart}" -n "${dep_ns}" --create-namespace --version "${dep_ver}" --wait)
    [[ -f "${values_file}" ]] && local_args+=(-f "${values_file}")
    helm "${local_args[@]}" 2>&1 | sed 's/^/  /'
  fi
done
echo ""

# ── RBAC ─────────────────────────────────────────────────────
log "Step 3/4: RBAC"
for f in "${SCRIPT_DIR}"/rbac/*.yaml; do
  if [[ -f "$f" ]]; then
    if $DRY_RUN; then
      echo "  [dry-run] kubectl apply -f ${f}"
    else
      kubectl apply -f "$f" 2>&1 | sed 's/^/  /'
    fi
  fi
done
echo ""

# ── Storage ──────────────────────────────────────────────────
log "Step 4/4: Storage"
warn "  TODO: Verify EBS CSI driver + gp3 StorageClass"
echo ""

if $DRY_RUN; then
  log "${BOLD}Dry run complete.${NC}"
else
  log "${BOLD}Bootstrap complete: ${cluster_name}${NC}"
fi
