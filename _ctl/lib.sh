#!/usr/bin/env bash
#
# _ctl/lib.sh — the shared ctl library for gophersys/.devcontainer.
#
# The body of every per-image verb lives here, 1 time only. Each per-image
# ctl.sh sets its metadata, sources this file, and dispatches into it. Before
# this file existed, the 5 per-image scripts each carried the same 140 lines,
# and 6 scripts each carried a copy of the push guard.
#
# The repo-root ctl.sh and .ci/ctl.sh source this file for the logging, the
# tool gate and the guard. Their own verbs act on the whole set of images, so
# they keep those verbs themselves.
#
# The pattern is the same one that gophersys/libs uses in go/_ctl/lib.sh. The
# directory name starts with an underscore, so Nx and Go ignore it. It is not
# an image directory.
#
# A sourcing script sets this metadata BEFORE the source line, because this
# file reads it while it loads:
#   PROJECT_ROOT           Required. The directory that holds the script.
#   IMAGE_NAME             Required for the image verbs. Example: flutter.
#   IMAGE_PLATFORMS        Optional. The default is SANCTIONED_PLATFORMS. Set it
#                          only to declare a measured narrower target, and give
#                          the measurement. Every entry must still be sanctioned.
#   IMAGE_BUILD_ARGS       Optional array. Extra arguments for docker build.
#
# This metadata is read at call time, so a script can set it after the source
# line, for example to use a value that this file computes:
#   IMAGE_USAGE_HEADER     Optional text. Extra lines below the Image: header.
#   IMAGE_USAGE_COMMANDS   Optional text. Extra lines below the command list.
#
# shellcheck shell=bash

set -Eeuo pipefail
IFS=$'\n\t'

: "${PROJECT_ROOT:?_ctl/lib.sh: the sourcing ctl.sh must set PROJECT_ROOT}"

# REPO_ROOT is advisory. A script that runs inside the container reads a
# bind-mounted repository, where a different uid trips the dubious-ownership
# guard of git. Fall back to PROJECT_ROOT, so no script stops at startup.
if [[ -z "${REPO_ROOT:-}" ]]; then
  REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel 2>/dev/null || printf '%s' "$PROJECT_ROOT")"
fi
export REPO_ROOT

# Every image of this repository is published under 1 registry namespace.
IMAGE_REGISTRY_NAMESPACE="ghcr.io/gophersys"

# The platforms a published image of this repository may carry. This list is the
# single source of truth: the guard, the build, the push and verify-published
# all read it, and nothing else declares a platform.
#
# 1 entry. No arm64 consumer can be verified for any image — gophersys/
# infrastructure docs/debt-register.md D42 — and the arm64 half that was
# published was an amd64 Ubuntu userland carrying aarch64 Go binaries, so it was
# mislabelled rather than native. Widen this list on the day a consumer exists,
# and not before.
SANCTIONED_PLATFORMS="linux/amd64"

# The platforms THIS image builds. Overridable, so an image can declare a
# measured narrower target the way runner/ctl.sh once did. Wider is not a
# choice: require_sanctioned_platforms refuses an entry outside the set above,
# and BOTH image_build and image_push call it. `build` needs it as much as
# `push` does, because `build` tags the official ref on the developer's host.
: "${IMAGE_PLATFORMS:=$SANCTIONED_PLATFORMS}"

if [[ -n "${IMAGE_NAME:-}" ]]; then
  IMAGE_REF="${IMAGE_REGISTRY_NAMESPACE}/${IMAGE_NAME}:latest"
fi

# Extra arguments for docker build. The runner layer threads its parent through
# BASE_IMAGE here. Declare the array only if the sourcing script did not.
if ! declare -p IMAGE_BUILD_ARGS >/dev/null 2>&1; then
  IMAGE_BUILD_ARGS=()
fi

