#!/usr/bin/env bash
#
# ctl.sh — repo-wide control for gophersys/.devcontainer
#
# Builds, pushes, lists, and validates every image under the repo root.
# Delegates per-image work to <name>/ctl.sh.
#
# Platform policy:
#   - `build`               the sanctioned platform, explicitly (fast dev loop)
#   - `push`                buildx + --push, guarded (see _ctl/lib.sh)
#   - `verify-published`    the published manifest must carry that same set
#
# Usage: ./ctl.sh <command> [args...]
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The logging, the tool gate and the push guard live in _ctl/lib.sh, 1 time
# only. This script owns the repo-wide verbs, which act on the whole set.
#
# This script does NOT call require_buildx_and_platforms, and that is
# deliberate. The guard enforces the platform list of 1 image, and an image is
# free to declare a measured narrower list. `push` delegates to the per-image
# ctl.sh, which calls the guard with its own list.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=_ctl/lib.sh
source "$PROJECT_ROOT/_ctl/lib.sh"

# Dependency order — parents first. `base` is the root of the dev-image
# family; `flutter` and `zephyr` both layer on top of `base`, and
# `zephyr-devbox` layers on top of `zephyr`.
#
# `base-runner` is the `+ runner` layer (directory `runner/`) applied to `base`.
# It is a CI image, not a devcontainer, so it has no devcontainer.json. One
# Dockerfile serves every parent — RUNNER_PARENT selects which — so adding
# `zephyr-runner` is a matrix entry, never a new directory.
#
# `cloud` is the successor image of the consolidation program (ledger #94):
# the reduced base + the CI fold, built FROM ubuntu directly. It is ADDITIVE
# today — no existing image depends on it and it depends on none — and the
# category images will layer on it in later steps of the migration.
BUILD_ORDER=(base base-runner flutter zephyr zephyr-devbox cloud)

# -------- helpers --------
# Image name -> source directory. These are 1:1 except for the `+ runner`
# variants: one directory (`runner/`) builds `<parent>-runner` for every parent,
# so `base-runner` resolves to `runner`. Keeping one directory is the point —
# a second runner Dockerfile would drift from the first.
function image_dir() {
  local name="$1"
  case "$name" in
    *-runner) printf '%s/runner' "$PROJECT_ROOT" ;;
    *)        printf '%s/%s' "$PROJECT_ROOT" "$name" ;;
  esac
}

# Image name -> the RUNNER_PARENT its ctl.sh expects (runner variants only).
function runner_parent() {
  printf '%s' "${1%-runner}"
}

function image_ctl() {
  local name="$1"
  shift
  local dir
  dir="$(image_dir "$name")"
  if [[ ! -x "$dir/ctl.sh" ]]; then
    log_error "missing or non-executable: $dir/ctl.sh"
    return 1
  fi
  # Runner variants share one directory, so the parent is passed in rather than
  # baked into the image's own ctl.sh.
  case "$name" in
    *-runner) (cd "$dir" && RUNNER_PARENT="$(runner_parent "$name")" bash ./ctl.sh "$@") ;;
    *)        (cd "$dir" && bash ./ctl.sh "$@") ;;
  esac
}

# -------- commands --------
function cmd_build() {
  local name="${1:-}"
  if [[ -z "$name" ]]; then
    log_error "usage: ./ctl.sh build <image>"
    exit 2
  fi
  shift
  image_ctl "$name" build "$@"
}

function cmd_push() {
  local name="${1:-}"
  if [[ -z "$name" ]]; then
    log_error "usage: ./ctl.sh push <image>"
    exit 2
  fi
  shift
  image_ctl "$name" push "$@"
}

function cmd_verify_published() {
  local name="${1:-}"
  if [[ -z "$name" ]]; then
    log_error "usage: ./ctl.sh verify-published <image> [tag]"
    exit 2
  fi
  shift
  image_ctl "$name" verify-published "$@"
}

