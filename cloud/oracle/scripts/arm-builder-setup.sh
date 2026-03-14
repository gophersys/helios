#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# arm-builder-setup.sh — One-time setup for transparent remote ARM builds
#
# Run this once on any dev machine. After setup:
#   docker-arm build -t myapp:latest .
# auto-starts the AWS ARM builder, builds natively, and returns.
#
# What it does:
#   1. Installs the "docker-arm" wrapper and "arm-builder" symlink
#   2. Adds shell aliases for convenience
#
# Requirements:
#   - AWS CLI configured (~/.aws/credentials) or AWS_ACCESS_KEY_ID set
#   - SSH key at ~/.ssh/arm-builder
#   - arm-builder EC2 instance exists (created by Terraform)
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARM_BUILDER="${SCRIPT_DIR}/arm-builder.sh"
WRAPPER_DIR="${HOME}/.local/bin"

# ── Verify prerequisites ────────────────────────────────────────────────────

if ! command -v aws >/dev/null 2>&1; then
    echo "⚠ AWS CLI not installed — ARM builder setup skipped" >&2
    echo "  Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html" >&2
    exit 0
fi

echo "▸ Setting up transparent ARM builder..."

# ── 1. Symlink arm-builder to PATH ───────────────────────────────────────────

mkdir -p "${WRAPPER_DIR}"
ln -sf "${ARM_BUILDER}" "${WRAPPER_DIR}/arm-builder"
echo "  ✓ arm-builder linked to ${WRAPPER_DIR}/"

# ── 2. Create docker-arm wrapper ─────────────────────────────────────────────

cat > "${WRAPPER_DIR}/docker-arm" <<'ARMWRAPPER'
#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# docker-arm — Build ARM64 containers on the remote AWS builder
#
# Usage (same as docker buildx build, but on remote ARM):
#   docker-arm build -t myapp:latest .
#   docker-arm build --push -t ghcr.io/org/img:tag .
#
# Automatically starts the builder if stopped (~20s resume).
###############################################################################

# Find arm-builder.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARM_BUILDER="${SCRIPT_DIR}/arm-builder"

if [[ ! -x "${ARM_BUILDER}" ]]; then
    echo "✗ arm-builder not found at ${ARM_BUILDER}" >&2
    exit 1
fi

# Ensure builder is running and get IP
echo "▸ Ensuring ARM builder is running..." >&2
BUILDER_IP=$("${ARM_BUILDER}" ensure 2>/dev/null)

if [[ -z "${BUILDER_IP}" || "${BUILDER_IP}" == "None" ]]; then
    echo "✗ Failed to start ARM builder" >&2
    exit 1
fi
echo "✓ ARM builder ready at ${BUILDER_IP}" >&2

# Inject --platform linux/arm64 if not already specified
HAS_PLATFORM=false
for arg in "$@"; do
    [[ "${arg}" == "--platform"* ]] && HAS_PLATFORM=true
done

ARGS=("$@")
if [[ "${HAS_PLATFORM}" == "false" && "${1:-}" == "build" ]]; then
    ARGS=("build" "--platform" "linux/arm64" "${@:2}")
fi

# Build on remote Docker via SSH
echo "▸ Building on ARM (${BUILDER_IP})..." >&2
DOCKER_HOST="ssh://ubuntu@${BUILDER_IP}" docker "${ARGS[@]}"
echo "✓ Build complete." >&2
ARMWRAPPER

chmod +x "${WRAPPER_DIR}/docker-arm"
echo "  ✓ docker-arm wrapper created"

# ── 3. Ensure ~/.local/bin is in PATH ─────────────────────────────────────────

SHELL_RC=""
if [[ -f "${HOME}/.zshrc" ]]; then
    SHELL_RC="${HOME}/.zshrc"
elif [[ -f "${HOME}/.bashrc" ]]; then
    SHELL_RC="${HOME}/.bashrc"
fi

if [[ -n "${SHELL_RC}" ]]; then
    if ! grep -q "# ARM builder PATH" "${SHELL_RC}" 2>/dev/null; then
        cat >> "${SHELL_RC}" <<'RCBLOCK'

# ARM builder PATH
export PATH="${HOME}/.local/bin:${PATH}"

# ARM builder aliases
alias arm-build='docker-arm build'
alias arm-up='arm-builder up'
alias arm-down='arm-builder down'
alias arm-status='arm-builder status'
alias arm-ssh='arm-builder ssh'
RCBLOCK
        echo "  ✓ PATH + aliases added to $(basename "${SHELL_RC}")"
    fi
fi

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "┌─────────────────────────────────────────────────────────────┐"
echo "│  ARM Builder Setup Complete (AWS)                           │"
echo "├─────────────────────────────────────────────────────────────┤"
echo "│                                                             │"
echo "│  Usage:                                                     │"
echo "│    docker-arm build -t myapp:latest .   # auto-starts       │"
echo "│    arm-builder up                       # manual start      │"
echo "│    arm-builder down                     # stop (\$0 compute) │"
echo "│    arm-builder status                   # check state       │"
echo "│                                                             │"
echo "│  ~20s resume from stopped. \$0 compute (free tier).          │"
echo "│  Auto-stops after 10 min idle.                              │"
echo "│                                                             │"
echo "│  Restart your shell or run: source ~/.zshrc                 │"
echo "└─────────────────────────────────────────────────────────────┘"
