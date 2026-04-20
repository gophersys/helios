#!/usr/bin/env bash
#
# providers/state-backend/ctl.sh — OCI Object Storage backend for
# Terraform state. One bucket serves every infrastructure module in the
# brain ecosystem; modules key their state by repo-relative path.
#
# Usage: ./ctl.sh <verb> [args...]
#
# Non-catalog verb:
#   bootstrap   Create the OCI Object Storage bucket if missing
#               (idempotent). Mutates cloud state — gated.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC2034  # retained as scaffold for future cross-tree paths
REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel)"

BUCKET_NAME="gophersys-tfstate"
OCI_NAMESPACE="ax0uzamxfteg"
OCI_REGION_DEFAULT="us-phoenix-1"

# -------- logging --------
function log_info()    { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()    { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error()   { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }
function log_success() { printf '\033[0;32m[ok]\033[0m    %s\n' "$*"; }
function log_step()    { printf '\033[1;35m[step]\033[0m  %s\n' "$*"; }

# -------- cleanup --------
TMPFS_FILES=()
SENSITIVE_VARS=()
function on_exit() {
  local rc=$?
  local f var
  if [[ ${#TMPFS_FILES[@]} -gt 0 ]]; then
    for f in "${TMPFS_FILES[@]}"; do
      [[ -f "$f" ]] && { shred -u "$f" 2>/dev/null || rm -f "$f"; }
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

# -------- tool + env requirements --------
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

function require_oci_env() {
  local missing=()
  local v
  for v in OCI_TENANCY_OCID OCI_USER_OCID OCI_FINGERPRINT OCI_PRIVATE_KEY_B64 OCI_COMPARTMENT_OCID; do
    [[ -n "${!v:-}" ]] || missing+=("$v")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "missing required env var(s): ${missing[*]}"
    log_error "load from BW item 'env:infrastructure' before running this verb"
    exit 2
  fi
  # OCI_REGION falls back to the module default.
  export OCI_REGION="${OCI_REGION:-$OCI_REGION_DEFAULT}"
}

function write_oci_config_to_tmpfs() {
  # Writes ~/.oci/{config,api.pem} backed by tmpfs on Linux (/dev/shm)
  # with strict perms. Registers the files for trap cleanup. Safe to
  # re-run — idempotent.
  local dir
  if [[ -d /dev/shm ]]; then
    dir="/dev/shm/oci-cfg-$$"
  else
    dir="${TMPDIR:-/tmp}/oci-cfg-$$"
  fi
  mkdir -p "$dir"
  chmod 700 "$dir"
  TMPFS_FILES+=("$dir/api.pem" "$dir/config")
  printf '%s' "$OCI_PRIVATE_KEY_B64" | base64 -d > "$dir/api.pem"
  chmod 600 "$dir/api.pem"
  cat > "$dir/config" <<EOF
[DEFAULT]
user=$OCI_USER_OCID
fingerprint=$OCI_FINGERPRINT
tenancy=$OCI_TENANCY_OCID
region=$OCI_REGION
key_file=$dir/api.pem
EOF
  chmod 600 "$dir/config"
  export OCI_CLI_CONFIG_FILE="$dir/config"
  export SUPPRESS_LABEL_WARNING=True
  SENSITIVE_VARS+=("OCI_CLI_CONFIG_FILE")
}

# -------- verbs --------

function cmd_help() {
  cat <<EOF
usage: ./ctl.sh <verb> [args...]

Verbs:
  status              Bucket reachability + object count (read-only)
  info                Print backend.hcl + consumer usage example
  validate            Shellcheck + syntactic validation of this project
  fmt                 terraform fmt on any .tf/.hcl files here (in-place)
  bootstrap           Create bucket $BUCKET_NAME if missing (idempotent)
  destroy [--force]   Delete the bucket (refuses without --force; only
                      proceeds if bucket is empty)
  help                This message

Required env for status/bootstrap/destroy:
  OCI_TENANCY_OCID, OCI_USER_OCID, OCI_FINGERPRINT, OCI_PRIVATE_KEY_B64,
  OCI_COMPARTMENT_OCID, OCI_REGION (defaults to $OCI_REGION_DEFAULT)

Bucket identity:
  name:      $BUCKET_NAME
  namespace: $OCI_NAMESPACE
  region:    $OCI_REGION_DEFAULT (overridable via OCI_REGION)
EOF
}

function cmd_info() {
  echo "### backend.hcl"
  echo
  cat "$PROJECT_ROOT/backend.hcl"
  echo
  echo "### consumer init example"
  cat <<'EOF'

# From the consuming module's directory, e.g. providers/oracle/modules/compute:
terraform init \
  -backend-config=../../state-backend/backend.hcl \
  -backend-config=key=providers/oracle/compute/terraform.tfstate

# Required env (loaded from BW "OCI S3 Customer Secret Key (Terraform State)"):
#   AWS_ACCESS_KEY_ID
#   AWS_SECRET_ACCESS_KEY
EOF
}

function cmd_status() {
  require_cmd oci jq
  require_oci_env
  write_oci_config_to_tmpfs
  log_step "checking bucket $BUCKET_NAME"
  local out
  if ! out=$(oci os bucket get --namespace "$OCI_NAMESPACE" --bucket-name "$BUCKET_NAME" --output json 2>&1); then
    if echo "$out" | grep -qi "BucketNotFound"; then
      log_warn "bucket $BUCKET_NAME does not exist (run: ./ctl.sh bootstrap)"
      return 1
    fi
    log_error "bucket query failed:"
    echo "$out" >&2
    return 1
  fi
  local created storage_tier
  created=$(echo "$out" | jq -r '.data."time-created"')
  storage_tier=$(echo "$out" | jq -r '.data."storage-tier"')
  log_success "bucket exists — created=$created tier=$storage_tier"

  log_step "counting objects"
  local count
  count=$(oci os object list --namespace "$OCI_NAMESPACE" --bucket-name "$BUCKET_NAME" --all --output json 2>/dev/null | jq -r '.data // [] | length')
  log_info "object count: $count"
}

function cmd_validate() {
  require_cmd shellcheck
  log_step "shellcheck ctl.sh"
  shellcheck -x "$PROJECT_ROOT/ctl.sh"
  log_success "shellcheck ok"

  log_step "backend.hcl exists"
  [[ -f "$PROJECT_ROOT/backend.hcl" ]] || { log_error "backend.hcl missing"; exit 1; }
  log_success "backend.hcl present"

  # Parse backend.hcl for a minimal sanity check — the required keys
  # should all appear as bare assignments.
  local missing=()
  local k
  for k in bucket region endpoints skip_credentials_validation use_path_style use_lockfile; do
    if ! grep -qE "^${k}[[:space:]]*=" "$PROJECT_ROOT/backend.hcl"; then
      missing+=("$k")
    fi
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "backend.hcl missing keys: ${missing[*]}"
    exit 1
  fi
  log_success "backend.hcl key surface ok"

  if command -v terraform >/dev/null 2>&1; then
    log_step "terraform fmt --check"
    ( cd "$PROJECT_ROOT" && terraform fmt -check -recursive ) || {
      log_error "terraform fmt failed — run './ctl.sh fmt'"
      exit 1
    }
    log_success "terraform fmt ok"
  else
    log_warn "terraform not installed — skipping fmt check"
  fi

  log_success "validate: all checks passed"
}

function cmd_fmt() {
  require_cmd terraform
  log_step "terraform fmt -recursive"
  ( cd "$PROJECT_ROOT" && terraform fmt -recursive )
  log_success "fmt applied"
}

function cmd_bootstrap() {
  require_cmd oci jq
  require_oci_env
  write_oci_config_to_tmpfs

  log_step "checking for existing bucket $BUCKET_NAME"
  if oci os bucket get --namespace "$OCI_NAMESPACE" --bucket-name "$BUCKET_NAME" >/dev/null 2>&1; then
    log_info "bucket already exists — nothing to do"
    return 0
  fi

  log_step "creating bucket $BUCKET_NAME in compartment $OCI_COMPARTMENT_OCID"
  oci os bucket create \
    --namespace "$OCI_NAMESPACE" \
    --compartment-id "$OCI_COMPARTMENT_OCID" \
    --name "$BUCKET_NAME" \
    --storage-tier Standard \
    --versioning Enabled \
    --public-access-type NoPublicAccess \
    >/dev/null
  log_success "bucket $BUCKET_NAME created (versioning=Enabled, storage-tier=Standard, no public access)"
}

function cmd_destroy() {
  local force=false
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --force) force=true ;;
      *) log_error "unknown arg: '$1'"; exit 2 ;;
    esac
    shift
  done
  if ! $force; then
    log_error "destroy requires --force. This deletes the bucket $BUCKET_NAME"
    log_error "and every terraform.tfstate stored in it."
    exit 2
  fi

  require_cmd oci jq
  require_oci_env
  write_oci_config_to_tmpfs

  log_step "checking bucket is empty"
  local count
  count=$(oci os object list --namespace "$OCI_NAMESPACE" --bucket-name "$BUCKET_NAME" --all --output json 2>/dev/null | jq -r '.data // [] | length')
  if [[ "$count" != "0" ]]; then
    log_error "bucket has $count object(s); refusing to delete a non-empty bucket"
    log_error "inspect with './ctl.sh status', manually clean if truly desired"
    exit 1
  fi

  log_step "deleting bucket $BUCKET_NAME"
  oci os bucket delete --namespace "$OCI_NAMESPACE" --bucket-name "$BUCKET_NAME" --force >/dev/null
  log_success "bucket $BUCKET_NAME deleted"
}

# -------- dispatch --------
function main() {
  local verb="${1:-help}"
  if [[ $# -gt 0 ]]; then shift; fi
  case "$verb" in
    status)    cmd_status "$@" ;;
    info)      cmd_info "$@" ;;
    validate)  cmd_validate "$@" ;;
    fmt)       cmd_fmt "$@" ;;
    bootstrap) cmd_bootstrap "$@" ;;
    destroy)   cmd_destroy "$@" ;;
    help|-h|--help) cmd_help ;;
    *) log_error "unknown verb: '$verb'"; cmd_help; exit 2 ;;
  esac
}

main "$@"
