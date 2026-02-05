#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LONGHORN_VERSION="1.7.2"
LONGHORN_NAMESPACE="longhorn-system"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

usage() {
  cat <<EOF
Usage: $(basename "$0") <command> [options]

Commands:
  apply [--step N]              Apply all infra steps (or a single step)
  status                        Show current state of all managed resources
  cleanup                       Remove stale resources from the cluster
  generate-kubeconfig           Generate a kubeconfig for a user

Steps:
  0  Node labels & taints
  1  Namespaces
  2  Longhorn (Helm install)
  3  Storage classes
  4  RBAC
  5  Resource quotas
  6  Limit ranges
  7  Network policies

Generate kubeconfig options:
  --role <super-admin|admin|developer|viewer>
  --user <username>
  --namespace <namespace>       (required for viewer role)
  --output <filepath>
EOF
}

# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

step_0() {
  log "Step 0: Node labels & taints"
  bash "${SCRIPT_DIR}/00-labels-taints.sh"
}

step_1() {
  log "Step 1: Namespaces"
  kubectl apply -f "${SCRIPT_DIR}/01-namespaces.yaml"
}

step_2() {
  log "Step 2: Longhorn"

  # Add repo if missing
  if ! helm repo list 2>/dev/null | grep -q "longhorn"; then
    helm repo add longhorn https://charts.longhorn.io
  fi
  helm repo update longhorn

  if helm status longhorn -n "${LONGHORN_NAMESPACE}" &>/dev/null; then
    log "Longhorn already installed, upgrading..."
    helm upgrade longhorn longhorn/longhorn \
      --namespace "${LONGHORN_NAMESPACE}" \
      --version "${LONGHORN_VERSION}" \
      -f "${SCRIPT_DIR}/02-longhorn-values.yaml" \
      --wait
  else
    log "Installing Longhorn..."
    helm install longhorn longhorn/longhorn \
      --namespace "${LONGHORN_NAMESPACE}" \
      --create-namespace \
      --version "${LONGHORN_VERSION}" \
      -f "${SCRIPT_DIR}/02-longhorn-values.yaml" \
      --wait
  fi
}

step_3() {
  log "Step 3: Storage classes"
  kubectl apply -f "${SCRIPT_DIR}/03-storage-classes.yaml"

  # Remove default annotation from local-path if longhorn is now default
  if kubectl get storageclass longhorn &>/dev/null; then
    kubectl patch storageclass local-path \
      -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}' \
      2>/dev/null || true
  fi
}

step_4() {
  log "Step 4: RBAC"
  kubectl apply -f "${SCRIPT_DIR}/04-rbac.yaml"
}

step_5() {
  log "Step 5: Resource quotas"
  kubectl apply -f "${SCRIPT_DIR}/05-resource-quotas.yaml"
}

step_6() {
  log "Step 6: Limit ranges"
  kubectl apply -f "${SCRIPT_DIR}/06-limit-ranges.yaml"
}

step_7() {
  log "Step 7: Network policies"
  kubectl apply -f "${SCRIPT_DIR}/07-network-policies.yaml"
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

cmd_apply() {
  local step=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --step) step="$2"; shift 2 ;;
      *) err "Unknown option: $1"; usage; exit 1 ;;
    esac
  done

  if [[ -n "${step}" ]]; then
    log "Running step ${step} only"
    "step_${step}"
  else
    log "Applying all infrastructure steps"
    echo ""
    for i in 0 1 2 3 4 5 6 7; do
      "step_${i}"
      echo ""
    done
    log "All steps complete."
  fi
}

cmd_status() {
  echo "=== Nodes ==="
  kubectl get nodes -o wide -L corekinect.com/role
  echo ""

  echo "=== Namespaces ==="
  kubectl get namespaces -L corekinect.com/environment
  echo ""

  echo "=== Storage Classes ==="
  kubectl get storageclass
  echo ""

  echo "=== Longhorn ==="
  if kubectl get namespace "${LONGHORN_NAMESPACE}" &>/dev/null; then
    kubectl get pods -n "${LONGHORN_NAMESPACE}" --no-headers 2>/dev/null || echo "  Not installed"
  else
    echo "  Not installed"
  fi
  echo ""

  echo "=== PVCs (all namespaces) ==="
  kubectl get pvc --all-namespaces 2>/dev/null || echo "  None"
  echo ""

  echo "=== Resource Quotas ==="
  for ns in production staging dev; do
    echo "  [${ns}]"
    kubectl get resourcequota -n "${ns}" --no-headers 2>/dev/null || echo "    Not set"
  done
  echo ""

  echo "=== RBAC ==="
  echo "  ClusterRoles:"
  kubectl get clusterroles -l '!kubernetes.io/bootstrapping' --no-headers 2>/dev/null \
    | grep "concord-" || echo "    None"
  echo "  RoleBindings:"
  for ns in production staging dev; do
    echo "    [${ns}]"
    kubectl get rolebindings -n "${ns}" --no-headers 2>/dev/null \
      | grep "concord-" || echo "      None"
  done
}

