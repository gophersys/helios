#!/usr/bin/env bash
#
# _ctl/tests/harness.sh — the assertion harness the *.test.sh files share.
#
# This repository has no test framework and does not need one: every check here
# is a comparison of a string or of an exit status. What it does need is the
# property that a check which never runs cannot be mistaken for a check that
# passed. So:
#
#   - every assertion prints its own NAME next to PASS or FAIL, and a reader
#     confirms the check ran by finding its name in the output;
#   - test_summary counts the checks and FAILS a file that ran none. A file
#     whose assertions were all skipped by a typo, a bad glob or an early
#     return exits 0 in every other design, and that is the exact failure mode
#     this repository has already shipped once.
#
# A test file sets PROJECT_ROOT, sources _ctl/lib.sh (for the logging), then
# sources this file, then calls its checks, then ends with:
#   test_summary "$TEST_NAME"
#
# shellcheck shell=bash

CHECKS_RUN=0
CHECKS_FAILED=0

# pass_check <name>
function pass_check() {
  CHECKS_RUN=$((CHECKS_RUN + 1))
  printf -- '--- PASS: %s\n' "$1"
}

# fail_check <name> [evidence line...]
function fail_check() {
  CHECKS_RUN=$((CHECKS_RUN + 1))
  CHECKS_FAILED=$((CHECKS_FAILED + 1))
  printf -- '--- FAIL: %s\n' "$1"
  shift
  local block line
  for block in "$@"; do
    # An evidence argument is often several lines (a diff, a grep result).
    # Indent every one of them, so the block reads as 1 piece of evidence.
    while IFS= read -r line; do
      printf '        %s\n' "$line"
    done <<< "$block"
  done
}

# assert_equal <name> <want> <got> [extra evidence line...]
function assert_equal() {
  local name="$1" want="$2" got="$3"
  shift 3
  if [[ "$got" == "$want" ]]; then
    pass_check "$name"
  else
    fail_check "$name" "want: ${want}" "got:  ${got}" "$@"
  fi
}

# assert_status_nonzero <name> <status> [extra evidence line...]
function assert_status_nonzero() {
  local name="$1" status="$2"
  shift 2
  if [[ "$status" -ne 0 ]]; then
    pass_check "$name"
  else
    fail_check "$name" "want: a non-zero exit status" "got:  0" "$@"
  fi
}

# ============================================================================
# NEVER PIPE A HAYSTACK INTO grep -q. USE A HERESTRING.
# ============================================================================
#
# `printf '%s' "$haystack" | grep -qF -- "$needle"` is WRONG, and it was the
# shape used here until 2026-08-17. grep -q exits at its FIRST match and closes
# the read end of the pipe. printf still has the rest of the haystack to write,
# that write gets EPIPE, and printf then returns non-zero. Every test file in
# this directory sets `set -o pipefail`, so the pipeline reports FAILURE for a
# needle that IS present — a green assertion turned red by the reader finding
# what it was looking for, sooner.
#
# It is a race between printf's next write and grep's exit, so it needs a
# haystack big enough to take more than 1 write and a match early enough that
# grep leaves first. A ~29 KB payload with the needle at byte 2984 does it. The
# race resolves the safe way on this mac and the unsafe way on a native amd64
# runner, so the suite passed locally and failed in CI:
#
#   .../smoke-contract.test.sh: line 260: printf: write error: Broken pipe
#   .../harness.sh: line 74: printf: write error: Broken pipe
#   --- FAIL: every_asserted_pin_reaches_the_guest
#   --- FAIL: the_payload_asserts_the_pnpm_pin
#
# (gophersys/.devcontainer run 31991914353, pull request #41.) Both assertions
# were TRUE. That is the worst class of defect this directory can hold: not a
# check that cannot fail, but a check that fails at random, which teaches a
# reader to re-run the suite until it is green.
#
# A herestring hands grep a temporary FILE. There is no writer process, so
# there is nothing for an early exit to kill. The match semantics are the same:
# `<<<` appends the trailing newline printf '%s\n' already wrote.
#
# assert_contains <name> <haystack> <needle> [extra evidence line...]
function assert_contains() {
  local name="$1" haystack="$2" needle="$3"
  shift 3
  if grep -qF -- "$needle" <<< "$haystack"; then
    pass_check "$name"
  else
    fail_check "$name" "the output does not name: ${needle}" "output was:" "$haystack" "$@"
  fi
}

# assert_not_contains <name> <haystack> <needle> [extra evidence line...]
function assert_not_contains() {
  local name="$1" haystack="$2" needle="$3"
  shift 3
  if grep -qF -- "$needle" <<< "$haystack"; then
    fail_check "$name" "the output must NOT name: ${needle}" "output was:" "$haystack" "$@"
  else
    pass_check "$name"
  fi
}

# test_summary <file name> — the last line of every test file.
function test_summary() {
  local name="$1"
  if [[ "$CHECKS_RUN" -eq 0 ]]; then
    printf -- '--- FAIL: %s\n' "$name"
    printf '        no check ran, so this file asserted nothing\n'
    printf 'FAIL %s\n' "$name"
    return 1
  fi
  printf -- '=== %s: %d checks, %d failed\n' "$name" "$CHECKS_RUN" "$CHECKS_FAILED"
  if [[ "$CHECKS_FAILED" -gt 0 ]]; then
    printf 'FAIL %s\n' "$name"
    return 1
  fi
  printf 'ok   %s\n' "$name"
  return 0
}
