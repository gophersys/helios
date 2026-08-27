#!/usr/bin/env bash
#
# .ci/affected.sh — does THIS commit change the inputs of THIS image?
#
# One home for the answer. Every job of build-and-push.yml asks it about its own
# image, and gates its build, its smoke, its push and its manifest read on the
# reply. A warm rebuild of the whole set measured ~35 minutes on every push to
# main, and most pushes to main touch 1 image or none of them. (That was
# measured when the set held 6; it holds 5 now, since base-runner was retired.
# The count is left out on purpose — images.yaml is the list, and a number
# restated in prose goes stale on its own.)
#
# THE PATH TABLE AND THE GRAPH ARE NOT HERE ANY MORE. This file carried an
# image_parent() and an image_own_paths() of its own, which made it 2 of the 6
# homes the dependency graph was declared in. Both come out of images.yaml now,
# through image_parent and image_input_paths in _ctl/lib.sh, so the answer this
# file gives and the jobs that ask for it are derived from one declaration.
#
#   bash .ci/affected.sh <image>
#       1 record on stdout, in the GITHUB_OUTPUT grammar:
#           build=true | build=false
#       and the reason on stderr, where the step log shows it.
#
#   Environment, all supplied by Actions:
#       GITHUB_EVENT_NAME   workflow_dispatch builds everything
#       GITHUB_REF          a tag push builds everything
#       GITHUB_EVENT_PATH   the push payload, read for `.before`
#
# ============================================================================
# WHAT AN UNBUILT IMAGE MEANS
# ============================================================================
#
# It means its `:latest` stays where the last build left it, and no `:<sha>` tag
# exists for this commit. That is the whole point — the image did not change, so
# republishing it would move `:latest` for no reason. The consequence a reader
# has to know: a `:<sha>` tag is NOT a promise that every image carries that sha.
#
# ============================================================================
# WHY A CHILD DECLARES ITS PARENT'S INPUTS
# ============================================================================
#
# mobile and embedded FROM an image this repository publishes. If
# base rebuilds and mobile does not, the published mobile is a layer on an
# image that no longer exists at that tag. So a child's input set CONTAINS its
# parent's, and `parent built => child builds` holds by construction —
# image_input_paths walks the `parent` edge of images.yaml to make it so.
#
# The other direction does not hold: mobile/ can change on its own, and then
# base publishes no `:<sha>` tag for this commit. That is why the workflow reads
# each parent job's `built` output and falls back to `:latest` for BASE_TAG —
# the child would otherwise FROM a tag that was never pushed.
#
# ============================================================================
# WHY THE FALLBACK IS ALWAYS "BUILD"
# ============================================================================
#
# Every condition this file cannot answer resolves to build. A false build costs
# minutes on a pool we own; a false skip ships a stale image and says nothing.
# The unanswerable conditions are: no previous commit in the payload (a new
# branch, a force push), and a previous commit the remote no longer has.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Set before the source line, the way .ci/smoke.sh sets it: the git fallback in
# _ctl/lib.sh reads the wrong root when this repository is a submodule worktree.
REPO_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"

# The logging and the tool gate live in _ctl/lib.sh, 1 time only.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../_ctl/lib.sh
source "$PROJECT_ROOT/../_ctl/lib.sh"

IMAGE="${1:-}"

if [[ -z "$IMAGE" ]]; then
  log_error "usage: bash .ci/affected.sh <image>"
  exit 2
fi

# A path that changes the build itself, rather than the content of 1 image:
# every workflow, and every file of this directory — the smoke driver, the guest
# checks, the fixtures, the provider copies and this file. A change there is a
# change to how every image is produced or judged, so every image builds.
BUILD_ALL_PATHS=(
  ".github/workflows/"
  ".ci/"
)

