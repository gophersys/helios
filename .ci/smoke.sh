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
# ============================================================================
# WHAT THIS FILE IS, AND WHAT .ci/image-checks.sh IS
# ============================================================================
#
# This file is the HOST driver. It knows where a pin LIVES (versions.env for the
# cloud family, the ARGs at the top of base/Dockerfile for the base family), it
# classifies every one of them, and it resolves the ones it says it asserts. The
# checks themselves are .ci/image-checks.sh, which this file sends to the
# container on stdin together with the fixtures the functional checks read.
#
# The split is the point. `<tool> --version` inside a container proves that the
# binary RUNS; it says nothing about WHICH version runs, so `gh --version` is
# green on gh 2.40 while versions.env pins 2.90. Only a COMPARISON sees that, and
# the comparison needs the pin, which exists on the host and not in the image.
#
# 3 things fail this script BEFORE a container is started, because each one would
# otherwise report an image as smoked while checking nothing:
#
#   - a pin of the home that carries no classification;
#   - a pin classified `asserted` that resolves to the empty string;
#   - a pin classified `asserted` with no command to read a version with.
#
# Usage: bash .ci/smoke.sh <image> [ref]
# where <image> ∈ {base, flutter, zephyr, zephyr-devbox, base-runner, cloud}
# and [ref] is the exact image reference to test. The default is the :latest tag
# that build-and-push.yml has just built, which is what CI runs. Naming a ref is
# how an operator audits the SHA tag a cluster is actually running — and how a
# developer proves a check against an image that is not the local :latest.
#
#   SMOKE_LIST_PINS=1 bash .ci/smoke.sh <image>
#
# prints `<PIN>|<class>` for every pin of that image's home and exits 0, with no
# docker command at all: a classification is a property of the FILES, so it is
# readable in the pull request gate, where a container is not.
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

# ---------------------------------------------------------------------------
# The 2 pin homes.
#
# They are free to move apart: the cloud family reads versions.env, the ONE home
# of the new mechanism, and the base family reads the ARGs at the top of
# base/Dockerfile. Each image is judged against the home that owns it.
# ---------------------------------------------------------------------------
CLOUD_PIN_HOME="versions.env"
BASE_PIN_HOME="base/Dockerfile"

# ---------------------------------------------------------------------------
# The classification, 1 row per pin:
#
#   <PIN>|<class>|<command that prints a version>|<extractor>
#
# The 3 classes are the whole taxonomy, and every pin of a home carries exactly
# 1 of them (_ctl/tests/version-coverage.test.sh holds that):
#
#   asserted           the smoke runs the command and compares what it reports
#   not-a-version      the pin is a digest, a channel or an untagged ref
#   not-in-this-image  the image does not install the tool
#
# The extractor is empty for the ~30 tools whose first `<digits>.<digits>` token
# IS the version. The 2 other readers are named in .ci/image-checks.sh, and each
# use below says why it is there.
# ---------------------------------------------------------------------------

