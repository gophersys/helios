#!/usr/bin/env bash
#
# tailscale-provision.sh — join the current host to the tailnet using a
# pre-auth key fetched from Bitwarden.
#
# Usage: ./tailscale-provision.sh <tag> [--hostname <name>] [--ssh] [--accept-routes]
#
# Arguments:
#   <tag>            BW item suffix: item name is "tailscale-authkey-<tag>".
#   --hostname       Override the advertised Tailscale hostname.
#   --ssh            Enable Tailscale SSH (tailscale up --ssh).
#   --accept-routes  Accept advertised subnet routes.
#
# Behavior:
#   1. Preflight bw status + tailscale binary present.
#   2. Fetch auth key to tmpfs.
#   3. Invoke `tailscale up` passing the key via --authkey-file so the
#      secret path (not its value) is what lands in /proc/<pid>/cmdline.
#      The file stays on tmpfs and is shredded on EXIT.
#   4. Scrub the tmpfs on EXIT.
#
set -Eeuo pipefail
IFS=$'\n\t'

function log_info()  { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()  { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error() { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }

SECRETS_DIR=""

function on_exit() {
  local rc=$?
  if [[ -n "$SECRETS_DIR" && -d "$SECRETS_DIR" ]]; then
    local f
    while IFS= read -r -d '' f; do
      shred -u -n 1 "$f" 2>/dev/null || rm -f "$f"
    done < <(find "$SECRETS_DIR" -type f -print0 2>/dev/null)
    rm -rf "$SECRETS_DIR"
  fi
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
  local state
  state="$(bw status --session "$BW_SESSION" 2>/dev/null | jq -r '.status' 2>/dev/null || true)"
  if [[ "$state" != "unlocked" ]]; then
    log_error "bitwarden vault is '${state:-unknown}', expected 'unlocked'. Run: bw unlock"
    exit 2
  fi
}

function main() {
  local tag="${1:-}"
  if [[ -z "$tag" ]]; then
    log_error "usage: $0 <tag> [--hostname <name>] [--ssh] [--accept-routes]"
    exit 2
  fi
  shift

  local hostname="" enable_ssh=0 accept_routes=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --hostname)      hostname="${2:-}"; shift 2 ;;
      --ssh)           enable_ssh=1; shift ;;
      --accept-routes) accept_routes=1; shift ;;
      *) log_error "unknown arg: $1"; exit 2 ;;
    esac
  done

  require_cmd bw jq python3 tailscale find
  preflight_bw

  local bw_item="tailscale-authkey-$tag"
  log_info "fetching Tailscale auth key: $bw_item"

  SECRETS_DIR="$(mktemp -d /dev/shm/brain-secrets-XXXXXX)"
  chmod 700 "$SECRETS_DIR"
  local key_file="$SECRETS_DIR/authkey"

  # Pipe the fetched value straight to a tmpfs file at mode 0600. The value
  # never lands in a shell variable; only the file path is ever handled in
  # bash, and the path is all that's visible via ps / /proc/<pid>/cmdline.
  if ! bw get password "$bw_item" --session "$BW_SESSION" \
      | python3 -c "import sys,os; d=sys.stdin.read().rstrip('\n'); \
fd=os.open(sys.argv[1], os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600); \
os.write(fd,d.encode()); os.close(fd)" "$key_file"; then
    log_error "failed to fetch tailscale auth key from bitwarden"
    exit 3
  fi

  # Pass the key by path via --authkey-file so the secret value is never on
  # the command line. Only the tmpfs file path appears in /proc/<pid>/cmdline.
  local args=("up" "--authkey-file=$key_file")
  if [[ -n "$hostname" ]]; then
    args+=("--hostname=$hostname")
  fi
  if [[ $enable_ssh -eq 1 ]]; then
    args+=("--ssh")
  fi
  if [[ $accept_routes -eq 1 ]]; then
    args+=("--accept-routes")
  fi

  log_info "running: tailscale up (hostname=${hostname:-<default>} ssh=$enable_ssh accept-routes=$accept_routes)"

  # Execute. tailscale itself may require sudo; we don't re-invoke, the caller
  # is expected to have the right privilege. The on_exit trap shreds the
  # tmpfs file regardless of outcome — no separate variable scrub needed.
  local rc=0
  tailscale "${args[@]}" || rc=$?

  if [[ $rc -ne 0 ]]; then
    log_error "tailscale up failed (exit $rc)"
    exit "$rc"
  fi

  log_info "tailscale up succeeded"
}

main "$@"
