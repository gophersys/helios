#!/usr/bin/env bash
#
# ctl.sh — control script for the base image and its devcontainer lifecycle.
#
# Host verbs build/push/pull/inspect the image:
#   ghcr.io/gophersys/base
# Container verbs run inside the container, wired from base/devcontainer.json:
#   - post-create   install the latest Claude Code + wire the `c` alias
#
# Multi-arch policy:
#   - build             native single-arch (fast dev loop)
#   - build-multi-arch  explicit buildx multi-arch build, --load=false (no push)
#   - push              ENFORCED multi-arch via buildx --push
#
# Usage: ./ctl.sh <command> [args...]
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Tolerant: post-create runs inside the container, where the bind-mounted repo
# can trip git's dubious-ownership guard (host uid != container uid). Fall back
# to PROJECT_ROOT so the script never aborts at startup — REPO_ROOT is advisory.
REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel 2>/dev/null || printf '%s' "$PROJECT_ROOT")"
export REPO_ROOT

IMAGE_NAME="base"
IMAGE_REF="ghcr.io/gophersys/${IMAGE_NAME}:latest"
MULTI_ARCH_PLATFORMS="linux/amd64,linux/arm64"

# Long-lived devcontainer used by the `up`/`exec`/`shell`/`down` verbs. Overridable so a
# host can run several side by side. The workspace mounted at /workspace is the *consuming*
# repo (the superproject that vendors this .devcontainer submodule), not the submodule itself —
# so /workspace/tools, /workspace/libs, etc. resolve. Falls back to REPO_ROOT when standalone.
CONTAINER_NAME="${DEVCONTAINER_NAME:-${IMAGE_NAME}-devcontainer}"
WORKSPACE_HOST="$(git -C "$PROJECT_ROOT" rev-parse --show-superproject-working-tree 2>/dev/null || true)"
[[ -z "$WORKSPACE_HOST" ]] && WORKSPACE_HOST="$REPO_ROOT"
export WORKSPACE_HOST

