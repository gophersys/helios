#!/usr/bin/env bash
#
# clusters/ctl.sh — control script for the clusters subtree.
#
# Usage: ./ctl.sh <command> [args...]
#
# Non-catalog verbs (not part of the generic verb catalog — justified here):
#   new-cluster      Infrastructure-specific authoring helper. Scaffolds
#                    clusters/instances/<name>/ from
#                    clusters/templates/<template>/ and stamps the name
#                    into cluster.yaml. There is no generic catalog verb
#                    for "create a new declarative cluster instance from
#                    a template" — this is a shape unique to the clusters
#                    subtree (mirrors machines/new-host).
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC2034  # REPO_ROOT is scaffold for cmd_* to reference repo-wide paths
REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel)"

function log_info()  { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()  { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error() { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }

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

TMPFS_MOUNTS=()
BG_PIDS=()
SENSITIVE_VARS=()

function on_exit() {
  local rc=$?
  local pid mnt var
  for pid in "${BG_PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true  # already exited
  done
  for mnt in "${TMPFS_MOUNTS[@]}"; do
    if mountpoint -q "$mnt" 2>/dev/null; then
      umount "$mnt" 2>/dev/null || log_warn "failed to unmount $mnt"
    fi
  done
  for var in "${SENSITIVE_VARS[@]}"; do
    unset "$var"
  done
  return "$rc"
}
trap on_exit EXIT

# -------- commands --------

function cmd_status() {
  log_info "clusters status"

  local instances=0 templates=0
  if [[ -d "$PROJECT_ROOT/instances" ]]; then
    instances=$(find "$PROJECT_ROOT/instances" -mindepth 1 -maxdepth 1 -type d | wc -l)
  fi
  if [[ -d "$PROJECT_ROOT/templates" ]]; then
    templates=$(find "$PROJECT_ROOT/templates" -mindepth 1 -maxdepth 1 -type d | wc -l)
  fi

  printf '  instances: %s\n' "$instances"
  printf '  templates: %s\n' "$templates"
}

function cmd_validate() {
  log_info "validating clusters/"
  local rc=0

  require_cmd jq find

  # Cluster instances must have at least a cluster.yaml.
  if [[ -d "$PROJECT_ROOT/instances" ]]; then
    local d
    while IFS= read -r -d '' d; do
      if [[ ! -f "$d/cluster.yaml" ]]; then
        log_error "cluster instance '$(basename "$d")' missing cluster.yaml"
        rc=1
      fi
    done < <(find "$PROJECT_ROOT/instances" -mindepth 1 -maxdepth 1 -type d -print0)
  fi

  # Bash scripts: syntax + shellcheck.
  local sh_files=()
  while IFS= read -r f; do
    sh_files+=("$f")
  done < <(find "$PROJECT_ROOT" -name '*.sh' -not -path '*/node_modules/*')

  local sh
  for sh in "${sh_files[@]}"; do
    if ! bash -n "$sh" 2>/dev/null; then
      log_error "bash syntax error: ${sh#"$PROJECT_ROOT"/}"
      rc=1
    fi
  done

  if command -v shellcheck >/dev/null 2>&1; then
    for sh in "${sh_files[@]}"; do
      if ! shellcheck "$sh" >/dev/null 2>&1; then
        log_error "shellcheck errors: ${sh#"$PROJECT_ROOT"/}"
        rc=1
      fi
    done
  fi

  # project.json JSON parse.
  local pj
  while IFS= read -r pj; do
    if ! jq . "$pj" >/dev/null 2>&1; then
      log_error "invalid JSON: ${pj#"$PROJECT_ROOT"/}"
      rc=1
    fi
  done < <(find "$PROJECT_ROOT" -name project.json)

  if [[ $rc -eq 0 ]]; then
    log_info "validate: OK"
  else
    log_error "validate: FAIL"
  fi
  return "$rc"
}

function cmd_new_cluster() {
  local template="${1:-}"
  local name="${2:-}"
  if [[ -z "$template" || -z "$name" ]]; then
    log_error "usage: new-cluster <template> <cluster-name>"
    exit 2
  fi

  if ! [[ "$name" =~ ^[a-z][a-z0-9-]*$ ]]; then
    log_error "invalid cluster name '$name' — must be lowercase kebab-case"
    exit 2
  fi

  local tpl_dir="$PROJECT_ROOT/templates/$template"
  local inst_dir="$PROJECT_ROOT/instances/$name"

  if [[ ! -d "$tpl_dir" ]]; then
    log_error "template not found: templates/$template"
    log_info "available templates:"
    if [[ -d "$PROJECT_ROOT/templates" ]]; then
      find "$PROJECT_ROOT/templates" -mindepth 1 -maxdepth 1 -type d \
        -exec basename {} \; | sort | sed 's/^/    /'
    fi
    exit 2
  fi

  if [[ -e "$inst_dir" ]]; then
    log_error "cluster already exists: instances/$name"
    exit 2
  fi

  log_info "scaffolding cluster '$name' from template '$template'"
  mkdir -p "$PROJECT_ROOT/instances"
  cp -r "$tpl_dir" "$inst_dir"

  # If the template has a cluster.yaml with __CLUSTER_NAME__, substitute it.
  local cy="$inst_dir/cluster.yaml"
  if [[ -f "$cy" ]] && grep -q '__CLUSTER_NAME__' "$cy"; then
    python3 -c "
import sys
p=sys.argv[1]; n=sys.argv[2]
with open(p) as f: t=f.read()
with open(p,'w') as f: f.write(t.replace('__CLUSTER_NAME__', n))
" "$cy" "$name"
  fi

  log_info "created instances/$name/"
  log_info "next: edit instances/$name/cluster.yaml and run: bash ctl.sh validate"
}

# -------- usage --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

clusters/ — Kubernetes clusters (cloud + manual).

Commands:
  status            Counts of instances + templates
  validate          cluster.yaml existence + JSON/bash checks
  new-cluster <template> <name>
                    Scaffold clusters/instances/<name>/ from clusters/templates/<template>/
  help              Show this message
EOF
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    status)       cmd_status       "$@" ;;
    validate)     cmd_validate     "$@" ;;
    new-cluster)  cmd_new_cluster  "$@" ;;
    help|"")      usage ;;
    *)            log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
