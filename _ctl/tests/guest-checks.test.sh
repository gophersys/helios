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
# ============================================================================
# THE OTHER TABLE: ABSENT_TABLE (ledger #103)
# ============================================================================
#
#   ABSENT_TABLE  1 row per binary that must NOT be in the image, `<PIN>|<binary>`.
#                 The driver builds it from every row it classifies
#                 `not-in-this-image:<binary>[,<binary>]`, so 1 pin with 2 probes
#                 arrives as 2 rows.
#
#   the binary is absent  exit 0, and the output NAMES the pin and the binary.
#                         The naming is the whole check: an absence probe that
#                         ran and said nothing is indistinguishable from a probe
#                         that never ran, and this class spent its whole life so
#                         far being exactly that.
#   the binary resolves   exit non-zero, naming the PIN, the BINARY and the PATH
#                         it was found at. The path is what turns "terraform is
#                         present" into a defect somebody can act on: it names
#                         the layer that installed it.
#   an empty binary       exit non-zero, naming the pin. A row with nothing to
#                         probe is a check that cannot fail, and the driver can
#                         emit one — its own reader drops a trailing empty field
#                         inside a `$( )`, so `not-in-this-image:aws,` reaches
#                         here as `AWS_CLI_VERSION|`.
#   the table is empty    exit 0, deliberately. This file is run with no
#                         ABSENT_TABLE by the pull request gate, and the driver
#                         REFUSES an image whose whole table names no probe — so
#                         the "nothing to probe" refusal belongs there, where the
#                         image is known, and not here.
#
# Until these cases existed the group was reachable by no test at all: the
# comparator half was checked on the host and the absence half only ever ran
# inside a container, after a build, on the publish path.
#
# ============================================================================
# THE THIRD ENVIRONMENT CONTRACT: SMOKE_IMAGE, AND THE MARKER
# ============================================================================
#
#   SMOKE_IMAGE   the image name the DRIVER was asked about. The guest holds
#                 GOPHERSYS_DEVCONTAINER — which every image of this repository
#                 exports as its OWN name — against it.
#
#   they agree    exit 0, and the output NAMES the image. Same reason the
#                 absence half names its rows: a marker check that ran and said
#                 nothing is indistinguishable from one that never ran.
#   they differ   exit non-zero, naming BOTH values. "the marker is wrong" sends
#                 the reader to guess which of the 2 is; the pair says whether
#                 the image lied about itself or the driver smoked the wrong ref.
#   SMOKE_IMAGE
#   is empty      exit 0 and check NOTHING, deliberately. That is how the pull
#                 request gate runs this file — with no image at all — and the
#                 host driver always sends the name.
#
# This check runs for EVERY image, which is what makes it worth cases of its
# own: it lived inside checks_content_cloud asserting the literal `cloud`, so 4
# of the 6 images asserted no marker, and the first image to inherit that group
# would have had to lie about its own name to pass. The stimulus below uses
# `hardware` because it is the image that made the old shape untenable — it
# inherits content-cloud and is not cloud.
#
# The wrong-marker case is the one the record demands. A mislabelled image is
# not hypothetical here: an arm64 image was published carrying an amd64
# userland, and every check on it passed.
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

# The image the marker cases state a world about, and the name a WRONG marker
# carries. Both are literals: a case that read the name out of the driver would
# agree with any name, including the one the driver got wrong.
MARKER_IMAGE="hardware"
MARKER_WRONG="cloud"

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

# The 1-row version of it, for the absence cases that need a tool to be present
# WITHOUT the comparator asserting the same tool in the same run. A pin cannot
# honestly be `asserted` and `not-in-this-image` at once, and a stimulus that
# states an impossible world proves nothing about the real one.
MINIMAL_TABLE="HNSLINT_VERSION|0.1.0|hnslint --version"

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
    if ! grep -qF -- "$needle" <<< "$GUEST_OUTPUT"; then
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

# assert_passed_naming <check name> <needle> [needle...]
#
# The mirror of assert_failed_naming, and it exists for the same reason. A bare
# "it exited 0" is the verdict an absence probe that ran NOTHING also produces —
# an empty ABSENT_TABLE is a legal input to this file and exits 0 — so the status
# alone cannot tell a check that passed from a check that never happened. The
# NAMES are what say the row was read.
function assert_passed_naming() {
  local name="$1"
  shift
  local needle missing_names=""
  for needle in "$@"; do
    if ! grep -qF -- "$needle" <<< "$GUEST_OUTPUT"; then
      missing_names="${missing_names:+${missing_names}
}${needle}"
    fi
  done
  if [[ "$GUEST_STATUS" -ne 0 ]]; then
    fail_check "$name" \
      "want: exit 0" \
      "got:  ${GUEST_STATUS}" \
      "output was:" "$GUEST_OUTPUT"
  elif [[ -n "$missing_names" ]]; then
    fail_check "$name" \
      "the guest exited 0, and its output names none of:" \
      "$missing_names" \
      "a probe that reported nothing cannot be told apart from a probe that never ran" \
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

