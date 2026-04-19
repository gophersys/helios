#!/usr/bin/env bash
#
# ctl.sh — control script for the libs shared submodule (repo-wide meta-targets)
#
# Usage: ./ctl.sh <command> [args...]
#
# This is the TOP-LEVEL ctl.sh for the gophersys/libs repository. It exposes
# repo-wide meta-verbs. Each individual library inside typescript/, python/,
# rust/, zephyr/, protocols/ has its own project.json + ctl.sh following the
# development-nx-run-command skill pattern.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC2034  # REPO_ROOT scaffold for future cmd_* handlers
REPO_ROOT="$PROJECT_ROOT"

# -------- logging --------
function log_info()  { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()  { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error() { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }

# -------- tool gate --------
function require_cmd() {
  local missing=()
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "missing required tool(s): ${missing[*]}"
    exit 127
  fi
}

# -------- cleanup --------
TMPFS_MOUNTS=()
BG_PIDS=()
SENSITIVE_VARS=()

function on_exit() {
  local rc=$?
  for pid in "${BG_PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true  # already exited — expected
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

# -------- language subtrees --------
LANG_SUBTREES=(typescript python rust zephyr protocols)

# -------- helpers --------
function count_libs_in() {
  # Count child libraries in a subtree: a "lib" is a directory that contains
  # both project.json and ctl.sh. The subtree root itself does not count.
  local subtree="$1"
  local base="$PROJECT_ROOT/$subtree"
  if [[ ! -d "$base" ]]; then
    printf '0'
    return 0
  fi
  local count=0
  local dirs=()
  mapfile -t dirs < <(find "$base" -mindepth 1 -maxdepth 4 -type f -name project.json -printf '%h\n' | sort -u)
  for dir in "${dirs[@]}"; do
    if [[ -f "$dir/ctl.sh" ]]; then
      count=$((count + 1))
    fi
  done
  printf '%d' "$count"
}

function find_all_ctl_scripts() {
  # Every ctl.sh under the repo, including the top-level one.
  find "$PROJECT_ROOT" -type f -name ctl.sh -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/target/*' -not -path '*/.git/*' | sort
}

function find_all_project_jsons() {
  find "$PROJECT_ROOT" -type f -name project.json -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/target/*' -not -path '*/.git/*' | sort
}

# -------- commands --------
function cmd_status() {
  log_info "gophersys/libs — inventory"
  printf '  %-12s  %s\n' "subtree" "libraries"
  printf '  %-12s  %s\n' "--------" "---------"
  local total=0
  for subtree in "${LANG_SUBTREES[@]}"; do
    local n
    n="$(count_libs_in "$subtree")"
    printf '  %-12s  %s\n' "$subtree" "$n"
    total=$((total + n))
  done
  printf '  %-12s  %s\n' "--------" "---------"
  printf '  %-12s  %s\n' "total" "$total"
}

function cmd_validate() {
  require_cmd shellcheck jq
  local failures=0

  log_info "validating all ctl.sh scripts via shellcheck"
  local ctl_scripts
  mapfile -t ctl_scripts < <(find_all_ctl_scripts)
  for script in "${ctl_scripts[@]}"; do
    if shellcheck "$script"; then
      log_info "  ok: ${script#"$PROJECT_ROOT"/}"
    else
      log_error "  shellcheck failed: ${script#"$PROJECT_ROOT"/}"
      failures=$((failures + 1))
    fi
  done

  log_info "validating all project.json files parse as JSON"
  local project_jsons
  mapfile -t project_jsons < <(find_all_project_jsons)
  for pj in "${project_jsons[@]}"; do
    if jq empty "$pj" >/dev/null 2>&1; then
      log_info "  ok: ${pj#"$PROJECT_ROOT"/}"
    else
      log_error "  invalid json: ${pj#"$PROJECT_ROOT"/}"
      failures=$((failures + 1))
    fi
  done

  log_info "checking target/usage drift (project.json targets must match ctl.sh usage)"
  for pj in "${project_jsons[@]}"; do
    local dir
    dir="$(dirname "$pj")"
    local ctl="$dir/ctl.sh"
    if [[ ! -f "$ctl" ]]; then
      log_error "  ${pj#"$PROJECT_ROOT"/}: sibling ctl.sh missing"
      failures=$((failures + 1))
      continue
    fi

    # Extract target names from project.json.
    local targets
    targets="$(jq -r '.targets // {} | keys[]' "$pj" 2>/dev/null | sort -u || true)"

    # Extract command names from ctl.sh usage block: lines between `cat <<EOF`
    # and `EOF` inside the usage() function. Take the first token per line
    # that starts with two spaces and a word character.
    local usage_cmds
    usage_cmds="$(awk '
      /^function usage\(\) \{/ { in_usage = 1; next }
      in_usage && /^\}/        { in_usage = 0 }
      in_usage && /cat <<EOF/  { in_heredoc = 1; next }
      in_usage && in_heredoc && /^EOF$/ { in_heredoc = 0 }
      in_usage && in_heredoc && /^  [A-Za-z]/ { print $1 }
    ' "$ctl" | sort -u || true)"

    # Drift detection: every target must appear in usage, and every usage
    # entry (except the conventional "help") must appear as a target.
    local drift=0
    while IFS= read -r t; do
      [[ -z "$t" ]] && continue
      if ! grep -Fxq "$t" <<<"$usage_cmds"; then
        log_error "  ${pj#"$PROJECT_ROOT"/}: target '$t' missing from ctl.sh usage"
        drift=1
      fi
    done <<<"$targets"
    while IFS= read -r u; do
      [[ -z "$u" ]] && continue
      [[ "$u" == "help" ]] && continue
      if ! grep -Fxq "$u" <<<"$targets"; then
        log_error "  ${ctl#"$PROJECT_ROOT"/}: usage entry '$u' missing from project.json targets"
        drift=1
      fi
    done <<<"$usage_cmds"
    if [[ "$drift" -eq 0 ]]; then
      log_info "  ok: ${pj#"$PROJECT_ROOT"/}"
    else
      failures=$((failures + 1))
    fi
  done

  if [[ "$failures" -gt 0 ]]; then
    log_error "validate: $failures issue(s)"
    exit 1
  fi
  log_info "validate: all checks passed"
}

function cmd_propagate() {
  # Delegates to brain's propagate.sh. Only runs when libs is included as a
  # submodule under brain (detected via git superproject).
  local brain_root
  brain_root="$(git -C "$PROJECT_ROOT" rev-parse --show-superproject-working-tree 2>/dev/null || true)"
  if [[ -z "$brain_root" ]]; then
    log_error "propagate must be run from within brain (brain/shared/libs/)"
    log_error "this clone is standalone — no superproject detected"
    log_error "to propagate: clone libs as a submodule under brain/shared/ and run from there"
    exit 1
  fi
  if [[ ! -f "$brain_root/.claude/scripts/propagate.sh" ]]; then
    log_error "propagate script not found at: $brain_root/.claude/scripts/propagate.sh"
    log_error "brain is present but its orchestration scripts are missing"
    exit 1
  fi
  log_info "delegating to brain propagate for shared 'libs'"
  bash "$brain_root/.claude/scripts/propagate.sh" libs "$@"
}

# -------- usage --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

Commands:
  status       Inventory: count libraries per language subtree
  validate     Run shellcheck on every ctl.sh, validate every project.json,
               and report drift between targets and usage blocks
  propagate    Fan out this repo's current commit to every consuming project
               monorepo (must be invoked from within brain/shared/libs/)
  help         Show this message
EOF
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    status)     cmd_status     "$@" ;;
    validate)   cmd_validate   "$@" ;;
    propagate)  cmd_propagate  "$@" ;;
    help|"")    usage ;;
    *)          log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
