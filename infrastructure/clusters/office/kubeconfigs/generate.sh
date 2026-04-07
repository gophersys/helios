#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────────
# Kubeconfig Generator
# ───────────────────────────────────────────────────────────────
# Generates role-scoped kubeconfigs for Concord team members.
# Uses K8s CertificateSigningRequest API — signed by the cluster CA.
#
# Usage:
#   ./generate.sh create --user <email> --role <ROLE> [--days 365]
#   ./generate.sh list
#   ./generate.sh revoke --user <email>
#
# Roles:
#   ADMIN       → group concord-admins       (full cluster access)
#   MAINTAINER  → group concord-maintainers  (staging+dev full, production read-only)
#   DEVELOPER   → group concord-developers   (staging+dev read-only)
#   OPERATOR    → group concord-operators     (staging read-only)
# ───────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/generated"
CLUSTER_NAME="concord-office"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[kubeconfig]${NC} $*"; }
warn() { echo -e "${YELLOW}[kubeconfig]${NC} $*"; }
err()  { echo -e "${RED}[kubeconfig]${NC} $*" >&2; }
info() { echo -e "${CYAN}[kubeconfig]${NC} $*"; }

# ─── Role → Group mapping ───────────────────────────────────

declare -A ROLE_GROUPS=(
  [ADMIN]="concord-admins"
  [MAINTAINER]="concord-maintainers"
  [DEVELOPER]="concord-developers"
  [OPERATOR]="concord-operators"
)

declare -A ROLE_DESCRIPTIONS=(
  [ADMIN]="Full cluster access — all namespaces, all operations"
  [MAINTAINER]="Full staging+dev+validation, read-only production"
  [DEVELOPER]="Read-only staging+dev — no production access"
  [OPERATOR]="Read-only staging only — manufacturing operations"
)

# ─── Helpers ─────────────────────────────────────────────────

username_from_email() {
  echo "$1" | sed 's/@.*//'
}

get_cluster_server() {
  kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}' 2>/dev/null
}

get_cluster_ca() {
  kubectl config view --minify --flatten -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' 2>/dev/null
}

# ─── Create Kubeconfig ──────────────────────────────────────

cmd_create() {
  local user="" role="" days=365

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --user)  user="$2"; shift 2 ;;
      --role)  role="$2"; shift 2 ;;
      --days)  days="$2"; shift 2 ;;
      *) err "Unknown option: $1"; exit 1 ;;
    esac
  done

  # Validate
  if [[ -z "${user}" ]]; then
    err "Required: --user <email>"
    exit 1
  fi
  if [[ -z "${role}" ]]; then
    err "Required: --role <ADMIN|MAINTAINER|DEVELOPER|OPERATOR>"
    exit 1
  fi
  role="${role^^}"  # uppercase
  if [[ -z "${ROLE_GROUPS[${role}]:-}" ]]; then
    err "Invalid role: ${role}"
    err "Valid roles: ADMIN, MAINTAINER, DEVELOPER, OPERATOR"
    exit 1
  fi

  local group="${ROLE_GROUPS[${role}]}"
  local cn="${user}"
  local username
  username=$(username_from_email "${user}")
  local csr_name="concord-${username}"
  local key_file="${OUTPUT_DIR}/${username}.key"
  local csr_file="${OUTPUT_DIR}/${username}.csr"
  local cert_file="${OUTPUT_DIR}/${username}.crt"
  local kubeconfig_file="${OUTPUT_DIR}/${username}.kubeconfig"

  mkdir -p "${OUTPUT_DIR}"

  log "Creating kubeconfig for ${BOLD}${user}${NC} (${role})"
  info "  Group: ${group}"
  info "  Description: ${ROLE_DESCRIPTIONS[${role}]}"
  info "  Valid for: ${days} days"

  # 1. Generate private key
  openssl genrsa -out "${key_file}" 2048 2>/dev/null
  chmod 600 "${key_file}"

  # 2. Generate CSR with user CN and group O
  openssl req -new -key "${key_file}" -out "${csr_file}" \
    -subj "/CN=${cn}/O=${group}" 2>/dev/null

  # 3. Delete old CSR if exists
  kubectl delete csr "${csr_name}" 2>/dev/null || true

  # 4. Submit CSR to K8s
  local csr_b64
  csr_b64=$(base64 -w0 < "${csr_file}")

  cat <<EOF | kubectl apply -f - > /dev/null
