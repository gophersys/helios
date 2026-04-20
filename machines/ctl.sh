#!/usr/bin/env bash
#
# machines/ctl.sh — control script for the machines subtree.
#
# Usage: ./ctl.sh <command> [args...]
#
# Verbs:
#   status           Counts of hosts, templates, roles, groups
#   validate         JSON + bash syntax + shellcheck on everything under machines/
#   new-host         Scaffold a new host from a template
#   generate-index   Regenerate machines/README.md + ledger.md (delegates)
#   help
#
# Non-catalog verbs (not part of the generic verb catalog — justified here):
#   new-host         Infrastructure-specific authoring helper. Scaffolds
#                    machines/hosts/<name>/ from machines/templates/<t>/
#                    and stamps the name into identity.yaml. There is no
#                    generic catalog verb for "create a new declarative
#                    host instance from a template" — this is a shape
#                    unique to the machines subtree.
#   generate-index   Infrastructure-specific authoring helper. Regenerates
#                    machines/README.md + machines/ledger.md from the
#                    hosts/ tree. Delegates to
#                    machines/scripts/generate-machine-index.sh. Not a
#                    generic verb because only this subtree maintains a
#                    materialized index.
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
  log_info "machines status"

  local hosts=0 templates=0 roles=0 groups=0 scripts=0
  if [[ -d "$PROJECT_ROOT/hosts" ]]; then
    hosts=$(find "$PROJECT_ROOT/hosts" -mindepth 1 -maxdepth 1 -type d | wc -l)
  fi
  if [[ -d "$PROJECT_ROOT/templates" ]]; then
    templates=$(find "$PROJECT_ROOT/templates" -mindepth 1 -maxdepth 1 -type d | wc -l)
  fi
  if [[ -d "$PROJECT_ROOT/roles" ]]; then
    roles=$(find "$PROJECT_ROOT/roles" -mindepth 1 -maxdepth 1 -type d | wc -l)
  fi
  if [[ -d "$PROJECT_ROOT/groups" ]]; then
    groups=$(find "$PROJECT_ROOT/groups" -mindepth 1 -maxdepth 1 -type d | wc -l)
  fi
  if [[ -d "$PROJECT_ROOT/scripts" ]]; then
    scripts=$(find "$PROJECT_ROOT/scripts" -mindepth 1 -maxdepth 1 -type f -name '*.sh' | wc -l)
  fi

  printf '  hosts:     %s\n' "$hosts"
  printf '  templates: %s\n' "$templates"
  printf '  roles:     %s\n' "$roles"
  printf '  groups:    %s (sub-dirs)\n' "$groups"
  printf '  scripts:   %s\n' "$scripts"
}

function cmd_validate() {
  log_info "validating machines/"
  local rc=0

  require_cmd jq find

  # Every host dir must contain identity.yaml.
  if [[ -d "$PROJECT_ROOT/hosts" ]]; then
    local d name
    while IFS= read -r -d '' d; do
      name="$(basename "$d")"
      if [[ ! -f "$d/identity.yaml" ]]; then
        log_error "host '$name' missing identity.yaml"
        rc=1
      fi
    done < <(find "$PROJECT_ROOT/hosts" -mindepth 1 -maxdepth 1 -type d -print0)
  fi

  # Every template must contain identity.yaml (as a template).
  if [[ -d "$PROJECT_ROOT/templates" ]]; then
    local t
    while IFS= read -r -d '' t; do
      if [[ ! -f "$t/identity.yaml" ]]; then
        log_error "template '$(basename "$t")' missing identity.yaml"
        rc=1
      fi
    done < <(find "$PROJECT_ROOT/templates" -mindepth 1 -maxdepth 1 -type d -print0)
  fi

  # Every role must contain tasks/main.yml.
  if [[ -d "$PROJECT_ROOT/roles" ]]; then
    local r
    while IFS= read -r -d '' r; do
      if [[ ! -f "$r/tasks/main.yml" ]]; then
        log_error "role '$(basename "$r")' missing tasks/main.yml"
        rc=1
      fi
    done < <(find "$PROJECT_ROOT/roles" -mindepth 1 -maxdepth 1 -type d -print0)
  fi

  # Bash scripts: syntax + shellcheck (if available).
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

function cmd_new_host() {
  local template="${1:-}"
  local name="${2:-}"
  if [[ -z "$template" || -z "$name" ]]; then
    log_error "usage: new-host <template> <host-name>"
    exit 2
  fi

  # Sanitize host-name. Kebab-case only.
  if ! [[ "$name" =~ ^[a-z][a-z0-9-]*$ ]]; then
    log_error "invalid host name '$name' — must be lowercase kebab-case"
    exit 2
  fi

  local tpl_dir="$PROJECT_ROOT/templates/$template"
  local host_dir="$PROJECT_ROOT/hosts/$name"

  if [[ ! -d "$tpl_dir" ]]; then
    log_error "template not found: templates/$template"
    log_info "available templates:"
    if [[ -d "$PROJECT_ROOT/templates" ]]; then
      find "$PROJECT_ROOT/templates" -mindepth 1 -maxdepth 1 -type d \
        -exec basename {} \; | sort | sed 's/^/    /'
    fi
    exit 2
  fi

  if [[ -e "$host_dir" ]]; then
    log_error "host already exists: hosts/$name"
    exit 2
  fi

  log_info "scaffolding host '$name' from template '$template'"
  mkdir -p "$PROJECT_ROOT/hosts"
  cp -r "$tpl_dir" "$host_dir"

  # Stamp the hostname into identity.yaml. The template file has:
  #   name: __HOST_NAME__
  # We replace it with the real name. If the marker is absent, leave the file
  # alone — operator will edit by hand.
  local id="$host_dir/identity.yaml"
  if [[ -f "$id" ]] && grep -q '__HOST_NAME__' "$id"; then
    # Use python for safe in-place rewrite (no sed -i portability issues)
    python3 -c "
import sys
p = sys.argv[1]
n = sys.argv[2]
with open(p) as f: t = f.read()
t = t.replace('__HOST_NAME__', n)
with open(p, 'w') as f: f.write(t)
" "$id" "$name"
  fi

  log_info "created hosts/$name/"
  log_info "next: edit hosts/$name/identity.yaml then run: bash ctl.sh generate-index"
}

function cmd_generate_index() {
  bash "$PROJECT_ROOT/scripts/generate-machine-index.sh"
}

# -------- usage --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

machines/ — Ansible + Tailscale hosts under IaC management.

Commands:
  status            Counts of hosts, templates, roles, groups, scripts
  validate          identity.yaml checks + bash syntax/shellcheck + JSON parse
  new-host <template> <name>
                    Scaffold machines/hosts/<name>/ from machines/templates/<template>/
  generate-index    Regenerate machines/README.md + ledger.md
  help              Show this message
EOF
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    status)         cmd_status         "$@" ;;
    validate)       cmd_validate       "$@" ;;
    new-host)       cmd_new_host       "$@" ;;
    generate-index) cmd_generate_index "$@" ;;
    help|"")        usage ;;
    *)              log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
