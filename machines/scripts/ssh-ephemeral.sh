#!/usr/bin/env bash
#
# ssh-ephemeral.sh — open an SSH session to a machine using an ephemeral key
# fetched from Bitwarden.
#
# Usage: ./ssh-ephemeral.sh <machine-name> [extra ssh args...]
#
# Resolution:
#   - SSH key is fetched from BW item named "ssh-key-<machine-name>" (the
#     private key is stored in the item's "notes" field).
#   - Target host is the machine's Tailscale hostname, which is the machine name
#     verbatim. There is no per-host override.
#
# Operation:
#   1. Preflight bw status (unlocked).
#   2. Write key to /dev/shm/<random>/id, mode 0600.
#   3. ssh-add the key (temp-only via -t 300 so agent forgets in 5 min).
#   4. Run ssh using Tailscale hostname.
#   5. On EXIT, shred key, unlink, ssh-add -d.
#
set -Eeuo pipefail
IFS=$'\n\t'

function log_info()  { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()  { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error() { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }

SECRETS_DIR=""
KEY_PATH=""
KEY_ADDED=0

function on_exit() {
  local rc=$?
  if [[ $KEY_ADDED -eq 1 && -n "$KEY_PATH" && -f "$KEY_PATH" ]]; then
    ssh-add -d "$KEY_PATH" >/dev/null 2>&1 || true  # agent may have expired it
  fi
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

# The machine name IS the Tailscale hostname.
#
# This used to read a `tailscale_hostname:` override out of
# machines/hosts/<machine>/identity.yaml first. There is no machines/hosts/ in
# this repository and there never was — hosts live at machines/<category>/<host>/
# — so the `[[ -f ]]` guard could only ever miss and the function always fell
# through to the line below.
#
# The field itself is NOT unused: machines/services/{macos,windows}-ci-runner
# declare it, and machines/scripts/generate-machine-index.sh reads it. Only this
# SSH-side read was dead, and in both declared cases the value already equals the
# machine name, so removing it changes no hostname this script has ever produced.
# The branch was deleted rather than repointed at machines/<category>/: an
# override that has never once differed from the default is a feature to add
# deliberately, when a host actually needs a different name, not a dead path to
# quietly re-aim.
function resolve_hostname() {
  local machine="$1"
  printf '%s\n' "$machine"
}

function main() {
  local machine="${1:-}"
  if [[ -z "$machine" ]]; then
    log_error "usage: $0 <machine-name> [extra ssh args...]"
    exit 2
  fi
  shift

  require_cmd bw jq python3 ssh ssh-add mktemp find

  # ssh-agent must be running for ssh-add to work.
  if [[ -z "${SSH_AUTH_SOCK:-}" ]]; then
    log_error "ssh-agent not running (SSH_AUTH_SOCK unset). Start it with: eval \"\$(ssh-agent -s)\""
    exit 2
  fi

  preflight_bw

  local bw_item="ssh-key-$machine"
  log_info "fetching SSH key for machine: $machine (bw item: $bw_item)"

  SECRETS_DIR="$(mktemp -d /dev/shm/brain-secrets-XXXXXX)"
  chmod 700 "$SECRETS_DIR"
  KEY_PATH="$SECRETS_DIR/id"

  # Private key is stored in the "notes" field of the BW item.
  if ! bw get notes "$bw_item" --session "$BW_SESSION" \
      | python3 -c "import sys,os; d=sys.stdin.read(); \
fd=os.open(sys.argv[1], os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600); \
os.write(fd,d.encode()); os.close(fd)" "$KEY_PATH"; then
    log_error "failed to fetch SSH key from bitwarden"
    exit 3
  fi

  # Validate the fetched content looks like a PEM/OpenSSH private key. If BW
  # returned garbage (login screen, HTML, note-prefix cruft) the first line
  # will not start with -----BEGIN, and ssh-add would fail later with a
  # confusing error. Catch it here, before the key is ever handed to a tool.
  local first_line
  first_line="$(head -n 1 "$KEY_PATH" 2>/dev/null || true)"
  if [[ "$first_line" != -----BEGIN* ]]; then
    log_error "fetched key does not look like a private key (first line does not start with -----BEGIN)"
    log_error "check the BW item '$bw_item' notes field"
    exit 3
  fi

  # ssh-add with 5-minute lifetime so agent forgets even if we crash.
  if ! ssh-add -t 300 "$KEY_PATH" >/dev/null 2>&1; then
    log_error "ssh-add refused the key (is it encrypted? is format valid?)"
    exit 4
  fi
  KEY_ADDED=1
  log_info "key added to ssh-agent (5 minute lifetime)"

  local host
  host="$(resolve_hostname "$machine")"
  log_info "connecting to: $host"

  # Exec ssh. Additional user-provided args flow straight through.
  #
  # StrictHostKeyChecking=accept-new is trust-on-first-use (TOFU): ssh will
  # add the host's public key to ~/.ssh/known_hosts the first time it sees
  # the host, and reject any future key change for that host. This is safer
  # than 'no' (which would accept silently on every change) but still leaves
  # the first connection vulnerable to a man-in-the-middle on the Tailscale
  # network. In practice the tailnet mitigates this, but a targeted attacker
  # with tailnet access could still intercept the first connection.
  #
  # TODO(security): pin known_hosts entries from Bitwarden (store the host
  # public key alongside the private key under ssh-key-<machine> and write
  # it into a dedicated known_hosts file here, then use
  # -o UserKnownHostsFile=<that-file> -o StrictHostKeyChecking=yes). This
  # eliminates the first-connection TOFU window.
  ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new "$host" "$@"
}

main "$@"