cmd_cleanup() {
  log "Cleaning up stale cluster resources..."

  # Force-delete stuck Terminating pods
  echo ""
  log "Checking for stuck Terminating pods..."
  TERMINATING=$(kubectl get pods --all-namespaces --field-selector=status.phase=Running \
    -o jsonpath='{range .items[?(@.metadata.deletionTimestamp)]}{.metadata.namespace}/{.metadata.name}{"\n"}{end}' 2>/dev/null || true)

  # Also check directly for Terminating status in output
  TERMINATING_PODS=$(kubectl get pods --all-namespaces 2>/dev/null | grep Terminating | awk '{print $1"/"$2}' || true)

  if [[ -n "${TERMINATING_PODS}" ]]; then
    for pod in ${TERMINATING_PODS}; do
      ns="${pod%%/*}"
      name="${pod##*/}"
      warn "Force-deleting stuck pod: ${ns}/${name}"
      kubectl delete pod "${name}" -n "${ns}" --force --grace-period=0
    done
  else
    log "No stuck pods found"
  fi

  # Clean up completed/failed jobs older than 7 days
  echo ""
  log "Cleaning up old Jobs..."
  OLD_JOBS=$(kubectl get jobs --all-namespaces -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name} {.status.completionTime}{"\n"}{end}' 2>/dev/null || true)
  if [[ -n "${OLD_JOBS}" ]]; then
    while IFS= read -r line; do
      job_ref="${line%% *}"
      if [[ -z "${job_ref}" || "${job_ref}" == "/" ]]; then continue; fi
      ns="${job_ref%%/*}"
      name="${job_ref##*/}"
      # Skip kube-system jobs
      if [[ "${ns}" == "kube-system" ]]; then continue; fi
      status=$(kubectl get job "${name}" -n "${ns}" -o jsonpath='{.status.conditions[0].type}' 2>/dev/null || echo "")
      if [[ "${status}" == "Complete" || "${status}" == "Failed" ]]; then
        warn "Deleting old job: ${ns}/${name} (${status})"
        kubectl delete job "${name}" -n "${ns}"
      fi
    done <<< "${OLD_JOBS}"
  else
    log "No old jobs found"
  fi

  # Clean up orphaned ReplicaSets (0 desired, 0 ready)
  echo ""
  log "Cleaning up orphaned ReplicaSets (0/0/0)..."
  kubectl get replicasets --all-namespaces --no-headers 2>/dev/null \
    | awk '$3==0 && $4==0 && $5==0 {print $1, $2}' \
    | while read -r ns name; do
        if [[ "${ns}" == "kube-system" ]]; then continue; fi
        warn "Deleting orphaned ReplicaSet: ${ns}/${name}"
        kubectl delete replicaset "${name}" -n "${ns}"
      done

  echo ""
  log "Cleanup complete."
}

cmd_generate_kubeconfig() {
  local role="" user="" namespace="" output=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --role)      role="$2"; shift 2 ;;
      --user)      user="$2"; shift 2 ;;
      --namespace) namespace="$2"; shift 2 ;;
      --output)    output="$2"; shift 2 ;;
      *) err "Unknown option: $1"; usage; exit 1 ;;
    esac
  done

  if [[ -z "${role}" || -z "${user}" ]]; then
    err "--role and --user are required"
    exit 1
  fi

  if [[ -z "${output}" ]]; then
    output="${user}.kubeconfig"
  fi

  # Determine the group based on role
  local group=""
  case "${role}" in
    super-admin) group="concord-super-admins" ;;
    admin)       group="concord-admins" ;;
    developer)   group="concord-developers" ;;
    viewer)      group="concord-viewers" ;;
    *) err "Invalid role: ${role}. Must be: super-admin, admin, developer, viewer"; exit 1 ;;
  esac

  # Use the first available namespace for the SA, or default
  local sa_namespace="${namespace:-default}"
  local sa_name="concord-${user}"

  # Create service account
  log "Creating ServiceAccount ${sa_name} in namespace ${sa_namespace}"
  kubectl create serviceaccount "${sa_name}" -n "${sa_namespace}" --dry-run=client -o yaml \
    | kubectl apply -f -

  # Create a long-lived token secret
  cat <<EOSECRET | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: ${sa_name}-token
  namespace: ${sa_namespace}
  annotations:
    kubernetes.io/service-account.name: ${sa_name}
type: kubernetes.io/service-account-token
EOSECRET

  # Wait for token to be populated
  sleep 2

  local token
  token=$(kubectl get secret "${sa_name}-token" -n "${sa_namespace}" -o jsonpath='{.data.token}' | base64 -d)
  local server
  server=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')
  local ca
  ca=$(kubectl config view --minify --flatten -o jsonpath='{.clusters[0].cluster.certificate-authority-data}')

  # Generate kubeconfig
  cat > "${output}" <<EOKC
apiVersion: v1
kind: Config
clusters:
  - name: concord
    cluster:
      server: ${server}
      certificate-authority-data: ${ca}
contexts:
  - name: concord-${role}
    context:
      cluster: concord
      user: ${user}
      namespace: ${sa_namespace}
current-context: concord-${role}
users:
  - name: ${user}
    user:
      token: ${token}
EOKC

  log "Kubeconfig written to ${output}"
  log "Role: ${role} (group: ${group})"
  warn "Remember: the ServiceAccount must be bound to the '${group}' group via RBAC."
  warn "For SA-based auth, you may also need a direct RoleBinding to the SA."
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

COMMAND="$1"
shift

case "${COMMAND}" in
  apply)               cmd_apply "$@" ;;
  status)              cmd_status ;;
  cleanup)             cmd_cleanup ;;
  generate-kubeconfig) cmd_generate_kubeconfig "$@" ;;
  help|-h|--help)      usage ;;
  *) err "Unknown command: ${COMMAND}"; usage; exit 1 ;;
esac
