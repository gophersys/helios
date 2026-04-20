#!/usr/bin/env bash
#
# .ci/smoke.sh — post-build native-arch smoke test for a single image.
#
# Dockerfiles in this repo deliberately do NOT run `bw --version`,
# `gh --version`, etc inside RUN steps because those binaries are native and
# fail under QEMU cross-arch builds. This script re-introduces those checks
# as a post-build step that runs the already-built image on its NATIVE arch.
# QEMU is not involved here.
#
# Usage: bash .ci/smoke.sh <image>
# where <image> ∈ {base, flutter, zephyr}
#
set -Eeuo pipefail
IFS=$'\n\t'

IMAGE="${1:-}"

if [[ -z "$IMAGE" ]]; then
  printf '\033[0;31m[error]\033[0m usage: bash .ci/smoke.sh <image>\n' >&2
  exit 2
fi

# -------- logging --------
function log_info()  { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_error() { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }

# -------- cleanup --------
BG_PIDS=()
function on_exit() {
  local rc=$?
  local pid
  if [[ ${#BG_PIDS[@]} -gt 0 ]]; then
    for pid in "${BG_PIDS[@]}"; do
      kill "$pid" 2>/dev/null || true  # already exited — expected
    done
  fi
  return "$rc"
}
trap on_exit EXIT

# Common smoke-test body applied to every image. Checks both native binaries
# (bw, gh, tailscale, kubectl, helm, terraform, k9s, go, rustc, nats) and
# interpreter-based tooling (node, python3, uv). Any failure aborts the
# zsh subshell inside the container via `set -e`.
read -r -d '' SMOKE_BASE <<'EOF' || true
set -e
echo "--- base smoke ---"
uname -m
bw --version
gh --version
tailscale version
kubectl version --client
helm version --short
terraform version
k9s version --short
go version
node --version
python3 --version
uv --version
rustc --version
cargo --version
nats --version
yq --version
EOF

# Flutter adds flutter + adb checks on top of the base smoke.
read -r -d '' SMOKE_FLUTTER <<'EOF' || true
echo "--- flutter smoke ---"
flutter --version
adb --version
java -version
EOF

# Zephyr adds west on top of the base smoke.
read -r -d '' SMOKE_ZEPHYR <<'EOF' || true
echo "--- zephyr smoke ---"
west --version
EOF

case "$IMAGE" in
  base)    SCRIPT="$SMOKE_BASE" ;;
  flutter) SCRIPT="${SMOKE_BASE}
${SMOKE_FLUTTER}" ;;
  zephyr)  SCRIPT="${SMOKE_BASE}
${SMOKE_ZEPHYR}" ;;
  *)
    log_error "unknown image: '$IMAGE'"
    log_error "valid images: base, flutter, zephyr"
    exit 2
    ;;
esac

REF="ghcr.io/gophersys/${IMAGE}:latest"

log_info "running smoke test in ${REF}"
docker run --rm "${REF}" /usr/bin/zsh -c "${SCRIPT}"
log_info "smoke test passed for ${IMAGE}"
