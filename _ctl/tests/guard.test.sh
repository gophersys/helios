#!/usr/bin/env bash
#
# _ctl/tests/guard.test.sh — the push guard, driven through the real dispatcher.
#
# Hermetic. A stub `docker` goes first on PATH, so no daemon is contacted, no
# socket is opened and no registry is resolved. Everything else is real: the
# real base/ctl.sh, the real _ctl/lib.sh, the real guard.
#
# The guard is entered through `push`, never by calling a function by name. The
# guard is being SPLIT in this feature, so its internal function names change;
# the verb does not. A test that named the function would be testing the shape
# of the refactor instead of the behaviour that must survive it.
#
# 2 groups of check, and they are not the same kind of thing:
#
#   NEW      an unsanctioned platform must be refused, and the message must
#            name the platform. Red today: the guard has no idea what
#            "sanctioned" means, so it accepts linux/arm64 and pushes.
#
#   KEEP     4 conditions that have nothing to do with arm64 and are the only
#            protection `push` has: an empty platform list, buildx absent, no
#            active builder, a builder that cannot emulate a required platform.
#            These are GREEN from the first run, and that is stated rather than
#            faked. Their power is proved by a counter-stimulus: each one flips
#            exactly 1 variable away from a baseline that is proven to exit 0
#            in the same run, so a check that had stopped discriminating would
#            show up as a baseline that also passes... and then as an identical
#            pass for the stimulus, which the pairing makes visible.
#
# The list of platforms reaches the library through the environment. That is
# how MULTI_ARCH_PLATFORMS works today (`: "${VAR:=default}"`), and the renamed
# IMAGE_PLATFORMS must keep the same shape or these checks cannot be driven at
# all. That requirement is a contract of the split, not an accident of this
# test.
#
# Usage: bash _ctl/tests/guard.test.sh
#
set -Eeuo pipefail
IFS=$'\n\t'

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
PROJECT_ROOT="$REPO_ROOT"

# shellcheck source-path=SCRIPTDIR
# shellcheck source=../lib.sh
source "$REPO_ROOT/_ctl/lib.sh"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=harness.sh
source "$TESTS_DIR/harness.sh"

TEST_NAME="guard.test.sh"

STUB_BIN="$TESTS_DIR/stubs"
BASE_CTL="$REPO_ROOT/base/ctl.sh"
FIXTURE_CTL="$TESTS_DIR/fixtures/no-platform-list/ctl.sh"

# A builder that emulates everything anyone could ask for. The refusals below
# must therefore come from the POLICY and not from a builder that happened to
# be unable to build the platform.
ALL_PLATFORMS="linux/amd64, linux/arm64, linux/riscv64, linux/386"

RUN_OUTPUT=""
RUN_STATUS=0

# run_push <ctl.sh> [KEY=VALUE ...] — run a real `push` with the stub docker
# first on PATH. Output and status are read from RUN_OUTPUT / RUN_STATUS.
function run_push() {
  local ctl="$1"
  shift
  RUN_STATUS=0
  RUN_OUTPUT="$(env PATH="${STUB_BIN}:${PATH}" "$@" bash "$ctl" push 2>&1)" || RUN_STATUS=$?
}

# assert_refused_naming <check name> <needle> — the refusal and the reason are
# 1 check, not 2. Split in two, the "does the message name it" half passes on
# an ACCEPTED push whenever the accepting log line happens to print the same
# platform string — which is exactly what the first run of this file did. A
# half that cannot fail is worse than no half.
function assert_refused_naming() {
  local name="$1" needle="$2"
  shift 2
  if [[ "$RUN_STATUS" -eq 0 ]]; then
    fail_check "$name" \
      "want: a non-zero exit status, with a message naming ${needle}" \
      "got:  0 — the push was accepted" "$@" "output was:" "$RUN_OUTPUT"
  elif ! grep -qF -- "$needle" <<< "$RUN_OUTPUT"; then
    fail_check "$name" \
      "the push was refused with status ${RUN_STATUS}, but the message never names ${needle}" \
      "$@" "output was:" "$RUN_OUTPUT"
  else
    pass_check "$name"
  fi
}

printf '=== RUN  %s\n' "$TEST_NAME"

