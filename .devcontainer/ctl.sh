#!/usr/bin/env bash
# .devcontainer/ctl.sh — dev container lifecycle management
#
# Host actions:   build | push | create | start
# Container actions (called by devcontainer.json):  post-create | post-start
#
# Secrets loading (post-create):
#   1. Bitwarden (preferred) — requires BW_SESSION from host: bw unlock
#   2. .env file (fallback)  — legacy, for machines without bw setup
#   3. CI environment         — GitHub Actions, etc. pass secrets as env vars
#
# Prerequisites:
#   build/push    docker (Desktop or CLI)
#   create/start  @devcontainers/cli  →  npm install -g @devcontainers/cli
#   bitwarden     bw unlock on host   →  export BW_SESSION="..."

set -euo pipefail

IMAGE="ghcr.io/mateosegura/dev-env:latest"
PLATFORM="linux/amd64"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
SECRETS_FILE="${HOME}/.secrets.env"

# Bitwarden item name for this project's env vars
BW_ENV_ITEM="env:infrastructure"

# ── helpers ───────────────────────────────────────────────────────────────────
info()  { echo "  [ctl] $*"; }
ok()    { echo "  [ctl] ✓ $*"; }
warn()  { echo "  [ctl] ! $*"; }
die()   { echo "  [ctl] ✗ $*" >&2; exit 1; }

usage() {
  cat <<EOF

  Usage: .devcontainer/ctl.sh <action>

  Host actions:
    build         Build the image locally (linux/amd64)
    push          Authenticate via Bitwarden or .env and push to ghcr.io
    create        Create and start the devcontainer
    start         Open a shell in the running container

  Container lifecycle (called by devcontainer.json):
    post-create   Load secrets, set up OCI config, SSH keys, git-crypt unlock
    post-start    Authenticate gh and ghcr.io, setup kubeconfig

  Secrets (pick one):
    a) bw unlock on your host machine (preferred — no plaintext on disk)
    b) cp .devcontainer/.env.example .devcontainer/.env (legacy fallback)

EOF
  exit 1
}

# ── secrets loading ───────────────────────────────────────────────────────────

# Detect environment and load secrets accordingly
_load_secrets() {
  # CI mode — secrets already injected by CI system
  if [ -n "${CI:-}" ] || [ -n "${GITHUB_ACTIONS:-}" ]; then
    ok "CI detected — using environment variables from CI"
    return 0
  fi

  # Bitwarden mode — preferred for local dev
  if [ -n "${BW_SESSION:-}" ]; then
    _load_secrets_bw
    return 0
  fi

  # Legacy .env fallback
  if [ -f "${ENV_FILE}" ]; then
    warn "No BW_SESSION — falling back to .env file (legacy)"
    warn "Consider: bw unlock on your host for encrypted-at-rest secrets"
    set -a
    # shellcheck source=/dev/null
    source "${ENV_FILE}"
    set +a
    return 0
  fi

  die "No secrets source found. Either:
    1. Run 'bw unlock' on your host and export BW_SESSION  (preferred)
    2. Create .devcontainer/.env from .env.example           (legacy)"
}

# Pull secrets from Bitwarden vault
_load_secrets_bw() {
  info "Loading secrets from Bitwarden (${BW_ENV_ITEM})..."

  # Install bw CLI if not present
  if ! command -v bw &>/dev/null; then
    info "Installing Bitwarden CLI..."
    npm install -g @bitwarden/cli --silent 2>/dev/null
    bw config server "${BW_SERVER:-https://secrets.mateosegura.com}" 2>/dev/null
  fi

  # Pull the env note
  local env_data
  env_data=$(bw get notes "${BW_ENV_ITEM}" --session "${BW_SESSION}" 2>/dev/null) \
    || die "Failed to pull '${BW_ENV_ITEM}' from Bitwarden. Is the vault unlocked?"

  [ -z "${env_data}" ] && die "Empty response from Bitwarden for '${BW_ENV_ITEM}'"

  # Write to secrets file (in-memory tmpfs if available, else /root)
  echo "${env_data}" > "${SECRETS_FILE}"
  chmod 600 "${SECRETS_FILE}"

  # Source into current environment
  set -a
  # shellcheck source=/dev/null
  source "${SECRETS_FILE}"
  set +a

  # Persist for future shells (zsh/bash)
  local source_line="[ -f ${SECRETS_FILE} ] && { set -a; source ${SECRETS_FILE}; set +a; }"
  grep -qF "${SECRETS_FILE}" ${HOME}/.zshrc 2>/dev/null \
    || echo "${source_line}" >> ${HOME}/.zshrc
  grep -qF "${SECRETS_FILE}" ${HOME}/.bashrc 2>/dev/null \
    || echo "${source_line}" >> ${HOME}/.bashrc

  ok "Secrets loaded from Bitwarden ($(echo "${env_data}" | grep -c '=') vars)"
}