function cmd_pull() {
  local name="${1:-}"
  if [[ -z "$name" ]]; then
    log_error "usage: ./ctl.sh pull <image>"
    exit 2
  fi
  shift
  image_ctl "$name" pull "$@"
}

function cmd_inspect() {
  local name="${1:-}"
  if [[ -z "$name" ]]; then
    log_error "usage: ./ctl.sh inspect <image>"
    exit 2
  fi
  shift
  image_ctl "$name" inspect "$@"
}

# base-currency — does the registry still hold the digest UBUNTU_BASE_REF pins?
# The body is require_base_image_current in _ctl/lib.sh, 1 time only. The nightly
# runs this verb, so a moved ubuntu digest turns the scheduled run red.
function cmd_base_currency() {
  require_base_image_current "$@"
}

function cmd_list() {
  local name ref
  printf '%-13s  %s\n' "IMAGE" "REF"
  printf '%-13s  %s\n' "-----" "---"
  for name in "${BUILD_ORDER[@]}"; do
    ref="ghcr.io/gophersys/${name}:latest"
    printf '%-13s  %s\n' "$name" "$ref"
  done
}

# The hadolint version base/Dockerfile pins. That ARG is the single source of
# truth for the whole repository: it is the hadolint the images ship, so it is
# the hadolint the gate must judge with.
function hadolint_pin() {
  local pin
  pin="$(grep -oE '^ARG HADOLINT_VERSION=[0-9]+\.[0-9]+\.[0-9]+' "$PROJECT_ROOT/base/Dockerfile" | head -1)"
  if [[ -z "$pin" ]]; then
    log_error "no 'ARG HADOLINT_VERSION=<semver>' in base/Dockerfile — the gate has no version to lint at"
    return 1
  fi
  printf '%s' "${pin#ARG HADOLINT_VERSION=}"
}

# hadolint_resolve <pin> — print HOW to reach that exact version, `host` or
# `container`. Its stdout is captured, so it logs nothing there; log_info writes
# to stdout in this repository and the caller would read the log line as the
# mode. It prints nothing at all and fails when neither route exists, because a
# Dockerfile that no linter read must not report as a Dockerfile that passed.
function hadolint_resolve() {
  local pin="$1" have=""
  if command -v hadolint >/dev/null 2>&1; then
    # 2>&1 rather than 2>/dev/null: a hadolint that cannot report its own version
    # is a hadolint whose output belongs on screen, not in the bin.
    have="$(hadolint --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)" || have=""
  fi
  if [[ "$have" == "$pin" ]]; then
    printf 'host'
    return 0
  fi
  if command -v docker >/dev/null 2>&1; then
    printf 'container'
    return 0
  fi
  log_error "hadolint ${pin} is required and this host has ${have:-none}, with no docker to run the pinned image"
  log_error "run this inside the devcontainer, which ships exactly ${pin}, or install that version"
  return 1
}

# hadolint_at_pin <mode> <pin> <dockerfile>
function hadolint_at_pin() {
  local mode="$1" pin="$2" file="$3"
  case "$mode" in
    host)      hadolint "$file" ;;
    container) docker run --rm -v "$(dirname "$file"):/w:ro" -w /w "hadolint/hadolint:v${pin}" hadolint "$(basename "$file")" ;;
    *)         log_error "hadolint_at_pin: unknown mode '${mode}'"; return 1 ;;
  esac
}

# Print every shell script in the repository, 1 per line. Matched by name AND by
# shebang: `_ctl/tests/stubs/docker` is a bash script with no extension, and a
# *.sh glob alone left it linted by nothing while this script claimed to lint
# every shell script.
function shell_scripts() {
  local file first
  while IFS= read -r file; do
    case "$file" in
      *.sh) printf '%s\n' "$file"; continue ;;
    esac
    # No pipe into grep here: with pipefail, grep -q closing the pipe early can
    # make a MATCH read as a failure, which would silently drop the file.
    first="$(head -n 1 "$file")"
    case "$first" in
      '#!'*bash*|'#!'*ksh*|'#!'*/sh|'#!'*'env sh') printf '%s\n' "$file" ;;
    esac
  done < <(find "$PROJECT_ROOT" -type f -not -path '*/.git/*' | sort)
}