# -------- logging --------
function log_info()  { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()  { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error() { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }

# -------- tripwire: the retired platform-list variable --------
# IMAGE_PLATFORMS was named MULTI_ARCH_* until arm64 was dropped. Both names now
# hold the same string, so a caller that still sets the old one gets the right
# platform by accident and nothing ever says the rename was missed. This fires
# at source time, on the name being set, whatever its value.
#
# The prefix match is why the retired name appears in the message and nowhere in
# this file: the same name check that finds a missed rename would otherwise find
# the tripwire itself.
_retired_platform_vars=("${!MULTI_ARCH@}")
if [[ ${#_retired_platform_vars[@]} -gt 0 ]]; then
  _retired_names="$(IFS=' '; printf '%s' "${_retired_platform_vars[*]}")"
  log_error "retired variable set: ${_retired_names} — rename it to IMAGE_PLATFORMS"
  log_error "it holds the same string IMAGE_PLATFORMS does, so nothing else would report the miss"
  exit 1
fi
unset _retired_platform_vars

# -------- tool gate --------
# A missing tool is a failure, never a skip.
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

# Guard: docker and docker buildx must be present. A verb that acts on the
# whole set of images calls this alone, because the platform list is not the
# same for every image.
function require_buildx() {
  require_cmd docker
  if ! docker buildx version >/dev/null 2>&1; then
    log_error "docker buildx is not installed — every publish of this repository goes through buildx"
    exit 127
  fi
}

# Guard: the platform list must be non-empty, and every entry must be in the
# sanctioned set. This is the condition that makes a re-added arm64 fail loudly
# at the guard instead of quietly restoring an emulated build, so it names the
# offending platform rather than only the list.
function require_sanctioned_platforms() {
  if [[ -z "${IMAGE_PLATFORMS:-}" ]]; then
    log_error "IMAGE_PLATFORMS is empty — the guard cannot enforce a platform"
    exit 1
  fi
  local p
  local -a _platforms
  IFS=',' read -r -a _platforms <<< "$IMAGE_PLATFORMS"
  for p in "${_platforms[@]}"; do
    if [[ ",${SANCTIONED_PLATFORMS}," != *",${p},"* ]]; then
      log_error "unsanctioned platform: ${p}"
      log_error "the sanctioned set is ${SANCTIONED_PLATFORMS}, declared in _ctl/lib.sh"
      log_error "widen SANCTIONED_PLATFORMS there, with a consumer you measured, before you publish another one"
      exit 1
    fi
  done
}

# Guard: the platform list must be sanctioned AND buildx must be able to build
# every entry on it. A verb that pushes MUST call this first.
#
# The guard fails closed in 5 conditions: a platform outside the sanctioned set,
# an empty platform list, buildx absent, no builder active, or the active
# builder unable to build 1 of the required platforms.
function require_buildx_and_platforms() {
  require_sanctioned_platforms
  require_buildx
  if ! docker buildx inspect >/dev/null 2>&1; then
    log_error "no active buildx builder — run: docker buildx create --use --name gophersys"
    exit 1
  fi
  local platforms
  platforms="$(docker buildx inspect --bootstrap 2>/dev/null | awk -F': ' '/^Platforms/ {print $2}' | head -1)"
  if [[ -z "$platforms" ]]; then
    log_error "buildx builder reports no platforms; cannot enforce a platform"
    exit 1
  fi
  local p
  local -a _platforms
  IFS=',' read -r -a _platforms <<< "$IMAGE_PLATFORMS"
  for p in "${_platforms[@]}"; do
    if ! printf '%s' "$platforms" | grep -q -- "$p"; then
      log_error "buildx builder missing required platform: $p"
      log_error "current builder platforms: $platforms"
      # Not a binfmt problem. An amd64 host builds linux/amd64 natively, and
      # Docker Desktop on Apple Silicon offers it too, so a builder that does not
      # list the 1 sanctioned platform did not bootstrap rather than lacking
      # emulation. The binfmt hint that used to be here was for the arm64 half.
      log_error "the builder did not bootstrap; recreate it: docker buildx create --use --name gophersys"
      exit 1
    fi
  done
}

# -------- no EXIT trap, and that is deliberate --------
# The 8 scripts of this repository each carried the same cleanup block: a
# BG_PIDS array, an on_exit function that killed the pids, and `trap on_exit
# EXIT`. Nothing ever added a pid to BG_PIDS, and no script starts a background
# job. The block killed nothing.
#
# It was not free. On bash 3.2, which is the bash of macOS and the bash that
# runs these scripts on a developer host, `$?` is 0 when the EXIT trap starts
# after the shell aborts on an unbound variable. Measured on this repository:
# with the trap, a script that aborts on an unbound variable exits 0. Without
# the trap, it exits 1. The block turned a fatal abort into a reported success.
#
# A script that starts a background job must clean up its own job, and it must
# not add an EXIT trap that returns a status.

# -------- image verbs --------
function image_build() {
  require_cmd docker
  # The same membership rule `push` uses. `build` tags the OFFICIAL ref, so an
  # unsanctioned platform here puts a mislabelled image on the developer's host
  # under the name the registry publishes — the exact defect this policy ends.
  require_sanctioned_platforms
  # --platform is explicit because a bare `docker build` builds for the HOST.
  # On an Apple Silicon host that is arm64, so the local image would not be the
  # image that gets published.
  if [[ "$IMAGE_PLATFORMS" == *,* ]]; then
    log_error "IMAGE_PLATFORMS holds more than 1 platform: ${IMAGE_PLATFORMS}"
    log_error "docker build produces 1 image; use push, which builds through buildx"
    exit 1
  fi
  log_info "building ${IMAGE_REF} (${IMAGE_PLATFORMS})"
  docker build \
    --platform "${IMAGE_PLATFORMS}" \
    "${IMAGE_BUILD_ARGS[@]+"${IMAGE_BUILD_ARGS[@]}"}" \
    -t "${IMAGE_REF}" \
    "$PROJECT_ROOT"
}

function image_push() {
  require_buildx_and_platforms
  require_cmd git
  local short_sha image_ref_sha
  short_sha="$(git -C "$PROJECT_ROOT" rev-parse --short=7 HEAD 2>/dev/null || true)"
  if [[ -z "$short_sha" ]]; then
    log_error "cannot determine short SHA for tag; is $PROJECT_ROOT a git repo?"
    exit 1
  fi
  image_ref_sha="${IMAGE_REGISTRY_NAMESPACE}/${IMAGE_NAME}:${short_sha}"
  log_info "buildx (${IMAGE_PLATFORMS}) + push to ${IMAGE_REF} and ${image_ref_sha}"
  docker buildx build \
    --platform "${IMAGE_PLATFORMS}" \
    "${IMAGE_BUILD_ARGS[@]+"${IMAGE_BUILD_ARGS[@]}"}" \
    --tag "${IMAGE_REF}" \
    --tag "${image_ref_sha}" \
    --push \
    "$PROJECT_ROOT"
}

# verify-published [tag] — read the manifest of a published tag and assert it
# carries EXACTLY the sanctioned set. A push declares a platform; this reads
# what the registry actually holds.
#
# An entry whose platform is unknown/unknown is an attestation manifest, not an
# image. buildx attaches 1 per variant on every push, so counting the entries
# reads a correct single-platform image as 2 platforms.
function image_verify_published() {
  require_buildx
  require_cmd jq
  local tag="${1:-latest}"
  local ref="${IMAGE_REGISTRY_NAMESPACE}/${IMAGE_NAME}:${tag}"
  log_info "reading the published manifest of ${ref}"

  # The 2 streams are kept apart on purpose. Merged, a client that writes a
  # warning to stderr on an otherwise successful read puts that warning inside
  # the JSON, and the parse fails for a reason that has nothing to do with the
  # manifest.
  local raw="" read_status=0 client_stderr
  client_stderr="$(mktemp)"
  raw="$(docker buildx imagetools inspect --raw "$ref" 2>"$client_stderr")" || read_status=$?
  if [[ "$read_status" -ne 0 ]]; then
    # The client's own words. A verdict about a manifest that was never read
    # describes a state nobody observed, which is how this repository once
    # documented a cluster it had not looked at.
    log_error "cannot read the manifest of ${ref}: the registry client exited ${read_status}"
    cat "$client_stderr" >&2
    rm -f "$client_stderr"
    exit 1
  fi
  rm -f "$client_stderr"

  local published="" parse_status=0
  published="$(printf '%s' "$raw" | jq -r '
    [ .manifests[]?
      | select(.platform != null)
      | select(.platform.os != "unknown" and .platform.architecture != "unknown")
      | .platform.os + "/" + .platform.architecture
        + (if .platform.variant then "/" + .platform.variant else "" end)
    ] | unique | join(",")
  ')" || parse_status=$?
  if [[ "$parse_status" -ne 0 ]]; then
    log_error "the manifest of ${ref} is not an image index this verb can read (jq exited ${parse_status})"
    printf '%s\n' "$raw" >&2
    exit 1
  fi

  local sanctioned
  sanctioned="$(jq -rn --arg s "$SANCTIONED_PLATFORMS" '$s | split(",") | unique | join(",")')"

  if [[ "$published" == "$sanctioned" ]]; then
    log_info "verify-published: ${ref} carries exactly ${published}"
    return 0
  fi

  log_error "verify-published: ${ref} does not carry the sanctioned platform set"
  log_error "  published:  ${published:-<the index declares no image platform>}"
  log_error "  sanctioned: ${sanctioned}"
  local p
  local -a _published
  IFS=',' read -r -a _published <<< "$published"
  for p in "${_published[@]+"${_published[@]}"}"; do
    if [[ ",${sanctioned}," != *",${p},"* ]]; then
      log_error "  published but not sanctioned: ${p}"
    fi
  done
  exit 1
}

function image_pull() {
  require_cmd docker
  log_info "pulling ${IMAGE_REF}"
  docker pull "${IMAGE_REF}"
}

function image_inspect() {
  require_cmd docker
  docker image inspect "${IMAGE_REF}"
}

# -------- usage --------
# This block is the specification of the per-image interface. An image that adds
# a verb adds its line through IMAGE_USAGE_COMMANDS.
function image_usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

Image: ${IMAGE_REF}${IMAGE_USAGE_HEADER:-}

Commands:
  build                   Build for ${IMAGE_PLATFORMS} (fast local loop)
  push                    GUARDED buildx build + push for ${IMAGE_PLATFORMS}
  verify-published [tag]  Assert the manifest published at [tag] (default latest)
                          carries exactly ${SANCTIONED_PLATFORMS}
  pull                    docker pull ${IMAGE_REF}
  inspect                 docker image inspect ${IMAGE_REF}${IMAGE_USAGE_COMMANDS:-}
  help                    Show this message
EOF
}

# -------- dispatcher --------
# A per-image ctl.sh that adds a verb handles that verb itself, then sends every
# other verb here.
function image_main() {
  : "${IMAGE_NAME:?_ctl/lib.sh: the sourcing ctl.sh must set IMAGE_NAME}"
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    build)             image_build             "$@" ;;
    push)              image_push              "$@" ;;
    verify-published)  image_verify_published  "$@" ;;
    pull)              image_pull              "$@" ;;
    inspect)           image_inspect           "$@" ;;
    help|"")           image_usage ;;
    *)                 log_error "unknown command: '$cmd'"; image_usage; exit 1 ;;
  esac
}
