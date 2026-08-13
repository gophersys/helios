#!/usr/bin/env bash
#
# _ctl/tests/tripwire.test.sh — the retired platform-variable name.
#
# IMAGE_PLATFORMS was called MULTI_ARCH_PLATFORMS until arm64 was dropped. Both
# names now hold the same string, so a caller that still sets the old one gets
# the right platform BY ACCIDENT and nothing else in the repository would ever
# report the missed rename. The library therefore refuses to load at all when
# the retired name is set.
#
# The mechanism was sound and completely untested: deleting it left 25 checks
# green. This file is the regression net.
#
# It drives the tripwire from the OUTSIDE, with an environment variable, and
# never by editing the library. That is not only ownership: the library cannot
# contain the retired name as a literal, because platform-policy.test.sh
# forbids exactly that token on the build path — the same name check that finds
# a missed rename would otherwise find the tripwire itself.
#
# Every check here is a CONSERVATION guard: all of them are green from the
# first run, and that is stated rather than faked. Their power is proved by a
# counter-stimulus in the same run — the identical command with the retired
# variable absent exits 0 and calls no docker at all.
#
# `help` is the verb on purpose. It reads no file, starts no container and
# needs no tool, so a refusal can only have come from the library while it
# loaded, which is where a rename check has to fire.
#
# Usage: bash _ctl/tests/tripwire.test.sh
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

TEST_NAME="tripwire.test.sh"

STUB_BIN="$TESTS_DIR/stubs"
BASE_CTL="$REPO_ROOT/base/ctl.sh"
ROOT_CTL="$REPO_ROOT/ctl.sh"

# The retired name, spelled out here because this file is not on the build path
# the token check polices, and a test for a name must contain the name.
RETIRED_NAME="MULTI_ARCH_PLATFORMS"
CURRENT_NAME="IMAGE_PLATFORMS"

RUN_OUTPUT=""
RUN_STATUS=0
RUN_ARGV=""

# run_ctl <script> <verb> [KEY=VALUE ...] — the stub docker goes first on PATH
# even though these verbs need no docker, so that an unexpected docker call is
# recorded instead of reaching a daemon.
function run_ctl() {
  local script="$1" verb="$2"
  shift 2
  local log
  log="$(mktemp)"
  RUN_STATUS=0
  RUN_OUTPUT="$(env PATH="${STUB_BIN}:${PATH}" STUB_DOCKER_LOG="$log" "$@" bash "$script" "$verb" 2>&1)" || RUN_STATUS=$?
  RUN_ARGV="$(cat "$log")"
  rm -f "$log"
}

# assert_tripwire_fired <check name> [evidence...] — non-zero, the retired name
# reported, and the name to use instead. 1 check: a status alone does not tell
# a caller which variable to rename, and this message is the only place they
# find out.
function assert_tripwire_fired() {
  local name="$1"
  shift
  if [[ "$RUN_STATUS" -eq 0 ]]; then
    fail_check "$name" "want: a non-zero exit status" \
      "got:  0 — the library loaded with the retired variable set" "$@" \
      "output was:" "$RUN_OUTPUT"
  elif ! printf '%s' "$RUN_OUTPUT" | grep -qF -- "$RETIRED_NAME"; then
    fail_check "$name" \
      "the run exited ${RUN_STATUS} but never names ${RETIRED_NAME}" "$@" \
      "output was:" "$RUN_OUTPUT"
  elif ! printf '%s' "$RUN_OUTPUT" | grep -qF -- "$CURRENT_NAME"; then
    fail_check "$name" \
      "the run named ${RETIRED_NAME} but not ${CURRENT_NAME}, so it never says what to rename it to" \
      "$@" "output was:" "$RUN_OUTPUT"
  else
    pass_check "$name"
  fi
}

printf '=== RUN  %s\n' "$TEST_NAME"

# -------- the counter-stimulus, first --------
# The same command with the retired variable absent. If this ever fails, every
# refusal below is meaningless, because the command would be failing anyway.
run_ctl "$BASE_CTL" help
assert_equal "counter_stimulus_help_succeeds_without_the_retired_variable" "0" "$RUN_STATUS" \
  "output was:" "$RUN_OUTPUT"
assert_equal "counter_stimulus_help_calls_no_docker" "" "$RUN_ARGV" \
  "help reads no file and needs no tool, so a refusal below can only come from" \
  "the library while it loads — which is where a rename check has to fire"

# -------- KEEP: the retired name is refused at load time --------
run_ctl "$BASE_CTL" help "${RETIRED_NAME}=linux/amd64"
assert_tripwire_fired "the_retired_variable_name_is_refused_at_load_time" \
  "the value is the CORRECT platform on purpose: the point is the missed rename," \
  "not a wrong platform, and both names now hold the same string"

# -------- KEEP: an empty value fires too --------
# The subtle one. A test written as `[[ -n "$VAR" ]]`, or a default written as
# `: "${VAR:=...}"`, treats an empty value as absent — so the caller that
# exported the retired name and left it empty would sail through the very check
# that exists to catch them.
run_ctl "$BASE_CTL" help "${RETIRED_NAME}="
assert_tripwire_fired "an_empty_retired_variable_is_refused_as_well" \
  "set-but-empty must fire: the name is what is retired, not the value"

# -------- KEEP: the repository-root script refuses it too --------
# The root script sources the same library and then delegates to a per-image
# ctl.sh, so a caller who exports the retired name once must be stopped at the
# first script that loads the library, not somewhere deep in a delegation.
run_ctl "$ROOT_CTL" list "${RETIRED_NAME}=linux/amd64"
assert_tripwire_fired "the_repository_root_script_refuses_it_too" \
  "list prints a table and touches nothing, so this too is a load-time refusal"

test_summary "$TEST_NAME"
