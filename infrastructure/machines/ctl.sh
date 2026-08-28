#!/usr/bin/env bash
#
# machines/ctl.sh — control script for the machines subtree.
#
# Usage: ./ctl.sh <command> [args...]
#
# Verbs:
#   status           Counts of hosts (dev + service), templates, roles, groups
#   validate         JSON + bash syntax + shellcheck on everything under machines/
#   new-host         Scaffold a new host from a template
#   generate-index   Regenerate machines/README.md + ledger.md (delegates)
#   help
#
# Non-catalog verbs (not part of the generic verb catalog — justified here):
#   new-host         Infrastructure-specific authoring helper. Scaffolds
#                    machines/<category>/<name>/ from
#                    machines/templates/<category>/<template>/ and stamps the
#                    name into identity.yaml. There is no generic catalog
#                    verb for "create a new declarative host instance from a
#                    template" — this is a shape unique to the machines
#                    subtree.
#   generate-index   Infrastructure-specific authoring helper. Regenerates
#                    machines/README.md + machines/ledger.md from the
#                    development/ + services/ trees. Delegates to
#                    machines/scripts/generate-machine-index.sh.
#
# Host taxonomy:
#   machines/development/<name>/   Developer workstations (laptops, desktops).
#                                  Templates under templates/development/.
#   machines/services/<name>/      Service hosts (cluster nodes, bastions,
#                                  ARM builders, etc). Templates under
#                                  templates/services/.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC2034  # REPO_ROOT is scaffold for cmd_* to reference repo-wide paths
REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel)"