# Test: run every hermetic test file under _ctl/tests/. A suite that finds no
# test file is a FAILURE and not a pass — a glob that matched nothing is the
# exact way a green result can mean nothing was checked.
function cmd_test() {
  local -a files=()
  local f
  for f in "$PROJECT_ROOT"/_ctl/tests/*.test.sh; do
    [[ -f "$f" ]] && files+=("$f")
  done
  if [[ ${#files[@]} -eq 0 ]]; then
    log_error "no test file matched _ctl/tests/*.test.sh — nothing ran, so nothing is proven"
    return 1
  fi

  local rc=0
  for f in "${files[@]}"; do
    log_info "test: ${f#"$PROJECT_ROOT"/}"
    bash "$f" || rc=1
  done

  if [[ $rc -eq 0 ]]; then
    log_info "test: OK (${#files[@]} files)"
  else
    log_error "test: FAILED"
  fi
  return "$rc"
}

# Validate: shellcheck every shell script, jq every project.json, hadolint every
# Dockerfile, and refuse Dockerfiles that hardcode a semver-shaped version inside
# a RUN line instead of threading an ARG.
function cmd_validate() {
  require_cmd shellcheck jq
  local rc=0
  local name dir script

  # Every shell script in the repository, not a hand-kept list. The list version
  # missed .ci/ctl.sh and .ci/smoke.sh, which no linter ran at all. -x follows
  # the source line, so each dispatcher is checked together with _ctl/lib.sh.
  local -a scripts=()
  while IFS= read -r script; do
    scripts+=("$script")
  done < <(shell_scripts)

  # A lint that matched nothing is not a clean lint. Without this, a glob or a
  # find that stopped matching leaves rc untouched and validate prints OK having
  # read no file at all.
  if [[ ${#scripts[@]} -eq 0 ]]; then
    log_error "no shell script found under ${PROJECT_ROOT} — nothing was linted, so nothing is proven"
    rc=1
  else
    for script in "${scripts[@]}"; do
      log_info "shellcheck: ${script#"$PROJECT_ROOT"/}"
      shellcheck -x -S style "$script" || rc=1
    done
  fi

  for name in "${BUILD_ORDER[@]}"; do
    dir="$(image_dir "$name")"

    log_info "jq parse: ${name}/project.json"
    jq empty "$dir/project.json" || rc=1

    if [[ ! -s "$dir/Dockerfile" ]]; then
      log_error "empty or missing Dockerfile: $dir/Dockerfile"
      rc=1
      continue
    fi
    if ! grep -qE '^[[:space:]]*FROM[[:space:]]+' "$dir/Dockerfile"; then
      log_error "Dockerfile has no FROM instruction: $dir/Dockerfile"
      rc=1
    fi

    # Reject semver literals inside RUN lines — every version MUST come
    # from an ARG at the top of the Dockerfile.
    local bad
    bad="$(grep -nE '^[[:space:]]*RUN[[:space:]].*=[0-9]+\.[0-9]+\.[0-9]+' "$dir/Dockerfile" || true)"
    if [[ -n "$bad" ]]; then
      log_error "${name}/Dockerfile: hardcoded version(s) in RUN lines — use ARGs"
      printf '%s\n' "$bad" >&2
      rc=1
    fi
  done

  log_info "jq parse: project.json"
  jq empty "$PROJECT_ROOT/project.json" || rc=1

  # hadolint's verdict depends on its version: 2.15.1 raises DL3064 and DL3066 on
  # Dockerfiles that 2.14.0 passes. A gate whose answer depends on what the
  # operator happened to install is not a gate, so it lints at the version
  # base/Dockerfile pins — the version the images themselves ship.
  # A missing tool is a FAILURE, never a skip. This once printed a warning and
  # returned OK, so `validate` reported success while linting no Dockerfile at
  # all — on a host without hadolint it checked nothing and said it passed.
  local hadolint_version="" hadolint_mode=""
  if ! hadolint_version="$(hadolint_pin)"; then
    rc=1
  elif ! hadolint_mode="$(hadolint_resolve "$hadolint_version")"; then
    rc=1
  else
    log_info "hadolint ${hadolint_version} (${hadolint_mode}), pinned by ARG HADOLINT_VERSION"
    for name in "${BUILD_ORDER[@]}"; do
      dir="$(image_dir "$name")"
      log_info "hadolint: ${name}/Dockerfile"
      hadolint_at_pin "$hadolint_mode" "$hadolint_version" "$dir/Dockerfile" || rc=1
    done
  fi

  if [[ $rc -eq 0 ]]; then
    log_info "validate: OK"
  else
    log_error "validate: FAILED"
  fi
  return "$rc"
}

# Propagate: delegate submodule pointer bumps to brain's propagate script.
function cmd_propagate() {
  local brain_root
  brain_root="$(git -C "$PROJECT_ROOT" rev-parse --show-superproject-working-tree 2>/dev/null || true)"
  if [[ -z "$brain_root" ]] || [[ ! -f "$brain_root/.claude/scripts/propagate.sh" ]]; then
    log_error "propagate must be run from within brain (brain/shared/.devcontainer/)"
    log_error "this script was invoked outside the brain orchestration context"
    exit 1
  fi
  bash "$brain_root/.claude/scripts/propagate.sh" ".devcontainer" "$@"
}

# Release: delegate to brain's release.sh. Same parent-context requirement.
function cmd_release() {
  local brain_root
  brain_root="$(git -C "$PROJECT_ROOT" rev-parse --show-superproject-working-tree 2>/dev/null || true)"
  if [[ -z "$brain_root" ]] || [[ ! -f "$brain_root/.claude/scripts/release.sh" ]]; then
    log_error "release must be run from within brain (brain/shared/.devcontainer/)"
    log_error "this script was invoked outside the brain orchestration context"
    exit 1
  fi
  bash "$brain_root/.claude/scripts/release.sh" ".devcontainer" "$@"
}

# -------- usage --------
function usage() {
  local order
  order="$(IFS=' '; printf '%s' "${BUILD_ORDER[*]}")"
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

Images (build order): ${order}

Per-image commands (take <image> as first arg):
  build <image>                    Build for the sanctioned platform (fast dev loop)
  push <image>                     GUARDED buildx build + push
  verify-published <image> [tag]   Assert the published manifest carries exactly
                                   the sanctioned platform set
  pull <image>                     docker pull ghcr.io/gophersys/<image>:latest
  inspect <image>                  docker image inspect ghcr.io/gophersys/<image>:latest

Repo-wide commands:
  base-currency [reference]        Assert the registry still holds the digest
                                   UBUNTU_BASE_REF pins (default ubuntu:24.04)
  list                             Print managed image refs
  validate                         shellcheck, jq, hadolint, ARG-discipline checks
  test                             Run every _ctl/tests/*.test.sh
  propagate                        Fan out submodule bumps (delegates to brain)
  release                          Cut a release (delegates to brain)
  help                             Show this message
EOF
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    build)              cmd_build             "$@" ;;
    push)               cmd_push              "$@" ;;
    verify-published)   cmd_verify_published  "$@" ;;
    pull)               cmd_pull              "$@" ;;
    inspect)            cmd_inspect           "$@" ;;
    base-currency)      cmd_base_currency     "$@" ;;
    list)               cmd_list              "$@" ;;
    validate)           cmd_validate          "$@" ;;
    test)               cmd_test              "$@" ;;
    propagate)          cmd_propagate         "$@" ;;
    release)            cmd_release           "$@" ;;
    help|"")            usage ;;
    *)                  log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
