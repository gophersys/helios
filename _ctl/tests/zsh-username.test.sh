#!/usr/bin/env bash
#
# _ctl/tests/zsh-username.test.sh — ${USERNAME} in a RUN under zsh is not the ARG.
#
# Static means static: this file reads files and calls 1 function of ctl.sh. It
# starts no container, it calls no daemon and it reaches no network, so it runs
# identically on a laptop and on a CI runner — and it runs in the PULL REQUEST
# gate.
#
# ============================================================================
# THE DEFECT (ledger #105)
# ============================================================================
#
# zsh sets USERNAME itself. It is a special parameter tied to the EFFECTIVE
# user, and zsh overwrites whatever the environment held at startup. Docker does
# not expand a RUN line — it hands the string to the shell — so under
# `SHELL ["/usr/bin/zsh", ...]` a `chown ${USERNAME}` means the user the layer
# happens to be running as, and NOT `ARG USERNAME=dev`. In a root layer it
# silently means `chown root`.
#
# The failure is silent by construction: the build succeeds, the image ships,
# and the wrong ownership surfaces at RUNTIME in another image. It has already
# happened here. flutter/Dockerfile chowned /opt/flutter and /opt/android-sdk
# that way, both shipped root-owned, and `flutter --version` as `dev` exited 128
# with "detected dubious ownership in repository at '/opt/flutter'" — found by
# the first smoke run that ever executed the tool, not by a build and not by a
# gate.
#
# `zsh_username_run_references` in ctl.sh is the reader that ends that silence,
# and `cmd_validate` fails on what it reports. Until this file, the reader was
# tested by nothing: it was written, it returned nothing on a clean tree, and a
# reader that has only ever been silent has never been observed to work.
#
# ============================================================================
# THE SEAM
# ============================================================================
#
# The reader is a function of ctl.sh, so this file sources ctl.sh with NO argv
# and calls it. `set --` first, so the dispatcher at the foot of that script
# takes its help path and returns 0 instead of exiting 1 on an unknown command —
# the shape scheduled-workflows.test.sh already uses to read BUILD_ORDER out of
# a running shell.
#
# Running `bash ./ctl.sh validate` instead would be the end-to-end read, and it
# is not hermetic: that verb needs shellcheck, jq, the pinned hadolint and, on a
# host without it, a docker daemon. So the WIRING — validate hands every
# Dockerfile to this reader and names the file — is held by 1 text check below,
# which says so where it stands.
#
# ============================================================================
# WHAT THIS FILE DOES NOT PROVE (measured, 2026-08-17)
# ============================================================================
#
# A reference that follows a Dockerfile COMMENT LINE inside the same RUN
# continuation is not reported. The reader ends the RUN at the comment, because
# a comment line carries no trailing backslash; docker's parser strips the
# comment and CONTINUES the RUN, so the line after it does reach zsh. Measured
# with this file, which reports nothing:
#
#   SHELL ["/usr/bin/zsh", "-o", "pipefail", "-c"]
#   RUN mkdir -p /opt/a \
#       # a comment line inside the continuation, which docker strips
#    && chown -R "${USERNAME}" /opt/a
#
# No Dockerfile of this repository has that shape today. It is written here
# rather than tested here because closing it is a change to the reader in
# ctl.sh, and a test file does not get to make that change.
#
# Usage: bash _ctl/tests/zsh-username.test.sh
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

TEST_NAME="zsh-username.test.sh"

ROOT_CTL="$REPO_ROOT/ctl.sh"

# The counter-stimulus pair. A detector that has only ever seen correct input
# has never been observed to fire, and one that has only ever seen broken input
# has never been observed to stay quiet.
BROKEN_FIXTURE="$TESTS_DIR/fixtures/zsh-username/post-switch.Dockerfile"
CLEAN_FIXTURE="$TESTS_DIR/fixtures/zsh-username/pre-switch.Dockerfile"

