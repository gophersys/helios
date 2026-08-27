#!/usr/bin/env bash
# Spec for scripts/lint-shell.sh — the shellcheck FLOOR, not the discovery glob.
#
# WHAT WAS WRONG, AND WHAT REPLACES IT
# The shellcheck gate went green over ZERO files. validate.yml piped an empty
# find into `xargs -0 -r shellcheck`: -r (--no-run-if-empty) runs shellcheck 0
# times and exits 0. ctl.sh cmd_validate looped over an empty array, so sc_fail
# stayed 0 and it logged "shellcheck clean" over nothing. A future path
# narrowing to zero scripts would have read as a pass. Reproduce the swallow:
#     printf '' | xargs -0 -r shellcheck; echo $?   ->   0   (shellcheck never ran)
#
# THE FIX, WITH ONE HOME
# A new scripts/lint-shell.sh discovers *.sh once, enforces a FLOOR (0 files ->
# exit non-zero, naming it), runs bash -n then shellcheck with findings VISIBLE,
# and prints `lint-shell: linted N shell script(s)`. BOTH validate.yml and
# ctl.sh validate call it, so the floor cannot be bypassed by one path.
#
# THE CONTRACT THESE CASES PIN (scripts/lint-shell.sh <dir>, dir defaults to root)
#   C1  0 scripts found -> exit non-zero AND a line carrying "no shell scripts
#       found". The floor. A green run that linted nothing is the one lie here.
#   C2  a script with a shellcheck violation -> exit non-zero AND the finding is
#       in the output (SC2086). Findings VISIBLE proves the linter RAN; it did
#       not merely count. The old ctl.sh hid them behind >/dev/null 2>&1.
#   C3  the real repo tree -> exit 0 AND a line "linted <N> shell script(s)"
#       with N >= 1. The count is the anti-false-green witness.
#   C4  ctl.sh validate -> exit 0 AND its output carries "lint-shell: linted",
#       proving cmd_validate delegates to the shared linter, not its old loop.
#
# Run: bash scripts/test-lint-shell.sh            # every case
#      bash scripts/test-lint-shell.sh <name>...  # one case, by name
#      bash scripts/test-lint-shell.sh --list     # the case names
#
# BAD FIXTURES LIVE UNDER mktemp ONLY, never in the repo tree: the real gate
# lints this repo, so a committed violating .sh would turn CI red.
#
# There is DELIBERATELY no "subject not found" preflight. When lint-shell.sh is
# absent (before it is implemented) each case must still run and fail by NAME on
# its own assertion, never abort the suite before a single case reports. An
# early exit that names no case is the "no test ran" false reading this suite
# exists to prevent.
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
SUT="$REPO_ROOT/scripts/lint-shell.sh"
CTL="$REPO_ROOT/ctl.sh"
ESC="$(printf '\033')"

CASES="
floor_fires_on_empty_tree
a_violating_script_fails
lints_the_real_tree
ctl_validate_uses_the_shared_linter
"

# A missing tool is a failure, never a skip. Every case drives shellcheck through
# the subject, so an absent shellcheck would turn each red into a 127 that says
# nothing about the floor. FAIL-NOT-SKIP, named, before any case runs.
command -v shellcheck >/dev/null 2>&1 || {
  echo "test-lint-shell: shellcheck is required and is not installed" >&2
  exit 127
}

# mktemp dirs to shred on exit. The guard form ${arr[@]+"${arr[@]}"} is for
# bash 3.2 (the macOS system bash) under set -u, where "${empty[@]}" aborts.
TMPDIRS=()
cleanup() {
  local d
  for d in ${TMPDIRS[@]+"${TMPDIRS[@]}"}; do
    [ -n "$d" ] && rm -rf "$d"
  done
}
trap cleanup EXIT

failures=0
case_failures=0
out=""
rc=0

note() { echo "    $*"; }

bad() {
  note "FAIL: $*"
  failures=$((failures + 1))
  case_failures=$((case_failures + 1))
}

