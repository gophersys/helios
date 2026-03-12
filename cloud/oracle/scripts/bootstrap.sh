#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# bootstrap.sh — Full 6-node cluster bootstrap from OCI instances
#
# Discovers running instances via OCI API, configures them with Ansible,
# and deploys core Kubernetes components. No Terraform state required.
#
# Node layout:
#   server-00    K3s control plane       (servers)
#   agent-00     K3s worker ARM          (agents)
#   agent-01     K3s worker x86, IB GW   (agents)
#   agent-02     K3s worker x86, light   (agents)
#   sentinel-00  Bastion/monitoring      (sentinels)
#   sentinel-01  Backup bastion          (sentinels)
#
# Prerequisites:
#   - OCI CLI configured (~/.oci/config)
#   - OCI_COMPARTMENT_OCID set (or in .env)
#   - TAILSCALE_AUTH_KEY set (or in .env)
#   - CLOUDFLARE_API_TOKEN set (or in .env)
#   - SSH key at ~/.ssh/codectl-bastion (or SSH_KEY_PATH env var)
#
# Usage:
#   ./bootstrap.sh              # interactive
#   ./bootstrap.sh --auto       # non-interactive (skip confirmations)
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
# Cleanup trap
# ---------------------------------------------------------------------------
cleanup() {
    local exit_code=$?
    if [[ "${exit_code}" -ne 0 ]]; then
        warn "Bootstrap failed at step: ${CURRENT_STEP:-unknown} (exit code ${exit_code})"
        warn "Fix the issue and re-run. This script is idempotent."
    fi
}
trap cleanup EXIT

CURRENT_STEP="init"
AUTO_APPROVE=false
[[ "${1:-}" == "--auto" ]] && AUTO_APPROVE=true

# ---------------------------------------------------------------------------
# Step 1: Load environment
# ---------------------------------------------------------------------------
CURRENT_STEP="environment"
info "Loading environment..."