# -------- 5. the absence half: what the image must NOT carry --------
#
# 2 rows for 1 pin, which is the shape the driver produces from
# `RUST_CHANNEL|not-in-this-image:rustc,cargo`. Both must be reported: a loop
# that reads the first row and stops gives 1 checked probe and 1 that is only
# believed, and neither the status nor a single name would say which.
run_guest "$MATCHING_TABLE" \
  "ABSENT_TABLE=RUST_CHANNEL|${ABSENT_TOOL}
RUST_CHANNEL|${ABSENT_TOOL}-cargo"
# Every argument after the check name is a NEEDLE — this helper takes no
# evidence lines, the way assert_failed_naming above takes none.
assert_passed_naming "every_absent_binary_passes_and_names_the_pin_and_the_binary" \
  "RUST_CHANNEL" "${ABSENT_TOOL}" "${ABSENT_TOOL}-cargo"

# The leak. This is the measured defect of ledger #103, staged with the stub
# PATH: the table says the image does not install the tool, and the tool is
# right there. On 2026-08-17 ghcr.io/gophersys/base:latest carried
# /usr/local/bin/terraform and /usr/local/bin/aws against 2 rows that said
# not-in-this-image, and nothing in this repository could report it.
#
# `gh` is the leaked binary because the stub PATH really holds it, and the
# comparator table for this run does NOT assert gh: a pin cannot be `asserted`
# and `not-in-this-image` in the same table.
run_guest "$MINIMAL_TABLE" "ABSENT_TABLE=GH_VERSION|gh"
assert_failed_naming "a_binary_that_leaked_in_fails_and_names_the_pin_the_binary_and_the_path" \
  "GH_VERSION" "gh" "${STUB_TOOLS}/gh"

# A row with no binary. The driver can emit one: its class_probes reader pipes
# through `tr` inside a `$( )`, which strips the trailing empty field, so
# `not-in-this-image:aws,` arrives here as `AWS_CLI_VERSION|` and 1 probe of that
# row is a check that cannot fail. It must be reported and never skipped.
run_guest "$MINIMAL_TABLE" "ABSENT_TABLE=AWS_CLI_VERSION|"
assert_failed_naming "an_absence_row_with_no_binary_fails_and_names_the_pin" \
  "AWS_CLI_VERSION" "no binary"

# -------- 6. the marker: the image says which image it is --------
#
# The 3 cases are the 3 branches of run_devcontainer_marker, and each one is a
# different verdict. Taken alone the agreeing case proves nothing: an
# unconditional `return 0` passes it, and so does a marker check that was
# deleted. It is the DISAGREEING case that has to fail, and the empty case that
# has to stay quiet, before the agreeing one means anything.

# The image is what the driver smoked.
run_guest "$MINIMAL_TABLE" "SMOKE_IMAGE=${MARKER_IMAGE}" "GOPHERSYS_DEVCONTAINER=${MARKER_IMAGE}"
assert_passed_naming "a_marker_that_matches_passes_and_names_the_image" \
  "GOPHERSYS_DEVCONTAINER" "$MARKER_IMAGE"

# The image lies about itself. This is the shape a child image takes when it
# inherits its parent's ENV and never overrides it: `hardware` FROMs `cloud`, so
# a missing `ENV GOPHERSYS_DEVCONTAINER=hardware` leaves the parent's value in
# place and every other check in this repository still passes.
run_guest "$MINIMAL_TABLE" "SMOKE_IMAGE=${MARKER_IMAGE}" "GOPHERSYS_DEVCONTAINER=${MARKER_WRONG}"
assert_failed_naming "a_marker_that_names_another_image_fails_and_names_both" \
  "GOPHERSYS_DEVCONTAINER" "$MARKER_WRONG" "$MARKER_IMAGE"

# The marker is absent entirely — the shape of an image that never exported it.
# An empty value must not read as "no image was named", which is the branch that
# turns the whole check off.
run_guest "$MINIMAL_TABLE" "SMOKE_IMAGE=${MARKER_IMAGE}" "GOPHERSYS_DEVCONTAINER="
assert_failed_naming "an_absent_marker_fails_and_names_the_image_the_driver_smoked" \
  "GOPHERSYS_DEVCONTAINER" "$MARKER_IMAGE"

# No image at all: the pull request gate's own shape. It must exit 0 AND say
# nothing about a marker — a run that reported one here would be asserting
# against an image that does not exist.
run_guest "$MINIMAL_TABLE"
if [[ "$GUEST_STATUS" -ne 0 ]]; then
  fail_check "no_SMOKE_IMAGE_runs_no_marker_check" \
    "want: exit 0 — this file runs with no image in the pull request gate" \
    "got:  ${GUEST_STATUS}" \
    "output was:" "$GUEST_OUTPUT"
elif grep -qF -- "GOPHERSYS_DEVCONTAINER" <<< "$GUEST_OUTPUT"; then
  fail_check "no_SMOKE_IMAGE_runs_no_marker_check" \
    "the guest exited 0 and reported a marker while no image was named:" \
    "$GUEST_OUTPUT" \
    "an 'ok' about an image nobody smoked is a green line that read nothing"
else
  pass_check "no_SMOKE_IMAGE_runs_no_marker_check"
fi

test_summary "$TEST_NAME"