apiVersion: certificates.k8s.io/v1
kind: CertificateSigningRequest
metadata:
  name: ${csr_name}
spec:
  request: ${csr_b64}
  signerName: kubernetes.io/kube-apiserver-client
  expirationSeconds: $((days * 86400))
  usages:
    - client auth
EOF

  # 5. Approve CSR
  kubectl certificate approve "${csr_name}" > /dev/null 2>&1

  # 6. Wait for certificate
  local retries=10
  while [[ ${retries} -gt 0 ]]; do
    local cert
    cert=$(kubectl get csr "${csr_name}" -o jsonpath='{.status.certificate}' 2>/dev/null || true)
    if [[ -n "${cert}" ]]; then
      echo "${cert}" | base64 -d > "${cert_file}"
      break
    fi
    sleep 1
    retries=$((retries - 1))
  done

  if [[ ! -f "${cert_file}" ]] || [[ ! -s "${cert_file}" ]]; then
    err "Failed to get signed certificate from K8s"
    kubectl get csr "${csr_name}" -o yaml 2>/dev/null
    exit 1
  fi

  # 7. Build kubeconfig
  local server ca_data
  server=$(get_cluster_server)
  ca_data=$(get_cluster_ca)

  cat > "${kubeconfig_file}" <<EOF
apiVersion: v1
kind: Config
clusters:
  - cluster:
      certificate-authority-data: ${ca_data}
      server: ${server}
    name: ${CLUSTER_NAME}
contexts:
  - context:
      cluster: ${CLUSTER_NAME}
      user: ${cn}
      namespace: staging
    name: ${CLUSTER_NAME}
current-context: ${CLUSTER_NAME}
users:
  - name: ${cn}
    user:
      client-certificate-data: $(base64 -w0 < "${cert_file}")
      client-key-data: $(base64 -w0 < "${key_file}")
EOF

  chmod 600 "${kubeconfig_file}"

  # 8. Write metadata
  cat > "${OUTPUT_DIR}/${username}.meta.json" <<EOF
{
  "user": "${user}",
  "role": "${role}",
  "group": "${group}",
  "csrName": "${csr_name}",
  "createdAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "expiresInDays": ${days},
  "kubeconfig": "${kubeconfig_file}"
}
EOF

  # 9. Clean up CSR file (not needed after signing)
  rm -f "${csr_file}"

  log "${BOLD}Kubeconfig created:${NC} ${kubeconfig_file}"
  echo ""
  echo "  Give this file to ${user}. They use it with:"
  echo ""
  echo "    export KUBECONFIG=${kubeconfig_file}"
  echo "    kubectl get pods -n staging"
  echo ""

  # 10. Quick access test
  info "Testing access..."
  local test_result
  if KUBECONFIG="${kubeconfig_file}" kubectl auth can-i list pods -n staging 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} staging: can list pods"
  else
    echo -e "  ${RED}✗${NC} staging: cannot list pods"
  fi
  if KUBECONFIG="${kubeconfig_file}" kubectl auth can-i list pods -n production 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} production: can list pods"
  else
    echo -e "  ${YELLOW}✗${NC} production: cannot list pods (expected for ${role})"
  fi
  if KUBECONFIG="${kubeconfig_file}" kubectl auth can-i delete pods -n staging 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} staging: can delete pods"
  else
    echo -e "  ${YELLOW}✗${NC} staging: cannot delete pods (expected for ${role})"
  fi
}

# ─── List Kubeconfigs ────────────────────────────────────────

