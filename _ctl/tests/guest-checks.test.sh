#!/usr/bin/env bash
#
# _ctl/tests/guest-checks.test.sh — the comparator that runs inside the image.
#
# Hermetic: stub tools first on PATH, and a table this file writes. No daemon,
# no network, no image.
#
# ============================================================================
# WHY THE COMPARATOR IS A FILE, AND NOT A HEREDOC
# ============================================================================
#
# The version checks live in .ci/smoke.sh today as a heredoc, and a heredoc runs
# in exactly 1 place: inside a container, after a build, on the publish path.
# Nothing on the pull request path can run it, so the comparator itself is
# tested by nothing. That is how an image assertion passes on a broken image —
# this repository has shipped that result once.
#
# .ci/image-checks.sh is a FILE that .ci/smoke.sh feeds to the container on
# stdin. The same file runs on the host against a stub PATH, which is what this
# test does, so the comparator is checked at pull request time and the image
# only supplies the tools.
#
# ============================================================================
# THE CONTRACT
# ============================================================================
#
#   PIN_TABLE   the environment carries the table, 1 row per line:
#
#                 <PIN NAME>|<expected version>|<command that prints a version>
#
#               A 4th field is free for a per-tool extractor. The 3 fields above
#               are the minimum, because the row must be readable without one.
#
#   every row matches   exit 0, and the output names each pin it compared. A
#                       comparator that skips a row quietly gives coverage that
#                       is not there, so the names are part of the contract.
#   a row differs       exit non-zero. The message names the TOOL, the PIN and
#                       the version it OBSERVED. All 3: "a version does not
#                       match" sends the reader to read 44 rows.
#   a tool is absent    exit non-zero, and name it. An absent tool is a version
#                       that cannot be compared, and a skip there is the exact
#                       green-while-broken result this file exists to prevent.
#   the table is empty  exit non-zero. A comparator that compares nothing must
#                       never report success (FAIL-NOT-SKIP).
#
# The absent-tool case names a command that no host holds, `gophersys-absent-
# tool`. A real tool name would make the case depend on the machine: the check
# would mean 1 thing on a laptop that has pnpm and another thing on a laptop
# that does not, and a stimulus that changes with the host is not a stimulus.
#
# Usage: bash _ctl/tests/guest-checks.test.sh
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

TEST_NAME="guest-checks.test.sh"

GUEST="$REPO_ROOT/.ci/image-checks.sh"
STUB_TOOLS="$TESTS_DIR/stubs/tools"

# The PATH every case runs with: the stub tools, then the 2 directories that
# hold the standard utilities the comparator needs. The developer's own PATH is
# left out on purpose, so a `gh` installed on this machine cannot answer.
GUEST_PATH="${STUB_TOOLS}:/usr/bin:/bin"

# The command no host holds. See the header.
ABSENT_TOOL="gophersys-absent-tool"
ABSENT_PIN="ABSENT_TOOL_VERSION"

GUEST_OUTPUT=""
GUEST_STATUS=0

# run_guest <table> [KEY=VALUE ...] — the comparator, on the host, against the
# stub PATH.
function run_guest() {
  local table="$1"
  shift
  GUEST_STATUS=0
  GUEST_OUTPUT="$(env PATH="$GUEST_PATH" PIN_TABLE="$table" "$@" \
    bash "$GUEST" < /dev/null 2>&1)" || GUEST_STATUS=$?
}

# The table every case starts from. 2 rows, 2 answer shapes: `gh version 2.90.0
# (date)` over 2 lines, and `hnslint 0.1.0` over 1.
MATCHING_TABLE="GH_VERSION|2.90.0|gh --version
HNSLINT_VERSION|0.1.0|hnslint --version"

# assert_failed_naming <check name> <needle> [needle...]
#
# The status AND every name, as 1 check. Written this way because a bare
# "the status is non-zero" passes on a run that died before it compared
# anything: an absent file exits 127, and 127 is non-zero. That reading is the
# one this whole phase exists to prevent, so the status is never asserted alone.
function assert_failed_naming() {
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
      "want: a non-zero exit status" \
      "got:  0 — the comparator accepted the table" \
      "output was:" "$GUEST_OUTPUT"
  elif [[ -n "$missing_names" ]]; then
    fail_check "$name" \
      "the comparator exited ${GUEST_STATUS}, and its message names none of:" \
      "$missing_names" \
      "output was:" "$GUEST_OUTPUT"
  else
    pass_check "$name"
  fi
}

printf '=== RUN  %s\n' "$TEST_NAME"

# -------- 0. the comparator is a file, and the stubs are runnable --------
if [[ -f "$GUEST" ]]; then
  pass_check "the_guest_comparator_is_a_file"
else
  fail_check "the_guest_comparator_is_a_file" \
    "absent: ${GUEST}" \
    "a comparator written inline in .ci/smoke.sh runs only inside a container, after a build," \
    "so nothing on the pull request path can test it at all"
fi
if [[ -x "$STUB_TOOLS/gh" && -x "$STUB_TOOLS/hnslint" ]]; then
  pass_check "the_tool_stubs_are_executable"
else
  fail_check "the_tool_stubs_are_executable" \
    "not executable: ${STUB_TOOLS}/gh and ${STUB_TOOLS}/hnslint" \
    "without them the tools of this machine answer, and nothing below is hermetic"
fi

# -------- 1. every row matches --------
run_guest "$MATCHING_TABLE"
assert_equal "a_table_that_matches_exits_zero" \
  "0" "$GUEST_STATUS" \
  "output was:" "$GUEST_OUTPUT"
assert_contains "a_matching_run_names_the_first_pin_it_compared" \
  "$GUEST_OUTPUT" "GH_VERSION" \
  "a comparator that skips a row quietly reports coverage it does not have"
assert_contains "a_matching_run_names_the_second_pin_it_compared" \
  "$GUEST_OUTPUT" "HNSLINT_VERSION" \
  "the 2 rows answer in 2 shapes; a comparator that reads 1 shape must not pass both"

# -------- 2. a version that drifted --------
# The stub reports 2.40.0 while the table expects 2.90.0. This is the whole
# defect in 1 line: `gh --version` exits 0 on both, so only a COMPARISON sees it.
run_guest "$MATCHING_TABLE" STUB_TOOL_GH_VERSION=2.40.0
assert_failed_naming "a_drifted_version_fails_and_names_the_tool_the_pin_and_the_observed" \
  "gh --version" "GH_VERSION" "2.40.0"

# -------- 3. a tool that is not on PATH --------
run_guest "${MATCHING_TABLE}
${ABSENT_PIN}|1.0.0|${ABSENT_TOOL} --version"
assert_failed_naming "an_absent_tool_fails_and_names_the_tool_and_its_pin" \
  "$ABSENT_TOOL" "$ABSENT_PIN"

# -------- 4. an empty table --------
# FAIL-NOT-SKIP. A comparator that compares nothing and exits 0 is the check
# this repository has already shipped: it printed a result and read no input.
run_guest ""
assert_failed_naming "an_empty_table_fails_and_names_PIN_TABLE" \
  "PIN_TABLE"

test_summary "$TEST_NAME"
