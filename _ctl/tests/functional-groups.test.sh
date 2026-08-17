#!/usr/bin/env bash
#
# _ctl/tests/functional-groups.test.sh — a failing functional group must fail
# the guest.
#
# Hermetic: a stub TOOLCHAIN first on PATH, the real .ci/fixtures/ copied to a
# temporary directory, and a 1-row comparator table this file writes. No daemon,
# no network, no image.
#
# ============================================================================
# WHY THIS IS A FILE OF ITS OWN, NEXT TO guest-checks.test.sh
# ============================================================================
#
# guest-checks.test.sh drives the COMPARATOR half of .ci/image-checks.sh: 2
# version stubs, a PATH built for reading `<tool> --version`, and evidence that
# reads "this pin was compared against that observed version".
#
# This file drives the FUNCTIONAL half: 12 stubbed tools, the real fixture tree,
# and evidence that reads "this step failed, so the run failed". The 2 halves
# share nothing but the script under test — a different stub surface, a
# different failure signature — and `bash ./ctl.sh test` names the file that
# broke, so keeping them apart names the contract that broke.
#
# ============================================================================
# THE DEFECT
# ============================================================================
#
# .ci/image-checks.sh wraps 2 prerequisite steps in a subshell:
#
#     ( cd "$module"   && run_step "go build" ... ) || return 0     :215
#     ( cd "$fixtures" && run_step "buf build" ... ) || return 0    :281
#
# `fail` sets FAILED=1, and it sets it INSIDE the subshell. The parent never
# sees the assignment, `|| return 0` then discards the status the subshell did
# carry out, and the run ends with:
#
#     FAIL: go build: exited 1
#     image-checks.sh: every check passed
#     EXIT=0
#
# A FAIL line, a success banner and exit 0, in 1 run. That is the
# check-that-cannot-fail class this repository has shipped before, and the whole
# reason .ci/image-checks.sh was made a testable file at all. Reproduced by
# drill on 2026-08-16 for both lines.
#
# So every case below asserts 3 things as 1 check — the STATUS, the FAIL line,
# and the ABSENCE of the success banner. Split into 3, a reader could see 2 of
# them green and believe the group is guarded; the defect above shows up as
# exactly that combination.
#
# ============================================================================
# WHAT THE CASES COVER
# ============================================================================
#
#   1 case per functional group (go-gate, dockerfile-lint, compose, debugger,
#     protocols) and 1 content group (content-flutter): 1 step of the group is
#     made to fail, and the run must fail.
#   reachability: 2 groups named together both run. The guest splits SMOKE_CHECKS
#     by hand because it runs with IFS=$'\n\t', and a split that regressed would
#     make every group unknown at once.
#   collection: the header of .ci/image-checks.sh states "every failure is
#     collected rather than fatal". A failure in the FIRST group must fail the
#     run AND leave the second group running.
#
# Usage: bash _ctl/tests/functional-groups.test.sh
#
set -Eeuo pipefail
IFS=$'\n\t'

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
PROJECT_ROOT="$REPO_ROOT"

# The logging lives in _ctl/lib.sh, 1 time only — the same source line every
# other script in this repository uses.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../lib.sh
source "$REPO_ROOT/_ctl/lib.sh"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=harness.sh
source "$TESTS_DIR/harness.sh"

TEST_NAME="functional-groups.test.sh"

GUEST="$REPO_ROOT/.ci/image-checks.sh"
STUB_TOOLCHAIN="$TESTS_DIR/stubs/toolchain"
FIXTURES="$REPO_ROOT/.ci/fixtures"

# The stubs this file needs on PATH. Named as a list because the precondition
# check below has to say WHICH one is missing: a stub that is not executable
# makes its group fail for a reason no case here chose, and the case would then
# be green about nothing.
STUB_TOOLS=(
  go gofumpt golangci-lint hnslint
  hadolint docker dlv buf grpcurl
  flutter adb java
)

# The PATH every case runs with: the stub toolchain, then the 2 directories that
# hold the standard utilities the guest needs (mktemp, cat, awk, rm, chmod). The
# developer's own PATH is left out on purpose, so a real `go` or a real
# `hadolint` on this machine cannot answer.
GUEST_PATH="${STUB_TOOLCHAIN}:/usr/bin:/bin"

# The comparator has to pass, so that every non-zero status below comes from a
# functional group and from nothing else. 1 row, read by the stub hnslint.
# An empty PIN_TABLE fails by contract, so "no table" is not an option here.
PIN_TABLE_OK="HNSLINT_VERSION|0.1.0|hnslint --version"

# The banner the guest prints when it believes everything passed. It is a
# literal here, and deliberately so: a test that read the sentence out of the
# file it checks would agree with any sentence, a wrong one included.
SUCCESS_BANNER="image-checks.sh: every check passed"

