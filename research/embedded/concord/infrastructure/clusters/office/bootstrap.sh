#!/usr/bin/env bash
# bootstrap.sh — Idempotent setup for the office K3s cluster.
# Takes the cluster from raw K3s install → ready for application Helm deploys.
#
# Lifecycle:
#   bootstrap.sh              Apply everything (idempotent)
#   bootstrap.sh --dry-run    Preview what would be applied
#   teardown.sh               Reverse everything (destructive)
#
# Order:
#   1. Namespaces
#   2. Node labels (workload types)
#   3. Cluster dependencies (cert-manager, future: otel, vault, etc.)
#   4. Post-install manifests (CA issuer, TLS certs)
#   5. RBAC (ClusterRoles + bindings)
#   6. Storage verification
#   7. Secrets (from .env file — bitbucket-ssh-key, build-service, etc.)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CLUSTER_YAML="${SCRIPT_DIR}/cluster.yaml"

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[bootstrap]${NC} $*"; }
info() { echo -e "${CYAN}[bootstrap]${NC} $*"; }
warn() { echo -e "${YELLOW}[bootstrap]${NC} $*"; }
err()  { echo -e "${RED}[bootstrap]${NC} $*" >&2; }

kube_apply() {
  local file="$1"
  if $DRY_RUN; then
    echo "  [dry-run] kubectl apply -f ${file}"
  else
    kubectl apply --server-side --force-conflicts -f "${file}" 2>&1 | sed 's/^/  /'
  fi
}

kube_label_node() {
  local node="$1"
  shift
  if $DRY_RUN; then
    echo "  [dry-run] kubectl label node ${node} $* --overwrite"
  else
    kubectl label node "${node}" "$@" --overwrite 2>/dev/null || true
  fi
}

helm_install() {
  local name="$1" chart="$2" namespace="$3" version="$4" repo="$5"
  local values_file="${INFRA_ROOT}/dependencies/${name}/values.yaml"
  local cluster_values="${SCRIPT_DIR}/dependencies/${name}.yaml"

  if $DRY_RUN; then
    echo "  [dry-run] helm upgrade --install ${name} ${chart} -n ${namespace} --create-namespace --version ${version}"
    [[ -f "${values_file}" ]] && echo "            -f ${values_file}"
    [[ -f "${cluster_values}" ]] && echo "            -f ${cluster_values}"
    return 0
  fi

  # Add repo if specified
  if [[ -n "${repo}" ]]; then
    local repo_name
    repo_name=$(echo "${chart}" | cut -d'/' -f1)
    helm repo add "${repo_name}" "${repo}" --force-update 2>/dev/null || true
    helm repo update "${repo_name}" 2>/dev/null || true
  fi

  # Clean up stale release secrets to prevent "release not found" errors on upgrade.
  # Keeps only the latest 5 revisions.
  local stale
  stale=$(kubectl get secrets -n "${namespace}" -l "name=${name},owner=helm" \
    --sort-by=.metadata.creationTimestamp -o name 2>/dev/null | head -n -5)
  if [[ -n "${stale}" ]]; then
    echo "${stale}" | xargs kubectl delete -n "${namespace}" 2>/dev/null || true
  fi

  local helm_args=(
    upgrade --install "${name}" "${chart}"
    -n "${namespace}" --create-namespace
    --version "${version}"
    --wait --timeout 120s
    --history-max 5
  )

  # Shared values
  [[ -f "${values_file}" ]] && helm_args+=(-f "${values_file}")

  # Cluster-specific overrides
  [[ -f "${cluster_values}" ]] && helm_args+=(-f "${cluster_values}")

  info "  Installing ${name} (${chart} ${version}) → namespace/${namespace}"
  helm "${helm_args[@]}" 2>&1 | sed 's/^/  /'
}

