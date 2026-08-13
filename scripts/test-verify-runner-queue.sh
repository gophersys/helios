#!/usr/bin/env bash
# Spec for scripts/verify-runner-queue.sh — the queue rule, not the anchoring.
#
# Run: bash scripts/test-verify-runner-queue.sh            # every case
#      bash scripts/test-verify-runner-queue.sh <name>...  # one case, by name
#      bash scripts/test-verify-runner-queue.sh --list     # the case names
#
# WHAT IS WRONG TODAY
# The verb FAILs a job when queue > execution. Measured on arc-org on
# 2026-08-13, that rule fires on 17 of 36 jobs, and every one of the 17 is a
# false alarm. Starting a runner pod costs a nearly fixed ~10 s, and an arc-org
# job runs for 7 to 10 s, so `queue > execution` is true whenever the work is
# short. The rule compares a fixed cost against a variable one.
#
# THE MODEL THE NEW RULE MUST EXPRESS
#
#   queue = dispatch    fixed cost to start a pod. A property of the pool and
#                       of the image, not of the job.
#         + contention  variable. Waiting for somebody else's job to end.
#
# Alarm on contention only. Estimate dispatch as the FLOOR of the observed
# queue times — the minimum, or a low percentile. NEVER the median: a median
# holds contention inside it, so under load the median rises, and a
# median-based threshold would lift its own alarm level exactly when the pool
# becomes saturated. A job that got a slot at once still paid dispatch, so the
# floor IS dispatch, measured instead of invented. No constant enters the
# script, and the rule follows the pool when the pool or the image gets faster.
#
# The anchoring is NOT under test here and must not move. Two run-level anchors
# were refuted before the jobs-API pair was adopted; see the header of
# verify-runner-queue.sh.
#
# THE CONTRACT THESE CASES PIN
#   C1  exit 0 when no job's queue rises above the dispatch floor by more than
#       the contention margin. exit 1 when at least 1 job does.
#   C2  a flagged job prints on a line that carries FAIL, the job name and
#       `contention=<seconds>s`.
#   C3  the run prints 1 line that carries `dispatch floor`, the estimate as
#       `<seconds>s`, and the word `sample` with the number of jobs behind it.
#   C4  a sample too small to estimate a floor (0 or 1 job) exits 3 and says
#       the sample is too small. It never exits 0, and it never returns a
#       saturation verdict it cannot support. FAIL-NOT-SKIP.
#   C5  the floor is estimated over the WHOLE sample, never per run. A floor
#       measured inside 1 saturated run rises with that run and hides it.
#
# THE MARGIN IS DELIBERATELY NOT PINNED
# These fixtures leave a wide corridor. A floor of 9 s must pass a queue of
# 12 s and must fail a queue of 250 s, so any rule of the form
# `queue > floor * K` with 1.4 <= K <= 27, or `contention > C` with
# 3 s <= C <= 240 s, satisfies every case here. Pick one and say why.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUT="$HERE/verify-runner-queue.sh"
DATA="$HERE/testdata/runner-queue"
ESC="$(printf '\033')"

CASES="
dispatch_overhead_alone_does_not_fire
real_contention_outlier_still_fires
estimator_is_a_floor_not_a_median
uniform_saturation_still_fires
sample_of_one_fails_loudly
sample_of_none_fails_loudly
long_queue_with_long_execution_fires
"

# A missing tool is a failure, never a skip. The subject needs both, and it
# checks for both before it reads a fixture, so an absent one would turn every
# case below into a 127 that says nothing about the rule.
missing=""
for tool in gh jq; do
  command -v "$tool" >/dev/null 2>&1 || missing="${missing:+$missing }$tool"
done
if [ -n "$missing" ]; then
  echo "test-verify-runner-queue: missing required tool(s): $missing" >&2
  exit 127
fi
if [ ! -x "$SUT" ] && [ ! -f "$SUT" ]; then
  echo "test-verify-runner-queue: subject not found: $SUT" >&2
  exit 2
fi

failures=0
case_failures=0
out=""
rc=0

note() { echo "    $*"; }

bad() {
  note "FAIL: $*"
  failures=$((failures + 1))
  case_failures=$((case_failures + 1))
}