if [[ -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
    ok "Loaded .env"
fi

# Validate required vars
[[ -z "${OCI_COMPARTMENT_OCID:-}" ]] && die "OCI_COMPARTMENT_OCID not set"
[[ -z "${TAILSCALE_AUTH_KEY:-}" ]] && die "TAILSCALE_AUTH_KEY not set"
[[ -z "${CLOUDFLARE_API_TOKEN:-}" ]] && die "CLOUDFLARE_API_TOKEN not set"

SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/codectl-bastion}"
[[ ! -f "${SSH_KEY}" ]] && die "SSH key not found at ${SSH_KEY}"

# If TAILSCALE_AUTH_KEY is an API key (not an auth key), generate a proper
# node auth key from it. API keys start with tskey-api-, auth keys with tskey-auth-.
if [[ "${TAILSCALE_AUTH_KEY}" == tskey-api-* ]]; then
    info "Generating Tailscale node auth key from API key..."
    TS_RESPONSE=$(curl -sf -X POST "https://api.tailscale.com/api/v2/tailnet/-/keys" \
        -u "${TAILSCALE_AUTH_KEY}:" \
        -H "Content-Type: application/json" \
        -d '{"capabilities":{"devices":{"create":{"reusable":true,"ephemeral":false,"preauthorized":true}}},"expirySeconds":86400}') \
        || die "Failed to generate Tailscale auth key. Check your API key."
    TAILSCALE_AUTH_KEY=$(echo "${TS_RESPONSE}" | jq -r '.key')
    [[ -z "${TAILSCALE_AUTH_KEY}" || "${TAILSCALE_AUTH_KEY}" == "null" ]] && die "Empty auth key returned from Tailscale API"
    ok "Generated reusable auth key (expires in 24h)"
fi

export OCI_COMPARTMENT_OCID SSH_KEY_PATH="${SSH_KEY}" TAILSCALE_AUTH_KEY

# ---------------------------------------------------------------------------
# Step 2: Discover instances via OCI API
# ---------------------------------------------------------------------------
CURRENT_STEP="oci-discovery"
info "Discovering OCI instances..."

INVENTORY_JSON=$("${SCRIPT_DIR}/oci-inventory.sh" --list 2>/dev/null) \
    || die "Failed to query OCI API. Check your OCI CLI config."

SERVER_COUNT=$(echo "${INVENTORY_JSON}" | jq '.servers.hosts | length')
AGENT_COUNT=$(echo "${INVENTORY_JSON}" | jq '.agents.hosts | length')
SENTINEL_COUNT=$(echo "${INVENTORY_JSON}" | jq '.sentinels.hosts | length')
SERVER_IP=$(echo "${INVENTORY_JSON}" | jq -r '._meta.hostvars[.servers.hosts[0]].ansible_host')

[[ "${SERVER_COUNT}" -eq 0 ]] && die "No server instances found. Expected *server* naming convention."

ok "Found ${SERVER_COUNT} server(s), ${AGENT_COUNT} agent(s), ${SENTINEL_COUNT} sentinel(s)"
echo "${INVENTORY_JSON}" | jq -r '._meta.hostvars | to_entries[] | "  \(.key): \(.value.ansible_host) (A1: \(.value.oci_a1_instance))"'

if [[ "${AUTO_APPROVE}" != "true" ]]; then
    echo ""
    echo -n "Proceed with bootstrap? [y/N] "
    read -r confirm
    [[ "${confirm}" != "y" && "${confirm}" != "Y" ]] && { info "Cancelled."; exit 0; }
fi

# ---------------------------------------------------------------------------
# Step 3: Verify SSH connectivity to all nodes
# ---------------------------------------------------------------------------
CURRENT_STEP="ssh-verify"
info "Verifying SSH access..."

SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10 -i ${SSH_KEY}"

for host in $(echo "${INVENTORY_JSON}" | jq -r '._meta.hostvars | to_entries[] | "\(.key)=\(.value.ansible_host)"'); do
    name="${host%%=*}"
    ip="${host##*=}"
    # shellcheck disable=SC2086
    if ssh ${SSH_OPTS} "ubuntu@${ip}" "echo ok" &>/dev/null; then
        ok "  ${name} (${ip}) — reachable"
    else
        die "  ${name} (${ip}) — SSH failed. Check key and security list."
    fi
done

# ---------------------------------------------------------------------------
# Step 4: Run Ansible playbooks
# ---------------------------------------------------------------------------
CURRENT_STEP="ansible"
info "Running Ansible configuration (K3s + Tailscale + hardening)..."
info "  This takes 5-10 minutes on fresh nodes..."

cd "${ORACLE_DIR}/ansible"

# Clear stale fact cache
rm -rf /tmp/ansible_facts 2>/dev/null || true

ansible-playbook site.yml -v

ok "Ansible configuration complete"

# ---------------------------------------------------------------------------
# Step 5: Fetch kubeconfig
# ---------------------------------------------------------------------------
CURRENT_STEP="kubeconfig"
info "Fetching kubeconfig..."

FETCHED_KC="${ORACLE_DIR}/ansible/fetched/kubeconfig.yaml"
if [[ -f "${FETCHED_KC}" ]]; then
    cp "${FETCHED_KC}" "${ORACLE_DIR}/kubeconfig"
    chmod 600 "${ORACLE_DIR}/kubeconfig"
    ok "Kubeconfig at ${ORACLE_DIR}/kubeconfig"
else
    # Fallback: fetch directly via SSH
    info "Fetching kubeconfig directly from server..."
    TAILSCALE_IP=$(ssh ${SSH_OPTS} "ubuntu@${SERVER_IP}" "tailscale ip -4" 2>/dev/null | tr -d '[:space:]')
    ssh ${SSH_OPTS} "ubuntu@${SERVER_IP}" "sudo cat /etc/rancher/k3s/k3s.yaml" \
        | sed "s|127.0.0.1|${TAILSCALE_IP}|g" \
        > "${ORACLE_DIR}/kubeconfig"
    chmod 600 "${ORACLE_DIR}/kubeconfig"
    ok "Kubeconfig fetched (server Tailscale IP: ${TAILSCALE_IP})"
fi

export KUBECONFIG="${ORACLE_DIR}/kubeconfig"

# Verify cluster connectivity
info "Testing cluster connectivity..."
if kubectl get nodes --request-timeout=15s &>/dev/null; then
    ok "Cluster is reachable"
    kubectl get nodes -o wide
else
    die "Cannot reach cluster. Is Tailscale connected?"
fi

# ---------------------------------------------------------------------------
# Step 6: Apply namespaces
# ---------------------------------------------------------------------------
CURRENT_STEP="namespaces"
info "Applying Kubernetes namespaces..."

if [[ -f "${ORACLE_DIR}/kubernetes/core/namespaces.yaml" ]]; then
    kubectl apply -f "${ORACLE_DIR}/kubernetes/core/namespaces.yaml"
    ok "Namespaces created"
else
    warn "No namespaces.yaml found — skipping"
fi

# ---------------------------------------------------------------------------
# Step 7: Install cert-manager via Helm
# ---------------------------------------------------------------------------
CURRENT_STEP="cert-manager"
info "Installing cert-manager..."

helm repo add jetstack https://charts.jetstack.io --force-update 2>/dev/null
helm repo update jetstack 2>/dev/null

CERT_MANAGER_VALUES="${ORACLE_DIR}/kubernetes/core/cert-manager/values.yaml"
CERT_MANAGER_ARGS=()
if [[ -f "${CERT_MANAGER_VALUES}" ]]; then
    CERT_MANAGER_ARGS+=(-f "${CERT_MANAGER_VALUES}")
fi

helm upgrade --install cert-manager jetstack/cert-manager \
    --namespace cert-manager \
    --create-namespace \
    "${CERT_MANAGER_ARGS[@]}" \
    --wait --timeout 5m

ok "cert-manager installed"

# ---------------------------------------------------------------------------
# Step 8: Apply Cloudflare secret + cluster issuers
# ---------------------------------------------------------------------------
CURRENT_STEP="cert-issuers"
info "Applying cert-manager issuers..."

# Create Cloudflare secret from env var
kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: cloudflare-api-token
  namespace: cert-manager
type: Opaque
stringData:
  api-token: "${CLOUDFLARE_API_TOKEN}"
EOF
ok "Cloudflare API token secret created"

for issuer_file in "${ORACLE_DIR}"/kubernetes/core/cert-manager/cluster-issuer-*.yaml; do
    if [[ -f "${issuer_file}" ]]; then
        kubectl apply -f "${issuer_file}"
        ok "Applied $(basename "${issuer_file}")"
    fi
done

# ---------------------------------------------------------------------------
# Step 9: Install ingress-nginx via Helm
# ---------------------------------------------------------------------------
CURRENT_STEP="ingress-nginx"
info "Installing ingress-nginx..."

helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx --force-update 2>/dev/null
helm repo update ingress-nginx 2>/dev/null

INGRESS_VALUES="${ORACLE_DIR}/kubernetes/core/ingress-nginx/values.yaml"
INGRESS_ARGS=()
if [[ -f "${INGRESS_VALUES}" ]]; then
    INGRESS_ARGS+=(-f "${INGRESS_VALUES}")
fi

helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
    --namespace ingress-nginx \
    --create-namespace \
    "${INGRESS_ARGS[@]}" \
    --wait --timeout 5m

ok "ingress-nginx installed"

# ---------------------------------------------------------------------------
# Step 10: Update Cloudflare DNS
# ---------------------------------------------------------------------------
CURRENT_STEP="dns"
info "Updating Cloudflare DNS to point to server (${SERVER_IP})..."

if [[ -n "${CLOUDFLARE_ZONE_ID:-}" && -n "${CLOUDFLARE_API_TOKEN:-}" ]]; then
    CF_API="https://api.cloudflare.com/client/v4"
    CF_HEADERS=(-H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" -H "Content-Type: application/json")
    DOMAIN="codectl.dev"

    update_dns_record() {
        local name="$1" content="$2"
        local record_id
        record_id=$(curl -sf "${CF_API}/zones/${CLOUDFLARE_ZONE_ID}/dns_records?name=${name}&type=A" \
            "${CF_HEADERS[@]}" | jq -r '.result[0].id // empty')

        if [[ -n "${record_id}" ]]; then
            curl -sf -X PUT "${CF_API}/zones/${CLOUDFLARE_ZONE_ID}/dns_records/${record_id}" \
                "${CF_HEADERS[@]}" \
                -d "{\"type\":\"A\",\"name\":\"${name}\",\"content\":\"${content}\",\"proxied\":false,\"ttl\":300}" \
                | jq -r '"  Updated: \(.result.name) → \(.result.content)"'
        else
            curl -sf -X POST "${CF_API}/zones/${CLOUDFLARE_ZONE_ID}/dns_records" \
                "${CF_HEADERS[@]}" \
                -d "{\"type\":\"A\",\"name\":\"${name}\",\"content\":\"${content}\",\"proxied\":false,\"ttl\":300}" \
                | jq -r '"  Created: \(.result.name) → \(.result.content)"'
        fi
    }

    update_dns_record "${DOMAIN}" "${SERVER_IP}"
    update_dns_record "*.${DOMAIN}" "${SERVER_IP}"
    ok "DNS updated: ${DOMAIN} + *.${DOMAIN} → ${SERVER_IP}"
else
    warn "CLOUDFLARE_ZONE_ID not set — skipping DNS update"
    warn "Manually point codectl.dev + *.codectl.dev to ${SERVER_IP}"
fi

# ---------------------------------------------------------------------------
# Step 11: Verify everything
# ---------------------------------------------------------------------------
CURRENT_STEP="verify"
info "Running verification checks..."

echo ""
echo "=== Nodes ==="
kubectl get nodes -o wide
echo ""
echo "=== Core Pods ==="
kubectl get pods -A | grep -E '(cert-manager|ingress-nginx|NAMESPACE)'
echo ""
echo "=== Helm Releases ==="
helm list -A
echo ""
echo "=== Cluster Issuers ==="
kubectl get clusterissuers
echo ""

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
CURRENT_STEP="done"
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  Bootstrap complete!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
info "Cluster: 6-node K3s on OCI (1 server, 3 agents, 2 sentinels)"
info "Domain:  codectl.dev → ${SERVER_IP}"
info "TLS:     Let's Encrypt via cert-manager (DNS01 Cloudflare)"
info ""
info "Kubeconfig: export KUBECONFIG=${ORACLE_DIR}/kubeconfig"
info ""
info "Next: deploy the application stack"
echo ""
ok "All done."
