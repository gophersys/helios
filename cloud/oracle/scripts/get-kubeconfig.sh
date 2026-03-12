#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# get-kubeconfig.sh — Fetch kubeconfig from the K3s server node
#
# Retrieves the K3s kubeconfig from server-00, replaces the localhost address
# with the server's Tailscale IP, and writes it to oracle/kubeconfig.
#
# Server discovery order:
#   1. CLI argument: ./get-kubeconfig.sh <server-ip>
#   2. OCI API: discovers *server* instances dynamically
#   3. Terraform output: terraform output -raw server_public_ip
#
# Usage:
#   ./get-kubeconfig.sh                  # auto-detect via OCI API or Terraform
#   ./get-kubeconfig.sh <server-ip>      # specify server IP explicitly
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORACLE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ORACLE_DIR}/.env"

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
# Load env if needed
# ---------------------------------------------------------------------------
if [[ -z "${OCI_COMPARTMENT_OCID:-}" && -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
fi

# ---------------------------------------------------------------------------
# Step 1: Get server IP
# ---------------------------------------------------------------------------
if [[ $# -ge 1 ]]; then
    SERVER_IP="${1}"
    info "Using provided server IP: ${SERVER_IP}"
elif [[ -n "${OCI_COMPARTMENT_OCID:-}" ]]; then
    info "Discovering server-00 via OCI API..."
    INSTANCE_ID=$(oci compute instance list \
        --compartment-id "${OCI_COMPARTMENT_OCID}" \
        --lifecycle-state RUNNING \
        --query 'data[?contains("display-name", `server`)].[id] | [0][0]' \
        --raw-output 2>/dev/null) || die "OCI API query failed"
    [[ -z "${INSTANCE_ID}" || "${INSTANCE_ID}" == "null" ]] && die "No server instance found"

    VNIC_ID=$(oci compute vnic-attachment list \
        --compartment-id "${OCI_COMPARTMENT_OCID}" \
        --instance-id "${INSTANCE_ID}" \
        --query 'data[0]."vnic-id"' \
        --raw-output 2>/dev/null)

    SERVER_IP=$(oci network vnic get \
        --vnic-id "${VNIC_ID}" \
        --query 'data."public-ip"' \
        --raw-output 2>/dev/null)
    [[ -z "${SERVER_IP}" || "${SERVER_IP}" == "null" ]] && die "No public IP for server"
    ok "Found server at ${SERVER_IP}"
else
    info "Getting server IP from Terraform output..."
    cd "${ORACLE_DIR}/terraform"
    SERVER_IP="$(terraform output -raw server_public_ip 2>/dev/null)" \
        || die "No OCI_COMPARTMENT_OCID and no Terraform state. Pass IP as argument."
    cd "${ORACLE_DIR}"
    ok "Server IP: ${SERVER_IP}"
fi

# SSH credentials
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/codectl-bastion}"
SSH_USER="${SSH_USER:-ubuntu}"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10 -i ${SSH_KEY}"

# ---------------------------------------------------------------------------
# Step 2: Fetch kubeconfig from the server
# ---------------------------------------------------------------------------
info "Fetching kubeconfig from ${SERVER_IP}..."

KUBECONFIG_DEST="${ORACLE_DIR}/kubeconfig"
TEMP_KUBECONFIG="$(mktemp)"

# shellcheck disable=SC2086
ssh ${SSH_OPTS} "${SSH_USER}@${SERVER_IP}" \
    "sudo cat /etc/rancher/k3s/k3s.yaml" > "${TEMP_KUBECONFIG}" \
    || die "Failed to fetch kubeconfig from server"

if [[ ! -s "${TEMP_KUBECONFIG}" ]]; then
    rm -f "${TEMP_KUBECONFIG}"
    die "Fetched kubeconfig is empty. Is K3s running on the server?"
fi

ok "Kubeconfig fetched"

# ---------------------------------------------------------------------------
# Step 3: Replace 127.0.0.1 with server's Tailscale IP
# ---------------------------------------------------------------------------
info "Getting server's Tailscale IP..."

# shellcheck disable=SC2086
SERVER_TS_IP="$(ssh ${SSH_OPTS} "${SSH_USER}@${SERVER_IP}" \
    "tailscale ip -4" 2>/dev/null)" \
    || die "Failed to get server's Tailscale IP. Is Tailscale running?"

SERVER_TS_IP=$(echo "${SERVER_TS_IP}" | tr -d '[:space:]')
ok "Server Tailscale IP: ${SERVER_TS_IP}"

info "Updating kubeconfig server address to Tailscale IP..."
sed -i "s|https://127.0.0.1:6443|https://${SERVER_TS_IP}:6443|g" "${TEMP_KUBECONFIG}"
sed -i "s|https://0.0.0.0:6443|https://${SERVER_TS_IP}:6443|g" "${TEMP_KUBECONFIG}"
ok "Server address updated"

# ---------------------------------------------------------------------------
# Step 4: Write to oracle/kubeconfig
# ---------------------------------------------------------------------------
mv "${TEMP_KUBECONFIG}" "${KUBECONFIG_DEST}"
chmod 600 "${KUBECONFIG_DEST}"
ok "Kubeconfig written to ${KUBECONFIG_DEST}"

# ---------------------------------------------------------------------------
# Step 5: Test the connection
# ---------------------------------------------------------------------------
echo ""
info "To use this kubeconfig:"
echo "  export KUBECONFIG=${KUBECONFIG_DEST}"
echo ""

info "Testing cluster connection..."
export KUBECONFIG="${KUBECONFIG_DEST}"

if kubectl get nodes --request-timeout=10s &>/dev/null; then
    ok "Connection successful. Cluster nodes:"
    echo ""
    kubectl get nodes -o wide
    echo ""
else
    warn "Could not reach the cluster. Possible causes:"
    echo "  - Tailscale is not connected on this machine"
    echo "  - The server's K3s API is not yet ready"
    echo "  - Use setup-kubeconfig.sh for SSH tunnel access from containers"
fi

ok "Done."