read -r -d '' PIN_CLASSES_CLOUD <<'PIN_CLASS_TABLE' || true
ZSH_VERSION|asserted|zsh --version|prefix
NVM_VERSION|asserted|zsh -c "nvm --version"|
NODE_VERSION|asserted|node --version|
NPM_VERSION|asserted|npm --version|
PNPM_VERSION|asserted|COREPACK_HOME=/home/dev/.cache/node/corepack pnpm --version|
BUN_VERSION|asserted|bun --version|
PYTHON_PACKAGE|asserted|python3 --version|prefix
UV_VERSION|asserted|uv --version|
GO_VERSION|asserted|go version|
GOFUMPT_VERSION|asserted|gofumpt --version|
GOLANGCI_LINT_VERSION|asserted|golangci-lint --version|
GOVULNCHECK_VERSION|asserted|govulncheck -version|line:govulncheck
GOSEC_VERSION|asserted|go version -m ${GOPATH}/bin/gosec|line:mod
HNSLINT_VERSION|asserted|go version -m ${GOPATH}/bin/hnslint|line:mod
GREMLINS_VERSION|asserted|go version -m ${GOPATH}/bin/gremlins|line:mod
BENCHSTAT_REF|not-a-version||
DELVE_VERSION|asserted|dlv version|
YQ_VERSION|asserted|yq --version|
HADOLINT_VERSION|asserted|hadolint --version|
KUBECONFORM_VERSION|asserted|kubeconform -v|
GITLEAKS_VERSION|asserted|gitleaks version|
KUBECTL_VERSION|asserted|kubectl version --client|
HELM_VERSION|asserted|helm version --short|
K9S_VERSION|asserted|k9s version --short|
K3D_VERSION|asserted|k3d version|
KIND_VERSION|asserted|kind version|
TAILSCALE_VERSION|asserted|tailscale version|
BW_VERSION|asserted|bw --version|
GH_VERSION|asserted|gh --version|
NATS_VERSION|asserted|nats --version|
DOCKER_COMPOSE_VERSION|asserted|docker compose version|
DOCKER_COMPOSE_SHA256_X86_64|not-a-version||
DOCKER_COMPOSE_SHA256_AARCH64|not-a-version||
DOCKER_BUILDX_VERSION|asserted|docker buildx version|
DOCKER_BUILDX_SHA256_AMD64|not-a-version||
DOCKER_BUILDX_SHA256_ARM64|not-a-version||
BUF_VERSION|asserted|buf --version|
GRPCURL_VERSION|asserted|grpcurl -version|
RUNNER_VERSION|asserted|/home/runner/bin/Runner.Listener --version|line:Version:
CICTL_VERSION|asserted|go version -m /usr/local/bin/cictl|line:mod
CLAUDE_CODE_VERSION|asserted|claude --version|
OMP_VERSION|asserted|omp --version|
CODEX_VERSION|asserted|codex --version|
TERRAFORM_VERSION|not-in-this-image||
AWS_CLI_VERSION|not-in-this-image||
OCI_CLI_VERSION|not-in-this-image||
ANSIBLE_VERSION|not-in-this-image||
ANSIBLE_CORE_VERSION|not-in-this-image||
PIN_CLASS_TABLE

read -r -d '' PIN_CLASSES_BASE <<'PIN_CLASS_TABLE' || true
ZSH_VERSION|asserted|zsh --version|prefix
NVM_VERSION|asserted|zsh -c "nvm --version"|
NODE_VERSION|asserted|node --version|
NPM_VERSION|asserted|npm --version|
PNPM_VERSION|asserted|COREPACK_HOME=/home/dev/.cache/node/corepack pnpm --version|
BUN_VERSION|asserted|bun --version|
UV_VERSION|asserted|uv --version|
GO_VERSION|asserted|go version|
RUST_CHANNEL|not-a-version||
GOFUMPT_VERSION|asserted|gofumpt --version|
GOLANGCI_LINT_VERSION|asserted|golangci-lint --version|
GOVULNCHECK_VERSION|asserted|govulncheck -version|line:govulncheck
GOSEC_VERSION|asserted|go version -m ${GOPATH}/bin/gosec|line:mod
HNSLINT_VERSION|asserted|go version -m ${GOPATH}/bin/hnslint|line:mod
GREMLINS_VERSION|asserted|go version -m ${GOPATH}/bin/gremlins|line:mod
BENCHSTAT_REF|not-a-version||
YQ_VERSION|asserted|yq --version|
HADOLINT_VERSION|asserted|hadolint --version|
KUBECONFORM_VERSION|asserted|kubeconform -v|
GITLEAKS_VERSION|asserted|gitleaks version|
KUBECTL_VERSION|asserted|kubectl version --client|
HELM_VERSION|asserted|helm version --short|
K9S_VERSION|asserted|k9s version --short|
K3D_VERSION|asserted|k3d version|
KIND_VERSION|asserted|kind version|
TAILSCALE_VERSION|asserted|tailscale version|
BW_VERSION|asserted|bw --version|
GH_VERSION|asserted|gh --version|
NATS_VERSION|asserted|nats --version|
DOCKER_COMPOSE_VERSION|asserted|docker compose version|
DOCKER_BUILDX_VERSION|asserted|docker buildx version|
TERRAFORM_VERSION|asserted|terraform version|
AWS_CLI_VERSION|asserted|aws --version|
OCI_CLI_VERSION|asserted|oci --version|
ANSIBLE_CORE_VERSION|asserted|ansible --version|
ANSIBLE_VERSION|asserted|/home/dev/.local/share/uv/tools/ansible-core/bin/python -c "import importlib.metadata as m; print(m.version('ansible'))"|
PIN_CLASS_TABLE

