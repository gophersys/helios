#!/usr/bin/env bash
#
# providers/oracle/modules/compute/ctl.sh — validation for the OCI
# compute-unit implementation.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTRACT_YAML="$PROJECT_ROOT/../../../compute-unit/contract.yaml"

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

function cmd_help() {
  cat <<EOF
usage: ./ctl.sh <verb>

Verbs:
  validate         shellcheck + terraform fmt/init/validate + contract cross-check
  fmt              terraform fmt -recursive (in-place)
  docs-generate    (deferred — wire terraform-docs when a module readme needs it)
  help             This message
EOF
}

function cmd_fmt() {
  require_cmd terraform
  log_step "terraform fmt -recursive"
  ( cd "$PROJECT_ROOT" && terraform fmt -recursive )
  log_success "fmt applied"
}

function cmd_validate() {
  require_cmd shellcheck terraform yq grep

  log_step "shellcheck ctl.sh"
  shellcheck -x "$PROJECT_ROOT/ctl.sh"
  log_success "shellcheck ok"

  log_step "terraform fmt --check"
  if ! ( cd "$PROJECT_ROOT" && terraform fmt -check -recursive ) ; then
    log_error "terraform fmt failed — run './ctl.sh fmt'"
    exit 1
  fi
  log_success "terraform fmt ok"

  log_step "terraform init (backend=false; library module)"
  ( cd "$PROJECT_ROOT" && terraform init -backend=false -input=false -no-color ) >/dev/null
  log_success "terraform init ok"

  log_step "terraform validate"
  ( cd "$PROJECT_ROOT" && terraform validate -no-color )
  log_success "terraform validate ok"

  log_step "contract cross-check: required variables"
  if [[ ! -f "$CONTRACT_YAML" ]]; then
    log_error "compute-unit contract.yaml not found at $CONTRACT_YAML"
    exit 1
  fi
  local vname missing=()
  while IFS= read -r vname; do
    if ! grep -qE "^variable \"${vname}\"[[:space:]]+\{" "$PROJECT_ROOT/variables.tf"; then
      missing+=("$vname")
    fi
  done < <(yq -r '.variables.required | .[].name' "$CONTRACT_YAML")
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "variables.tf is missing required contract variables: ${missing[*]}"
    exit 1
  fi
  log_success "all required contract variables declared"

  log_step "contract cross-check: required outputs"
  local oname
  missing=()
  while IFS= read -r oname; do
    if ! grep -qE "^output \"${oname}\"[[:space:]]+\{" "$PROJECT_ROOT/outputs.tf"; then
      missing+=("$oname")
    fi
  done < <(yq -r '.outputs.required | .[].name' "$CONTRACT_YAML")
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "outputs.tf is missing required contract outputs: ${missing[*]}"
    exit 1
  fi
  log_success "all required contract outputs declared"

  log_success "validate: all checks passed"
}

function cmd_docs_generate() {
  log_warn "docs-generate not yet wired — deferring to terraform-docs integration"
}

function main() {
  local verb="${1:-help}"
  if [[ $# -gt 0 ]]; then shift; fi
  case "$verb" in
    validate)      cmd_validate "$@" ;;
    fmt)           cmd_fmt "$@" ;;
    docs-generate) cmd_docs_generate "$@" ;;
    help|-h|--help) cmd_help ;;
    *) log_error "unknown verb: '$verb'"; cmd_help; exit 2 ;;
  esac
}

main "$@"
