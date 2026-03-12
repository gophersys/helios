#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# add-node.sh — Add an external node to the K3s cluster via Tailscale
#
# Connects a node from any cloud provider to the existing K3s cluster using
# Tailscale as the mesh network. The node joins as a K3s agent (worker).
#
# Usage:
#   ./add-node.sh <node-ip> <ssh-user> [ssh-key]
#
# Arguments:
#   node-ip   Public IP address of the node to add
#   ssh-user  SSH username on the target node
#   ssh-key   (Optional) Path to SSH private key. Defaults to ~/.ssh/id_rsa
#
# Prerequisites:
#   - The K3s server (server-00) must already be running with Tailscale
#   - The target node must be SSH-accessible from this machine
#   - A valid kubeconfig must exist at oracle/kubeconfig
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
# Step 1: Parse arguments
# ---------------------------------------------------------------------------
if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <node-ip> <ssh-user> [ssh-key]"
    echo ""
    echo "Arguments:"
    echo "  node-ip   Public IP of the node to add"
    echo "  ssh-user  SSH username on the target node"
    echo "  ssh-key   Path to SSH private key (default: ~/.ssh/id_rsa)"
    exit 1
fi

NODE_IP="${1}"
SSH_USER="${2}"
SSH_KEY="${3:-${HOME}/.ssh/id_rsa}"

if [[ ! -f "${SSH_KEY}" ]]; then
    die "SSH key not found at ${SSH_KEY}"
fi

KUBECONFIG_FILE="${ORACLE_DIR}/kubeconfig"
if [[ ! -f "${KUBECONFIG_FILE}" ]]; then
    die "Kubeconfig not found at ${KUBECONFIG_FILE}. Run bootstrap.sh first."
fi
export KUBECONFIG="${KUBECONFIG_FILE}"

info "Adding node ${NODE_IP} (user: ${SSH_USER}) to K3s cluster..."

# SSH options used throughout the script
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10 -i ${SSH_KEY}"

# ---------------------------------------------------------------------------
# Step 2: Verify SSH connectivity to the new node
# ---------------------------------------------------------------------------
info "Verifying SSH connectivity to ${NODE_IP}..."
# shellcheck disable=SC2086
if ! ssh ${SSH_OPTS} "${SSH_USER}@${NODE_IP}" "echo ok" &>/dev/null; then
    die "Cannot SSH to ${SSH_USER}@${NODE_IP}. Check IP, user, and key."
fi
ok "SSH to ${NODE_IP} is reachable"

# ---------------------------------------------------------------------------
# Step 3: Install Tailscale on the new node
# ---------------------------------------------------------------------------
info "Installing Tailscale on ${NODE_IP}..."

# shellcheck disable=SC2086
ssh ${SSH_OPTS} "${SSH_USER}@${NODE_IP}" bash <<'REMOTE_TAILSCALE'
set -euo pipefail

# Skip if Tailscale is already installed
if command -v tailscale &>/dev/null; then
    echo "Tailscale already installed, skipping installation"
else
    curl -fsSL https://tailscale.com/install.sh | sh
fi

# Ensure tailscaled is running
if ! systemctl is-active --quiet tailscaled 2>/dev/null; then
    sudo systemctl enable --now tailscaled
fi

echo "Tailscale installation complete"
REMOTE_TAILSCALE

ok "Tailscale installed on ${NODE_IP}"

# ---------------------------------------------------------------------------
# Step 4: Authenticate Tailscale on the new node
# ---------------------------------------------------------------------------
info "Tailscale authentication required on the new node."
info "You will need to visit the URL printed below to authenticate."
echo ""

# shellcheck disable=SC2086
ssh ${SSH_OPTS} -t "${SSH_USER}@${NODE_IP}" \
    "sudo tailscale up --ssh --accept-routes"

ok "Tailscale authenticated on ${NODE_IP}"

# Get the node's Tailscale IP
# shellcheck disable=SC2086
NODE_TS_IP="$(ssh ${SSH_OPTS} "${SSH_USER}@${NODE_IP}" \
    "tailscale ip -4" 2>/dev/null)" \
    || die "Failed to get Tailscale IP for the new node"