# The functional groups .ci/image-checks.sh runs for each image, beyond the
# version comparison. An image with no list is refused: a smoke that ran the
# comparator alone would assert every version and exercise nothing.
function image_check_groups() {
  case "$1" in
    base)          printf 'content-base go-gate dockerfile-lint compose' ;;
    base-runner)   printf 'content-base content-runner go-gate dockerfile-lint compose' ;;
    flutter)       printf 'content-base content-flutter go-gate dockerfile-lint compose' ;;
    zephyr)        printf 'content-base content-zephyr go-gate dockerfile-lint compose' ;;
    zephyr-devbox) printf 'content-base content-zephyr content-devbox go-gate dockerfile-lint compose' ;;
    cloud)         printf 'content-cloud content-runner go-gate dockerfile-lint compose debugger protocols' ;;
    *)             printf '' ;;
  esac
}

case "$IMAGE" in
  cloud)
    PIN_HOME="$CLOUD_PIN_HOME"
    PIN_CLASSES="$PIN_CLASSES_CLOUD"
    ;;
  base|base-runner|flutter|zephyr|zephyr-devbox)
    PIN_HOME="$BASE_PIN_HOME"
    PIN_CLASSES="$PIN_CLASSES_BASE"
    ;;
  *)
    log_error "unknown image: '$IMAGE'"
    log_error "valid images: base, base-runner, flutter, zephyr, zephyr-devbox, cloud"
    exit 2
    ;;
esac

CHECK_GROUPS="$(image_check_groups "$IMAGE")"
if [[ -z "$CHECK_GROUPS" ]]; then
  log_error "no functional check group is declared for '${IMAGE}'"
  log_error "a smoke that compares versions and exercises nothing is not a smoke"
  exit 2
fi

# ---------------------------------------------------------------------------
# The readers.
# ---------------------------------------------------------------------------

# home_pin_names <home> — every pin the home declares, 1 per line, in file order.
#
# versions.env declares `NAME=value`. base/Dockerfile declares `ARG NAME=value`,
# and only the version-shaped names are pins: `*_VERSION`, `*_REF`, `*_CHANNEL`,
# the 3 suffixes dockerfile-args.test.sh governs. TARGETPLATFORM, USERNAME and
# USER_UID pin no tool, so no smoke test can assert them.
function home_pin_names() {
  local home="$1"
  case "$home" in
    "$CLOUD_PIN_HOME")
      awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/ { print $1 }' "$REPO_ROOT/$home" | awk '!seen[$0]++'
      ;;
    "$BASE_PIN_HOME")
      awk '
        /^[[:space:]]*ARG[[:space:]]+/ {
          split($2, parts, "=")
          if (parts[1] ~ /(_VERSION|_REF|_CHANNEL)$/) { print parts[1] }
        }
      ' "$REPO_ROOT/$home" | awk '!seen[$0]++'
      ;;
    *)
      log_error "no reader for pin home '${home}'"
      exit 1
      ;;
  esac
}

# resolve_pin <NAME> <home> — the value that home declares for that pin.
#
# 2 globals come out, never a printed value: PIN_VALUE, and PIN_PROBLEM when
# there is nothing to use. Every unreadable case ends with an EMPTY PIN_VALUE,
# and an empty value for an asserted pin stops this script before it starts a
# container — an image compared against an empty string is an image nobody
# checked, which is the result this repository has already published once.
#
# This 1 function replaced 2 that could each read only the buildx pin. They
# answered "declares no ARG" whenever their single regex missed, which is a lie
# when the file plainly declares one, so the shapes a human writes are read here:
# leading whitespace, a trailing `# comment`, and a `v` on the value.
PIN_VALUE=""
PIN_PROBLEM=""
function resolve_pin() {
  local name="$1" home="$2"
  local file="$REPO_ROOT/$home"
  local line="" status=0
  PIN_VALUE=""
  PIN_PROBLEM=""

  if [[ ! -f "$file" ]]; then
    PIN_PROBLEM="the pin home ${home} is not a file: ${file}"
    return 0
  fi

  case "$home" in
    "$CLOUD_PIN_HOME")
      line="$(grep -E "^${name}=" "$file")" || status=$?
      ;;
    "$BASE_PIN_HOME")
      # Docker uses the LAST declaration of a name, so the last one is the pin.
      # Taking the first disagrees with the built image whenever an ARG is
      # re-declared further down.
      line="$(grep -E "^[[:space:]]*ARG[[:space:]]+${name}=" "$file" | tail -n 1)" || status=$?
      ;;
    *)
      PIN_PROBLEM="no reader for pin home '${home}'"
      return 0
      ;;
  esac

  if [[ "$status" -ne 0 || -z "$line" ]]; then
    PIN_PROBLEM="${home} declares no ${name}"
    return 0
  fi

  line="${line%%#*}"
  line="${line%"${line##*[![:space:]]}"}"
  local assignment="${name}="
  PIN_VALUE="${line#*"$assignment"}"
  if [[ -z "$PIN_VALUE" ]]; then
    PIN_PROBLEM="${home} declares ${name} with an empty value"
  fi
}