# Host-side env loading (for push/create commands)
_load_env_host() {
  # Try Bitwarden first (host machine)
  if [ -n "${BW_SESSION:-}" ] && command -v bw &>/dev/null; then
    local env_data
    env_data=$(bw get notes "${BW_ENV_ITEM}" --session "${BW_SESSION}" 2>/dev/null)
    if [ -n "${env_data}" ]; then
      eval "$(echo "${env_data}" | grep -E '^[A-Z_]+=.' | sed 's/^/export /')"
      ok "Host secrets loaded from Bitwarden"
      return 0
    fi
  fi

  # Fallback to .env
  if [ -f "${ENV_FILE}" ]; then
    set -a; source "${ENV_FILE}"; set +a
    return 0
  fi

  die "No secrets available on host. Run 'bw unlock' or create .devcontainer/.env"
}

# ── host actions ──────────────────────────────────────────────────────────────
cmd_build() {
  info "Building ${IMAGE} ..."
  docker build \
    --platform "${PLATFORM}" \
    --tag "${IMAGE}" \
    "${SCRIPT_DIR}"
  ok "Build complete — ${IMAGE}"
}

cmd_push() {
  _load_env_host
  [ -z "${GITHUB_TOKEN:-}" ] && die "GITHUB_TOKEN not available"
  info "Authenticating with ghcr.io ..."
  echo "${GITHUB_TOKEN}" | docker login ghcr.io -u MateoSegura --password-stdin
  info "Pushing ${IMAGE} ..."
  docker push "${IMAGE}"
  ok "Push complete — ${IMAGE}"
}

cmd_create() {
  command -v devcontainer > /dev/null 2>&1 \
    || die "devcontainer CLI not found — run: npm install -g @devcontainers/cli"

  # Ensure bw config dir exists (for mount)
  mkdir -p "${HOME}/.config/Bitwarden CLI" 2>/dev/null || true

  info "Creating devcontainer ..."
  devcontainer up --workspace-folder "${REPO_ROOT}"
  ok "Devcontainer ready.  Run: .devcontainer/ctl.sh start"
}

cmd_start() {
  command -v devcontainer > /dev/null 2>&1 \
    || die "devcontainer CLI not found — run: npm install -g @devcontainers/cli"
  info "Opening shell (root, IS_SANDBOX=1) ..."
  devcontainer exec --workspace-folder "${REPO_ROOT}" zsh
}

