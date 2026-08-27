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
#   MEMBERSHIP  a platform outside the sanctioned set must be refused, and the
#               message must NAME the platform. The set holds 2 platforms now,
#               so the stimulus is a platform that is genuinely outside it:
#               linux/riscv64, and the bare linux/arm, which is a PREFIX of the
#               sanctioned linux/arm64 and would slip past a substring test.
#               `push_refuses_linux_arm64_and_names_it` used to stand here and
#               is INVERTED rather than deleted — arm64 is sanctioned, the mini
#               builds it natively, and the check that replaces it asserts a
#               2-platform list REACHES the push.
#
#   KEEP        4 conditions that have nothing to do with membership and are the
#               only other protection `push` has: an empty platform list, buildx
#               absent, no active builder, a builder that cannot emulate a
#               required platform. Their power is proved by a counter-stimulus:
#               each one flips exactly 1 variable away from a baseline that is
#               proven to exit 0 in the same run, so a check that had stopped
#               discriminating would show up as a baseline that also passes...
#               and then as an identical pass for the stimulus, which the
#               pairing makes visible.
#
# The list of platforms reaches the library through the environment, and the
# library tests whether the name was DECLARED rather than whether it holds
# anything (`${VAR+declared}`). That distinction is a checked rule here and not
# an implementation detail: `IMAGE_PLATFORMS=` is a caller naming an EMPTY list,
# and read as "unset" it would be replaced by the manifest's set — the refusal
# for an empty list could then never fire from the environment at all. It was a
# real defect, found and fixed, and the check below pins it.
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

# -------- the full sanctioned set REACHES the push --------
# The inversion. `push_refuses_linux_arm64_and_names_it` stood here while the
# set held 1 platform; publishing both architectures is the whole point of the
# widening, so the 2-entry list is now the case that must be ACCEPTED. It is
# also the counter-stimulus for every refusal below: a guard stuck on would
# refuse this too, and each refusal check would then pass for a reason that has
# nothing to do with the rule it names.
run_push "$BASE_CTL" \
  IMAGE_PLATFORMS="linux/amd64,linux/arm64" \
  STUB_BUILDER_PLATFORMS="$ALL_PLATFORMS"
assert_equal "push_accepts_the_full_sanctioned_set" "0" "$RUN_STATUS" \
  "both entries are sanctioned and the builder offers both, so nothing may refuse this" \
  "output was:" "$RUN_OUTPUT"
assert_contains "push_passes_the_full_sanctioned_set_to_buildx" "$RUN_OUTPUT" \
  "linux/amd64,linux/arm64" \
  "the log line names the list it is about to build; a push that silently dropped" \
  "the arm64 half would exit 0 and publish a single-platform manifest"

# -------- an unsanctioned platform is refused, by name --------
run_push "$BASE_CTL" \
  IMAGE_PLATFORMS="linux/amd64,linux/riscv64" \
  STUB_BUILDER_PLATFORMS="$ALL_PLATFORMS"
assert_refused_naming "push_refuses_linux_riscv64_and_names_it" "linux/riscv64" \
  "the builder could emulate riscv64, so the only thing that may refuse this push is" \
  "the sanctioned-platform rule, and the rule is MEMBERSHIP of the set rather than a" \
  "deny-list of 1 platform"

run_push "$BASE_CTL" \
  IMAGE_PLATFORMS="linux/amd64,linux/arm" \
  STUB_BUILDER_PLATFORMS="$ALL_PLATFORMS"
assert_refused_naming "push_refuses_a_platform_that_is_only_a_prefix_of_a_sanctioned_one" \
  "linux/arm" \
  "linux/arm is a 32-bit arm platform of its own AND a prefix of the sanctioned" \
  "linux/arm64, so a membership test written as a substring search would publish it"

# -------- a DECLARED but empty list, straight from the environment --------
# Distinct from the fixture case below, and it is the half that broke. The
# fixture unsets the variable inside a dispatcher; this one DECLARES it empty
# from outside. Read with `:-` instead of `+`, the empty value looks unset, the
# manifest's set replaces it, and the push goes out on a list the caller never
# named while the refusal for an empty list sits unreachable.
run_push "$BASE_CTL" \
  IMAGE_PLATFORMS="" \
  STUB_BUILDER_PLATFORMS="$ALL_PLATFORMS"
assert_refused_naming "push_refuses_a_declared_but_empty_platform_list_from_the_environment" \
  "empty" \
  "IMAGE_PLATFORMS= is a caller naming an empty list, not a caller naming nothing"

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