# The stub must be usable at all. A stub that is not executable makes the real
# docker win the PATH lookup, and every check below would then be testing the
# host's docker installation.
if [[ -x "$STUB_BIN/docker" ]]; then
  pass_check "the_docker_stub_is_executable"
else
  fail_check "the_docker_stub_is_executable" \
    "not executable: ${STUB_BIN}/docker" \
    "without it the real docker answers, and nothing below is hermetic"
fi

# -------- baseline: a sanctioned list on a capable builder reaches the push --------
# Every KEEP check below is this run with 1 variable changed. If this baseline
# ever fails, no refusal check underneath it means anything.
run_push "$BASE_CTL" \
  IMAGE_PLATFORMS="linux/amd64" \
  STUB_BUILDER_PLATFORMS="$ALL_PLATFORMS"
assert_equal "baseline_a_sanctioned_list_reaches_the_push" "0" "$RUN_STATUS" \
  "output was:" "$RUN_OUTPUT"
assert_contains "baseline_reached_the_stub_buildx_build" "$RUN_OUTPUT" \
  "no daemon was contacted"

# -------- NEW: an unsanctioned platform is refused, by name --------
run_push "$BASE_CTL" \
  IMAGE_PLATFORMS="linux/amd64,linux/arm64" \
  STUB_BUILDER_PLATFORMS="$ALL_PLATFORMS"
assert_refused_naming "push_refuses_linux_arm64_and_names_it" "linux/arm64" \
  "IMAGE_PLATFORMS was linux/amd64,linux/arm64 and the builder could emulate both," \
  "so the only thing that may refuse this push is the sanctioned-platform rule."

run_push "$BASE_CTL" \
  IMAGE_PLATFORMS="linux/amd64,linux/riscv64" \
  STUB_BUILDER_PLATFORMS="$ALL_PLATFORMS"
assert_refused_naming "push_refuses_linux_riscv64_and_names_it" "linux/riscv64" \
  "the rule is membership of the sanctioned set, not a deny-list of 1 platform"

# -------- KEEP 1: an empty platform list --------
# Counter-stimulus first: the same fixture, list intact, must reach the push.
run_push "$FIXTURE_CTL" \
  UNSET_PLATFORM_LIST="0" \
  STUB_BUILDER_PLATFORMS="$ALL_PLATFORMS"
assert_equal "counter_stimulus_fixture_with_a_platform_list_reaches_the_push" "0" "$RUN_STATUS" \
  "output was:" "$RUN_OUTPUT"

run_push "$FIXTURE_CTL" \
  UNSET_PLATFORM_LIST="1" \
  STUB_BUILDER_PLATFORMS="$ALL_PLATFORMS"
assert_refused_naming "push_refuses_an_empty_platform_list_and_says_so" "empty"

# -------- KEEP 2: buildx is absent --------
# 127 and not 1. The tool gate of this repository answers a missing tool with
# 127, and a caller that reads the status tells "you have no buildx" apart from
# "your platforms are wrong".
run_push "$BASE_CTL" \
  IMAGE_PLATFORMS="linux/amd64" \
  STUB_BUILDER_PLATFORMS="$ALL_PLATFORMS" \
  STUB_BUILDX_VERSION_STATUS="1"
assert_refused_naming "push_refuses_when_buildx_is_absent_and_names_buildx" "buildx"
assert_equal "push_exits_127_when_buildx_is_absent" "127" "$RUN_STATUS" \
  "127 is the tool-gate status of this repository; 1 would read as a policy refusal" \
  "output was:" "$RUN_OUTPUT"

# -------- KEEP 3: no active buildx builder --------
run_push "$BASE_CTL" \
  IMAGE_PLATFORMS="linux/amd64" \
  STUB_BUILDER_PLATFORMS="$ALL_PLATFORMS" \
  STUB_BUILDX_INSPECT_STATUS="1"
assert_refused_naming "push_refuses_when_no_buildx_builder_is_active" "builder"

# -------- KEEP 4: the builder cannot emulate a required platform --------
run_push "$BASE_CTL" \
  IMAGE_PLATFORMS="linux/amd64" \
  STUB_BUILDER_PLATFORMS="linux/386"
assert_refused_naming "push_refuses_a_builder_that_offers_only_linux_386" "linux/amd64"

test_summary "$TEST_NAME"