# expected_version <raw pin value> — the version INSIDE the pin. Everything
# before the first digit goes: CICTL_VERSION is written `v0.1.0`, and
# PYTHON_PACKAGE is written `python3.12` because apt names a package rather than
# a version. Empty when the value holds no digit at all, which the caller reports.
function expected_version() {
  local raw="$1"
  printf '%s' "${raw#"${raw%%[0-9]*}"}"
}

# class_row <PIN> — the classification row for a pin, empty when it has none.
function class_row() {
  local name="$1" row
  while IFS= read -r row; do
    [[ "${row%%|*}" == "$name" ]] || continue
    printf '%s' "$row"
    return 0
  done <<< "$PIN_CLASSES"
  printf ''
}

# ---------------------------------------------------------------------------
# The listing. A classification is a property of the files, so this runs with no
# daemon at all and it is the seam the pull request gate reads.
# ---------------------------------------------------------------------------
if [[ "${SMOKE_LIST_PINS:-}" == "1" ]]; then
  while IFS= read -r pin; do
    [[ -z "$pin" ]] && continue
    row="$(class_row "$pin")"
    [[ -z "$row" ]] && continue
    row="${row#*|}"
    printf '%s|%s\n' "$pin" "${row%%|*}"
  done <<< "$(home_pin_names "$PIN_HOME")"
  exit 0
fi

# ---------------------------------------------------------------------------
# The assertion table, built BEFORE anything touches docker.
# ---------------------------------------------------------------------------
PIN_TABLE=""
UNCLASSIFIED=""
while IFS= read -r pin; do
  [[ -z "$pin" ]] && continue
  if [[ -z "$(class_row "$pin")" ]]; then
    UNCLASSIFIED="${UNCLASSIFIED:+${UNCLASSIFIED} }${pin}"
  fi
done <<< "$(home_pin_names "$PIN_HOME")"
if [[ -n "$UNCLASSIFIED" ]]; then
  log_error "these pins of ${PIN_HOME} carry no classification: ${UNCLASSIFIED}"
  log_error "assert each one in .ci/smoke.sh, or classify it not-a-version or not-in-this-image"
  log_error "a pin nothing compares against the image is a number in a file"
  exit 1
fi

while IFS='|' read -r pin class probe extractor; do
  [[ -z "$pin" ]] && continue
  [[ "$class" == "asserted" ]] || continue
  if [[ -z "$probe" ]]; then
    log_error "${pin} is classified asserted and names no command to read a version with"
    log_error "give it a command in the ${PIN_HOME} table of .ci/smoke.sh, or classify it not-a-version"
    exit 1
  fi
  resolve_pin "$pin" "$PIN_HOME"
  if [[ -z "$PIN_VALUE" ]]; then
    log_error "${pin} is classified asserted and resolves to the empty string: ${PIN_PROBLEM}"
    log_error "an empty expected version compares against nothing, so NOTHING was asserted about ${IMAGE}"
    exit 1
  fi
  expected="$(expected_version "$PIN_VALUE")"
  if [[ -z "$expected" ]]; then
    log_error "${pin} is classified asserted and its value '${PIN_VALUE}' holds no version to compare"
    exit 1
  fi
  PIN_TABLE="${PIN_TABLE:+${PIN_TABLE}
}${pin}|${expected}|${probe}|${extractor:-}"
done <<< "$PIN_CLASSES"

if [[ -z "$PIN_TABLE" ]]; then
  log_error "no pin of ${PIN_HOME} is classified asserted, so the guest would compare nothing"
  exit 1
fi