GUEST_OUTPUT=""
GUEST_STATUS=0

# run_groups <SMOKE_CHECKS> [KEY=VALUE ...] — the guest, on the host, against the
# stub toolchain and a fresh copy of the real fixture tree.
#
# The fixtures are COPIED and not pointed at: the go-gate group writes caches and
# a binary under a temporary root, and a case must not be able to modify the tree
# the next case reads.
function run_groups() {
  local groups="$1"
  shift
  local fixture_dir
  fixture_dir="$(mktemp -d)"
  cp -R "${FIXTURES}/." "${fixture_dir}/"
  GUEST_STATUS=0
  GUEST_OUTPUT="$(env PATH="$GUEST_PATH" \
    PIN_TABLE="$PIN_TABLE_OK" \
    SMOKE_CHECKS="$groups" \
    SMOKE_FIXTURE_DIR="$fixture_dir" \
    "$@" bash "$GUEST" < /dev/null 2>&1)" || GUEST_STATUS=$?
  rm -rf "$fixture_dir"
}

# assert_group_failed <check name> <needle> [needle...]
#
# 3 conditions, 1 check. See the header: the defect under test prints a FAIL
# line, prints the success banner and exits 0, so a check that read any one of
# those alone would report 2 greens on a run that swallowed a failure.
function assert_group_failed() {
  local name="$1"
  shift
  local needle missing_names=""
  for needle in "$@"; do
    if ! printf '%s' "$GUEST_OUTPUT" | grep -qF -- "$needle"; then
      missing_names="${missing_names:+${missing_names}
}${needle}"
    fi
  done
  if [[ "$GUEST_STATUS" -eq 0 ]]; then
    fail_check "$name" \
      "want: a non-zero exit status — a step of this group failed" \
      "got:  0 — the guest reported the image as checked" \
      "output was:" "$GUEST_OUTPUT"
  elif [[ -n "$missing_names" ]]; then
    fail_check "$name" \
      "the guest exited ${GUEST_STATUS}, and its output names none of:" \
      "$missing_names" \
      "a run that fails without naming the step sends the reader to read every group" \
      "output was:" "$GUEST_OUTPUT"
  elif printf '%s' "$GUEST_OUTPUT" | grep -qF -- "$SUCCESS_BANNER"; then
    fail_check "$name" \
      "the guest exited ${GUEST_STATUS} and named the step, and it ALSO printed:" \
      "$SUCCESS_BANNER" \
      "a run that reports a failure and success at once is read as success by a human" \
      "output was:" "$GUEST_OUTPUT"
  else
    pass_check "$name"
  fi
}

# assert_group_passed <check name> <needle> [needle...] — the mirror. Exit 0, and
# every named step really ran. The names matter: a guest that dispatched no group
# at all also exits 0, and that is a whole functional half silently unreachable.
function assert_group_passed() {
  local name="$1"
  shift
  local needle missing_names=""
  for needle in "$@"; do
    if ! printf '%s' "$GUEST_OUTPUT" | grep -qF -- "$needle"; then
      missing_names="${missing_names:+${missing_names}
}${needle}"
    fi
  done
  if [[ "$GUEST_STATUS" -ne 0 ]]; then
    fail_check "$name" \
      "want: exit 0 — every stubbed tool answers" \
      "got:  ${GUEST_STATUS}" \
      "output was:" "$GUEST_OUTPUT"
  elif [[ -n "$missing_names" ]]; then
    fail_check "$name" \
      "the guest exited 0, and its output names none of:" \
      "$missing_names" \
      "a group that is named and never dispatched exits 0 while checking nothing" \
      "output was:" "$GUEST_OUTPUT"
  else
    pass_check "$name"
  fi
}

printf '=== RUN  %s\n' "$TEST_NAME"

# -------- 0. the preconditions every case below depends on --------
if [[ -f "$GUEST" ]]; then
  pass_check "the_guest_checker_is_a_file"
else
  fail_check "the_guest_checker_is_a_file" \
    "absent: ${GUEST}" \
    "the functional groups live in that file, and nothing here can run them without it"
fi

missing_stubs=""
for stub in "${STUB_TOOLS[@]}"; do
  [[ -x "${STUB_TOOLCHAIN}/${stub}" ]] && continue
  missing_stubs="${missing_stubs:+${missing_stubs} }${stub}"
done
if [[ -z "$missing_stubs" ]]; then
  pass_check "every_toolchain_stub_is_executable"
else
  fail_check "every_toolchain_stub_is_executable" \
    "not executable under ${STUB_TOOLCHAIN}: ${missing_stubs}" \
    "a stub that cannot run makes its group fail for a reason no case here chose"