wait_for_ready() {
  local namespace="$1" label="$2" timeout="${3:-60}"
  if $DRY_RUN; then
    echo "  [dry-run] wait for ${label} in ${namespace} (${timeout}s)"
    return 0
  fi
  info "  Waiting for ${label} in ${namespace}..."
  kubectl wait --for=condition=Available deployment -l "${label}" \
    -n "${namespace}" --timeout="${timeout}s" 2>/dev/null || {
    warn "  Timed out waiting for ${label} — continuing anyway"
  }
}

# ── Require tools ─────────────────────────────────────────────
command -v kubectl >/dev/null 2>&1 || { err "kubectl not found"; exit 1; }
command -v helm >/dev/null 2>&1 || { err "helm not found"; exit 1; }
command -v yq >/dev/null 2>&1 || { err "yq not found"; exit 1; }

# ── Header ────────────────────────────────────────────────────
cluster_name=$(yq -r '.name' "${CLUSTER_YAML}")
log "${BOLD}Bootstrapping cluster: ${cluster_name}${NC}"
$DRY_RUN && info "  Mode: DRY RUN (no changes will be made)"
echo ""

# ── Step 1: Namespaces ───────────────────────────────────────
log "Step 1/7: Namespaces"
for f in "${SCRIPT_DIR}"/namespaces/*.yaml; do
  [[ -f "$f" ]] && kube_apply "$f"
done
echo ""

# ── Step 2: Node labels (workload types) ────────────────────
log "Step 2/7: Node labels"
node_count=$(yq -r '.nodes | length' "${SCRIPT_DIR}/nodes/labels.yaml" 2>/dev/null || echo 0)
for ((i=0; i<node_count; i++)); do
  node_name=$(yq -r ".nodes[${i}].name" "${SCRIPT_DIR}/nodes/labels.yaml")
  labels=()

  # Primary workload label
  primary=$(yq -r ".nodes[${i}].workloads[0]" "${SCRIPT_DIR}/nodes/labels.yaml" 2>/dev/null | grep -v '^null$' || true)
  [[ -n "${primary}" ]] && labels+=("concord.corekinect.com/workload=${primary}")

  # Per-type labels
  wl_count=$(yq -r ".nodes[${i}].workloads | length" "${SCRIPT_DIR}/nodes/labels.yaml" 2>/dev/null || echo 0)
  for ((j=0; j<wl_count; j++)); do
    wl=$(yq -r ".nodes[${i}].workloads[${j}]" "${SCRIPT_DIR}/nodes/labels.yaml" 2>/dev/null)
    labels+=("concord.corekinect.com/workload-${wl}=true")
  done

  # Extra labels
  while IFS= read -r key; do
    [[ -z "${key}" ]] && continue
    val=$(yq -r ".nodes[${i}].labels.\"${key}\"" "${SCRIPT_DIR}/nodes/labels.yaml")
    labels+=("${key}=${val}")
  done < <(yq -r ".nodes[${i}].labels // {} | keys | .[]" "${SCRIPT_DIR}/nodes/labels.yaml" 2>/dev/null || true)

  if [[ ${#labels[@]} -gt 0 ]]; then
    kube_label_node "${node_name}" "${labels[@]}"
  fi
done
echo ""

# ── Step 3: Cluster dependencies (Helm charts) ──────────────
log "Step 3/7: Cluster dependencies"
dep_count=$(yq -r '.dependencies | length' "${CLUSTER_YAML}" 2>/dev/null || echo 0)
if [[ "${dep_count}" -eq 0 ]]; then
  info "  No dependencies defined"
else
  for ((i=0; i<dep_count; i++)); do
    dep_name=$(yq -r ".dependencies[${i}].name" "${CLUSTER_YAML}")
    dep_chart=$(yq -r ".dependencies[${i}].chart" "${CLUSTER_YAML}")
    dep_ns=$(yq -r ".dependencies[${i}].namespace" "${CLUSTER_YAML}")
    dep_ver=$(yq -r ".dependencies[${i}].version" "${CLUSTER_YAML}")
    dep_repo=$(yq -r ".dependencies[${i}].repo" "${CLUSTER_YAML}" 2>/dev/null | grep -v '^null$' || true)

    helm_install "${dep_name}" "${dep_chart}" "${dep_ns}" "${dep_ver}" "${dep_repo}"
  done
fi
echo ""

# ── Step 4: Post-install manifests ──────────────────────────
log "Step 4/7: Post-install manifests"
for ((i=0; i<dep_count; i++)); do
  dep_name=$(yq -r ".dependencies[${i}].name" "${CLUSTER_YAML}")
  post_count=$(yq -r ".dependencies[${i}].postInstall // [] | length" "${CLUSTER_YAML}" 2>/dev/null || echo 0)
  if [[ "${post_count}" -gt 0 ]]; then
    # Wait for the dependency to be ready before applying post-install
    dep_ns=$(yq -r ".dependencies[${i}].namespace" "${CLUSTER_YAML}")
    wait_for_ready "${dep_ns}" "app.kubernetes.io/instance=${dep_name}" 90

    for ((j=0; j<post_count; j++)); do
      manifest=$(yq -r ".dependencies[${i}].postInstall[${j}]" "${CLUSTER_YAML}")
      manifest_path="${SCRIPT_DIR}/${manifest}"
      if [[ -f "${manifest_path}" ]]; then
        kube_apply "${manifest_path}"
      else
        warn "  Post-install manifest not found: ${manifest}"
      fi
    done
  fi
done
echo ""

# ── Step 5: RBAC ────────────────────────────────────────────
log "Step 5/7: RBAC"
kube_apply "${SCRIPT_DIR}/rbac/clusterroles.yaml"
kube_apply "${SCRIPT_DIR}/rbac/service-accounts.yaml"
for f in "${SCRIPT_DIR}"/rbac/bindings-*.yaml; do
  [[ -f "$f" ]] && kube_apply "$f"
done
echo ""

# ── Step 6: Storage ─────────────────────────────────────────
log "Step 6/7: Storage"
expected_sc=$(yq -r '.storage.defaultClass' "${CLUSTER_YAML}")
if $DRY_RUN; then
  echo "  [dry-run] verify StorageClass '${expected_sc}' exists"
else
  if kubectl get sc "${expected_sc}" >/dev/null 2>&1; then
    info "  ✓ StorageClass '${expected_sc}' exists"
  else
    warn "  ✗ StorageClass '${expected_sc}' not found"
    if [[ -f "${SCRIPT_DIR}/storage/storage-classes.yaml" ]]; then
      info "  Applying storage-classes.yaml..."
      kube_apply "${SCRIPT_DIR}/storage/storage-classes.yaml"
    fi
  fi
fi
echo ""

# ── Step 7: Secrets ─────────────────────────────────────────
log "Step 7/7: Secrets"
secrets_script="${SCRIPT_DIR}/secrets/create-all.sh"
if [[ -f "${secrets_script}" ]]; then
  shared_env="${SCRIPT_DIR}/secrets/shared.env"
  if [[ -f "${shared_env}" ]]; then
    if $DRY_RUN; then
      bash "${secrets_script}" --dry-run
    else
      bash "${secrets_script}"
    fi
  else
    warn "  No secrets/shared.env found — skipping secret creation"
    warn "  Copy secrets/.env.example and create shared.env + {namespace}.env files"
  fi
else
  info "  No secrets/create-all.sh found — skipping"
fi
echo ""

# ── Summary ─────────────────────────────────────────────────
if $DRY_RUN; then
  log "${BOLD}Dry run complete.${NC} No changes were made."
else
  log "${BOLD}Bootstrap complete: ${cluster_name}${NC}"
  info "  Namespaces, labels, dependencies, RBAC, certificates, storage, secrets — all configured."
  info "  The cluster is ready for: ./deploy/ctl.sh <env> start"
fi
