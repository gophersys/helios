#!/usr/bin/env bash
#
# base/ctl.sh — control script for the base image and its devcontainer
# lifecycle:
#   ghcr.io/gophersys/base
#
# The image verbs build/push/verify-published/pull/inspect come from
# _ctl/lib.sh, where their bodies live 1 time only.
#
# This image adds the lifecycle verbs, which no other image has:
#   up / exec / shell / down   run on the host and drive a long-lived container
#   post-create                runs INSIDE the container, wired from
#                              base/devcontainer.json
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

IMAGE_NAME="base"

# shellcheck source-path=SCRIPTDIR
# shellcheck source=../_ctl/lib.sh
source "$PROJECT_ROOT/../_ctl/lib.sh"

# Long-lived devcontainer that the `up`/`exec`/`shell`/`down` verbs use. You can
# override the name, so a host can run several containers at the same time. The
# workspace at /workspace is the *consuming* repository (the superproject that
# vendors this .devcontainer submodule), not the submodule itself. Thus
# /workspace/libs and /workspace/harnesses resolve. It falls back to REPO_ROOT
# when this repository is standalone.
CONTAINER_NAME="${DEVCONTAINER_NAME:-${IMAGE_NAME}-devcontainer}"
WORKSPACE_HOST="$(git -C "$PROJECT_ROOT" rev-parse --show-superproject-working-tree 2>/dev/null || true)"
[[ -z "$WORKSPACE_HOST" ]] && WORKSPACE_HOST="$REPO_ROOT"
export WORKSPACE_HOST

IMAGE_USAGE_COMMANDS="

Devcontainer lifecycle (self-managed, run from the host):
  up                 Start '${CONTAINER_NAME}' (repo->/workspace, docker socket), run post-create
  exec [--] <cmd>    Run a command inside the devcontainer (login zsh, full toolchain on PATH)
  shell              Interactive zsh inside the devcontainer
  down               Stop and remove the devcontainer

  post-create        (in container) install Claude Code + omp + codex, 'c' alias"

# -------- devcontainer lifecycle (run inside the container) --------

# post-create — runs once when the devcontainer is first created (wired from
# base/devcontainer.json's postCreateCommand). Installs the current Claude
# Code release fresh on every create — never pinned into the image — then
# wires the `c` launch alias.
# post_create_die ends post-create with a named cause. Every install here used to
# warn and continue, so the container reported ready while a pinned harness or a
# gate tool was absent, and the failure surfaced much later somewhere else.
function post_create_die() { log_error "post-create: $*"; exit 1; }

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
    # These 2 also only warned and continued. A container that finishes
    # post-create with no omp is a container whose harness-conformance job fails
    # later, far from the cause. ADR-0021 pins these versions; a pin that did not
    # install is not a pin.
    npm install -g "$omp_pkg"   || post_create_die "omp ${omp_pkg} failed to install"
    npm install -g "$codex_pkg" || post_create_die "codex ${codex_pkg} failed to install"
  else
    post_create_die "npm is not on PATH, so omp and codex cannot be installed"
  fi

  # hnslint is NOT built here. It comes from `gophersys/hnslint`, and the base Dockerfile
  # installs it pinned by ARG HNSLINT_VERSION. post-create used to build it from the
  # bind-mounted `eden/tools/hnslint`, which gave a developer the working tree while CI got
  # nothing, and the 2 copies then drifted. To change the version, cut a release in
  # `gophersys/hnslint` and raise the pin.

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
# then runs post-create once inside to install the harness CLIs.
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

# -------- dispatcher --------
# The lifecycle verbs are this image's own. Every other verb, and the usage
# block, come from _ctl/lib.sh.
case "${1:-help}" in
  up)          shift; cmd_up          "$@" ;;
  exec)        shift; cmd_exec        "$@" ;;
  shell)       shift; cmd_shell       "$@" ;;
  down)        shift; cmd_down        "$@" ;;
  post-create) shift; cmd_post_create "$@" ;;
  *)           image_main "$@" ;;
esac
