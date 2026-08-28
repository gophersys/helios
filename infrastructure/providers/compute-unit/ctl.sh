#!/usr/bin/env bash
#
# providers/compute-unit/ctl.sh — validation + introspection for the
# cloud-neutral compute-unit contract.
#
# Usage: ./ctl.sh <verb>
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# -------- logging --------
function log_info()    { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()    { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error()   { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }
function log_success() { printf '\033[0;32m[ok]\033[0m    %s\n' "$*"; }
function log_step()    { printf '\033[1;35m[step]\033[0m  %s\n' "$*"; }

function require_cmd() {
  local missing=()
  local cmd
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "missing required tool(s): ${missing[*]}"
    log_error "run this verb inside the base devcontainer (ghcr.io/gophersys/base)"
    exit 127
  fi
}

# -------- verbs --------

function cmd_help() {
  cat <<EOF
usage: ./ctl.sh <verb>

Verbs:
  status     One-line summary of contract version + declared vars/outputs
  info       Print the authoritative contract.yaml
  validate   Syntactic check of contract.yaml + README/contract agreement
  help       This message

This project has no terraform state — it's the contract definition that
every providers/<cloud>/modules/compute implementation agrees on.
EOF
}

function cmd_status() {
  require_cmd yq
  local v req_vars opt_vars req_outs
  v=$(yq -r '.version' "$PROJECT_ROOT/contract.yaml")
  req_vars=$(yq -r '.variables.required | length' "$PROJECT_ROOT/contract.yaml")
  opt_vars=$(yq -r '.variables.optional | length' "$PROJECT_ROOT/contract.yaml")
  req_outs=$(yq -r '.outputs.required | length' "$PROJECT_ROOT/contract.yaml")
  log_info "contract v$v — $req_vars required vars, $opt_vars optional vars, $req_outs required outputs"
}

function cmd_info() {
  cat "$PROJECT_ROOT/contract.yaml"
}

function cmd_validate() {
  require_cmd shellcheck yq

  log_step "shellcheck ctl.sh"
  shellcheck -x "$PROJECT_ROOT/ctl.sh"
  log_success "shellcheck ok"

  log_step "contract.yaml parses"
  if ! yq -r '.' "$PROJECT_ROOT/contract.yaml" >/dev/null 2>&1; then
    log_error "contract.yaml does not parse as YAML"
    exit 1
  fi
  log_success "contract.yaml parses"

  log_step "contract schema sanity"
  local version req_vars opt_vars req_outs
  version=$(yq -r '.version' "$PROJECT_ROOT/contract.yaml")
  [[ "$version" =~ ^[0-9]+$ ]] || { log_error "contract.yaml: .version must be an integer"; exit 1; }
  req_vars=$(yq -r '.variables.required | length' "$PROJECT_ROOT/contract.yaml")
  opt_vars=$(yq -r '.variables.optional | length' "$PROJECT_ROOT/contract.yaml")
  req_outs=$(yq -r '.outputs.required | length' "$PROJECT_ROOT/contract.yaml")
  [[ "$req_vars" -gt 0 ]] || { log_error "contract.yaml: .variables.required must be non-empty"; exit 1; }
  [[ "$req_outs" -gt 0 ]] || { log_error "contract.yaml: .outputs.required must be non-empty"; exit 1; }
  log_success "contract.yaml schema ok (v$version, $req_vars+$opt_vars vars, $req_outs outputs)"

  log_step "README mentions every contract variable name"
  local vname missing=()
  # All variable names (required + optional) must appear in README.md as
  # backtick-quoted tokens. Detects drift between the human doc + the
  # machine-readable contract.
  while IFS= read -r vname; do
    if ! grep -qE "\`${vname}\`" "$PROJECT_ROOT/README.md"; then
      missing+=("$vname")
    fi
  done < <(yq -r '(.variables.required + .variables.optional) | .[].name' "$PROJECT_ROOT/contract.yaml")
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "README.md is missing backticked mention of: ${missing[*]}"
    exit 1
  fi
  log_success "README ↔ contract variable agreement"

  log_step "README mentions every required output name"
  local oname
  missing=()
  while IFS= read -r oname; do
    if ! grep -qE "\`${oname}\`" "$PROJECT_ROOT/README.md"; then
      missing+=("$oname")
    fi
  done < <(yq -r '.outputs.required | .[].name' "$PROJECT_ROOT/contract.yaml")
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "README.md is missing backticked mention of outputs: ${missing[*]}"
    exit 1
  fi
  log_success "README ↔ contract output agreement"

  log_success "validate: all checks passed"
}

# -------- dispatch --------
function main() {
  local verb="${1:-help}"
  if [[ $# -gt 0 ]]; then shift; fi
  case "$verb" in
    status)   cmd_status "$@" ;;
    info)     cmd_info "$@" ;;
    validate) cmd_validate "$@" ;;
    help|-h|--help) cmd_help ;;
    *) log_error "unknown verb: '$verb'"; cmd_help; exit 2 ;;
  esac
}

main "$@"