# ── container lifecycle actions ───────────────────────────────────────────────
cmd_post_create() {
  # Runs once after the container is first created
  WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

  # ── Load secrets (Bitwarden → .env → CI) ──────────────────────────────────
  _load_secrets

  # ── OCI CLI configuration ──────────────────────────────────────────────────
  if [ -n "${OCI_TENANCY_OCID:-}" ] && [ -n "${OCI_USER_OCID:-}" ]; then
    mkdir -p ${HOME}/.oci
    local key_dest="${HOME}/.oci/oci_api_key.pem"

    if [ -n "${OCI_PRIVATE_KEY_B64:-}" ]; then
      echo "${OCI_PRIVATE_KEY_B64}" | base64 -d > "${key_dest}"
      chmod 600 "${key_dest}"
      ok "OCI API key written from OCI_PRIVATE_KEY_B64"
    elif [ -f "${WORKSPACE}/.devcontainer/oci_api_key.pem" ]; then
      cp "${WORKSPACE}/.devcontainer/oci_api_key.pem" "${key_dest}"
      chmod 600 "${key_dest}"
      ok "OCI API key deployed from .devcontainer/oci_api_key.pem"
    else
      warn "No OCI API key found — set OCI_PRIVATE_KEY_B64 or place oci_api_key.pem in .devcontainer/"
    fi

    cat > ${HOME}/.oci/config <<EOF
[DEFAULT]
user=${OCI_USER_OCID}
fingerprint=${OCI_FINGERPRINT:-}
tenancy=${OCI_TENANCY_OCID}
region=${OCI_REGION:-us-phoenix-1}
key_file=${HOME}/.oci/oci_api_key.pem
EOF
    chmod 600 ${HOME}/.oci/config
    ok "OCI config written (~/.oci/config)"
  else
    warn "OCI_TENANCY_OCID / OCI_USER_OCID not set — skipping OCI config"
  fi

  # ── SSH key for infrastructure access ────────────────────────────────────
  if [ -n "${SSH_PRIVATE_KEY_B64:-}" ]; then
    mkdir -p ${HOME}/.ssh
    chmod 700 ${HOME}/.ssh
    echo "${SSH_PRIVATE_KEY_B64}" | base64 -d > ${HOME}/.ssh/infra-bastion
    chmod 600 ${HOME}/.ssh/infra-bastion
    ssh-keygen -y -f ${HOME}/.ssh/infra-bastion > ${HOME}/.ssh/infra-bastion.pub 2>/dev/null
    chmod 644 ${HOME}/.ssh/infra-bastion.pub
    ok "SSH key written from SSH_PRIVATE_KEY_B64 (~/.ssh/infra-bastion)"
  fi

  # ── git-crypt unlock ───────────────────────────────────────────────────────
  GIT_CRYPT_KEY_FILE="${WORKSPACE}/.devcontainer/git-crypt.key"
  if [ -n "${GIT_CRYPT_KEY_B64:-}" ]; then
    local tmp_key
    tmp_key=$(mktemp)
    echo "${GIT_CRYPT_KEY_B64}" | base64 -d > "${tmp_key}"
    chmod 600 "${tmp_key}"
    if command -v git-crypt > /dev/null 2>&1; then
      if git -C "${WORKSPACE}" crypt unlock "${tmp_key}" 2>/dev/null; then
        ok "git-crypt unlocked (from GIT_CRYPT_KEY_B64)"
      else
        warn "git-crypt unlock failed (may already be unlocked)"
      fi
    else
      warn "git-crypt not installed — encrypted files will remain encrypted"
    fi
    rm -f "${tmp_key}"
  elif [ -f "${GIT_CRYPT_KEY_FILE}" ]; then
    if command -v git-crypt > /dev/null 2>&1; then
      if git -C "${WORKSPACE}" crypt unlock "${GIT_CRYPT_KEY_FILE}" 2>/dev/null; then
        ok "git-crypt unlocked (from .devcontainer/git-crypt.key)"
      else
        warn "git-crypt unlock failed (may already be unlocked)"
      fi
    else
      warn "git-crypt not installed — encrypted files will remain encrypted"
    fi
  else
    info "No git-crypt key found — skipping unlock"
  fi
}

cmd_post_start() {
  WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

  # Re-source secrets if available (env vars don't persist across container restarts)
  if [ -f "${SECRETS_FILE}" ]; then
    set -a; source "${SECRETS_FILE}"; set +a
  elif [ -f "${ENV_FILE}" ]; then
    set -a; source "${ENV_FILE}"; set +a
  fi

  # Runs every time the container starts
  if [ -z "${GITHUB_TOKEN:-}" ]; then
    warn "GITHUB_TOKEN not set — skipping auth"
    warn "Run 'bw unlock' on host or set it in .devcontainer/.env"
    exit 0
  fi

  # gh: GITHUB_TOKEN in env is sufficient — no login needed
  if timeout 10 gh auth status 2>&1; then
    ok "gh authenticated (via GITHUB_TOKEN env)"
  else
    warn "gh auth status failed (non-fatal)"
  fi

  # docker: override credsStore to avoid host's wincred/desktop helper
  mkdir -p ${HOME}/.docker
  echo '{}' > ${HOME}/.docker/config.json

  if echo "${GITHUB_TOKEN}" | timeout 10 docker login ghcr.io -u MateoSegura --password-stdin 2>&1; then
    ok "ghcr.io authenticated"
  else
    warn "ghcr.io auth failed (non-fatal)"
  fi

  # ── K3s kubeconfig + SSH tunnel ──────────────────────────────────────────
  KUBECONFIG_SCRIPT="${WORKSPACE}/cloud/oracle/scripts/setup-kubeconfig.sh"
  if [ -f "${KUBECONFIG_SCRIPT}" ] && [ -n "${OCI_COMPARTMENT_OCID:-}" ]; then
    if bash "${KUBECONFIG_SCRIPT}"; then
      ok "K3s access configured (kubeconfig + tunnel)"
    else
      warn "K3s setup failed (non-fatal) — run: bash cloud/oracle/scripts/setup-kubeconfig.sh"
    fi
  else
    info "Skipping K3s setup — OCI_COMPARTMENT_OCID not set or script missing"
  fi

  ok "Ready"
}

# ── dispatch ──────────────────────────────────────────────────────────────────
case "${1:-}" in
  build)        cmd_build       ;;
  push)         cmd_push        ;;
  create)       cmd_create      ;;
  start)        cmd_start       ;;
  post-create)  cmd_post_create ;;
  post-start)   cmd_post_start  ;;
  *)            usage           ;;
esac