# -------- logging --------
function log_info()  { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()  { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error() { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }

# -------- tool gate --------
function require_cmd() {
  local missing=()
  local cmd
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "missing required tool(s): ${missing[*]}"
    exit 127
  fi
}

function require_buildx_and_multi_arch() {
  require_cmd docker
  if ! docker buildx version >/dev/null 2>&1; then
    log_error "docker buildx is not installed — multi-arch push is mandatory"
    exit 127
  fi
  if ! docker buildx inspect >/dev/null 2>&1; then
    log_error "no active buildx builder — run: docker buildx create --use --name gophersys"
    exit 1
  fi
  local platforms
  platforms="$(docker buildx inspect --bootstrap 2>/dev/null | awk -F': ' '/^Platforms/ {print $2}' | head -1)"
  if [[ -z "$platforms" ]]; then
    log_error "buildx builder reports no platforms; cannot enforce multi-arch"
    exit 1
  fi
  local p
  local -a _platforms
  IFS=',' read -r -a _platforms <<< "$MULTI_ARCH_PLATFORMS"
  for p in "${_platforms[@]}"; do
    if ! printf '%s' "$platforms" | grep -q -- "$p"; then
      log_error "buildx builder missing required platform: $p"
      log_error "current builder platforms: $platforms"
      log_error "enable via QEMU: docker run --privileged --rm tonistiigi/binfmt --install all"
      exit 1
    fi
  done
}

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

# -------- commands --------
function cmd_build() {
  require_cmd docker
  log_info "building ${IMAGE_REF} (native single-arch)"
  docker build -t "${IMAGE_REF}" "$PROJECT_ROOT"
}

function cmd_build_multi_arch() {
  require_buildx_and_multi_arch
  log_info "buildx multi-arch (${MULTI_ARCH_PLATFORMS}) — no push"
  docker buildx build \
    --platform "${MULTI_ARCH_PLATFORMS}" \
    --tag "${IMAGE_REF}" \
    --load=false \
    "$PROJECT_ROOT"
}

function cmd_push() {
  require_buildx_and_multi_arch
  require_cmd git
  local short_sha image_ref_sha
  short_sha="$(git -C "$PROJECT_ROOT" rev-parse --short=7 HEAD 2>/dev/null || true)"
  if [[ -z "$short_sha" ]]; then
    log_error "cannot determine short SHA for tag; is $PROJECT_ROOT a git repo?"
    exit 1
  fi
  image_ref_sha="ghcr.io/gophersys/${IMAGE_NAME}:${short_sha}"
  log_info "buildx multi-arch (${MULTI_ARCH_PLATFORMS}) + push to ${IMAGE_REF} and ${image_ref_sha}"
  docker buildx build \
    --platform "${MULTI_ARCH_PLATFORMS}" \
    --tag "${IMAGE_REF}" \
    --tag "${image_ref_sha}" \
    --push \
    "$PROJECT_ROOT"
}

function cmd_pull() {
  require_cmd docker
  log_info "pulling ${IMAGE_REF}"
  docker pull "${IMAGE_REF}"
}

function cmd_inspect() {
  require_cmd docker
  docker image inspect "${IMAGE_REF}"
}

# -------- devcontainer lifecycle (run inside the container) --------

# post-create — runs once when the devcontainer is first created (wired from
# base/devcontainer.json's postCreateCommand). Installs the current Claude
# Code release fresh on every create — never pinned into the image — then
# wires the `c` launch alias.
function cmd_post_create() {
  require_cmd curl

  # Harness version pins — the consuming repo's manifest is the single source of truth (Eden
  # pins exact versions so agent runs are reproducible — ADR-0021). When present, install those
  # exact versions; otherwise fall back to latest so the shared base image still works for repos
  # that do not pin. `HARNESS_CHANNEL=latest` forces latest (the upgrade-testing path).
  local versions_file="${HARNESS_VERSIONS_FILE:-/workspace/harnesses/versions.env}"
  local channel="${HARNESS_CHANNEL:-pinned}"
  local claude_version="" omp_version="" codex_version=""
  if [[ "$channel" != "latest" && -f "$versions_file" ]]; then
    # shellcheck disable=SC1090
    source "$versions_file"
    claude_version="${CLAUDE_CODE_VERSION:-}"
    omp_version="${OMP_VERSION:-}"
    codex_version="${CODEX_VERSION:-}"
    log_info "post-create: pinning harnesses from ${versions_file} (claude=${claude_version:-latest} omp=${omp_version:-latest} codex=${codex_version:-latest})"
  else
    log_info "post-create: installing latest harnesses (no pin file / HARNESS_CHANNEL=latest)"
  fi

  log_info "post-create: installing Claude Code"
  # Official native installer — https://docs.claude.com/en/docs/claude-code/setup
  # The installer takes an optional explicit version argument.
  if [[ -n "$claude_version" ]]; then
    curl -fsSL https://claude.ai/install.sh | bash -s "$claude_version"
  else
    curl -fsSL https://claude.ai/install.sh | bash
  fi

  # The other two harnesses — Oh My Pi (`omp`) and Codex — are npm-global packages. omp's CLI
  # shebang is `#!/usr/bin/env bun`; `bun` is baked into the image so it resolves at runtime.
  # nvm is sourced for npm. All three harness CLIs are present so spawned agent pods (which
  # dogfood this image) can run any harness, and the adapter live tests have a real binary.
  log_info "post-create: installing the omp + codex harnesses via npm"
  export NVM_DIR="${HOME}/.nvm"
  # shellcheck disable=SC1091
  [[ -s "${NVM_DIR}/nvm.sh" ]] && . "${NVM_DIR}/nvm.sh"
  if command -v npm >/dev/null 2>&1; then
    local omp_pkg="@oh-my-pi/pi-coding-agent"; [[ -n "$omp_version" ]] && omp_pkg="${omp_pkg}@${omp_version}"
    local codex_pkg="@openai/codex";          [[ -n "$codex_version" ]] && codex_pkg="${codex_pkg}@${codex_version}"
    npm install -g "$omp_pkg"   || log_warn "post-create: omp install failed (continuing)"
    npm install -g "$codex_pkg" || log_warn "post-create: codex install failed (continuing)"
  else
    log_warn "post-create: npm not found — skipping omp/codex install"
  fi

  # hnslint — the repo-local structural HNS-1 linter (tools/hnslint). The repo is bind-mounted
  # at /workspace; install into GOPATH/bin (already on PATH). GOWORK=off so it builds standalone.
  local hnsdir="/workspace/tools/hnslint"
  if [[ -d "$hnsdir" ]] && command -v go >/dev/null 2>&1; then
    log_info "post-create: installing hnslint from ${hnsdir}"
    ( cd "$hnsdir" && GOWORK=off go install ./cmd/hnslint ) || log_warn "post-create: hnslint install failed (continuing)"
  else
    log_warn "post-create: ${hnsdir} or go not found — skipping hnslint install"
  fi

  # `c` drops straight into Claude Code, skipping the permission prompt.
  # Idempotent: only append if this container's zshrc lacks it.
  local zshrc="${HOME}/.zshrc"
  if ! grep -qs 'alias c=' "$zshrc" 2>/dev/null; then
    echo "alias c='claude --dangerously-skip-permissions'" >> "$zshrc"
    log_info "post-create: added 'c' alias to ${zshrc}"
  fi
  log_info "post-create: done — open a new shell and run 'c'"
}

# _require_running — guard for exec/shell.
function _require_running() {
  local state
  state="$(docker inspect -f '{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null || true)"
  if [[ "$state" != "running" ]]; then
    log_error "devcontainer '${CONTAINER_NAME}' is not running — run: bash ./ctl.sh up"
    exit 1
  fi
}

# up — start (or reuse) the long-lived devcontainer: the consuming repo bind-mounted at
# /workspace, the host Docker socket mounted (so the k3d/kind/docker integration + load lanes
# work from inside), running as the dev user. Idempotent (reuses a stopped/running container);
# then runs post-create once inside to install the harness CLIs + hnslint.
function cmd_up() {
  require_cmd docker
  if [[ ! -d "$WORKSPACE_HOST" ]]; then
    log_error "workspace not found: $WORKSPACE_HOST"; exit 1
  fi
  local state
  state="$(docker inspect -f '{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null || true)"
  if [[ "$state" == "running" ]]; then
    log_info "devcontainer '${CONTAINER_NAME}' already running"
  elif [[ -n "$state" ]]; then
    log_info "starting existing devcontainer '${CONTAINER_NAME}'"
    docker start "$CONTAINER_NAME" >/dev/null
  else
    log_info "creating devcontainer '${CONTAINER_NAME}' from ${IMAGE_REF}"
    log_info "  workspace: ${WORKSPACE_HOST} -> /workspace"
    # --init injects tini as PID 1 so orphaned children (the harness/gateway/vite/test processes
    # this container spawns and detaches) are REAPED. Without it PID 1 is `sleep infinity`, which
    # never wait()s, so defunct zombies accumulate for the container's whole lifetime — the same
    # reap obligation the agent-pod runtime sidecar owns as PID 1, applied to the dev substrate.
    docker run -d --name "$CONTAINER_NAME" \
      --init \
      --hostname "$CONTAINER_NAME" \
      -v "${WORKSPACE_HOST}:/workspace" \
      -v /var/run/docker.sock:/var/run/docker.sock \
      -w /workspace \
      --user dev \
      "$IMAGE_REF" sleep infinity >/dev/null
  fi
  # The mounted host socket is usually root-owned 0660 inside the container; let dev use it.
  docker exec -u root "$CONTAINER_NAME" sh -c 'chmod 666 /var/run/docker.sock 2>/dev/null || true'
  # host uid != container uid trips git's dubious-ownership guard on the bind mount.
  docker exec -u root "$CONTAINER_NAME" git config --system --add safe.directory '*' >/dev/null 2>&1 || true
  log_info "running post-create inside '${CONTAINER_NAME}'"
  docker exec -w /workspace "$CONTAINER_NAME" bash .devcontainer/base/ctl.sh post-create
  log_info "up: ready — 'bash ./ctl.sh exec -- <cmd>' or 'bash ./ctl.sh shell'"
}

# exec — run a command inside the running devcontainer as the dev user under a login zsh
# (/etc/zsh/zshenv sources nvm + the toolchain PATH, so node/omp/codex/go-tools all resolve).
# Accepts `exec -- <command line>` or `exec <command line>`.
function cmd_exec() {
  require_cmd docker
  [[ "${1:-}" == "--" ]] && shift
  if [[ $# -eq 0 ]]; then log_error "usage: bash ./ctl.sh exec [--] <command line>"; exit 2; fi
  _require_running
  local IFS=' '   # join argv with spaces (the script-global IFS is newline/tab)
  docker exec -w /workspace "$CONTAINER_NAME" zsh -lc "$*"
}

# shell — interactive zsh inside the devcontainer.
function cmd_shell() {
  require_cmd docker
  _require_running
  docker exec -it -w /workspace "$CONTAINER_NAME" zsh
}

# down — stop and remove the devcontainer. The bind-mounted repo on the host is untouched.
function cmd_down() {
  require_cmd docker
  if docker inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    log_info "removing devcontainer '${CONTAINER_NAME}'"
    docker rm -f "$CONTAINER_NAME" >/dev/null
  else
    log_info "devcontainer '${CONTAINER_NAME}' not present"
  fi
}

# -------- usage --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

Image: ${IMAGE_REF}

Commands:
  build              Build the image natively (single-arch, fast)
  build-multi-arch   buildx --platform ${MULTI_ARCH_PLATFORMS}, no push
  push               ENFORCED multi-arch buildx build + push
  pull               docker pull ${IMAGE_REF}
  inspect            docker image inspect ${IMAGE_REF}

Devcontainer lifecycle (self-managed, run from the host):
  up                 Start '${CONTAINER_NAME}' (repo->/workspace, docker socket), run post-create
  exec [--] <cmd>    Run a command inside the devcontainer (login zsh, full toolchain on PATH)
  shell              Interactive zsh inside the devcontainer
  down               Stop and remove the devcontainer

  post-create        (in container) install Claude Code + omp + codex + hnslint, 'c' alias
  help               Show this message
EOF
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    build)             cmd_build             "$@" ;;
    build-multi-arch)  cmd_build_multi_arch  "$@" ;;
    push)              cmd_push              "$@" ;;
    pull)              cmd_pull              "$@" ;;
    inspect)           cmd_inspect           "$@" ;;
    up)                cmd_up                "$@" ;;
    exec)              cmd_exec              "$@" ;;
    shell)             cmd_shell             "$@" ;;
    down)              cmd_down              "$@" ;;
    post-create)       cmd_post_create       "$@" ;;
    help|"")           usage ;;
    *)                 log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