# Drive the subject and keep its REAL exit code. set +e wraps the call so a
# non-zero exit (the whole point of a floor) does not abort the run, and rc=$?
# sits on the line right after the substitution so nothing runs between them. A
# pipeline would report its last stage instead — a misreading that has produced
# false findings in this repository.
run_lint() {
  set +e
  out="$(bash "$SUT" "$@" 2>&1)"
  rc=$?
  out="$(printf '%s\n' "$out" | sed "s/${ESC}\[[0-9;]*m//g")"
  set -e
}

run_ctl_validate() {
  set +e
  out="$(bash "$CTL" validate 2>&1)"
  rc=$?
  out="$(printf '%s\n' "$out" | sed "s/${ESC}\[[0-9;]*m//g")"
  set -e
}

expect_rc() { # <want> <why>
  if [ "$rc" -eq "$1" ]; then
    return 0
  fi
  bad "exit $rc, want $1 — $2"
  printf '%s\n' "$out" | tail -4 | sed 's/^/      | /'
}

expect_nonzero() { # <why>
  if [ "$rc" -ne 0 ]; then
    return 0
  fi
  bad "exit $rc, want non-zero — $1"
  printf '%s\n' "$out" | tail -4 | sed 's/^/      | /'
}

expect_line() { # <extended-regex> <why>
  if printf '%s\n' "$out" | grep -qE "$1"; then
    return 0
  fi
  bad "no line matched /$1/ — $2"
  printf '%s\n' "$out" | tail -6 | sed 's/^/      | /'
}

# -------- the cases --------

# 1. THE FLOOR. An empty tree has no scripts to lint, so a linter that reports
# clean has measured nothing — the exact false green this whole change exists to
# kill. The floor must FAIL and must name what is missing.
test_floor_fires_on_empty_tree() {
  local dir
  dir="$(mktemp -d)"; TMPDIRS+=("$dir")
  run_lint "$dir"
  expect_nonzero "an empty tree must never lint clean over nothing (C1)"
  expect_line 'no shell scripts found' "the floor must name what is missing (C1)"
}

# 2. THE LINTER ACTUALLY RUNS. A single script with a real shellcheck violation
# (SC2086, an unquoted expansion) must fail the run AND surface the finding. A
# linter that only counted files, or hid findings behind >/dev/null as the old
# ctl.sh did, would pass this. The fixture lives under mktemp, never in the repo.
test_a_violating_script_fails() {
  local dir
  dir="$(mktemp -d)"; TMPDIRS+=("$dir")
  cat >"$dir/bad.sh" <<'EOSH'
#!/usr/bin/env bash
rm $HOME/nope
EOSH
  run_lint "$dir"
  expect_nonzero "a shellcheck violation must fail the linter (C2)"
  expect_line 'SC2086' "the finding must be visible, proving shellcheck ran (C2)"
}

# 3. THE REAL TREE. The repo carries many scripts and they are clean, so the
# linter must exit 0 and report a non-zero count. The count is the witness that
# distinguishes "linted N and all passed" from "linted nothing and passed".
test_lints_the_real_tree() {
  run_lint "$REPO_ROOT"
  expect_rc 0 "the repo has scripts and they are shellcheck-clean (C3)"
  expect_line 'linted [0-9]+ shell script' "the run must report a count >= 1 (C3)"
}

# 4. ONE HOME. ctl.sh validate must delegate to the shared linter, not run its
# old inline loop. The marker `lint-shell: linted`, which only lint-shell.sh
# prints, proves the delegation. Without it the workflow and ctl.sh could drift
# apart and the floor would guard only one of the two paths.
test_ctl_validate_uses_the_shared_linter() {
  run_ctl_validate
  expect_rc 0 "validate must pass on a clean tree (C4)"
  expect_line 'lint-shell: linted' "ctl.sh must call the shared linter (C4)"
}

# -------- runner --------

run_case() {
  local name="$1"
  case_failures=0
  echo "== $name"
  "test_$name"
  if [ "$case_failures" -eq 0 ]; then
    note "ok"
  fi
}

main() {
  local selected="" name known found
  if [ "$#" -eq 0 ]; then
    selected="$CASES"
  elif [ "$1" = "--list" ]; then
    printf '%s' "$CASES" | sed '/^$/d'
    return 0
  else
    for name in "$@"; do
      found=0
      for known in $CASES; do
        [ "$name" = "$known" ] && found=1
      done
      if [ "$found" -eq 0 ]; then
        echo "test-lint-shell: no such case: $name" >&2
        echo "  known: $(printf '%s' "$CASES" | tr '\n' ' ')" >&2
        exit 2
      fi
      selected="$selected$name
"
    done
  fi

  local total=0
  for name in $selected; do
    run_case "$name"
    total=$((total + 1))
  done

  echo
  echo "cases=$total assertion-failures=$failures"
  [ "$failures" -eq 0 ] || exit 1
}

main "$@"