# Feed 1 fixture to the subject and keep its REAL exit code. `rc=$?` sits on
# its own line right after the assignment: an assignment from a command
# substitution carries that command's status, and nothing may run between the
# two lines. A pipeline would report the status of its LAST stage instead, and
# that misreading has produced 2 false findings in this repository.
run_fixture() {
  local fixture="$DATA/$1.json"
  if [ ! -f "$fixture" ]; then
    echo "test-verify-runner-queue: fixture missing: $fixture" >&2
    exit 2
  fi
  out="$(RUNNER_QUEUE_FIXTURE="$fixture" bash "$SUT" 2>&1)"
  rc=$?
  out="$(printf '%s\n' "$out" | sed "s/${ESC}\[[0-9;]*m//g")"
}

expect_rc() { # <want> <why>
  if [ "$rc" -eq "$1" ]; then
    return 0
  fi
  bad "exit $rc, want $1 — $2"
  printf '%s\n' "$out" | tail -4 | sed 's/^/      | /'
}

expect_line() { # <extended-regex> <why>
  if printf '%s\n' "$out" | grep -qE "$1"; then
    return 0
  fi
  bad "no line matched /$1/ — $2"
}

expect_no_line() { # <extended-regex> <why>
  if printf '%s\n' "$out" | grep -qE "$1"; then
    bad "a line matched /$1/ and none should — $2"
    printf '%s\n' "$out" | grep -E "$1" | sed 's/^/      | /'
  fi
}

# The sharpest half of the floor-versus-median question. A median estimator
# cannot report a low number on a contended window; a floor estimator must.
expect_floor_at_most() { # <max-seconds> <why>
  local line value
  line="$(printf '%s\n' "$out" | grep -E 'dispatch floor' | head -1)"
  if [ -z "$line" ]; then
    bad "no 'dispatch floor' line in the output — $2 (C3)"
    return 0
  fi
  case "$line" in
    *sample*) : ;;
    *) bad "the 'dispatch floor' line names no sample size: $line (C3)" ;;
  esac
  value="$(printf '%s\n' "$line" | sed -n 's/.*dispatch floor[^0-9]*\([0-9][0-9]*\)s.*/\1/p')"
  if [ -z "$value" ]; then
    bad "the 'dispatch floor' line carries no <N>s figure: $line (C3)"
    return 0
  fi
  if [ "$value" -gt "$1" ]; then
    bad "dispatch floor is ${value}s, want at most ${1}s — $2"
  fi
}

# -------- the cases --------

# 1. The false fire that motivates the change. 36 short arc-org jobs, ~10 s of
# queue against ~8 s of execution. 17 of them have queue > execution and every
# one is dispatch overhead, not saturation. The new rule must stay quiet.
test_dispatch_overhead_alone_does_not_fire() {
  run_fixture dispatch-only
  expect_rc 0 "36 short jobs are dispatch overhead, not contention (C1)"
  # A per-job verdict line carries the run id after the word. The pattern needs
  # that id: the banner of the verb states its own rule and holds the word FAIL
  # too, and an assertion that matches the banner can never go green.
  expect_no_line 'FAIL[[:space:]]+[0-9]{6,}' \
    "no job in a uniformly short window waited for anybody"
  expect_floor_at_most 20 "the floor of a quiet window is the dispatch cost"
}

# 2. The true positive that must survive. The real worst case on this pool:
# run 31531318733 waited 1114 s and then ran for 151 s, among jobs that show a
# 9 s floor. A refinement that silences this is worthless.
test_real_contention_outlier_still_fires() {
  run_fixture contention-outlier
  expect_rc 1 "1114 s of queue on a 9 s floor is contention (C1)"
  expect_line 'FAIL.*contention-outlier' "the outlier must be named (C2)"
  expect_line 'contention-outlier.*contention=[0-9]+s' \
    "the report must separate contention from dispatch (C2)"
  expect_floor_at_most 60 "1 outlier must not drag the floor up with it"
}

