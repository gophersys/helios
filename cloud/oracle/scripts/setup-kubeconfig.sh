#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# setup-kubeconfig.sh -- Dynamic kubeconfig fetch + SSH tunnel for K3s access
#
# Discovers the K3s server (server-00) via OCI API, fetches the kubeconfig
# over SSH, and starts a persistent SSH tunnel so kubectl works from inside
# containers or environments without Tailscale.
#
# Uses port 16443 locally to avoid clashing with any local K3s/K8s on 6443.
#
# Prerequisites:
#   - OCI CLI configured (~/.oci/config)
#   - OCI_COMPARTMENT_OCID set (or in .env)
#   - SSH key at ~/.ssh/codectl-bastion
#
# Usage:
#   ./setup-kubeconfig.sh              # discover + fetch + tunnel
#   ./setup-kubeconfig.sh --kill       # tear down the SSH tunnel
#   ./setup-kubeconfig.sh --status     # check tunnel status
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORACLE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ORACLE_DIR}/.env"

KUBECONFIG_PATH="${ORACLE_DIR}/kubeconfig"
TUNNEL_PID_FILE="/tmp/k3s-tunnel.pid"
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/codectl-bastion}"
SSH_USER="${SSH_USER:-ubuntu}"
LOCAL_PORT=16443
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=15 -i ${SSH_KEY}"

export SUPPRESS_LABEL_WARNING=True

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { printf "[kubeconfig] %s\n" "$*"; }
err()  { printf "[kubeconfig] ERROR: %s\n" "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------
kill_tunnel() {
    if [[ -f "${TUNNEL_PID_FILE}" ]]; then
        local pid
        pid=$(cat "${TUNNEL_PID_FILE}")
        if kill -0 "${pid}" 2>/dev/null; then
            kill "${pid}" 2>/dev/null || true
            log "Tunnel (PID ${pid}) stopped"
        fi
        rm -f "${TUNNEL_PID_FILE}"
    fi
    pkill -f "ssh.*-L ${LOCAL_PORT}:127.0.0.1:6443" 2>/dev/null || true
}

tunnel_status() {
    if [[ -f "${TUNNEL_PID_FILE}" ]]; then
        local pid
        pid=$(cat "${TUNNEL_PID_FILE}")
        if kill -0 "${pid}" 2>/dev/null; then
            log "Tunnel active (PID ${pid}) -- localhost:${LOCAL_PORT} -> server:6443"
            [[ -f "${KUBECONFIG_PATH}" ]] && log "Kubeconfig: ${KUBECONFIG_PATH}"
            return 0
        fi
    fi
    log "No active tunnel"
    return 1
}

# Handle subcommands early (no env needed)
case "${1:-}" in
    --kill)   kill_tunnel; exit 0 ;;
    --status) tunnel_status; exit 0 ;;
esac

