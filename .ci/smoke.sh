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
# where <image> ∈ {base, flutter, zephyr, zephyr-devbox}
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
bun --version
python3 --version
uv --version
rustc --version
cargo --version
nats --version
yq --version
echo "--- ADR-0020 gate toolchain (Kubernetes substrates + Go gate tools) ---"
k3d version
kind version
gofumpt --version
golangci-lint --version
govulncheck -version
gosec --version
gremlins --version
benchstat -h >/dev/null 2>&1 && echo "benchstat: ok"
gitleaks version
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

# zephyr-devbox adds the SSH + flash/debug stack on top of the zephyr smoke.
# Runs as the dev user (the image itself defaults to root for sshd); root
# steps go through the dev user's passwordless sudo. Throwaway host keys are
# generated so `sshd -t` can validate the full effective config, HostKey
# paths included.
read -r -d '' SMOKE_DEVBOX <<'EOF' || true
echo "--- zephyr-devbox smoke ---"
openocd --version
st-info --version
esptool version
picocom --help >/dev/null && echo "picocom: ok"
gdb-multiarch --version | head -n 1
clangd --version
# west extension commands + blob fetchers import these at runtime.
/opt/west-venv/bin/python -c "import requests, jsonschema" && echo "west venv deps: ok"
# `west espressif monitor` imports esptool + pyserial inside the west venv.
/opt/west-venv/bin/python -c "import esptool, serial" && echo "west venv esptool: ok"
for t in xtensa-espressif_esp32_zephyr-elf xtensa-espressif_esp32s2_zephyr-elf xtensa-espressif_esp32s3_zephyr-elf riscv64-zephyr-elf; do
  test -x "${ZEPHYR_SDK_INSTALL_DIR}/${t}/bin/${t}-gcc" && echo "sdk toolchain ${t}: ok"
done
sudo mkdir -p /etc/ssh/hostkeys
sudo ssh-keygen -q -N '' -t ed25519 -f /etc/ssh/hostkeys/ssh_host_ed25519_key
sudo ssh-keygen -q -N '' -t rsa -f /etc/ssh/hostkeys/ssh_host_rsa_key
sudo /usr/sbin/sshd -t
echo "sshd config: ok"
EOF

case "$IMAGE" in
  base)    SCRIPT="$SMOKE_BASE" ;;
  flutter) SCRIPT="${SMOKE_BASE}
${SMOKE_FLUTTER}" ;;
  zephyr)  SCRIPT="${SMOKE_BASE}
${SMOKE_ZEPHYR}" ;;
  zephyr-devbox) SCRIPT="${SMOKE_BASE}
${SMOKE_ZEPHYR}
${SMOKE_DEVBOX}" ;;
  *)
    log_error "unknown image: '$IMAGE'"
    log_error "valid images: base, flutter, zephyr, zephyr-devbox"
    exit 2
    ;;
esac

REF="ghcr.io/gophersys/${IMAGE}:latest"

log_info "running smoke test in ${REF}"
if [[ "$IMAGE" == "zephyr-devbox" ]]; then
  # The devbox image defaults to USER root (sshd entrypoint) and its
  # entrypoint execs any provided argv; force the dev user so the base
  # checks run in the same identity as the other images.
  docker run --rm --user dev "${REF}" /usr/bin/zsh -c "${SCRIPT}"
else
  docker run --rm "${REF}" /usr/bin/zsh -c "${SCRIPT}"
fi
log_info "smoke test passed for ${IMAGE}"
