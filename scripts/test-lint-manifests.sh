#!/usr/bin/env bash
# Spec for scripts/lint-manifests.sh — the kubeconform FLOOR, not the discovery glob.
#
# WHAT WAS WRONG, AND WHAT REPLACES IT
# The kubeconform "raw manifests" gate went green over ZERO files. validate.yml
# piped an empty find into `xargs -0 -r kubeconform`: -r (--no-run-if-empty) runs
# kubeconform 0 times and exits 0. A future path narrowing to zero manifests — or
# a roots list that resolved to nothing — would have read as a pass. Same class as
# the shellcheck swallow #57 closed one job over. Reproduce it:
#     printf '' | xargs -0 -r kubeconform; echo $?   ->   0   (kubeconform never ran)
#
# THE FIX, WITH ONE HOME
# A new scripts/lint-manifests.sh discovers the raw manifests once (the fixed root
# set + the non-templated registry path: values, minus the 4 excludes), enforces a
# FLOOR (0 files -> exit non-zero, naming it), runs kubeconform -strict
# -ignore-missing-schemas -summary with findings VISIBLE, and prints
# `lint-manifests: checked N manifest(s)`. validate.yml calls it, so the floor
# cannot be bypassed.
#
# THE CONTRACT THESE CASES PIN (scripts/lint-manifests.sh [dir], dir defaults to root)
#   C1  0 manifests found -> exit non-zero AND a line carrying "no manifests
#       found". The floor. A green run that checked nothing is the one lie here.
#   C2  a manifest with a real schema violation -> exit non-zero AND kubeconform's
#       finding is in the output ("is invalid" / "/data"). Findings VISIBLE proves
#       kubeconform RAN; it did not merely count files. The bad manifest sits under
#       the fixture's `apps/` root, because `apps` is a static discovery root
#       resolved relative to [dir].
#   C3  the real repo tree -> exit 0 AND a line "checked <N> manifest(s)" with
#       N >= 1. The count is the anti-false-green witness (N == 92 today).
#
# Run: bash scripts/test-lint-manifests.sh            # every case
#      bash scripts/test-lint-manifests.sh <name>...  # one case, by name
#      bash scripts/test-lint-manifests.sh --list     # the case names
#
# BAD FIXTURES LIVE UNDER mktemp ONLY, never in the repo tree: the real gate
# validates this repo, so a committed invalid manifest would turn CI red.
#
# There is DELIBERATELY no "subject not found" preflight. When lint-manifests.sh
# is absent (before it is implemented) each case must still run and fail by NAME
# on its own assertion, never abort the suite before a single case reports. An
# early exit that names no case is the "no test ran" false reading this suite
# exists to prevent.
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
SUT="$REPO_ROOT/scripts/lint-manifests.sh"
ESC="$(printf '\033')"

CASES="
floor_fires_on_empty_tree
an_invalid_manifest_fails
checks_the_real_tree
"

# A missing tool is a failure, never a skip. C2 and C3 drive kubeconform through
# the subject, so an absent kubeconform would turn each red into a 127 that says
# nothing about the floor. FAIL-NOT-SKIP, named, before any case runs.
command -v kubeconform >/dev/null 2>&1 || {
  echo "test-lint-manifests: kubeconform is required and is not installed" >&2
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

# 1. THE FLOOR. An empty tree has no manifests to validate, so a gate that reports
# clean has measured nothing — the exact false green this whole change exists to
# kill. None of the discovery roots exist under a fresh mktemp dir, so the file
# list is empty and the floor must FAIL and name what is missing.
test_floor_fires_on_empty_tree() {
  local dir
  dir="$(mktemp -d)"; TMPDIRS+=("$dir")
  run_lint "$dir"
  expect_nonzero "an empty tree must never validate clean over nothing (C1)"
  expect_line 'no manifests found' "the floor must name what is missing (C1)"
}

# 2. KUBECONFORM ACTUALLY RUNS. A single manifest with a real schema violation — a
# ConfigMap whose `data` is a string, which -strict rejects as
# "at '/data': got string, want null or object" — must fail the run AND surface
# the finding. A gate that only counted files, or hid findings, would pass this.
# The manifest sits under `<dir>/apps/`, because `apps` is a static discovery root
# the subject resolves relative to [dir]. The fixture lives under mktemp, never in
# the repo tree.
test_an_invalid_manifest_fails() {
  local dir
  dir="$(mktemp -d)"; TMPDIRS+=("$dir")
  mkdir -p "$dir/apps"
  cat >"$dir/apps/bad.yaml" <<'EOYAML'
apiVersion: v1
kind: ConfigMap
metadata:
  name: bad
data: this-is-a-string-not-an-object
EOYAML
  run_lint "$dir"
  expect_nonzero "a schema violation must fail the gate (C2)"
  expect_line 'is invalid|/data' "kubeconform's finding must be visible, proving it ran (C2)"
}

# 3. THE REAL TREE. The repo carries many raw manifests and they are valid, so the
# gate must exit 0 and report a non-zero count. The count is the witness that
# distinguishes "checked N and all passed" from "checked nothing and passed".
test_checks_the_real_tree() {
  run_lint "$REPO_ROOT"
  expect_rc 0 "the repo has manifests and they are kubeconform-valid (C3)"
  expect_line 'checked [0-9]+ manifest' "the run must report a count >= 1 (C3)"
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
        echo "test-lint-manifests: no such case: $name" >&2
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