# 3. THE DISCRIMINATOR. This case exists for 1 purpose: to make the median
# mistake impossible to make silently. The window holds 14 contended jobs, so
# the median queue is ~600 s while the floor is 9 s. `discriminator-target`
# waited 250 s — far above the floor, far below the median.
#   a floor estimator  flags it (250 s is 27x the dispatch cost)
#   a median estimator does not (250 s is better than typical)
# A test suite that cannot tell the 2 estimators apart has not tested the thing
# that matters.
test_estimator_is_a_floor_not_a_median() {
  run_fixture floor-not-median
  expect_rc 1 "the target waited 27x the dispatch floor (C1)"
  expect_line 'FAIL.*discriminator-target' \
    "a median estimator would call 250 s better than typical (C2)"
  expect_floor_at_most 60 \
    "the median of this window is ~600 s; the floor is 9 s"
}

# 4. Uniform saturation. Every job of run 31700000001 waited about 10 minutes,
# so a floor measured inside that run alone is ~590 s and nothing fires. The
# wide sample around it shows the true floor of 8 s, and all 4 must fire.
# This is the case that proves C5: the floor is a pool property, measured over
# the whole sample, never over the neighbours of 1 run.
test_uniform_saturation_still_fires() {
  run_fixture uniform-saturation
  expect_rc 1 "a fully saturated run must not hide behind its own floor (C1)"
  expect_line 'FAIL.*saturated-1' "the whole run waited, so the whole run fires"
  expect_line 'FAIL.*saturated-2' "the whole run waited, so the whole run fires"
  expect_line 'FAIL.*saturated-3' "the whole run waited, so the whole run fires"
  expect_line 'FAIL.*saturated-4' "the whole run waited, so the whole run fires"
  expect_floor_at_most 60 "the floor comes from the wide sample (C5)"
}

# 5a. 1 job is not a sample. The floor cannot be estimated from it, so no
# verdict is available. Today the ratio rule answers anyway, from nothing.
test_sample_of_one_fails_loudly() {
  run_fixture sample-of-one
  expect_rc 3 "1 job cannot separate dispatch from contention (C4)"
  expect_line 'sample.*(too small|too few)|(too small|too few).*sample' \
    "the message must name what is missing (C4)"
}

# 5b. An empty window. Today this exits 0 and checks nothing, which is the
# exact defect this verb exists to expose: a green result that measured
# nothing is believed.
test_sample_of_none_fails_loudly() {
  run_fixture sample-of-none
  expect_rc 3 "an empty window must never read as a pass (C4)"
  expect_line 'sample.*(too small|too few)|(too small|too few).*sample' \
    "the message must name what is missing (C4)"
}

# 6. Long queue AND long execution. `late-but-long` waited 300 s on a 9 s
# floor, then ran for 900 s. The ratio rule passes it because 300 < 900. The
# 300 s wait is contention whatever the job did afterwards. This proves the new
# rule is not merely a weaker ratio.
test_long_queue_with_long_execution_fires() {
  run_fixture long-queue-long-execution
  expect_rc 1 "291 s of contention is contention, however long the job ran (C1)"
  expect_line 'FAIL.*late-but-long' \
    "a long execution does not excuse a long wait (C2)"
  expect_floor_at_most 60 "the floor of this window is 9 s"
}

# -------- runner --------

run_case() {
  local name="$1"
  case_failures=0
  echo "== $name"
  "test_$name"
  if [ "$case_failures" -eq 0 ]; then
    note "ok"
  fi
}

main() {
  local selected="" name found
  if [ "$#" -eq 0 ]; then
    selected="$CASES"
  elif [ "$1" = "--list" ]; then
    printf '%s' "$CASES" | sed '/^$/d'
    return 0
  else
    for name in "$@"; do
      found=0
      for known in $CASES; do
        [ "$name" = "$known" ] && found=1
      done
      if [ "$found" -eq 0 ]; then
        echo "test-verify-runner-queue: no such case: $name" >&2
        echo "  known: $(printf '%s' "$CASES" | tr '\n' ' ')" >&2
        exit 2
      fi
      selected="$selected$name
"
    done
  fi

  local total=0
  for name in $selected; do
    run_case "$name"
    total=$((total + 1))
  done

  echo
  echo "cases=$total assertion-failures=$failures"
  [ "$failures" -eq 0 ] || exit 1
}

main "$@"
