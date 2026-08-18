#!/usr/bin/env bash
#
# _ctl/tests/build.test.sh — the LOCAL build path.
#
# Hermetic: a stub `docker` first on PATH, and every argv it receives is
# recorded. No daemon, no network, no image.
#
# `build` was the hole in the first suite. Nothing invoked it, so 2 defects
# lived under 25 green checks:
#
#   1. the explicit `--platform` could be deleted and no gate noticed, even
#      though the plan called it the most likely silent breakage this feature
#      closes — a bare `docker build` targets the HOST, which is arm64 on an
#      Apple Silicon machine, so the local image is not the published one;
#   2. `build` never asked whether its platform was sanctioned at all, so an
#      unsanctioned IMAGE_PLATFORMS really did build and tag an image, while
#      `push` refused the same list. A guard on the publish path only is a guard
#      a developer walks around without knowing.
#
# So this file asserts the argv, not just the exit status. An exit status of 0
# says a command ran; only the argv says WHICH image was built.
#
# ============================================================================
# WHAT THE 2-PLATFORM SET DID TO THIS FILE
# ============================================================================
#
# A bare `bash base/ctl.sh build` USED to succeed, because the default list held
# 1 platform. It cannot any more and it must not: `docker build` produces
# exactly 1 image, the default is now the 2-platform sanctioned set, and the verb
# refuses a list of more than 1 by design. So the old
# `build_succeeds_on_the_default_platform_list` asserted a contract that no
# longer exists, and flipping its literal would have kept a green check over a
# command nobody can run.
#
# The contract this file holds instead is the one a developer meets:
#
#   bash base/ctl.sh build                      -> REFUSED, naming the 2-entry list
#   IMAGE_PLATFORMS=linux/amd64 ... build       -> builds, --platform linux/amd64
#   IMAGE_PLATFORMS=linux/arm64 ... build       -> builds, --platform linux/arm64
#
# The arm64 row is the inversion. `build_refuses_linux_arm64_and_names_it` was a
# real rule while the set held 1 platform; arm64 is sanctioned now, the Mac mini
# builds it natively, and a test that still refused it would forbid the local
# loop this widening exists to serve. The refusal checks moved to platforms that
# are genuinely outside the set.
#
# Usage: bash _ctl/tests/build.test.sh
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

TEST_NAME="build.test.sh"

STUB_BIN="$TESTS_DIR/stubs"
BASE_CTL="$REPO_ROOT/base/ctl.sh"

# The policy, written as a literal for the same reason platform-policy.test.sh
# writes it: a test that reads the value out of the implementation agrees with
# a wrong value too.
SANCTIONED="linux/amd64,linux/arm64"

# Its members, named one at a time. `build` takes exactly 1, so every accepting
# case below names one of these and no list.
AMD64="linux/amd64"
ARM64="linux/arm64"

# Outside the set. riscv64 is an architecture no node of ours runs and no digest
# row answers for. The bare `linux/arm` is the near-miss: it is a PREFIX of the
# sanctioned linux/arm64, so a guard that tested membership with a substring
# instead of a comma-fenced comparison would accept it.
UNSANCTIONED="linux/riscv64"
UNSANCTIONED_PREFIX_OF_A_MEMBER="linux/arm"

RUN_OUTPUT=""
RUN_STATUS=0
RUN_ARGV=""

# run_build <ctl.sh> [KEY=VALUE ...] — a real `build` against the stub docker.
# RUN_ARGV holds every docker invocation the run made, 1 per line, which is how
# a check tells "it refused" apart from "it built the wrong thing quietly".
function run_build() {
  local ctl="$1"
  shift
  local log
  log="$(mktemp)"
  RUN_STATUS=0
  RUN_OUTPUT="$(env PATH="${STUB_BIN}:${PATH}" STUB_DOCKER_LOG="$log" "$@" bash "$ctl" build 2>&1)" || RUN_STATUS=$?
  RUN_ARGV="$(cat "$log")"
  rm -f "$log"
}

# assert_refused_without_building <check name> <needle> [evidence...]
#
# 3 conditions, 1 check, on purpose: a non-zero status, the offending platform
# named, and NO `docker build` invocation. As separate checks the first 2 pass
# on runs that have nothing to do with the rule — an unrelated abort also exits
# non-zero, and the info line of an ACCEPTED build prints the platform string it
# is about to build. The third is the one that cannot be faked: if docker build
# ran, an image was built and tagged whatever the status said afterwards.
function assert_refused_without_building() {
  local name="$1" needle="$2"
  shift 2
  if [[ "$RUN_STATUS" -eq 0 ]]; then
    fail_check "$name" \
      "want: a non-zero exit status, with a message naming ${needle}" \
      "got:  0 — the build was accepted" "$@" \
      "docker was called with:" "${RUN_ARGV:-<no docker invocation>}" \
      "output was:" "$RUN_OUTPUT"
  elif ! grep -qF -- "$needle" <<< "$RUN_OUTPUT"; then
    fail_check "$name" \
      "the build exited ${RUN_STATUS}, but the message never names ${needle}" "$@" \
      "docker was called with:" "${RUN_ARGV:-<no docker invocation>}" \
      "output was:" "$RUN_OUTPUT"
  elif grep -q '^docker build' <<< "$RUN_ARGV"; then
    fail_check "$name" \
      "the build exited ${RUN_STATUS} and said the right thing, but it had ALREADY built:" \
      "$RUN_ARGV" "$@" \
      "a refusal that runs docker build first has tagged an image nobody sanctioned"
  else
    pass_check "$name"
  fi
}

printf '=== RUN  %s\n' "$TEST_NAME"

