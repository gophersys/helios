#!/usr/bin/env bash
#
# secrets-purge.sh — idempotent scrub of all brain-secrets tmpfs scratch dirs
# owned by the current user.
#
# Usage: ./secrets-purge.sh [--all]
#
# Default: purge only /dev/shm/brain-secrets-$$ (this shell's).
# --all:   purge every /dev/shm/brain-secrets-* owned by $USER. Useful after a
#          crash where a trap did not fire.
#
# Unsets any *_FILE env vars whose value points inside /dev/shm/brain-secrets-*.
# Safe to run when nothing is loaded (no-op).
#
set -Eeuo pipefail
IFS=$'\n\t'

function log_info()  { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()  { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error() { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }

function purge_dir() {
  local d="$1"
  [[ -d "$d" ]] || return 0
  local f
  while IFS= read -r -d '' f; do
    shred -u -n 1 "$f" 2>/dev/null || rm -f "$f"
  done < <(find "$d" -type f -print0 2>/dev/null)
  rm -rf "$d"
  log_info "purged $d"
}

function purge_env() {
  # Unset every *_FILE var whose value starts with /dev/shm/brain-secrets-
  local var val
  while IFS= read -r var; do
    val="${!var:-}"
    if [[ "$val" == /dev/shm/brain-secrets-* ]]; then
      unset "$var"
      log_info "unset \$$var"
    fi
  done < <(compgen -v | grep '_FILE$' || true)
}

function main() {
  local all=0
  if [[ "${1:-}" == "--all" ]]; then
    all=1
  fi

  if [[ $all -eq 1 ]]; then
    local d
    # Glob may match nothing; guard.
    shopt -s nullglob
    for d in /dev/shm/brain-secrets-*; do
      # Only act on directories we own.
      if [[ -d "$d" && -O "$d" ]]; then
        purge_dir "$d"
      fi
    done
    shopt -u nullglob
  else
    purge_dir "/dev/shm/brain-secrets-$$"
  fi

  purge_env
  log_info "purge complete"
}

main "$@"
