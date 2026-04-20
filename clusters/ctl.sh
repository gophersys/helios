#!/usr/bin/env bash
#
# clusters/ctl.sh — control script for the clusters subtree.
#
# Usage: ./ctl.sh <command> [args...]
#
# Non-catalog verbs (not part of the generic verb catalog — justified here):
#   new-cluster       Infrastructure-specific authoring helper. Scaffolds
#                     clusters/instances/<name>/ from
#                     clusters/templates/<template>/ and stamps the name
#                     into identity.yaml. There is no generic catalog verb
#                     for "create a new declarative cluster instance from
#                     a template" — this is a shape unique to the clusters
#                     subtree (mirrors machines/new-host).
#   new-cluster-node  Scaffold a node (cluster member) from the cluster
#                     template's nodes/<node-template>/ into
#                     clusters/instances/<cluster>/nodes/<host>/.
#                     Applies only to self-managed clusters (manual-k3s).
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
  if [[ ${#BG_PIDS[@]} -gt 0 ]]; then
    for pid in "${BG_PIDS[@]}"; do
      kill "$pid" 2>/dev/null || true
    done
  fi
  if [[ ${#TMPFS_MOUNTS[@]} -gt 0 ]]; then
    for mnt in "${TMPFS_MOUNTS[@]}"; do
      if mountpoint -q "$mnt" 2>/dev/null; then
        umount "$mnt" 2>/dev/null || log_warn "failed to unmount $mnt"
      fi
    done
  fi
  if [[ ${#SENSITIVE_VARS[@]} -gt 0 ]]; then
    for var in "${SENSITIVE_VARS[@]}"; do
      unset "$var"
    done
  fi
  return "$rc"
}
trap on_exit EXIT

# -------- commands --------

function cmd_status() {
  log_info "clusters status"

  local instances=0 templates=0 total_nodes=0
  if [[ -d "$PROJECT_ROOT/instances" ]]; then
    instances=$(find "$PROJECT_ROOT/instances" -mindepth 1 -maxdepth 1 -type d | wc -l | awk '{print $1}')
    if [[ "$instances" -gt 0 ]]; then
      total_nodes=$(find "$PROJECT_ROOT/instances" -mindepth 3 -maxdepth 3 -name identity.yaml \
                          -path '*/nodes/*' 2>/dev/null | wc -l | awk '{print $1}')
    fi
  fi
  if [[ -d "$PROJECT_ROOT/templates" ]]; then
    templates=$(find "$PROJECT_ROOT/templates" -mindepth 1 -maxdepth 1 -type d | wc -l | awk '{print $1}')
  fi

  printf '  instances: %s (with %s node(s) total)\n' "$instances" "$total_nodes"
  printf '  templates: %s\n' "$templates"
}

function cmd_validate() {
  log_info "validating clusters/"
  local rc=0

  require_cmd jq find

  # Cluster instances must have identity.yaml.
  if [[ -d "$PROJECT_ROOT/instances" ]]; then
    local d
    local name
    while IFS= read -r -d '' d; do
      name="$(basename "$d")"
      if [[ ! -f "$d/identity.yaml" ]]; then
        log_error "cluster instance '$name' missing identity.yaml"
        rc=1
      fi
      # Each node under instances/<c>/nodes/<host>/ must have identity.yaml.
      if [[ -d "$d/nodes" ]]; then
        local n
        while IFS= read -r -d '' n; do
          if [[ ! -f "$n/identity.yaml" ]]; then
            log_error "cluster node '$name/nodes/$(basename "$n")' missing identity.yaml"
            rc=1
          fi
        done < <(find "$d/nodes" -mindepth 1 -maxdepth 1 -type d -print0)
      fi
    done < <(find "$PROJECT_ROOT/instances" -mindepth 1 -maxdepth 1 -type d -print0)
  fi

  # Cluster templates must have identity.yaml.
  if [[ -d "$PROJECT_ROOT/templates" ]]; then
    local t
    while IFS= read -r -d '' t; do
      if [[ ! -f "$t/identity.yaml" ]]; then
        log_error "cluster template '$(basename "$t")' missing identity.yaml"
        rc=1
      fi
    done < <(find "$PROJECT_ROOT/templates" -mindepth 1 -maxdepth 1 -type d -print0)
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
  mkdir -p "$inst_dir/nodes" "$inst_dir/overlays"

  # Copy only the cluster-level identity; NOT nodes/ (those are scaffolded
  # per-node via new-cluster-node).
  if [[ -f "$tpl_dir/identity.yaml" ]]; then
    cp "$tpl_dir/identity.yaml" "$inst_dir/identity.yaml"
  else
    log_error "template missing identity.yaml: $tpl_dir/identity.yaml"
    exit 2
  fi

  # Substitute __CLUSTER_NAME__ in identity.yaml.
  local id="$inst_dir/identity.yaml"
  if grep -q '__CLUSTER_NAME__' "$id"; then
    python3 -c "
import sys
p=sys.argv[1]; n=sys.argv[2]
with open(p) as f: t=f.read()
with open(p,'w') as f: f.write(t.replace('__CLUSTER_NAME__', n))
" "$id" "$name"
  fi

  # Keep nodes/ and overlays/ trackable in git.
  touch "$inst_dir/nodes/.gitkeep" "$inst_dir/overlays/.gitkeep"

  log_info "created instances/$name/"
  log_info "next: edit instances/$name/identity.yaml then (for self-managed"
  log_info "      clusters) scaffold members with:"
  log_info "  bash clusters/ctl.sh new-cluster-node $name <node-template> <host-name>"
}

function cmd_new_cluster_node() {
  local cluster="${1:-}"
  local node_template="${2:-}"
  local host="${3:-}"
  if [[ -z "$cluster" || -z "$node_template" || -z "$host" ]]; then
    log_error "usage: new-cluster-node <cluster> <node-template> <host-name>"
    exit 2
  fi

  if ! [[ "$host" =~ ^[a-z][a-z0-9-]*$ ]]; then
    log_error "invalid host name '$host' — must be lowercase kebab-case"
    exit 2
  fi

  local inst_dir="$PROJECT_ROOT/instances/$cluster"
  if [[ ! -d "$inst_dir" ]]; then
    log_error "cluster '$cluster' does not exist"
    exit 2
  fi

  # Resolve which template the cluster was scaffolded from to find its
  # node-template dir. Parse "template: <value>" from identity.yaml.
  local cluster_template=""
  if [[ -f "$inst_dir/identity.yaml" ]]; then
    cluster_template="$(grep -E '^template:' "$inst_dir/identity.yaml" | awk '{print $2}')"
  fi
  if [[ -z "$cluster_template" ]]; then
    log_error "cannot resolve cluster template from $inst_dir/identity.yaml"
    exit 2
  fi

  local node_tpl_dir="$PROJECT_ROOT/templates/$cluster_template/nodes/$node_template"
  if [[ ! -d "$node_tpl_dir" ]]; then
    log_error "node template not found: templates/$cluster_template/nodes/$node_template"
    log_info "available node templates for '$cluster_template':"
    if [[ -d "$PROJECT_ROOT/templates/$cluster_template/nodes" ]]; then
      find "$PROJECT_ROOT/templates/$cluster_template/nodes" -mindepth 1 -maxdepth 1 -type d \
        -exec basename {} \; | sort | sed 's/^/    /'
    fi
    exit 2
  fi

  local node_dir="$inst_dir/nodes/$host"
  if [[ -e "$node_dir" ]]; then
    log_error "node already exists: instances/$cluster/nodes/$host"
    exit 2
  fi

  log_info "scaffolding node '$host' from template '$cluster_template/nodes/$node_template'"
  cp -r "$node_tpl_dir" "$node_dir"

  # Substitute __HOST_NAME__ in identity.yaml.
  local id="$node_dir/identity.yaml"
  if [[ -f "$id" ]] && grep -q '__HOST_NAME__' "$id"; then
    python3 -c "
import sys
p=sys.argv[1]; n=sys.argv[2]
with open(p) as f: t=f.read()
with open(p,'w') as f: f.write(t.replace('__HOST_NAME__', n))
" "$id" "$host"
  fi

  log_info "created instances/$cluster/nodes/$host/"
  log_info "next: edit instances/$cluster/nodes/$host/identity.yaml"
}

# -------- usage --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

clusters/ — Kubernetes clusters (cloud + manual).

Commands:
  status                                  Counts of instances, nodes, templates
  validate                                identity.yaml + JSON/bash checks
  new-cluster <template> <name>           Scaffold clusters/instances/<name>/
                                          from clusters/templates/<template>/
  new-cluster-node <cluster> <node-template> <host>
                                          Scaffold clusters/instances/<cluster>/nodes/<host>/
                                          from the cluster's node template.
  help                                    Show this message
EOF
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    status)             cmd_status            "$@" ;;
    validate)           cmd_validate          "$@" ;;
    new-cluster)        cmd_new_cluster       "$@" ;;
    new-cluster-node)   cmd_new_cluster_node  "$@" ;;
    help|"")            usage ;;
    *)                  log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
