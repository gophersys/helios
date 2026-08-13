#!/usr/bin/env bash
#
# .ci/smoke.sh — post-build smoke test for a single image.
#
# Dockerfiles in this repo deliberately do NOT run `bw --version`,
# `gh --version`, etc inside RUN steps: those binaries are built for the target,
# and they could not run while an image was cross-built under QEMU. This script
# re-introduces those checks as a post-build step that runs the already-built
# image. Nothing is emulated here, and nothing is cross-built any more either.
#
# Usage: bash .ci/smoke.sh <image> [ref]
# where <image> ∈ {base, flutter, zephyr, zephyr-devbox, base-runner}
# and [ref] is the exact image reference to test. The default is the :latest tag
# that build-and-push.yml has just built, which is what CI runs. Naming a ref is
# how an operator audits the SHA tag a cluster is actually running — and how a
# developer proves a check against an image that is not the local :latest.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Set before the source line, the way .ci/ctl.sh sets it: the git fallback in
# _ctl/lib.sh reads the wrong root when this repository is a submodule worktree.
REPO_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"

# The logging, the tool gate and the platform policy live in _ctl/lib.sh, 1 time
# only.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../_ctl/lib.sh
source "$PROJECT_ROOT/../_ctl/lib.sh"

IMAGE="${1:-}"
REF_ARG="${2:-}"

if [[ -z "$IMAGE" ]]; then
  log_error "usage: bash .ci/smoke.sh <image> [ref]"
  exit 2
fi

# The buildx version base/Dockerfile pins. Read the way ctl.sh reads the hadolint
# pin: the ARG is the single source of truth, and a version the image reports
# back that differs from it is drift.
#
# The ARG NAME is matched by pattern rather than spelled out. Every version ARG
# in this repository is <TOOL>_VERSION, and this asserts against whichever of
# those names carries buildx, so the check does not fail over a spelling.
#
# It prints nothing and still returns 0 when there is no such ARG. That case is
# reported from inside the image, next to the version it could not check, rather
# than here — an absent pin and an absent plugin are 2 different defects and a
# reader has to be able to tell which one fired.
function buildx_pin() {
  local file="$REPO_ROOT/base/Dockerfile"
  local line="" status=0
  line="$(grep -oE '^ARG [A-Z0-9_]*BUILDX[A-Z0-9_]*_VERSION=[0-9]+\.[0-9]+\.[0-9]+' "$file" | head -n 1)" || status=$?
  if [[ "$status" -ne 0 || -z "$line" ]]; then
    return 0
  fi
  printf '%s' "${line#*=}"
}

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
kubeconform -v
echo "--- docker cli-plugins ---"
# The runner image is the CLIENT of the arm64 builder: gophersys/infrastructure
# dials the Mac mini over SSH and drives `docker buildx build` from inside the
# job. The image shipped the compose plugin alone, so that documented step could
# not run at all, and nothing here said so.
#
# `docker buildx version` reaches no daemon, so this is a pure image-content
# check and it is meaningful in a plain `docker run` with no dind sidecar.
if ! BUILDX_OUTPUT="$(docker buildx version 2>&1)"; then
  echo "FAIL: docker buildx does not run in this image"
  echo "      docker said: ${BUILDX_OUTPUT}"
  echo "      /usr/local/lib/docker/cli-plugins holds:"
  ls -1 /usr/local/lib/docker/cli-plugins || echo "      (there is no cli-plugins directory)"
  exit 1
fi
echo "${BUILDX_OUTPUT}"
# Drift guard. The version that RUNS must be the version base/Dockerfile pins.
# EXPECTED_BUILDX_VERSION is read out of that ARG by .ci/smoke.sh on the host and
# passed in here. An image that passes its own assertion while shipping a version
# nobody declared is the defect this repository has already published once, so an
# absent pin FAILS rather than skipping.
BUILDX_INSTALLED=""
if BUILDX_TOKENS="$(printf '%s' "${BUILDX_OUTPUT}" | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+')"; then
  BUILDX_INSTALLED="$(printf '%s' "${BUILDX_TOKENS}" | head -n 1)"
fi
if [ -z "${BUILDX_INSTALLED}" ]; then
  echo "FAIL: docker buildx runs but reports no version this check can read"
  echo "      it printed: ${BUILDX_OUTPUT}"
  exit 1
fi
if [ -z "${EXPECTED_BUILDX_VERSION}" ]; then
  echo "FAIL: base/Dockerfile declares no ARG *BUILDX*_VERSION, so the ${BUILDX_INSTALLED} in this image is pinned by nothing"
  exit 1
fi
if [ "${BUILDX_INSTALLED}" != "v${EXPECTED_BUILDX_VERSION}" ]; then
  echo "FAIL: buildx version drift: the image runs ${BUILDX_INSTALLED}, base/Dockerfile pins v${EXPECTED_BUILDX_VERSION}"
  exit 1
fi
echo "docker buildx: ${BUILDX_INSTALLED} matches the pin in base/Dockerfile"
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
code-server --version
# Baked-in extension seed (the entrypoint copies it onto a fresh PVC home).
code-server --extensions-dir "${CODE_SERVER_SEED_EXTENSIONS}" --list-extensions \
  | grep llvm-vs-code-extensions.vscode-clangd \
  && echo "code-server clangd extension: ok"
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