# matches_any <file> <prefix...> — a trailing `/` matches a directory, anything
# else is an exact path.
function matches_any() {
  local file="$1"
  shift
  local prefix
  for prefix in "$@"; do
    case "$prefix" in
      */) if [[ "$file" == "$prefix"* ]]; then return 0; fi ;;
      *)  if [[ "$file" == "$prefix" ]]; then return 0; fi ;;
    esac
  done
  return 1
}

# emit <true|false> <reason...> — the record on stdout, the reason on stderr.
# log_info writes to STDOUT in this repository, and this script's stdout is
# appended to GITHUB_OUTPUT, so a log line there would be read as an output key.
function emit() {
  local verdict="$1"
  shift
  printf 'affected: %s: build=%s — %s\n' "$IMAGE" "$verdict" "$*" >&2
  printf 'build=%s\n' "$verdict"
  exit 0
}

require_cmd git jq
require_active_image "$IMAGE" || exit 2

# The input set is read before any trigger is answered, so an image the manifest
# does not declare fails here rather than being quietly called unaffected.
#
# Through an assignment and not a process substitution: image_input_paths fails
# on an image it does not know, and inside `< <( )` that status kills a subshell
# the reader never sees, leaving an empty path set that matches nothing.
paths_text="$(image_input_paths "$IMAGE")" || exit 2
PATHS=()
while IFS= read -r path; do
  [[ -z "$path" ]] && continue
  PATHS+=("$path")
done <<< "$paths_text"

if [[ "${GITHUB_EVENT_NAME:-}" == "workflow_dispatch" ]]; then
  emit true "workflow_dispatch is the manual all-images build"
fi

if [[ "${GITHUB_REF:-}" == refs/tags/* ]]; then
  emit true "a tag push publishes the whole set at :${GITHUB_REF#refs/tags/}"
fi

BEFORE=""
if [[ -n "${GITHUB_EVENT_PATH:-}" && -f "${GITHUB_EVENT_PATH}" ]]; then
  BEFORE="$(jq -r '.before // ""' "$GITHUB_EVENT_PATH")"
fi

if [[ -z "$BEFORE" || "$BEFORE" =~ ^0+$ ]]; then
  emit true "the event carries no previous commit, so nothing can be compared"
fi

# actions/checkout takes 1 commit by default, so the commit this push started
# from is not in the local object store. Fetching it by sha costs 1 object;
# cloning the history would cost it on every job of every run.
if ! git -C "$REPO_ROOT" cat-file -e "${BEFORE}^{commit}" 2>/dev/null; then
  if ! git -C "$REPO_ROOT" fetch --no-tags --depth=1 origin "$BEFORE" >&2; then
    log_warn "the remote no longer has ${BEFORE} — a force push, or a rewritten history"
    emit true "the previous commit cannot be read, so nothing can be compared"
  fi
fi

diff_status=0
CHANGED=""
CHANGED="$(git -C "$REPO_ROOT" diff --name-only "$BEFORE" HEAD --)" || diff_status=$?
if [[ "$diff_status" -ne 0 ]]; then
  log_error "git diff ${BEFORE}..HEAD exited ${diff_status} with both commits present"
  log_error "this is a broken checkout, not an answer about ${IMAGE}"
  exit 1
fi

build_all_hits=""
image_hits=""
while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  if matches_any "$file" "${BUILD_ALL_PATHS[@]}"; then
    build_all_hits="${build_all_hits:+${build_all_hits} }${file}"
  fi
  if matches_any "$file" "${PATHS[@]}"; then
    image_hits="${image_hits:+${image_hits} }${file}"
  fi
done <<< "$CHANGED"

if [[ -n "$build_all_hits" ]]; then
  emit true "the build path changed: ${build_all_hits}"
fi

if [[ -n "$image_hits" ]]; then
  emit true "changed: ${image_hits}"
fi

emit false "no input of ${IMAGE} changed since ${BEFORE} (inputs: $(IFS=' '; printf '%s' "${PATHS[*]}"))"