# ---------------------------------------------------------------------------
# Load environment
# ---------------------------------------------------------------------------
if [[ -z "${OCI_COMPARTMENT_OCID:-}" && -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
fi

[[ -z "${OCI_COMPARTMENT_OCID:-}" ]] && err "OCI_COMPARTMENT_OCID not set"
[[ ! -f "${SSH_KEY}" ]] && err "SSH key not found at ${SSH_KEY}"

# ---------------------------------------------------------------------------
# Step 1: Discover K3s server via OCI API
# ---------------------------------------------------------------------------
log "Discovering K3s server via OCI API..."

oci compute instance list \
    --compartment-id "${OCI_COMPARTMENT_OCID}" \
    --lifecycle-state RUNNING \
    --query 'data[?contains("display-name", `server`)].[id,"display-name"]' \
    --output json > /tmp/oci-discover-$$.json 2>/dev/null \
    || err "OCI API query failed. Check ~/.oci/config"

INSTANCE_ID=$(jq -r '.[0][0] // empty' /tmp/oci-discover-$$.json)
INSTANCE_NAME=$(jq -r '.[0][1] // empty' /tmp/oci-discover-$$.json)
rm -f /tmp/oci-discover-$$.json

[[ -z "${INSTANCE_ID}" ]] && err "No server instance found (expected *server* in name)"

# Get public IP via VNIC attachment
VNIC_ID=$(oci compute vnic-attachment list \
    --compartment-id "${OCI_COMPARTMENT_OCID}" \
    --instance-id "${INSTANCE_ID}" \
    --query 'data[0]."vnic-id"' \
    --raw-output 2>/dev/null)

SERVER_IP=$(oci network vnic get \
    --vnic-id "${VNIC_ID}" \
    --query 'data."public-ip"' \
    --raw-output 2>/dev/null)

[[ -z "${SERVER_IP}" || "${SERVER_IP}" == "null" ]] && err "No public IP for ${INSTANCE_NAME}"

log "Found ${INSTANCE_NAME} at ${SERVER_IP}"

# ---------------------------------------------------------------------------
# Step 2: Fetch kubeconfig from the server
# ---------------------------------------------------------------------------
log "Fetching kubeconfig from ${SERVER_IP}..."

# shellcheck disable=SC2086
if ! ssh ${SSH_OPTS} "${SSH_USER}@${SERVER_IP}" "echo ok" &>/dev/null; then
    err "Cannot SSH to ${SERVER_IP}. Check key and security list."
fi

# shellcheck disable=SC2086
RAW_CONFIG=$(ssh ${SSH_OPTS} "${SSH_USER}@${SERVER_IP}" \
    "sudo cat /etc/rancher/k3s/k3s.yaml" 2>/dev/null) \
    || err "Failed to read kubeconfig from server"

[[ -z "${RAW_CONFIG}" ]] && err "Empty kubeconfig -- is K3s running?"

# Rewrite server address to use the local SSH tunnel port (16443)
echo "${RAW_CONFIG}" | sed "s|https://127.0.0.1:6443|https://127.0.0.1:${LOCAL_PORT}|g" \
    > "${KUBECONFIG_PATH}"
chmod 600 "${KUBECONFIG_PATH}"

log "Kubeconfig written (port ${LOCAL_PORT})"

# ---------------------------------------------------------------------------
# Step 3: Start SSH tunnel
# ---------------------------------------------------------------------------
kill_tunnel  # clean up any existing tunnel

log "Starting SSH tunnel: localhost:${LOCAL_PORT} -> ${SERVER_IP}:6443..."

ssh -f -N -o StrictHostKeyChecking=no -o ConnectTimeout=15 \
    -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
    -o ExitOnForwardFailure=yes \
    -i "${SSH_KEY}" \
    -L "${LOCAL_PORT}:127.0.0.1:6443" \
    "${SSH_USER}@${SERVER_IP}"

TUNNEL_PID=$(pgrep -f "ssh.*-L ${LOCAL_PORT}:127.0.0.1:6443.*${SERVER_IP}" | head -1)

if [[ -n "${TUNNEL_PID}" ]]; then
    echo "${TUNNEL_PID}" > "${TUNNEL_PID_FILE}"
    log "Tunnel active (PID ${TUNNEL_PID})"
else
    err "Failed to start SSH tunnel"
fi

# ---------------------------------------------------------------------------
# Step 4: Verify
# ---------------------------------------------------------------------------
log "Testing cluster connectivity..."
export KUBECONFIG="${KUBECONFIG_PATH}"

if kubectl get nodes --request-timeout=10s &>/dev/null; then
    log "Cluster reachable via tunnel"
    kubectl get nodes -o wide 2>/dev/null
else
    log "Warning: kubectl not responding yet -- tunnel may need a moment"
fi

echo ""
log "kubectl is ready. Kubeconfig: ${KUBECONFIG_PATH}"
log "Tunnel: localhost:${LOCAL_PORT} -> ${SERVER_IP}:6443"
