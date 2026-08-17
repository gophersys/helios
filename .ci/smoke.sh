#!/usr/bin/env bash
#
# .ci/smoke.sh — post-build smoke test for a single image.
#
# Dockerfiles in this repo deliberately do NOT run `bw --version`,
# `gh --version`, etc inside RUN steps: those binaries are built for the target,
# and they could not run while an image was cross-built under QEMU. This script
# re-introduces those checks as a post-build step that runs the already-built
# image. Nothing is cross-built any more.
#
# It prefers to run the image NATIVELY, for that same reason, and the platform
# resolver below is what makes that the default. On a developer host of another
# architecture it runs the sanctioned image under emulation instead — which is
# the only way to check the published image from that host at all, and it is
# slower rather than impossible.
#
# Usage: bash .ci/smoke.sh <image> [ref]
# where <image> ∈ {base, flutter, zephyr, zephyr-devbox, base-runner, cloud}
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
# 2 globals come out, never a printed value: BUILDX_PIN, and BUILDX_PIN_PROBLEM
# when there is no pin to use. Both are passed into the image, so the reason is
# printed next to the version it could not be compared against — an absent pin
# and an absent plugin are 2 different defects and a reader has to be able to
# tell which one fired.
#
# Every unreadable case ends with an empty BUILDX_PIN, so every one of them is a
# FAILURE inside the image. What this function owes the reader is an accurate
# SENTENCE. It used to answer "declares no ARG" whenever its single regex missed,
# which is a lie when the file plainly declares one — an indented ARG, a value
# written `v0.36.1`, or 2 candidate names each produced that same wrong sentence.
# The cloud image pins buildx in versions.env, the one home of the new
# mechanism, so its expected version is read THERE and never out of
# base/Dockerfile — the two families must be free to move apart.
function resolve_cloud_buildx_pin() {
  local file="$REPO_ROOT/versions.env"
  BUILDX_PIN=""
  BUILDX_PIN_PROBLEM=""
  local line="" status=0
  line="$(grep -E '^DOCKER_BUILDX_VERSION=' "$file")" || status=$?
  if [[ "$status" -ne 0 || -z "$line" ]]; then
    BUILDX_PIN_PROBLEM="versions.env declares no DOCKER_BUILDX_VERSION pin"
    return 0
  fi
  line="${line%%#*}"
  line="${line%"${line##*[![:space:]]}"}"
  BUILDX_PIN="${line#DOCKER_BUILDX_VERSION=}"
  BUILDX_PIN="${BUILDX_PIN#v}"
  if ! [[ "$BUILDX_PIN" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    BUILDX_PIN_PROBLEM="versions.env holds DOCKER_BUILDX_VERSION='${BUILDX_PIN}', which this check cannot read as <semver>"
    BUILDX_PIN=""
  fi
}

BUILDX_PIN=""
BUILDX_PIN_PROBLEM=""
function resolve_buildx_pin() {
  local file="$REPO_ROOT/base/Dockerfile"
  BUILDX_PIN=""
  BUILDX_PIN_PROBLEM=""

  # Leading whitespace is allowed, and so is a `v` on the value: both are shapes
  # a human writes, and neither is a reason to report the ARG as absent.
  local strict='^[[:space:]]*ARG[[:space:]]+[A-Za-z0-9_]*BUILDX[A-Za-z0-9_]*=v?[0-9]+\.[0-9]+\.[0-9]+'
  local loose='^[[:space:]]*ARG[[:space:]].*BUILDX'

  local matches="" status=0
  matches="$(grep -nE "$strict" "$file")" || status=$?
  if [[ "$status" -ne 0 || -z "$matches" ]]; then
    local loose_hits="" loose_status=0
    loose_hits="$(grep -nE "$loose" "$file")" || loose_status=$?
    if [[ "$loose_status" -eq 0 && -n "$loose_hits" ]]; then
      BUILDX_PIN_PROBLEM="base/Dockerfile DOES declare a buildx ARG, in a shape this check cannot read as <NAME>=<semver>: ${loose_hits//$'\n'/ ; }"
    else
      BUILDX_PIN_PROBLEM="base/Dockerfile declares no ARG whose name carries BUILDX"
    fi
    return 0
  fi

  # More than 1 candidate NAME is an ambiguity, not a pin. Taking the first match
  # silently answered with a decoy ARG that Docker never threads into the install.
  local -a candidate_names=()
  local name
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    candidate_names+=("$name")
  done < <(printf '%s\n' "$matches" | sed -E 's/^[0-9]+:[[:space:]]*ARG[[:space:]]+([A-Za-z0-9_]+)=.*/\1/' | sort -u)

  if [[ "${#candidate_names[@]}" -ne 1 ]]; then
    # Joined by hand: "${array[*]}" uses only the FIRST character of IFS, so
    # IFS=', ' would run the names together with no space after the comma.
    local joined="" candidate
    for candidate in "${candidate_names[@]}"; do
      joined="${joined:+${joined}, }${candidate}"
    done
    BUILDX_PIN_PROBLEM="base/Dockerfile declares ${#candidate_names[@]} ARGs that could each be the buildx pin (${joined}); this check will not choose between them"
    return 0
  fi

  # Docker uses the LAST declaration of a name, so the last one is the pin. The
  # first one was what this read before, which disagrees with the built image
  # whenever an ARG is re-declared further down.
  local last
  last="$(printf '%s\n' "$matches" | tail -n 1)"
  BUILDX_PIN="$(printf '%s' "$last" | sed -E 's/.*=v?([0-9]+\.[0-9]+\.[0-9]+).*/\1/')"
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
  echo "FAIL: no buildx pin could be read, so the ${BUILDX_INSTALLED} in this image is checked against nothing"
  echo "      ${BUILDX_PIN_PROBLEM}"
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

# The cloud image: the reduced base + the CI fold, one image for dev and CI.
# Self-contained on purpose — cloud DROPS tools the base smoke asserts
# (terraform, rustc, cargo), so appending to SMOKE_BASE would assert content
# the image is defined not to have. Runs as the image default user (dev),
# which is the user a devcontainer and an ARC pod that keeps the default get.
read -r -d '' SMOKE_CLOUD <<'EOF' || true
set -e
echo "--- cloud smoke ---"
uname -m
test "${GOPHERSYS_DEVCONTAINER}" = "cloud"
bw --version
gh --version
tailscale version
kubectl version --client
helm version --short
k9s version --short
go version
node --version
bun --version
python3 --version
uv --version
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
echo "--- the Go caches are OUT of the image (the 1.6 GB fix) ---"
# The gate-tools layer measured 2.06 GB in base because the RUN never removed
# the module and build caches. The cleanup is MANDATORY in cloud, and a green
# smoke on an image that silently kept them would bless the exact regression.
if [ -d "${GOPATH}/pkg/mod" ]; then echo "FAIL: ${GOPATH}/pkg/mod is still in the image"; exit 1; fi
if [ -d "${HOME}/.cache/go-build" ]; then echo "FAIL: ${HOME}/.cache/go-build is still in the image"; exit 1; fi
echo "go caches: absent, as built"
echo "--- docker cli-plugins ---"
# `docker buildx version` reaches no daemon, so this is a pure image-content
# check. The CI pod is the CLIENT of the remote arm64 builder, and base-runner
# measurably shipped without the plugin once.
if ! BUILDX_OUTPUT="$(docker buildx version 2>&1)"; then
  echo "FAIL: docker buildx does not run in this image"
  echo "      docker said: ${BUILDX_OUTPUT}"
  echo "      /usr/local/lib/docker/cli-plugins holds:"
  ls -1 /usr/local/lib/docker/cli-plugins || echo "      (there is no cli-plugins directory)"
  exit 1
fi
echo "${BUILDX_OUTPUT}"
# Drift guard. The version that RUNS must be the version versions.env pins.
# EXPECTED_BUILDX_VERSION is read out of versions.env by .ci/smoke.sh on the
# host and passed in here; an absent pin FAILS rather than skipping.
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
  echo "FAIL: no buildx pin could be read, so the ${BUILDX_INSTALLED} in this image is checked against nothing"
  echo "      ${BUILDX_PIN_PROBLEM}"
  exit 1
fi
if [ "${BUILDX_INSTALLED}" != "v${EXPECTED_BUILDX_VERSION}" ]; then
  echo "FAIL: buildx version drift: the image runs ${BUILDX_INSTALLED}, versions.env pins v${EXPECTED_BUILDX_VERSION}"
  exit 1
fi
echo "docker buildx: ${BUILDX_INSTALLED} matches the pin in versions.env"
echo "--- cloud components: debug, protocols, data clients, comforts ---"
dlv version
buf --version
grpcurl -version
psql --version
sqlite3 --version
redis-cli --version
bat --version
htop --version
btop --version
http --version
echo "--- the CI fold: runner + agents (inert files in a devcontainer) ---"
test -x /home/runner/run.sh
# The runner writes .runner and .credentials into /home/runner at
# registration. An unwritable directory means every pod fails to start, and
# it is invisible until a job is queued. The first runner build shipped that.
test -w /home/runner || { echo "FAIL: /home/runner is not writable"; exit 1; }
test -d /home/runner/externals
test -w /home/runner/_work
/home/runner/bin/Runner.Listener --version
# A pod that runs as root needs this or run.sh exits 1 in under a second.
[ "${RUNNER_ALLOW_RUNASROOT:-}" = "1" ] || { echo "FAIL: RUNNER_ALLOW_RUNASROOT is not 1; run.sh will refuse to start as root"; exit 1; }
# node must resolve in a NON-login shell: CI jobs run bash, not an interactive zsh.
command -v node >/dev/null || { echo "FAIL: node is not on PATH"; exit 1; }
echo "--- CI tooling + the harness bake (ADR-0021 pins) ---"
cictl help >/dev/null
command -v cictl
claude --version
omp --version
codex --version
EOF

case "$IMAGE" in
  base)    SCRIPT="$SMOKE_BASE" ;;
  cloud)   SCRIPT="$SMOKE_CLOUD" ;;
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
    log_error "valid images: base, base-runner, flutter, zephyr, zephyr-devbox, cloud"
    exit 2
    ;;
esac

REF="${REF_ARG:-ghcr.io/gophersys/${IMAGE}:latest}"

# A missing tool is a failure, never a skip.
require_cmd docker

# Every entry of the list must be sanctioned before 1 of them is chosen.
require_sanctioned_platforms

# A smoke test runs 1 image, so it names exactly 1 platform. When the sanctioned
# set holds several, the answer is to SELECT one — never to refuse to run.
#
# Refusing is what this block did first: it exited 1 whenever the list held more
# than 1 entry. Widening SANCTIONED_PLATFORMS to a second architecture — the 1
# edit this whole feature exists to make possible — would then have exited 1 at
# build-and-push.yml BEFORE asserting anything, turning the publish job red while
# checking nothing. .claude/rules/00-identity.md says "Widening it is 1 edit, and
# every path reads it". This path reads it now.
#
# The token for the second architecture is deliberately not written anywhere in
# this file: _ctl/tests/platform-policy.test.sh forbids it on the named build
# path, and a comment is not an exemption.
#
# The order, and why:
#   1. SMOKE_PLATFORM, when an operator names one deliberately. It must still be
#      in the list, so this is a choice WITHIN the guard and not a way around it.
#   2. the platform of the docker DAEMON, when the list holds it. This is the
#      premise of the whole script: the version checks the Dockerfiles dropped
#      could not run under emulation, so the native variant is the one to smoke.
#      The moment arm64 is sanctioned, the amd64 runner smokes amd64 and the
#      arm64 builder smokes arm64, each natively, with no further edit here.
#   3. the only entry, when the list holds exactly 1. This is today, and on a
#      developer host of another architecture it runs emulated.
#   4. otherwise FAIL, naming the list and the daemon. An unspecified platform is
#      how a smoke test silently asserts against the wrong architecture, which is
#      worse than not running.
#
# The daemon is read rather than `uname -m` because the daemon is what runs the
# container: on Docker Desktop the host is darwin and the daemon is linux.
SMOKE_PLATFORM_RESOLVED=""
function platform_is_listed() {
  [[ ",${IMAGE_PLATFORMS}," == *",${1},"* ]]
}
function resolve_smoke_platform() {
  local requested="${SMOKE_PLATFORM:-}"
  if [[ -n "$requested" ]]; then
    if ! platform_is_listed "$requested"; then
      log_error "SMOKE_PLATFORM=${requested} is not in IMAGE_PLATFORMS (${IMAGE_PLATFORMS})"
      log_error "a smoke test may choose among the sanctioned platforms; it may not add one"
      exit 1
    fi
    SMOKE_PLATFORM_RESOLVED="$requested"
    return 0
  fi

  local daemon="" status=0
  daemon="$(docker version --format '{{.Server.Os}}/{{.Server.Arch}}')" || status=$?
  if [[ "$status" -ne 0 || -z "$daemon" ]]; then
    log_error "cannot read the platform of the docker daemon (docker version exited ${status})"
    log_error "the daemon has to answer before this script can choose which image to run"
    exit 1
  fi

  if platform_is_listed "$daemon"; then
    SMOKE_PLATFORM_RESOLVED="$daemon"
    return 0
  fi
  if [[ "$IMAGE_PLATFORMS" != *,* ]]; then
    SMOKE_PLATFORM_RESOLVED="$IMAGE_PLATFORMS"
    log_info "the daemon is ${daemon} and the only sanctioned platform is ${SMOKE_PLATFORM_RESOLVED}; this run is emulated"
    return 0
  fi

  log_error "cannot choose a platform to smoke: the daemon is ${daemon}, which is not in IMAGE_PLATFORMS (${IMAGE_PLATFORMS})"
  log_error "name one with SMOKE_PLATFORM=<platform>; running an unnamed one would assert against an architecture nobody chose"
  exit 1
}
resolve_smoke_platform

# The image has to be here before anything is asserted about it, and here FOR THE
# PLATFORM that was chosen. A pull that failed and a tool that is absent both come
# back as a non-zero status, and they are not the same defect — so the one that
# happened is named.
#
# The architecture is read rather than assumed. `docker image inspect` answers
# about whichever variant the local store holds, so an image of one architecture
# satisfies a bare presence check, and `docker run --platform <the other one>`
# then fails with "pull access denied ... may require 'docker login'" — a
# message about credentials, for a defect that is an architecture. Measured.
#
# The inspect is quiet on purpose: its "No such image" is the expected answer on
# a cold host, and the branch below acts on it.
STORED_PLATFORM=""
if ! STORED_PLATFORM="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$REF" 2>/dev/null)"; then
  STORED_PLATFORM=""
fi
if [[ "$STORED_PLATFORM" != "$SMOKE_PLATFORM_RESOLVED" ]]; then
  if [[ -n "$STORED_PLATFORM" ]]; then
    log_info "${REF} is in the local store as ${STORED_PLATFORM}, and this run needs ${SMOKE_PLATFORM_RESOLVED}"
  else
    log_info "${REF} is not in the local image store"
  fi
  log_info "pulling ${REF} for ${SMOKE_PLATFORM_RESOLVED}"
  if ! docker pull --platform "$SMOKE_PLATFORM_RESOLVED" "$REF"; then
    log_error "cannot obtain ${REF} for ${SMOKE_PLATFORM_RESOLVED}${STORED_PLATFORM:+ — the local store holds ${STORED_PLATFORM} instead}"
    log_error "NOTHING was asserted about this image"
    exit 1
  fi
fi

# The pin the drift guard inside the image compares against, and the reason when
# there is none. Both travel into the image, so an unreadable pin is reported
# next to the version it could not be compared against. The cloud image reads
# its pin from versions.env — the one home of the new mechanism; every other
# image reads base/Dockerfile's ARG.
if [[ "$IMAGE" == "cloud" ]]; then
  resolve_cloud_buildx_pin
else
  resolve_buildx_pin
fi

# The R4 size gate, cloud only: the acceptance budget is <= 5.75 GB (decimal,
# the unit every census figure uses). It runs on the HOST against the loaded
# or pulled image, BEFORE the container smoke, and in CI this whole script
# runs before the push — so an oversize image never reaches a consumer.
#
# The budget did not move quietly. The first build measured 6,303,346,803
# bytes against the original 5.5 GB budget, the R4 levers were applied and
# measured one by one — in-layer npm/nvm cache hygiene −676.2 MB, the
# --no-install-recommends audit −0 (every install already carried the flag),
# stripping the 7 Go gate binaries −35.9 MB — and the measured floor with
# every tool kept came out at ~5.63–5.67 GB. Per R4 the decision then went
# to a human: Mateo decided on 2026-08-16 to keep every tool and set the
# budget to 5.75 GB. Above THIS budget the remaining levers are splitting
# build-essential out or dropping a tool — and either goes back to Mateo.
if [[ "$IMAGE" == "cloud" ]]; then
  CLOUD_SIZE_BUDGET_BYTES=5750000000
  CLOUD_SIZE_BYTES=""
  if ! CLOUD_SIZE_BYTES="$(docker image inspect --format '{{.Size}}' "$REF")"; then
    log_error "cannot read the size of ${REF}; the 5.75 GB gate cannot run, which is a FAILURE and not a skip"
    exit 1
  fi
  if [[ "$CLOUD_SIZE_BYTES" -gt "$CLOUD_SIZE_BUDGET_BYTES" ]]; then
    log_error "cloud size gate: ${REF} is ${CLOUD_SIZE_BYTES} bytes, over the ${CLOUD_SIZE_BUDGET_BYTES}-byte (5.75 GB) budget"
    log_error "the budget is acceptance metric 2 of the image program (risk R4); it does not move quietly"
    exit 1
  fi
  log_info "cloud size gate: ${CLOUD_SIZE_BYTES} bytes <= ${CLOUD_SIZE_BUDGET_BYTES} (5.75 GB budget)"
fi

RUN_ARGS=(
  --rm
  --platform "$SMOKE_PLATFORM_RESOLVED"
  -e "EXPECTED_BUILDX_VERSION=${BUILDX_PIN}"
  -e "BUILDX_PIN_PROBLEM=${BUILDX_PIN_PROBLEM}"
)
if [[ "$IMAGE" == "zephyr-devbox" ]]; then
  # The devbox image defaults to USER root (sshd entrypoint) and its
  # entrypoint execs any provided argv; force the dev user so the base
  # checks run in the same identity as the other images.
  RUN_ARGS+=(--user dev)
fi

log_info "running smoke test in ${REF} (${SMOKE_PLATFORM_RESOLVED})"
docker run "${RUN_ARGS[@]}" "${REF}" /usr/bin/zsh -c "${SCRIPT}"
log_info "smoke test passed for ${IMAGE}"
