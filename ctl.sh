#!/usr/bin/env bash
#
# ctl.sh — top-level infrastructure control
#
# Usage: ./ctl.sh <command> [args...]
#
# Delegates to sub-project ctl.sh files or to machines/scripts/* for work that
# spans the whole infrastructure repo (status, validation, machine-index
# regeneration, propagation to consuming project monorepos).
#
# Non-catalog verbs (not part of the generic verb catalog — justified here):
#   generate-index  Infrastructure-specific helper. Regenerates the
#                   monorepo-wide machine index by delegating to
#                   machines/scripts/generate-machine-index.sh. It is not
#                   a generic catalog verb because only this repo has a
#                   'machines' concept and its authoring flow needs an
#                   index refresh step after new-host / edit-identity.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC2034  # REPO_ROOT is scaffold for cmd_* to reference repo-wide paths
REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel)"

# -------- logging --------
function log_info()  { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()  { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error() { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }

# -------- tool gate --------
function require_cmd() {
  local missing=()
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "missing required tool(s): ${missing[*]}"
    exit 127
  fi
}

# -------- cleanup --------
# NOTE: the ${arr[@]+"${arr[@]}"} form below is deliberate. Under `set -u`,
# bash 3.2 (the macOS system bash) treats "${empty[@]}" as an unbound variable
# and aborts. CI runs bash 5 where it is fine, so the failure only ever showed
# up locally — after on_exit had already printed a success line.
TMPFS_MOUNTS=()
BG_PIDS=()
SENSITIVE_VARS=()

function on_exit() {
  local rc=$?
  for pid in ${BG_PIDS[@]+"${BG_PIDS[@]}"}; do
    kill "$pid" 2>/dev/null || true  # already exited — expected
  done
  for mnt in ${TMPFS_MOUNTS[@]+"${TMPFS_MOUNTS[@]}"}; do
    if mountpoint -q "$mnt" 2>/dev/null; then
      umount "$mnt" 2>/dev/null || log_warn "failed to unmount $mnt"
    fi
  done
  for var in ${SENSITIVE_VARS[@]+"${SENSITIVE_VARS[@]}"}; do
    unset "$var"
  done
  return "$rc"
}
trap on_exit EXIT

# -------- commands --------

function cmd_status() {
  log_info "infrastructure status"

  local machines_hosts=0 machines_templates=0 machines_roles=0
  if [[ -d "$PROJECT_ROOT/machines/hosts" ]]; then
    machines_hosts=$(find "$PROJECT_ROOT/machines/hosts" -mindepth 1 -maxdepth 1 -type d | wc -l)
  fi
  if [[ -d "$PROJECT_ROOT/machines/templates" ]]; then
    machines_templates=$(find "$PROJECT_ROOT/machines/templates" -mindepth 1 -maxdepth 1 -type d | wc -l)
  fi
  if [[ -d "$PROJECT_ROOT/machines/roles" ]]; then
    machines_roles=$(find "$PROJECT_ROOT/machines/roles" -mindepth 1 -maxdepth 1 -type d | wc -l)
  fi

  local clusters_instances=0 clusters_templates=0
  if [[ -d "$PROJECT_ROOT/clusters/instances" ]]; then
    clusters_instances=$(find "$PROJECT_ROOT/clusters/instances" -mindepth 1 -maxdepth 1 -type d | wc -l)
  fi
  if [[ -d "$PROJECT_ROOT/clusters/templates" ]]; then
    clusters_templates=$(find "$PROJECT_ROOT/clusters/templates" -mindepth 1 -maxdepth 1 -type d | wc -l)
  fi

  local providers=0
  if [[ -d "$PROJECT_ROOT/providers" ]]; then
    providers=$(find "$PROJECT_ROOT/providers" -mindepth 1 -maxdepth 1 -type d | wc -l)
  fi

  local platform_services=0
  if [[ -d "$PROJECT_ROOT/platform" ]]; then
    platform_services=$(find "$PROJECT_ROOT/platform" -mindepth 1 -maxdepth 1 -type d | wc -l)
  fi

  local charts=0
  if [[ -d "$PROJECT_ROOT/charts" ]]; then
    charts=$(find "$PROJECT_ROOT/charts" -mindepth 1 -maxdepth 1 -type d | wc -l)
  fi

  printf '  machines:  hosts=%s  templates=%s  roles=%s\n' \
    "$machines_hosts" "$machines_templates" "$machines_roles"
  printf '  clusters:  instances=%s  templates=%s\n' \
    "$clusters_instances" "$clusters_templates"
  printf '  providers: %s\n' "$providers"
  printf '  platform:  %s services\n' "$platform_services"
  printf '  charts:    %s\n' "$charts"
}

function cmd_validate() {
  log_info "validating infrastructure tree"
  local rc=0

  # project.json files must parse as JSON
  require_cmd jq shellcheck
  local pj_files=()
  while IFS= read -r f; do
    pj_files+=("$f")
  done < <(find "$PROJECT_ROOT" -name project.json -not -path '*/node_modules/*')

  local pj
  for pj in "${pj_files[@]}"; do
    if ! jq . "$pj" >/dev/null 2>&1; then
      log_error "invalid JSON: ${pj#"$PROJECT_ROOT"/}"
      rc=1
    fi
  done
  log_info "parsed ${#pj_files[@]} project.json file(s)"

  # Bash scripts must be syntactically valid
  local sh_files=()
  while IFS= read -r f; do
    sh_files+=("$f")
  done < <(find "$PROJECT_ROOT" -name '*.sh' -not -path '*/node_modules/*' -not -path '*/.git/*')

  local sh
  for sh in "${sh_files[@]}"; do
    if ! bash -n "$sh" 2>/dev/null; then
      log_error "bash syntax error: ${sh#"$PROJECT_ROOT"/}"
      rc=1
    fi
  done
  log_info "checked ${#sh_files[@]} bash script(s) for syntax"

  # Run the linter at full strictness. Warning, info and style findings fail the
  # build. A missing linter is a FAILURE, not a skip: this branch used to
  # print "shellcheck not installed — skipping lint" and then "validate: OK",
  # which is a green result that checked nothing. Proven by running validate with
  # the linter removed from PATH.
  local sc_fail=0
  for sh in "${sh_files[@]}"; do
    if ! shellcheck "$sh" >/dev/null 2>&1; then
      log_error "shellcheck errors: ${sh#"$PROJECT_ROOT"/}"
      sc_fail=1
    fi
  done
  if [[ $sc_fail -eq 0 ]]; then
    log_info "shellcheck clean (strict mode)"
  else
    rc=1
  fi

  if [[ $rc -eq 0 ]]; then
    log_info "validate: OK"
  else
    log_error "validate: FAIL"
  fi
  return "$rc"
}

function cmd_generate_index() {
  log_info "regenerating machine index"
  require_cmd bash
  bash "$PROJECT_ROOT/machines/scripts/generate-machine-index.sh"
}

function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

Top-level infrastructure control. Delegates to machines/, clusters/, etc.

Commands:
  status            Summarize counts of hosts, clusters, providers, platform, charts
  validate          Lint all project.json + bash scripts (jq + shellcheck REQUIRED)
  generate-index    Regenerate machines/README.md + machines/ledger.md from
                    machines/{development,services}/*/identity.yaml
  verify-access     Assert every machine in contracts/access.yaml is reachable
  verify-exposure   Assert every hostname matches contracts/exposure.yaml
  verify-registry   Assert every in-repo Argo Application path resolves
  verify-structure  Assert contract front-matter/sections + chart READMEs
  verify-runner-image <tag>  Assert a runner image works in the ARC pod shape
  verify-image-arch <ref>    Assert every manifest variant IS the arch it declares
  verify-runner-queue [repo] [workflow] [runs]
                    Assert no job waited far past the measured dispatch floor
  help              Show this message

Every verb in the dispatcher below must appear in this list. Two did not
(verify-access, verify-exposure). CI runs verify-exposure. CI does not run
verify-access: that verb needs LAN and tailnet access, and a CI runner does not
have it. Run verify-access by hand from a machine on the tailnet.
EOF
}

function cmd_verify_access() {
  # Assert every machine in contracts/access.yaml is reachable by its declared
  # method. Read-only: one SSH hostname echo per host.
  bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/verify-access.sh" "$@"
}

function cmd_verify_image_arch() {
  # Assert that a multi-arch image is what its manifest says. A manifest declares
  # a platform and nothing verified the content, which is how the published
  # linux/arm64 base image came to be an amd64 userland. See D42.
  bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/verify-image-arch.sh" "$@"
}

function cmd_verify_runner_image() {
  # Assert a runner image works in the pod shape ARC uses, WITH the dind sidecar.
  # Run this before pinning a new tag: neither the image build nor `docker run`
  # can see a broken Docker socket, and two defects reached a published image
  # that way.
  bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/verify-runner-image.sh" "$@"
}

function cmd_verify_runner_queue() {
  # Assert no job's queue rose far above the dispatch floor of the pool, where
  # the floor is a low percentile of the queue times of EVERY workflow in the
  # window. `timeout-minutes` counts execution only, so a job that waits 18
  # minutes for a slot and then runs for 151 seconds reports success and no
  # dashboard notices. The rule was `queue > execution` until 79d7fe3; it fired
  # on 17 of 36 arc-org jobs and all 17 were false, because a pod start costs
  # about 10 s and those jobs ran for 8 s. Read-only: it reads the runs and jobs
  # APIs.
  bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/verify-runner-queue.sh" "$@"
}

function cmd_verify_registry() {
  # Assert every Argo Application path that points at THIS repo resolves. Some
  # registry entries deploy from a sibling repo (gophersys/home carries rayne's
  # page); those are reported as skipped, not failed.
  bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/verify-registry-paths.sh" "$@"
}

function cmd_verify_structure() {
  # Assert the 2 structural rules that survived the deletion of .ci/: every
  # contract carries its front-matter and its 5 sections, and every chart
  # archetype has a README. Read-only.
  bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/verify-structure.sh" "$@"
}

function cmd_verify_exposure() {
  # Assert every hostname is exposed the way contracts/exposure.yaml declares.
  # Read-only: DNS resolution + one HTTP probe per host. Changes nothing.
  bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/verify-exposure.sh" "$@"
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    status)         cmd_status         "$@" ;;
    validate)        cmd_validate        "$@" ;;
    verify-exposure) cmd_verify_exposure "$@" ;;
    verify-access)   cmd_verify_access   "$@" ;;
    verify-registry) cmd_verify_registry "$@" ;;
    verify-structure) cmd_verify_structure "$@" ;;
    verify-image-arch)   cmd_verify_image_arch   "$@" ;;
    verify-runner-image) cmd_verify_runner_image "$@" ;;
    verify-runner-queue) cmd_verify_runner_queue "$@" ;;
    generate-index) cmd_generate_index "$@" ;;
    help|"")        usage ;;
    *)              log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