# Every Dockerfile of the repository, named file by file rather than found by a
# glob, for the reason platform-policy.test.sh names its list: a glob that stops
# matching leaves a green result that read nothing.
#
# `runner/Dockerfile` is in the list and OUTSIDE validate's reach: that verb
# walks BUILD_ORDER, which runner left when the image was retired. So for that 1
# file this test is the only reader, and it stays until the deletion wave takes
# the directory.
DOCKERFILES=(
  "base/Dockerfile"
  "runner/Dockerfile"
  "flutter/Dockerfile"
  "zephyr/Dockerfile"
  "zephyr-devbox/Dockerfile"
  "cloud/Dockerfile"
)

DETECTOR_OUTPUT=""
DETECTOR_STATUS=0

# run_detector <dockerfile> — zsh_username_run_references, out of a shell that
# sourced ctl.sh. stderr is kept: a source that failed must be READ, not turned
# into an empty report that looks like a clean file.
function run_detector() {
  DETECTOR_STATUS=0
  DETECTOR_OUTPUT="$(CTL_SCRIPT="$ROOT_CTL" DOCKERFILE="$1" bash -c '
    set --
    source "$CTL_SCRIPT" > /dev/null
    zsh_username_run_references "$DOCKERFILE"
  ' 2>&1)" || DETECTOR_STATUS=$?
}

# reported_line <file> <fixed string> — the `<line>: <text>` record the reader
# must print for the fixture line holding that string.
#
# The expectation is COMPUTED from the fixture and never written here as a
# number: a hardcoded line number is a test that goes red when somebody adds a
# sentence to a comment, which teaches the reader to edit the number.
function reported_line() {
  local file="$1" needle="$2" number
  number="$(grep -nF -- "$needle" "$file" | head -1 | cut -d: -f1)"
  [[ -z "$number" ]] && return 0
  printf '%s: %s' "$number" "$(sed -n "${number}p" "$file")"
}

printf '=== RUN  %s\n' "$TEST_NAME"

# -------- 1. the fixtures, and the reader, are really there --------
missing_fixtures=""
for fixture in "$BROKEN_FIXTURE" "$CLEAN_FIXTURE"; do
  [[ -f "$fixture" ]] || missing_fixtures="${missing_fixtures:+${missing_fixtures}
}${fixture}"
done
if [[ -n "$missing_fixtures" ]]; then
  fail_check "the_counter_stimulus_pair_exists" \
    "the fixtures this test proves the reader with are absent:" \
    "$missing_fixtures"
else
  pass_check "the_counter_stimulus_pair_exists"
fi

# -------- 2. the reader FIRES on the broken file --------
# This runs before the real Dockerfiles on purpose. A clean verdict on the tree
# means nothing until the same function has been watched to report a file that
# carries the trap.
run_detector "$BROKEN_FIXTURE"
if [[ "$DETECTOR_STATUS" -ne 0 ]]; then
  fail_check "the_reader_runs_and_reports_the_broken_fixture" \
    "sourcing ctl.sh and calling zsh_username_run_references exited ${DETECTOR_STATUS}" \
    "it printed:" "${DETECTOR_OUTPUT:-<nothing>}" \
    "with no report to read, every check below passes over an empty string"
elif [[ -z "$DETECTOR_OUTPUT" ]]; then
  fail_check "the_reader_runs_and_reports_the_broken_fixture" \
    "the fixture carries \${USERNAME} in a RUN after the SHELL switched to zsh, and the reader found nothing" \
    "the reader cannot fail, so its silence on the real Dockerfiles is worthless"
else
  pass_check "the_reader_runs_and_reports_the_broken_fixture"
fi

# The report names the LINE and the line's own text. "flutter/Dockerfile has a
# ${USERNAME} problem" sends a reader through 400 lines; a line number does not.
# shellcheck disable=SC2016
# The single quotes are the point: the needle is the literal text of a fixture
# line, and a `${USERNAME}` this file expanded would search for the wrong string.
assert_contains "a_zsh_run_reference_is_reported_with_its_line" \
  "$DETECTOR_OUTPUT" \
  "$(reported_line "$BROKEN_FIXTURE" 'chown -R "${USERNAME}:${USERNAME}" /opt/tool')" \
  "under a zsh SHELL this chown means the uid of the layer, and in a root layer it means root"

