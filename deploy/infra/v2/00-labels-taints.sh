#!/usr/bin/env bash
set -euo pipefail

# 00-labels-taints.sh
# Applies standardized labels and taints to all Concord cluster nodes.
# Idempotent - safe to re-run.
#
# Labels applied:
#   corekinect.com/role    = server | agent | edge
#   corekinect.com/purpose = platform | manufacturing | validation  (per-node)
#
# Taints applied (Phase C — only when --with-taints is passed):
#   server/agent: corekinect.com/role=<role>:PreferNoSchedule
#   edge:         corekinect.com/role=edge:NoSchedule

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

APPLY_TAINTS=false
if [[ "${1:-}" == "--with-taints" ]]; then
  APPLY_TAINTS=true
fi

SERVER_NODES=("concordserver01" "concordserver02" "concordserver03")
AGENT_NODES=("concordagent01" "concordagent02" "concordagent03")

# Purpose mapping — edit these arrays when nodes change function.
# Nodes not listed here get role label only (no purpose).
declare -A NODE_PURPOSE=(
  # Servers
  ["concordserver01"]="platform"
  ["concordserver02"]="platform"
  ["concordserver03"]="platform"
  # Agents
  ["concordagent01"]="manufacturing"   # theta fixture
  ["concordagent02"]="manufacturing"   # sigma5
  # concordagent03 intentionally omitted — idle
  # Edge — set dynamically below per manufacturing/validation lists
)

# Edge nodes by purpose (hostnames from deployment manifests)
EDGE_MANUFACTURING=(
  "verdin-imx8mm-15005658"
  "verdin-imx8mm-15005679"
  "verdin-imx8mm-15005689"
  "verdin-imx8mm-15005816"
  "verdin-imx8mm-15005817"
)
EDGE_VALIDATION=(
  "verdin-imx8mm-15702161"
)

# Pre-populate edge purpose map
for node in "${EDGE_MANUFACTURING[@]}"; do
  NODE_PURPOSE["${node}"]="manufacturing"
done
for node in "${EDGE_VALIDATION[@]}"; do
  NODE_PURPOSE["${node}"]="validation"
done

label_node() {
  local node="$1"
  local role="$2"

  echo "  Labeling ${node} -> corekinect.com/role=${role}"
  kubectl label node "${node}" "corekinect.com/role=${role}" --overwrite

  local purpose="${NODE_PURPOSE[${node}]:-}"
  if [ -n "${purpose}" ]; then
    echo "  Labeling ${node} -> corekinect.com/purpose=${purpose}"
    kubectl label node "${node}" "corekinect.com/purpose=${purpose}" --overwrite
  fi
}

taint_node() {
  local node="$1"
  local role="$2"
  local effect="$3"

  if [ "${APPLY_TAINTS}" != "true" ]; then
    return
  fi

  echo "  Tainting ${node} -> corekinect.com/role=${role}:${effect}"
  kubectl taint node "${node}" "corekinect.com/role=${role}:${effect}-" 2>/dev/null || true
  kubectl taint node "${node}" "corekinect.com/role=${role}:${effect}"
}

echo "=== Concord Node Labels${APPLY_TAINTS:+ & Taints} ==="
echo ""

# --- Server Nodes ---
echo "[server nodes] core services (http-api, db, ui)"
for node in "${SERVER_NODES[@]}"; do
  label_node "${node}" "server"
  taint_node "${node}" "server" "PreferNoSchedule"
done
echo ""

# --- Agent Nodes ---
echo "[agent nodes] ephemeral compute, storage (Longhorn)"
for node in "${AGENT_NODES[@]}"; do
  label_node "${node}" "agent"
  taint_node "${node}" "agent" "PreferNoSchedule"
done
echo ""

# --- Edge Nodes ---
# Discover edge nodes dynamically by arch label (arm64 = Verdin iMX8MM boards)
echo "[edge nodes] MTIB custom hardware"
EDGE_NODES=$(kubectl get nodes -l "kubernetes.io/arch=arm64" -o jsonpath='{.items[*].metadata.name}')
if [ -z "${EDGE_NODES}" ]; then
  echo "  No edge nodes found (no arm64 nodes in cluster)"
else
  for node in ${EDGE_NODES}; do
    label_node "${node}" "edge"
    taint_node "${node}" "edge" "NoSchedule"
  done
fi
echo ""

echo "Done. Current node labels:"
kubectl get nodes -L corekinect.com/role,corekinect.com/purpose
