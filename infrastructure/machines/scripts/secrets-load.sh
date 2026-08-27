#!/usr/bin/env bash
#
# secrets-load.sh — fetch Bitwarden items listed in a manifest to tmpfs and
# export env vars pointing at the tmpfs files.
#
# Usage: ./secrets-load.sh <manifest-bw-item-name>
#
# Manifest item notes must contain one mapping per line:
#   ENV_VAR_NAME=bw-item-name
# Blank lines and lines starting with '#' are ignored.
#
# Preconditions:
#   - $BW_SESSION is set and non-empty.
#   - `bw status` reports "unlocked".
#   - /dev/shm is a tmpfs (on Linux it always is).
#
# Secrets are written to /dev/shm/brain-secrets-$$/<env-var>, mode 0600. For
# every mapping, an env var of the form <ENV_VAR>_FILE is exported pointing
# at the tmpfs path. Consumers read the file; scripts never log values.
#
# A cleanup trap shreds the tmpfs directory on EXIT so secrets never persist
# beyond the shell session that invoked this script.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC2034  # convention across ctl.sh + scripts
REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel 2>/dev/null || echo "$PROJECT_ROOT")"

function log_info()  { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()  { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error() { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }

SECRETS_DIR=""
EXPORTED_VARS=()

function on_exit() {
  local rc=$?
  if [[ -n "$SECRETS_DIR" && -d "$SECRETS_DIR" ]]; then
    # Shred every file before unlinking. find -print0 handles exotic names.
    while IFS= read -r -d '' f; do
      shred -u -n 1 "$f" 2>/dev/null || rm -f "$f"
    done < <(find "$SECRETS_DIR" -type f -print0 2>/dev/null)
    rm -rf "$SECRETS_DIR"
  fi
  local v
  for v in ${EXPORTED_VARS[@]+"${EXPORTED_VARS[@]}"}; do
    unset "$v"
  done
  return "$rc"
}
trap on_exit EXIT

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

function preflight_bw() {
  if [[ -z "${BW_SESSION:-}" ]]; then
    log_error "BW_SESSION is not set. Run: export BW_SESSION=\$(bw unlock --raw)"
    exit 2
  fi
  local status state
  status="$(bw status --session "$BW_SESSION" 2>/dev/null || true)"
  if [[ -z "$status" ]]; then
    log_error "bw status failed. Is the bitwarden CLI logged in?"
    exit 2
  fi
  state="$(printf '%s' "$status" | jq -r '.status' 2>/dev/null || true)"
  if [[ "$state" != "unlocked" ]]; then
    log_error "bitwarden vault is '${state:-unknown}', expected 'unlocked'. Run: bw unlock"
    exit 2
  fi
}

function main() {
  local manifest="${1:-}"
  if [[ -z "$manifest" ]]; then
    log_error "usage: $0 <bw-manifest-item-name>"
    exit 2
  fi

  require_cmd bw jq python3 mktemp find
  preflight_bw

  # Unpredictable per-invocation path on tmpfs. Matches the pattern in
  # ssh-ephemeral.sh / tailscale-provision.sh.
  SECRETS_DIR="$(mktemp -d -p /dev/shm brain-secrets-XXXXXXXX)"
  chmod 700 "$SECRETS_DIR"

  log_info "resolving manifest: $manifest"
  local manifest_notes
  # bw get notes fetches the "notes" field of the item
  if ! manifest_notes="$(bw get notes "$manifest" --session "$BW_SESSION" 2>/dev/null)"; then
    log_error "failed to fetch manifest '$manifest' from bitwarden"
    exit 3
  fi

  if [[ -z "$manifest_notes" ]]; then
    log_warn "manifest '$manifest' has empty notes — nothing to load"
    return 0
  fi

  local loaded=0
  local line env_var item_name
  while IFS= read -r line; do
    # strip leading/trailing whitespace
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    # skip blanks and comments
    [[ -z "$line" || "$line" == \#* ]] && continue
    # parse ENV=item
    if [[ "$line" != *=* ]]; then
      log_warn "skipping malformed manifest line: $line"
      continue
    fi
    env_var="${line%%=*}"
    item_name="${line#*=}"
    # Validate env var name (letters, digits, underscore; must not start with digit)
    if ! [[ "$env_var" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
      log_warn "skipping invalid env var name: $env_var"
      continue
    fi

    local dest="$SECRETS_DIR/$env_var"
    # Fetch the password value and write atomically without ever logging it.
    # bw get password writes the value to stdout with a trailing newline we strip.
    if ! bw get password "$item_name" --session "$BW_SESSION" \
        | python3 -c "import sys,os; d=sys.stdin.read(); d=d.rstrip('\n'); \
fd=os.open(sys.argv[1], os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600); \
os.write(fd,d.encode()); os.close(fd)" "$dest"; then
      log_error "failed to fetch/write secret for $env_var"
      exit 4
    fi

    local file_var="${env_var}_FILE"
    export "${file_var}=${dest}"
    EXPORTED_VARS+=("$file_var")
    log_info "loaded $env_var (item: $item_name) -> \$$file_var"
    loaded=$((loaded + 1))
  done <<< "$manifest_notes"

  log_info "loaded $loaded secret(s) to $SECRETS_DIR"
  log_warn "this shell's EXIT trap will purge the tmpfs. Source or run in the consumer's shell."
}

main "$@"