ok "Node Tailscale IP: ${NODE_TS_IP}"

# ---------------------------------------------------------------------------
# Step 5: Get K3s server token and Tailscale IP
# ---------------------------------------------------------------------------
info "Retrieving K3s server token from server-00..."

# Discover server-00 via OCI API
ENV_FILE="${ORACLE_DIR}/.env"
if [[ -z "${OCI_COMPARTMENT_OCID:-}" && -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
fi

if [[ -n "${OCI_COMPARTMENT_OCID:-}" ]]; then
    SERVER_IP=$("${SCRIPT_DIR}/oci-inventory.sh" --list 2>/dev/null \
        | jq -r '._meta.hostvars[.servers.hosts[0]].ansible_host')
else
    # Fallback: terraform
    cd "${ORACLE_DIR}/terraform"
    SERVER_IP="$(terraform output -raw server_public_ip 2>/dev/null)" \
        || die "Cannot discover server-00. Set OCI_COMPARTMENT_OCID or pass server IP."
    cd "${ORACLE_DIR}"
fi

SERVER_SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/codectl-bastion}"
SERVER_SSH_USER="ubuntu"
SERVER_SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10 -i ${SERVER_SSH_KEY}"

# Get the K3s node token from the server
# shellcheck disable=SC2086
K3S_TOKEN="$(ssh ${SERVER_SSH_OPTS} "${SERVER_SSH_USER}@${SERVER_IP}" \
    "sudo cat /var/lib/rancher/k3s/server/node-token" 2>/dev/null)" \
    || die "Failed to retrieve K3s node token from server"

# Get the server's Tailscale IP
# shellcheck disable=SC2086
SERVER_TS_IP="$(ssh ${SERVER_SSH_OPTS} "${SERVER_SSH_USER}@${SERVER_IP}" \
    "tailscale ip -4" 2>/dev/null)" \
    || die "Failed to get server's Tailscale IP"

ok "Server Tailscale IP: ${SERVER_TS_IP}"

# ---------------------------------------------------------------------------
# Step 6: Install K3s agent on the new node
# ---------------------------------------------------------------------------
info "Installing K3s agent on ${NODE_IP}..."

# shellcheck disable=SC2086
ssh ${SSH_OPTS} "${SSH_USER}@${NODE_IP}" bash <<REMOTE_K3S
set -euo pipefail

# Install K3s as an agent, connecting via Tailscale
curl -sfL https://get.k3s.io | \
    K3S_URL="https://${SERVER_TS_IP}:6443" \
    K3S_TOKEN="${K3S_TOKEN}" \
    INSTALL_K3S_EXEC="agent --node-ip ${NODE_TS_IP} --flannel-iface tailscale0" \
    sh -

echo "K3s agent installation complete"
REMOTE_K3S

ok "K3s agent installed on ${NODE_IP}"

# ---------------------------------------------------------------------------
# Step 7: Wait for node to appear in kubectl get nodes
# ---------------------------------------------------------------------------
info "Waiting for node to join the cluster..."

MAX_RETRIES=30
RETRY_INTERVAL=10
retries=0

while true; do
    # Look for the node by its Tailscale IP in the node list
    if kubectl get nodes -o wide 2>/dev/null | grep -q "${NODE_TS_IP}"; then
        break
    fi

    retries=$((retries + 1))
    if [[ "${retries}" -ge "${MAX_RETRIES}" ]]; then
        die "Node did not appear in cluster after ${MAX_RETRIES} attempts"
    fi

    info "  Attempt ${retries}/${MAX_RETRIES} — waiting ${RETRY_INTERVAL}s..."
    sleep "${RETRY_INTERVAL}"
done

ok "Node joined the cluster"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  Node added successfully!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
info "Node details:"
echo "  Public IP:     ${NODE_IP}"
echo "  Tailscale IP:  ${NODE_TS_IP}"
echo ""
info "Current cluster nodes:"
kubectl get nodes -o wide
echo ""
ok "Done."