fi

# -------- 1. go-gate: the prerequisite step fails --------
# The subshell at .ci/image-checks.sh:215. `go build` is the step, and it is the
# prerequisite of the debugger group, so its failure is the one that matters most.
run_groups "go-gate" STUB_FAIL_GO=1
assert_group_failed "a_failing_go_build_fails_the_run" \
  "FAIL: go build"

# -------- 2. dockerfile-lint --------
run_groups "dockerfile-lint" STUB_FAIL_HADOLINT=1
assert_group_failed "a_failing_hadolint_fails_the_run" \
  "FAIL: hadolint"

# -------- 3. compose --------
run_groups "compose" STUB_FAIL_DOCKER_COMPOSE=1
assert_group_failed "a_failing_compose_config_fails_the_run" \
  "FAIL: docker compose config"

# -------- 4. debugger --------
# go-gate runs first and passes, so the debugger group gets the binary it needs
# and the ONLY failing step is the debugger itself. Without that, this case would
# fail on the "no binary to trace" precondition and prove nothing about dlv.
run_groups "go-gate debugger" STUB_FAIL_DLV=1
assert_group_failed "a_failing_debugger_fails_the_run" \
  "FAIL: dlv exec"

# -------- 5. protocols: the second prerequisite step --------
# The subshell at .ci/image-checks.sh:281, the same shape as :215.
run_groups "protocols" STUB_FAIL_BUF=1
assert_group_failed "a_failing_buf_build_fails_the_run" \
  "FAIL: buf build"

# The other half of the same group, which is NOT in a subshell. Both halves are
# checked, so a fix that repairs 1 line and leaves the other cannot read as done.
run_groups "protocols" STUB_FAIL_GRPCURL=1
assert_group_failed "a_failing_grpcurl_fails_the_run" \
  "FAIL: grpcurl"

# -------- 6. a content group --------
run_groups "content-flutter" STUB_FAIL_FLUTTER=1
assert_group_failed "a_failing_content_step_fails_the_run" \
  "FAIL: flutter"
# ... and the steps after it still ran. This is the collected-failures rule of
# the header, inside 1 group: 3 tools with 1 broken should report 1 broken tool,
# not stop at the first.
assert_contains "a_failing_content_step_does_not_stop_the_steps_after_it" \
  "$GUEST_OUTPUT" "ok   java" \
  "the header of .ci/image-checks.sh states that every failure is collected rather than fatal" \
  "a group that stops at its first failure reports 1 broken tool out of an unknown number"

# -------- 7. every named group is reached --------
# The guest runs with IFS=$'\n\t' and splits SMOKE_CHECKS by hand. A regression
# there reads the whole list as 1 word, every group becomes unknown at once, and
# the functional half of the smoke silently stops running.
run_groups "go-gate protocols"
assert_group_passed "naming_two_groups_runs_both_of_them" \
  "ok   go build" "ok   buf build" "ok   grpcurl list"

# -------- 8. a failure in the first group is collected, not fatal --------
# 2 angles, because the 2 failure paths of the guest behave in opposite ways and
# a fix for either one can break the other.
#
# The swallowed path first: the first group is go-gate, whose failing step is
# inside the `|| return 0` subshell. The run must fail.
run_groups "go-gate protocols" STUB_FAIL_GO=1
assert_group_failed "a_failure_in_the_first_group_fails_the_whole_run" \
  "FAIL: go build"
# The second group runs today only BECAUSE that failure was swallowed, so this
# check is here to hold the fix: repairing the subshell must not turn a failing
# group into an abort that takes every later group with it.
assert_contains "a_failure_in_the_first_group_does_not_stop_the_second" \
  "$GUEST_OUTPUT" "ok   buf build" \
  "the header of .ci/image-checks.sh states that every failure is collected rather than fatal" \
  "44 pins with 3 drifts must report 3 drifts, and a fatal first failure reports 1"

# The fatal path second: the first group is dockerfile-lint, whose failing step
# is a bare `run_step` and not a subshell, so `set -e` ends the guest there.
run_groups "dockerfile-lint protocols" STUB_FAIL_HADOLINT=1
assert_group_failed "a_fatal_first_group_still_fails_the_whole_run" \
  "FAIL: hadolint"
assert_contains "a_failing_first_group_leaves_the_second_group_running" \
  "$GUEST_OUTPUT" "ok   buf build" \
  "the header of .ci/image-checks.sh states that every failure is collected rather than fatal" \
  "an image with a broken hadolint AND a broken buf must report both, and a run that" \
  "stops at the first one publishes the reader an incomplete list of what is wrong"

test_summary "$TEST_NAME"