# ---------------------------------------------------------------------------
# The payload: the fixtures, the table, and .ci/image-checks.sh, in 1 stream.
#
# It travels on stdin and not in the argv because the guest also receives FILES,
# and an argv is not a place to put a file. The guest script is written out and
# exec'd rather than piped into bash, so a check that reads stdin cannot eat the
# rest of the script.
# ---------------------------------------------------------------------------
FIXTURES_DIR="$PROJECT_ROOT/fixtures"
PAYLOAD_EOF="GOPHERSYS_SMOKE_PAYLOAD_EOF"

FIXTURE_FILES=()
while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  FIXTURE_FILES+=("${file#"$FIXTURES_DIR/"}")
done < <(find "$FIXTURES_DIR" -type f | sort)

if [[ "${#FIXTURE_FILES[@]}" -eq 0 ]]; then
  log_error "no fixture found under ${FIXTURES_DIR} — the functional checks would have nothing to run on"
  exit 1
fi

# A file that carried the delimiter would end its own heredoc, and the rest of it
# would be read as shell. The check names the file, because that is the edit
# somebody has to make.
EMBEDDED_FILES=("$PROJECT_ROOT/image-checks.sh")
for relative in "${FIXTURE_FILES[@]}"; do
  EMBEDDED_FILES+=("$FIXTURES_DIR/$relative")
done
for file in "${EMBEDDED_FILES[@]}"; do
  if grep -qF -- "$PAYLOAD_EOF" "$file"; then
    log_error "the embedded file ${file} carries the heredoc delimiter ${PAYLOAD_EOF}"
    log_error "the payload would end there and the rest of the file would run as shell"
    exit 1
  fi
done

# payload_text — the stream the container reads on stdin.
#
# Every `$` below belongs to the GUEST shell and must reach it unexpanded, so
# the single quotes are the point rather than an oversight.
# shellcheck disable=SC2016
function payload_text() {
  local relative
  printf 'SMOKE_FIXTURE_DIR="$(mktemp -d)"\n'
  printf 'export SMOKE_FIXTURE_DIR\n'
  for relative in "${FIXTURE_FILES[@]}"; do
    printf 'mkdir -p "${SMOKE_FIXTURE_DIR}/%s"\n' "$(dirname "$relative")"
    printf 'cat > "${SMOKE_FIXTURE_DIR}/%s" <<'\''%s'\''\n' "$relative" "$PAYLOAD_EOF"
    cat "$FIXTURES_DIR/$relative"
    printf '%s\n' "$PAYLOAD_EOF"
  done
  # The table travels IN the payload and is exported from there, so no pin name
  # ever becomes an environment variable of the container: zsh sets ZSH_VERSION
  # itself, and a pin that collided with it would be compared against the shell.
  printf 'PIN_TABLE="$(cat <<'\''%s'\''\n' "$PAYLOAD_EOF"
  printf '%s\n' "$PIN_TABLE"
  printf '%s\n)"\n' "$PAYLOAD_EOF"
  printf 'export PIN_TABLE\n'
  printf 'SMOKE_CHECKS=%q\n' "$CHECK_GROUPS"
  printf 'export SMOKE_CHECKS\n'
  printf 'SMOKE_GUEST="$(mktemp)"\n'
  printf 'cat > "$SMOKE_GUEST" <<'\''%s'\''\n' "$PAYLOAD_EOF"
  cat "$PROJECT_ROOT/image-checks.sh"
  printf '%s\n' "$PAYLOAD_EOF"
  printf 'exec bash "$SMOKE_GUEST" < /dev/null\n'
}

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
  --interactive
  --platform "$SMOKE_PLATFORM_RESOLVED"
)
if [[ "$IMAGE" == "zephyr-devbox" ]]; then
  # The devbox image defaults to USER root (sshd entrypoint) and its
  # entrypoint execs any provided argv; force the dev user so the base
  # checks run in the same identity as the other images.
  RUN_ARGS+=(--user dev)
fi

log_info "running smoke test in ${REF} (${SMOKE_PLATFORM_RESOLVED})"
log_info "asserting $(printf '%s\n' "$PIN_TABLE" | wc -l | tr -d ' ') pins of ${PIN_HOME}; check groups: ${CHECK_GROUPS}"
docker run "${RUN_ARGS[@]}" "${REF}" bash -s <<< "$(payload_text)"
log_info "smoke test passed for ${IMAGE}"