# The `+ runner` layer adds only the GitHub Actions runner, so its smoke test is
# the parent's plus proof that the runner unpacked and is executable by `dev`.
read -r -d '' SMOKE_RUNNER <<'EOF' || true
echo "--- runner smoke ---"
test -x /home/runner/run.sh
# The runner writes .runner and .credentials into /home/runner at registration.
# Root ownership here makes every pod fail to start, and it is invisible until a
# job is queued. The first build of this layer shipped exactly that.
# This image runs as root, so ownership is not a question. What matters is that
# the runner directory is writable by the process that will use it.
test -w /home/runner || { echo "FAIL: /home/runner is not writable"; exit 1; }
test -d /home/runner/externals
test -w /home/runner/_work
/home/runner/bin/Runner.Listener --version
# Deliberately NOT asserted here: membership of the docker group. The pod grants
# it with securityContext.supplementalGroups, because the dind sidecar chooses the
# socket's gid. A `docker run` has no dind sidecar, so this script cannot test it
# at all. gophersys/infrastructure `ctl.sh verify-runner-image` tests it in the
# real pod shape, which is the only place the answer is meaningful.
# node must resolve in a NON-login shell: CI jobs run bash, not an interactive zsh.
command -v node >/dev/null || { echo "FAIL: node is not on PATH"; exit 1; }
# The runner refuses to start as root without this. The image runs as root, so a
# missing value means every pod exits 1 in under a second and no job ever runs.
[ "${RUNNER_ALLOW_RUNASROOT:-}" = "1" ] || { echo "FAIL: RUNNER_ALLOW_RUNASROOT is not 1; run.sh will refuse to start as root"; exit 1; }
# The review agent needs the Claude CLI. Its absence was found only when a review
# job failed with "missing required tool: claude".
command -v claude >/dev/null || { echo "FAIL: claude is not on PATH"; exit 1; }
echo "--- CI tooling ---"
cictl help >/dev/null
command -v cictl
EOF

case "$IMAGE" in
  base)    SCRIPT="$SMOKE_BASE" ;;
  base-runner) SCRIPT="${SMOKE_BASE}
${SMOKE_RUNNER}" ;;
  flutter) SCRIPT="${SMOKE_BASE}
${SMOKE_FLUTTER}" ;;
  zephyr)  SCRIPT="${SMOKE_BASE}
${SMOKE_ZEPHYR}" ;;
  zephyr-devbox) SCRIPT="${SMOKE_BASE}
${SMOKE_ZEPHYR}
${SMOKE_DEVBOX}" ;;
  *)
    log_error "unknown image: '$IMAGE'"
    log_error "valid images: base, base-runner, flutter, zephyr, zephyr-devbox"
    exit 2
    ;;
esac

REF="${REF_ARG:-ghcr.io/gophersys/${IMAGE}:latest}"

# A missing tool is a failure, never a skip.
require_cmd docker

# Name the platform explicitly. Every image of this repository publishes exactly
# the sanctioned set (_ctl/lib.sh), a CI runner is that architecture already so
# the flag is a no-op there, and on a developer host of another architecture it
# is the difference between testing the published image and not starting it.
require_sanctioned_platforms
if [[ "$IMAGE_PLATFORMS" == *,* ]]; then
  log_error "IMAGE_PLATFORMS holds more than 1 platform: ${IMAGE_PLATFORMS}"
  log_error "a smoke test runs 1 image, so it can name only 1 platform"
  exit 1
fi

# The image has to be here before anything is asserted about it. A pull that
# failed and a tool that is absent both come back as a non-zero status, and they
# are not the same defect — so the one that happened is named.
# The inspect is quiet on purpose: its "No such image" is the expected answer on
# a cold host, and the branch below acts on it.
if ! docker image inspect "$REF" >/dev/null 2>&1; then
  log_info "${REF} is not in the local image store; pulling it"
  if ! docker pull --platform "$IMAGE_PLATFORMS" "$REF"; then
    log_error "cannot obtain ${REF} for ${IMAGE_PLATFORMS} — NOTHING was asserted about this image"
    exit 1
  fi
fi

# The pin the drift guard inside the image compares against.
EXPECTED_BUILDX_VERSION="$(buildx_pin)"

RUN_ARGS=(--rm --platform "$IMAGE_PLATFORMS" -e "EXPECTED_BUILDX_VERSION=${EXPECTED_BUILDX_VERSION}")
if [[ "$IMAGE" == "zephyr-devbox" ]]; then
  # The devbox image defaults to USER root (sshd entrypoint) and its
  # entrypoint execs any provided argv; force the dev user so the base
  # checks run in the same identity as the other images.
  RUN_ARGS+=(--user dev)
fi

log_info "running smoke test in ${REF} (${IMAGE_PLATFORMS})"
docker run "${RUN_ARGS[@]}" "${REF}" /usr/bin/zsh -c "${SCRIPT}"
log_info "smoke test passed for ${IMAGE}"