CATEGORIES=(development services)

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
  if [[ ${#BG_PIDS[@]} -gt 0 ]]; then
    for pid in ${BG_PIDS[@]+"${BG_PIDS[@]}"}; do
      kill "$pid" 2>/dev/null || true  # already exited
    done
  fi
  if [[ ${#TMPFS_MOUNTS[@]} -gt 0 ]]; then
    for mnt in ${TMPFS_MOUNTS[@]+"${TMPFS_MOUNTS[@]}"}; do
      if mountpoint -q "$mnt" 2>/dev/null; then
        umount "$mnt" 2>/dev/null || log_warn "failed to unmount $mnt"
      fi
    done
  fi
  if [[ ${#SENSITIVE_VARS[@]} -gt 0 ]]; then
    for var in ${SENSITIVE_VARS[@]+"${SENSITIVE_VARS[@]}"}; do
      unset "$var"
    done
  fi
  return "$rc"
}
trap on_exit EXIT

# Count real directories (exclude .gitkeep placeholders) under a given path.
function count_dirs() {
  local d="$1"
  if [[ ! -d "$d" ]]; then printf '0'; return 0; fi
  find "$d" -mindepth 1 -maxdepth 1 -type d | wc -l | awk '{print $1}'
}

# -------- commands --------

function cmd_status() {
  log_info "machines status"

  local cat dev_hosts=0 svc_hosts=0
  dev_hosts=$(count_dirs "$PROJECT_ROOT/development")
  svc_hosts=$(count_dirs "$PROJECT_ROOT/services")
  local total_hosts=$((dev_hosts + svc_hosts))

  local dev_templates=0 svc_templates=0
  dev_templates=$(count_dirs "$PROJECT_ROOT/templates/development")
  svc_templates=$(count_dirs "$PROJECT_ROOT/templates/services")
  local total_templates=$((dev_templates + svc_templates))

  local roles=0 groups=0 scripts=0
  roles=$(count_dirs "$PROJECT_ROOT/roles")
  groups=$(count_dirs "$PROJECT_ROOT/groups")
  if [[ -d "$PROJECT_ROOT/scripts" ]]; then
    scripts=$(find "$PROJECT_ROOT/scripts" -mindepth 1 -maxdepth 1 -type f -name '*.sh' | wc -l | awk '{print $1}')
  fi

  printf '  hosts:     %s (development: %s, services: %s)\n' "$total_hosts" "$dev_hosts" "$svc_hosts"
  printf '  templates: %s (development: %s, services: %s)\n' "$total_templates" "$dev_templates" "$svc_templates"
  printf '  roles:     %s\n' "$roles"
  printf '  groups:    %s (sub-dirs)\n' "$groups"
  printf '  scripts:   %s (fleet-wide, under machines/scripts/)\n' "$scripts"
}

function cmd_validate() {
  log_info "validating machines/"
  local rc=0

  require_cmd jq find shellcheck

  # Every host dir (under development/ or services/) must have identity.yaml.
  local cat d name
  for cat in "${CATEGORIES[@]}"; do
    if [[ -d "$PROJECT_ROOT/$cat" ]]; then
      while IFS= read -r -d '' d; do
        name="$(basename "$d")"
        if [[ ! -f "$d/identity.yaml" ]]; then
          log_error "host '$cat/$name' missing identity.yaml"
          rc=1
        fi
      done < <(find "$PROJECT_ROOT/$cat" -mindepth 1 -maxdepth 1 -type d -print0)
    fi
  done

  # Every template (under templates/<cat>/) must have identity.yaml.
  for cat in "${CATEGORIES[@]}"; do
    if [[ -d "$PROJECT_ROOT/templates/$cat" ]]; then
      local t
      while IFS= read -r -d '' t; do
        if [[ ! -f "$t/identity.yaml" ]]; then
          log_error "template '$cat/$(basename "$t")' missing identity.yaml"
          rc=1
        fi
      done < <(find "$PROJECT_ROOT/templates/$cat" -mindepth 1 -maxdepth 1 -type d -print0)
    fi
  done

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

    for sh in "${sh_files[@]}"; do
    if ! shellcheck "$sh" >/dev/null 2>&1; then
      log_error "shellcheck errors: ${sh#"$PROJECT_ROOT"/}"
      rc=1
    fi
  done

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
  local category="${1:-}"
  local template="${2:-}"
  local name="${3:-}"
  if [[ -z "$category" || -z "$template" || -z "$name" ]]; then
    log_error "usage: new-host <category> <template> <host-name>"
    log_error "  <category>  one of: ${CATEGORIES[*]}"
    exit 2
  fi

  # Validate category.
  local cat_ok=false c
  for c in "${CATEGORIES[@]}"; do
    [[ "$c" == "$category" ]] && cat_ok=true
  done
  if ! $cat_ok; then
    log_error "invalid category '$category' — must be one of: ${CATEGORIES[*]}"
    exit 2
  fi

  # Sanitize host-name. Kebab-case only.
  if ! [[ "$name" =~ ^[a-z][a-z0-9-]*$ ]]; then
    log_error "invalid host name '$name' — must be lowercase kebab-case"
    exit 2
  fi

  local tpl_dir="$PROJECT_ROOT/templates/$category/$template"
  local host_dir="$PROJECT_ROOT/$category/$name"

  if [[ ! -d "$tpl_dir" ]]; then
    log_error "template not found: templates/$category/$template"
    log_info "available templates in '$category':"
    if [[ -d "$PROJECT_ROOT/templates/$category" ]]; then
      find "$PROJECT_ROOT/templates/$category" -mindepth 1 -maxdepth 1 -type d \
        -exec basename {} \; | sort | sed 's/^/    /'
    fi
    exit 2
  fi

  if [[ -e "$host_dir" ]]; then
    log_error "host already exists: $category/$name"
    exit 2
  fi

  log_info "scaffolding host '$category/$name' from template '$category/$template'"
  mkdir -p "$PROJECT_ROOT/$category"
  cp -r "$tpl_dir" "$host_dir"

  # Stamp the hostname into identity.yaml. The template file has:
  #   name: __HOST_NAME__
  # Replace it with the real name. If the marker is absent, leave the file
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

  log_info "created $category/$name/"
  log_info "next: edit $category/$name/identity.yaml then run: bash ctl.sh generate-index"
}

function cmd_generate_index() {
  bash "$PROJECT_ROOT/scripts/generate-machine-index.sh"
}

# -------- usage --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

machines/ — Ansible + Tailscale hosts under IaC management.

Host categories:
  development   Developer workstations (laptops, desktops).
  services      Service hosts (cluster nodes, bastions, builders, etc.).

Commands:
  status                          Counts of hosts per category, templates, roles
  validate                        identity.yaml + bash syntax/shellcheck + JSON parse
  new-host <category> <template> <name>
                                  Scaffold machines/<category>/<name>/ from
                                  machines/templates/<category>/<template>/
  generate-index                  Regenerate machines/README.md + ledger.md
  help                            Show this message

Examples:
  bash ctl.sh new-host services linux-server-kubernetes agent-03
  bash ctl.sh new-host development linux-developer-workstation my-laptop
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