# The continuation line is where a real one hides: the RUN opens with an
# innocent line, and a reader that only looks at lines starting with RUN sees
# nothing at all.
# shellcheck disable=SC2016
# A literal needle again, and this one carries the BARE spelling on purpose.
assert_contains "a_zsh_run_reference_on_a_continuation_line_is_reported" \
  "$DETECTOR_OUTPUT" \
  "$(reported_line "$BROKEN_FIXTURE" 'chown -R "$USERNAME" /opt/second')" \
  "the bare \$USERNAME spelling reaches zsh exactly like the braced one"

# -------- 3. the reader stays QUIET where no shell is involved --------
# One that reports every ${USERNAME} is as useless as one that reports none, and
# it is worse in 1 way: it teaches the reader that the gate is noise.
assert_not_contains "a_reference_before_the_switch_is_not_reported" \
  "$DETECTOR_OUTPUT" "before-the-switch" \
  "that RUN is above the SHELL line, so /bin/sh runs it and /bin/sh does not touch USERNAME"

assert_not_contains "an_ENV_after_the_switch_is_not_reported" \
  "$DETECTOR_OUTPUT" "HOME_DIRECTORY" \
  "the Dockerfile PARSER expands an ENV out of the build args; no shell is involved"

# shellcheck disable=SC2016
# The needle IS the literal text of the fixture line, so the `$` must not expand.
assert_not_contains "a_USER_after_the_switch_is_not_reported" \
  "$DETECTOR_OUTPUT" 'USER ${USERNAME}' \
  "the parser expands a USER line the same way, which is why base and cloud still declare the ARG"

assert_not_contains "a_comment_inside_a_run_continuation_is_not_reported" \
  "$DETECTOR_OUTPUT" "may name" \
  "docker strips a comment line before any shell reads it, so it is prose and not an instruction"

# -------- 4. the reader is SILENT on the correct file --------
run_detector "$CLEAN_FIXTURE"
if [[ "$DETECTOR_STATUS" -eq 0 && -z "$DETECTOR_OUTPUT" ]]; then
  pass_check "the_correct_file_is_reported_clean"
else
  fail_check "the_correct_file_is_reported_clean" \
    "the reader exited ${DETECTOR_STATUS} and reported this about a file that spells the user out:" \
    "${DETECTOR_OUTPUT:-<nothing>}" \
    "every reference in that fixture is before the switch, or an ENV, or a USER, or the literal dev"
fi

# -------- 5. every Dockerfile of the repository is clean --------
for relative in "${DOCKERFILES[@]}"; do
  file="$REPO_ROOT/$relative"
  if [[ ! -f "$file" ]]; then
    fail_check "${relative}_has_no_zsh_username_run_reference" \
      "the file list in this test is stale: ${relative} is named here and absent from the tree"
    continue
  fi
  run_detector "$file"
  if [[ "$DETECTOR_STATUS" -eq 0 && -z "$DETECTOR_OUTPUT" ]]; then
    pass_check "${relative}_has_no_zsh_username_run_reference"
  else
    fail_check "${relative}_has_no_zsh_username_run_reference" \
      "these RUN lines read \${USERNAME} after the file switched SHELL to zsh:" \
      "${DETECTOR_OUTPUT:-<the reader exited ${DETECTOR_STATUS} and printed nothing>}" \
      "zsh auto-sets USERNAME to the EFFECTIVE user, so each one reads the layer's uid and not the ARG" \
      "write the literal 'dev' — the pattern flutter/, zephyr/ and zephyr-devbox/ document in their headers"
  fi
done

# -------- 6. the gate is WIRED to the reader --------
# A text check, and the header says why: the end-to-end read is `bash ./ctl.sh
# validate`, which needs shellcheck, jq, the pinned hadolint and a docker daemon,
# and this suite is hermetic. What it holds is the 1 line that makes every check
# above matter — delete the call and the reader is a function nothing invokes,
# with the whole trap wide open and this file still green on its fixtures.
# shellcheck disable=SC2016
# The needle is the literal source line, `$dir` included.
assert_contains "ctl_sh_validate_hands_every_Dockerfile_to_the_reader" \
  "$(cat "$ROOT_CTL")" 'zsh_username_run_references "$dir/Dockerfile"' \
  "cmd_validate walks BUILD_ORDER and reports what this reader returns, naming the file" \
  "without that call the gate is dead text and only a fixture would ever exercise the reader"

test_summary "$TEST_NAME"