if [[ -x "$STUB_BIN/docker" ]]; then
  pass_check "the_docker_stub_is_executable"
else
  fail_check "the_docker_stub_is_executable" \
    "not executable: ${STUB_BIN}/docker" \
    "without it the real docker answers, and nothing below is hermetic"
fi

# -------- the default list is the sanctioned set, and build cannot take it --------
# The stimulus is a run with NO IMAGE_PLATFORMS in the environment, so the value
# under test is the one resolve_image_platforms produces for `base`: no
# `platforms` key in images.yaml, therefore SANCTIONED_PLATFORMS. This is the
# 1 check that reads the DEFAULT rather than a value the test handed in, and it
# is what makes "the local loop must name its platform" a checked statement
# instead of a sentence in a document.
run_build "$BASE_CTL"
assert_refused_without_building "build_refuses_the_default_platform_list_and_names_it" \
  "$SANCTIONED" \
  "the default is the 2-platform sanctioned set and docker build makes exactly 1 image," \
  "so a bare build must fail NAMING the list a developer has to choose from —" \
  "IMAGE_PLATFORMS=linux/arm64 bash base/ctl.sh build"

# -------- KEEP: the platform is explicit, and it is the one that was named --------
# The deletion this catches is 1 line:
#   docker build --platform "${IMAGE_PLATFORMS}" ...  ->  docker build ...
# Nothing else in the repository reads that argument, so without this check the
# local image silently becomes whatever the host happens to be.
run_build "$BASE_CTL" IMAGE_PLATFORMS="$AMD64"
assert_equal "build_succeeds_when_the_developer_names_1_sanctioned_platform" "0" "$RUN_STATUS" \
  "output was:" "$RUN_OUTPUT"
assert_contains "build_passes_the_platform_explicitly_to_docker_build" \
  "$RUN_ARGV" "docker build --platform ${AMD64}" \
  "a bare docker build targets the HOST: arm64 on an Apple Silicon machine," \
  "so the image built locally would not be the image that gets published"

# -------- linux/arm64 is SANCTIONED now, and build must serve it --------
# The inversion, and the reason it is 2 checks rather than a flipped literal.
# The status says the guard lets arm64 through; the argv says the value reached
# `--platform` unchanged. A build that accepted arm64 and then passed amd64 to
# docker would satisfy the first alone, and it is the exact defect the mislabelled
# arm64 variant was made of: a label that did not describe the bytes.
run_build "$BASE_CTL" IMAGE_PLATFORMS="$ARM64"
assert_equal "build_accepts_linux_arm64_now_that_it_is_sanctioned" "0" "$RUN_STATUS" \
  "arm64 is in SANCTIONED_PLATFORMS and the mini builds it natively; a build that" \
  "refused it would forbid the local loop the widening exists to serve" \
  "output was:" "$RUN_OUTPUT"
assert_contains "build_passes_linux_arm64_explicitly_to_docker_build" \
  "$RUN_ARGV" "docker build --platform ${ARM64}" \
  "this is what proves the value is THREADED rather than hardcoded: the amd64 check" \
  "above passes on a build that ignores IMAGE_PLATFORMS and always writes linux/amd64"

# -------- KEEP: 1 platform per docker build --------
# The stimulus is a 2-entry list whose every entry is sanctioned, so the ONLY
# rule that can refuse it is the 1-image rule. The order is REVERSED against the
# default so this case cannot be satisfied by whatever refuses the default: the
# 2 arrive by different routes, this one through the environment and that one
# through resolve_image_platforms.
run_build "$BASE_CTL" IMAGE_PLATFORMS="${ARM64},${AMD64}"
assert_refused_without_building "build_refuses_a_list_that_holds_more_than_1_entry" \
  "${ARM64},${AMD64}" \
  "docker build produces exactly 1 image; a 2-entry list has to go through push"

# -------- an unsanctioned platform is refused on the BUILD path too --------
run_build "$BASE_CTL" IMAGE_PLATFORMS="$UNSANCTIONED"
assert_refused_without_building "build_refuses_linux_riscv64_and_names_it" \
  "$UNSANCTIONED" \
  "push already refuses this list. A developer who runs build instead must not get" \
  "an unsanctioned image tagged ghcr.io/gophersys/base:latest on their host," \
  "and the rule is membership of the sanctioned set, not a deny-list of 1 platform"

run_build "$BASE_CTL" IMAGE_PLATFORMS="$UNSANCTIONED_PREFIX_OF_A_MEMBER"
assert_refused_without_building "build_refuses_a_platform_that_is_only_a_prefix_of_a_sanctioned_one" \
  "$UNSANCTIONED_PREFIX_OF_A_MEMBER" \
  "linux/arm is a PREFIX of the sanctioned linux/arm64 and is a platform of its own," \
  "so a membership test written as a substring search would build 32-bit arm and" \
  "tag it with the published name"

# -------- a DECLARED but empty list is a caller naming nothing --------
# `IMAGE_PLATFORMS=` is not an absent variable. The library tests for the name
# being DECLARED (`${VAR+declared}`) and not for it holding anything, precisely
# so this case reaches the refusal: read as unset, it would be replaced by the
# manifest's set and a caller that named an empty list would get a build it never
# asked for. That was a real defect, found and fixed, and this pins it.
run_build "$BASE_CTL" IMAGE_PLATFORMS=""
assert_refused_without_building "build_refuses_a_declared_but_empty_platform_list" \
  "empty" \
  "an empty value must not fall back to the default: the caller named a list, the" \
  "list has no entries, and there is no platform to build"

test_summary "$TEST_NAME"