cmd_list() {
  log "Generated kubeconfigs:"
  echo ""

  if [[ ! -d "${OUTPUT_DIR}" ]] || [[ -z "$(ls -A "${OUTPUT_DIR}"/*.meta.json 2>/dev/null)" ]]; then
    info "  No kubeconfigs generated yet."
    return
  fi

  printf "  ${BOLD}%-30s %-14s %-25s %s${NC}\n" "USER" "ROLE" "CREATED" "FILE"
  echo "  $(printf '%.0s─' {1..90})"

  for meta in "${OUTPUT_DIR}"/*.meta.json; do
    local user role created file
    user=$(jq -r '.user' "${meta}")
    role=$(jq -r '.role' "${meta}")
    created=$(jq -r '.createdAt' "${meta}" | cut -dT -f1)
    file=$(basename "$(jq -r '.kubeconfig' "${meta}")")
    printf "  %-30s %-14s %-25s %s\n" "${user}" "${role}" "${created}" "${file}"
  done
  echo ""

  # Also show active K8s CSRs
  info "Active CSRs in cluster:"
  kubectl get csr --no-headers 2>/dev/null | grep "^concord-" | while read -r line; do
    echo "  ${line}"
  done || info "  (none)"
}

# ─── Revoke Kubeconfig ──────────────────────────────────────

cmd_revoke() {
  local user=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --user) user="$2"; shift 2 ;;
      *) err "Unknown option: $1"; exit 1 ;;
    esac
  done

  if [[ -z "${user}" ]]; then
    err "Required: --user <email>"
    exit 1
  fi

  local username
  username=$(username_from_email "${user}")
  local csr_name="concord-${username}"

  log "Revoking kubeconfig for ${BOLD}${user}${NC}"

  # Delete K8s CSR (invalidates the certificate)
  if kubectl delete csr "${csr_name}" 2>/dev/null; then
    log "  CSR deleted: ${csr_name}"
  else
    warn "  CSR not found: ${csr_name}"
  fi

  # Remove local files
  local removed=0
  for ext in key crt kubeconfig meta.json; do
    if [[ -f "${OUTPUT_DIR}/${username}.${ext}" ]]; then
      rm -f "${OUTPUT_DIR}/${username}.${ext}"
      removed=$((removed + 1))
    fi
  done

  if [[ ${removed} -gt 0 ]]; then
    log "  Removed ${removed} local files"
  else
    warn "  No local files found for ${username}"
  fi

  log "Kubeconfig revoked for ${user}"
  echo ""
  warn "Note: The certificate is still technically valid until expiry."
  warn "For immediate revocation, the user must stop using the kubeconfig file."
  warn "K8s does not support CRL — re-bootstrap RBAC bindings to fully lock out if needed."
}

# ─── Batch Generate ─────────────────────────────────────────

cmd_batch() {
  log "Batch generating kubeconfigs for team..."
  echo ""

  # Team roster from seed/platform.py
  cmd_create --user "mateo@corekinect.com" --role ADMIN
  echo ""
  cmd_create --user "jared@corekinect.com" --role ADMIN
  echo ""
  cmd_create --user "mitchel@corekinect.com" --role ADMIN
  echo ""
  cmd_create --user "chris@corekinect.com" --role DEVELOPER
  echo ""
  cmd_create --user "christian@corekinect.com" --role DEVELOPER
  echo ""
  cmd_create --user "gwen@corekinect.com" --role OPERATOR
  echo ""

  log "${BOLD}All team kubeconfigs generated.${NC}"
  echo ""
  cmd_list
}

# ─── Usage ──────────────────────────────────────────────────

usage() {
  cat <<EOF

${BOLD}Concord Kubeconfig Generator${NC}

${BOLD}Usage:${NC}
  $(basename "$0") <action> [options]

${BOLD}Actions:${NC}
  ${GREEN}create${NC}    Generate a kubeconfig for a user
  ${GREEN}list${NC}      Show all generated kubeconfigs
  ${GREEN}revoke${NC}    Revoke a user's kubeconfig
  ${GREEN}batch${NC}     Generate kubeconfigs for the entire team

${BOLD}Create Options:${NC}
  --user <email>     User email (used as CN in certificate)
  --role <ROLE>      Platform role: ADMIN, MAINTAINER, DEVELOPER, OPERATOR
  --days <N>         Certificate validity in days (default: 365)

${BOLD}Revoke Options:${NC}
  --user <email>     User email to revoke

${BOLD}Roles:${NC}
  ADMIN        Full cluster access — all namespaces, all operations
  MAINTAINER   Full staging+dev+validation, read-only production
  DEVELOPER    Read-only staging+dev — no production access
  OPERATOR     Read-only staging only — manufacturing operations

${BOLD}Examples:${NC}
  $(basename "$0") create --user chris@corekinect.com --role DEVELOPER
  $(basename "$0") create --user mateo@corekinect.com --role ADMIN --days 730
  $(basename "$0") list
  $(basename "$0") revoke --user chris@corekinect.com
  $(basename "$0") batch     # Generate for entire team

EOF
}

# ─── Main ────────────────────────────────────────────────────

ACTION="${1:-help}"
shift || true

case "${ACTION}" in
  create)  cmd_create "$@" ;;
  list)    cmd_list ;;
  revoke)  cmd_revoke "$@" ;;
  batch)   cmd_batch ;;
  help|--help|-h) usage ;;
  *) err "Unknown action: ${ACTION}"; usage; exit 1 ;;
esac
