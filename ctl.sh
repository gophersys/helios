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
  if [[ ${#BG_PIDS[@]} -gt 0 ]]; then
    for pid in "${BG_PIDS[@]}"; do
      kill "$pid" 2>/dev/null || true  # already exited — expected
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

# -------- language subtrees --------
LANG_SUBTREES=(go typescript python rust zephyr protocols)

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
  # BSD find (the macOS dev host) lacks the GNU print-format primary, so the version
  # that used it errored and this process substitution silently yielded zero libraries.
  # Strip the trailing /project.json with sed to get the dir — portable on BSD and GNU.
  mapfile -t dirs < <(find "$base" -mindepth 1 -maxdepth 4 -type f -name project.json | sed 's#/[^/]*$##' | sort -u)
  for dir in "${dirs[@]}"; do
    if [[ -f "$dir/ctl.sh" ]]; then
      count=$((count + 1))
    fi
  done
  printf '%d' "$count"
}

function find_all_ctl_scripts() {
  # Every control script under the repo: each project's ctl.sh (including the
  # top-level one) AND the shared verb bodies under <lang>/_ctl/ that those
  # dispatchers source. The _ctl half was covered by nothing until 2026-08, so
  # go/_ctl/lib.sh — the file holding every gate verb — was the one place in the
  # repo where a defect could not be caught by a gate.
  find "$PROJECT_ROOT" -type f \( -name ctl.sh -o -path '*/_ctl/*.sh' \) -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/target/*' -not -path '*/.git/*' | sort
}

function find_all_test_scripts() {
  find "$PROJECT_ROOT" -type f -name '*_test.sh' -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/target/*' -not -path '*/.git/*' | sort
}

function find_all_project_jsons() {
  find "$PROJECT_ROOT" -type f -name project.json -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/target/*' -not -path '*/.git/*' | sort
}

function _floor_of_one() {
  # A floor of 1 on a file list: 0 files found is indistinguishable from 0 files checked, so a
  # rename, a move, or a broken find predicate would delete a whole class of checks and still
  # report a green validate. EVERY list this verb walks carries its own floor — a full list
  # cannot vouch for an empty one, and merging two lists lets the full one mask the empty one.
  local count="$1" why="$2"
  [[ "$count" -gt 0 ]] && return 0
  log_error "$why"
  return 1
}

function _usage_verbs() {
  # The verbs a dispatcher documents, one per line, taken from the program itself:
  # `<ctl> help`, first token of every line indented exactly two spaces. Reading the
  # source text instead was blind to three shapes in this repo — the POSIX `usage() {`,
  # the quoted `cat <<'EOF'`, and a usage that arrives from a sourced file — and each
  # blind spot yielded an EMPTY list, which made the usage-to-targets half of the drift
  # check vacuously green. .ci/ctl.sh:200 (cmd_list_verbs, invoked as `__verbs`) already
  # sets the rule: ask the dispatcher, do not parse it.
  #
  # A failing help exits non-zero here, and the caller counts it. stderr is left alone so
  # a dispatcher's own diagnostic reaches the reader.
  local ctl="$1"
  timeout 10 bash "$ctl" help | awk '/^  [a-z][a-z0-9-]*([[:space:]]|$)/ { print $1 }' | sort -u
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
  require_cmd shellcheck jq timeout
  local failures=0

  # The three lists this verb walks, gathered together so the three floors sit together.
  local ctl_scripts test_scripts project_jsons
  mapfile -t ctl_scripts    < <(find_all_ctl_scripts)
  mapfile -t test_scripts   < <(find_all_test_scripts)
  mapfile -t project_jsons  < <(find_all_project_jsons)
  _floor_of_one "${#ctl_scripts[@]}" \
    "no ctl.sh or <lang>/_ctl/*.sh found under $PROJECT_ROOT; the dispatchers are what this verb exists to check, so finding none is a failure, not a pass" ||
    failures=$((failures + 1))
  _floor_of_one "${#test_scripts[@]}" \
    "no *_test.sh found under $PROJECT_ROOT; the shell suites are the only mechanical proof of the ctl.sh verbs, so finding none is a failure, not a pass" ||
    failures=$((failures + 1))
  _floor_of_one "${#project_jsons[@]}" \
    "no project.json found under $PROJECT_ROOT; the drift check has nothing to compare against, so finding none is a failure, not a pass" ||
    failures=$((failures + 1))

  # The *_test.sh suites are shellchecked alongside the dispatchers they prove: a suite
  # was the one shell file no gate read, so it could carry a real finding, exit 0, and be
  # reported ok.
  log_info "validating all ctl.sh and *_test.sh scripts via shellcheck"
  for script in "${ctl_scripts[@]:-}" "${test_scripts[@]:-}"; do
    [[ -z "$script" ]] && continue
    if shellcheck "$script"; then
      log_info "  ok: ${script#"$PROJECT_ROOT"/}"
    else
      log_error "  shellcheck failed: ${script#"$PROJECT_ROOT"/}"
      failures=$((failures + 1))
    fi
  done

  # Portability floor: the macOS dev host runs BSD find, which lacks the GNU
  # print-format primary. A find that uses it errors, and a discovery loop reading its
  # process substitution then SILENTLY reports zero — the FAIL-NOT-SKIP class that made
  # count_libs_in report 0 libraries on macOS. Reject the primary in every shell script.
  # The pattern brackets the leading dash so it matches the find flag, never the printf
  # builtin, and stays BSD-grep safe.
  log_info "validating no GNU-only find print-format primary (BSD/macOS portability)"
  for script in "${ctl_scripts[@]:-}" "${test_scripts[@]:-}"; do
    [[ -z "$script" ]] && continue
    if grep -nE '[-]printf' "$script" >/dev/null 2>&1; then
      log_error "  GNU-only find print-format primary (fails on BSD, silently yields empty): ${script#"$PROJECT_ROOT"/}"
      grep -nE '[-]printf' "$script" | sed 's/^/      /'
      failures=$((failures + 1))
    fi
  done

  log_info "validating all project.json files parse as JSON"
  for pj in "${project_jsons[@]:-}"; do
    [[ -z "$pj" ]] && continue
    if jq empty "$pj" >/dev/null 2>&1; then
      log_info "  ok: ${pj#"$PROJECT_ROOT"/}"
    else
      log_error "  invalid json: ${pj#"$PROJECT_ROOT"/}"
      failures=$((failures + 1))
    fi
  done

  log_info "checking target/usage drift (project.json targets must match ctl.sh usage)"
  for pj in "${project_jsons[@]:-}"; do
    [[ -z "$pj" ]] && continue
    local dir
    dir="$(dirname "$pj")"
    local ctl="$dir/ctl.sh"
    if [[ ! -f "$ctl" ]]; then
      log_error "  ${pj#"$PROJECT_ROOT"/}: sibling ctl.sh missing"
      failures=$((failures + 1))
      continue
    fi

    # Extract target names from project.json. A .targets that jq cannot take the keys of —
    # an array, a string — must name itself: swallowing the error left the target list empty,
    # and the loop below then blamed every documented verb for a fault in the JSON.
    local targets jq_rc=0
    targets="$(jq -r '.targets // {} | keys[]' "$pj" | sort -u)" || jq_rc=$?
    if [[ "$jq_rc" -ne 0 ]]; then
      log_error "  ${pj#"$PROJECT_ROOT"/}: jq could not read .targets (exit $jq_rc), so its targets cannot be checked"
      failures=$((failures + 1))
      continue
    fi

    # Ask the dispatcher for its verbs. A help that fails, or that documents nothing,
    # is its own counted failure naming the script: an empty verb list would make the
    # usage-to-targets half of the loop below vacuous, and report a clean sheet.
    local usage_cmds help_rc=0
    usage_cmds="$(_usage_verbs "$ctl")" || help_rc=$?
    if [[ "$help_rc" -ne 0 ]]; then
      log_error "  ${ctl#"$PROJECT_ROOT"/}: 'help' exited $help_rc, so the verbs it printed cannot be trusted"
      # Sourcing a dispatcher resolves the repository root with `git rev-parse` under errexit
      # (go/_ctl/lib.sh, templates/_ctl/template.sh, .ci/ctl.sh), so a tree whose .git is
      # absent or unresolvable — a `git archive`, a release tarball, a docker context that
      # excludes it — fails every dispatcher here with git's own 128 and no mention of git.
      if [[ "$help_rc" -eq 128 ]]; then
        log_error "    128 is git's exit: the dispatcher could not resolve its git root — is .git present and readable in $PROJECT_ROOT?"
      fi
      failures=$((failures + 1))
      continue
    fi
    if [[ -z "$usage_cmds" ]]; then
      log_error "  ${ctl#"$PROJECT_ROOT"/}: 'help' documented no verbs, so its targets cannot be checked"
      failures=$((failures + 1))
      continue
    fi

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

  log_info "running ${#test_scripts[@]} shell test suite(s) (*_test.sh)"
  for script in "${test_scripts[@]:-}"; do
    [[ -z "$script" ]] && continue
    if bash "$script"; then
      log_info "  ok: ${script#"$PROJECT_ROOT"/}"
    else
      log_error "  test suite failed: ${script#"$PROJECT_ROOT"/}"
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
  validate     Run shellcheck on every ctl.sh, every <lang>/_ctl/*.sh and every
               *_test.sh, validate every project.json, report drift between
               targets and the verbs each dispatcher's own help prints, and run
               every *_test.sh shell suite
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
