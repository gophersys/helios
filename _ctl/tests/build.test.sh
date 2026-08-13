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
#   2. `build` never asked whether its platform was sanctioned at all, so
#      `IMAGE_PLATFORMS=linux/arm64 bash base/ctl.sh build` really did build and
#      tag an arm64 image, while `push` refused the same list. A guard on the
#      publish path only is a guard a developer walks around without knowing.
#
# So this file asserts the argv, not just the exit status. An exit status of 0
# says a command ran; only the argv says WHICH image was built.
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
SANCTIONED="linux/amd64"

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
  elif ! printf '%s' "$RUN_OUTPUT" | grep -qF -- "$needle"; then
    fail_check "$name" \
      "the build exited ${RUN_STATUS}, but the message never names ${needle}" "$@" \
      "docker was called with:" "${RUN_ARGV:-<no docker invocation>}" \
      "output was:" "$RUN_OUTPUT"
  elif printf '%s' "$RUN_ARGV" | grep -q '^docker build'; then
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

# -------- KEEP: the platform is explicit, and it is the sanctioned one --------
# GREEN from the first run. The deletion this catches is 1 line:
#   docker build --platform "${IMAGE_PLATFORMS}" ...  ->  docker build ...
# Nothing else in the repository reads that argument, so without this check the
# local image silently becomes whatever the host happens to be.
run_build "$BASE_CTL"
assert_equal "build_succeeds_on_the_default_platform_list" "0" "$RUN_STATUS" \
  "output was:" "$RUN_OUTPUT"
assert_contains "build_passes_the_platform_explicitly_to_docker_build" \
  "$RUN_ARGV" "docker build --platform ${SANCTIONED}" \
  "a bare docker build targets the HOST: arm64 on an Apple Silicon machine," \
  "so the image built locally would not be the image that gets published"

# -------- KEEP: 1 platform per docker build --------
# The stimulus is a 2-entry list whose every entry is sanctioned, so the ONLY
# rule that can refuse it is the 1-image rule. A list with 2 different entries
# would be refused by the sanctioned-set rule and prove nothing about this one.
run_build "$BASE_CTL" IMAGE_PLATFORMS="${SANCTIONED},${SANCTIONED}"
assert_refused_without_building "build_refuses_a_list_that_holds_more_than_1_entry" \
  "${SANCTIONED},${SANCTIONED}" \
  "docker build produces exactly 1 image; a 2-entry list has to go through push"

# -------- NEW: an unsanctioned platform is refused on the BUILD path too --------
run_build "$BASE_CTL" IMAGE_PLATFORMS="linux/arm64"
assert_refused_without_building "build_refuses_linux_arm64_and_names_it" \
  "linux/arm64" \
  "push already refuses this list. A developer who runs build instead must not" \
  "get an arm64 image tagged ghcr.io/gophersys/base:latest on their host."

run_build "$BASE_CTL" IMAGE_PLATFORMS="linux/riscv64"
assert_refused_without_building "build_refuses_linux_riscv64_and_names_it" \
  "linux/riscv64" \
  "the rule is membership of the sanctioned set, not a deny-list of 1 platform"

test_summary "$TEST_NAME"
