#!/usr/bin/env bash
# .devcontainer/ctl.sh — dev container lifecycle management
#
# Host actions:   build | push | create | start
# Container actions (called by devcontainer.json):  post-create | post-start
#
# Prerequisites:
#   build/push    docker (Desktop or CLI)
#   create/start  @devcontainers/cli  →  npm install -g @devcontainers/cli
#   create/start  .devcontainer/.env   →  copy .env.example, fill in values

set -euo pipefail

IMAGE="ghcr.io/mateosegura/dev-env:latest"
PLATFORM="linux/amd64"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

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
    push          Authenticate via .env token and push to ghcr.io
    create        Create and start the devcontainer (.env loaded via --env-file)
    start         Open a shell in the running container

  Container lifecycle (called by devcontainer.json):
    post-create   Set up OCI config, SSH keys, git-crypt unlock
    post-start    Authenticate gh and ghcr.io, setup kubeconfig

  Setup:
    cp .devcontainer/.env.example .devcontainer/.env
    # Fill in values, then run: .devcontainer/ctl.sh create

EOF
  exit 1
}

# Load .env and export vars (host-side only — container gets them via --env-file)
_load_env() {
  if [ ! -f "${ENV_FILE}" ]; then
    die "Missing .env — run: cp .devcontainer/.env.example .devcontainer/.env"
  fi
  set -a
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
  set +a
  [ -z "${GITHUB_TOKEN:-}" ] && die "GITHUB_TOKEN is empty in .env"
  [ -z "${IS_SANDBOX:-}" ]   && die "IS_SANDBOX is empty in .env (must be 1)"
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
  _load_env
  info "Authenticating with ghcr.io ..."
  echo "${GITHUB_TOKEN}" | docker login ghcr.io -u MateoSegura --password-stdin
  info "Pushing ${IMAGE} ..."
  docker push "${IMAGE}"
  ok "Push complete — ${IMAGE}"
}

cmd_create() {
  command -v devcontainer > /dev/null 2>&1 \
    || die "devcontainer CLI not found — run: npm install -g @devcontainers/cli"
  _load_env
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

  # ── OCI CLI configuration ──────────────────────────────────────────────────
  if [ -n "${OCI_TENANCY_OCID:-}" ] && [ -n "${OCI_USER_OCID:-}" ]; then
    mkdir -p /root/.oci
    local key_dest="/root/.oci/oci_api_key.pem"

    if [ -n "${OCI_PRIVATE_KEY_B64:-}" ]; then
      echo "${OCI_PRIVATE_KEY_B64}" | base64 -d > "${key_dest}"
      chmod 600 "${key_dest}"
      ok "OCI API key written from OCI_PRIVATE_KEY_B64"
    elif [ -f "${WORKSPACE}/.devcontainer/oci_api_key.pem" ]; then
      cp "${WORKSPACE}/.devcontainer/oci_api_key.pem" "${key_dest}"
      chmod 600 "${key_dest}"
      ok "OCI API key deployed from .devcontainer/oci_api_key.pem"
    else
      warn "No OCI API key found — set OCI_PRIVATE_KEY_B64 in .env or place oci_api_key.pem in .devcontainer/"
    fi

    cat > /root/.oci/config <<EOF
[DEFAULT]
user=${OCI_USER_OCID}
fingerprint=${OCI_FINGERPRINT:-}
tenancy=${OCI_TENANCY_OCID}
region=${OCI_REGION:-us-phoenix-1}
key_file=/root/.oci/oci_api_key.pem
EOF
    chmod 600 /root/.oci/config
    ok "OCI config written (~/.oci/config)"
  else
    warn "OCI_TENANCY_OCID / OCI_USER_OCID not set — skipping OCI config"
    info "Set OCI_* vars in .devcontainer/.env to enable OCI CLI"
  fi

  # ── SSH key for infrastructure access ────────────────────────────────────
  if [ -n "${SSH_PRIVATE_KEY_B64:-}" ]; then
    mkdir -p /root/.ssh
    chmod 700 /root/.ssh
    echo "${SSH_PRIVATE_KEY_B64}" | base64 -d > /root/.ssh/infra-bastion
    chmod 600 /root/.ssh/infra-bastion
    ssh-keygen -y -f /root/.ssh/infra-bastion > /root/.ssh/infra-bastion.pub 2>/dev/null
    chmod 644 /root/.ssh/infra-bastion.pub
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

  # Runs every time the container starts
  if [ -z "${GITHUB_TOKEN:-}" ]; then
    warn "GITHUB_TOKEN not set — skipping auth"
    warn "Set it in .devcontainer/.env and rebuild the container"
    exit 0
  fi

  # gh: GITHUB_TOKEN in env is sufficient — no login needed
  if timeout 10 gh auth status 2>&1; then
    ok "gh authenticated (via GITHUB_TOKEN env)"
  else
    warn "gh auth status failed (non-fatal)"
  fi

  # docker: override credsStore to avoid host's wincred/desktop helper
  mkdir -p /root/.docker
  echo '{}' > /root/.docker/config.json

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
