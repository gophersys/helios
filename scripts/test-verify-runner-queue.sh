#!/usr/bin/env bash
# Spec for scripts/verify-runner-queue.sh — the queue rule, not the anchoring.
#
# Run: bash scripts/test-verify-runner-queue.sh            # every case
#      bash scripts/test-verify-runner-queue.sh <name>...  # one case, by name
#      bash scripts/test-verify-runner-queue.sh --list     # the case names
#
# WHAT WAS WRONG, AND WHAT REPLACED IT
# The rule was `FAIL when queue > execution`. Measured on arc-org on 2026-08-13
# it fired on 17 of 36 jobs, and every one of the 17 was a false alarm: a pod
# start costs about 10 s and an arc-org job runs for 7 to 10 s, so the condition
# was true whenever the work was short. It compared a fixed cost against a
# variable one.
#
# THE MODEL THE RULE EXPRESSES
#
#   queue = dispatch    cost to give the job a runner. A property of the pool
#                       and of the image, not of the job.
#         + contention  variable. Waiting for somebody else's job to end.
#
# Alarm on contention only. Dispatch is estimated as a FLOOR of the observed
# queue times — a low percentile over the whole sample. NEVER the median: a
# median holds contention inside it, so under load the median rises, and a
# median-based threshold would lift its own alarm level exactly when the pool
# becomes saturated.
#
# NEVER THE MINIMUM EITHER. Queue times are BIMODAL, measured over 69 arc-org
# jobs on 2026-08-13:
#
#   1 to 7 s    14 of 69   a runner pod was already registered and idle. WARM.
#   9 to 16 s   51 of 69   a new pod had to start. COLD.
#   21 s and up  4 of 69   the tail, and only 3 of those are true waits.
#
# The sample MINIMUM is therefore the warm-start cost, not the pod-start cost.
# An alarm at 3x that minimum sits at 3 s and fires on 57 of the 69 healthy
# jobs — the original defect with the sign reversed. The estimator must clear
# the warm cluster and sit at the bottom of the cold one. The script uses the
# lower quartile. `estimator_clears_the_warm_start_cluster` is the case that
# holds it there, and without that case the minimum and the lower quartile are
# indistinguishable.
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
#   C6  the estimator sits ABOVE the warm-start cluster and at or below the top
#       of the cold-start cluster. Not the minimum, not the median.
#   C7  a job that never reached a runner (`skipped`) is in neither the floor
#       sample nor the verdicts. A job still in flight is in the floor sample —
#       its queue is already final — but gets no verdict, because it has no
#       execution yet.
#
# THE ADMISSIBLE BAND, MEASURED BY SWEEP AND NOT DERIVED
# Both constants of the rule were swept against these cases, changing one token
# of the script at a time and nothing else:
#
#   FLOOR_PERCENTILE   admissible [20, 28], shipped 25
#     19 and below  estimator_clears_the_warm_start_cluster fails: the warm
#                   cluster leaks into the floor and healthy jobs alarm.
#     29 and above  estimator_is_a_floor_not_a_median fails: the floor climbs
#                   into the contended cluster.
#   ALARM_FACTOR       admissible [2, 20], shipped 3
#     1             3 cases fail, all of them false fires on healthy jobs.
#     21 and above  estimator_is_a_floor_not_a_median fails.
#
# An earlier version of this header claimed K from 1.4 to 20.8, and the commit
# message of f579be5 claimed 1.4 to 27. Both were arithmetic on 1 fixture rather
# than a sweep, and both were wrong: K=1.4 and K=27 are red. Sweep, do not
# derive. The commit message cannot be corrected and stands wrong in the log.
#
# WHAT NO CASE HERE CAN SEE: THE REPO-WIDE SAMPLE
# The headline of 79d7fe3 is that the floor comes from EVERY workflow in the
# window while the verdicts stay on the requested workflow. NOTHING BELOW TESTS
# THAT. Change 1 word — the sample loop reads `$JOBS_WINDOW` instead of
# `$JOBS_SAMPLE` — and all cases here stay green, while the live answer moves
# from a 9 s floor over 107 jobs to a 7 s floor over 18.
#
# This is a property of the seam, not a missing fixture. On the fixture path the
# script does `cp "$JOBS_SAMPLE" "$JOBS_WINDOW"`, so the 2 files are
# byte-identical for every fixture — measured, with cmp, on all of them. The
# mutation swaps 2 identical files, so NO fixture content can distinguish it.
# The split happens live on `run.path` from the RUNS endpoint, and a jobs-API
# response carries no run path, so the fixture cannot express "these jobs are
# from another workflow" at all.
#
# To close it the seam has to grow, and that is the implementer's change, not a
# test file's:
#   preferred  let the fixture carry the runs index beside the jobs, for example
#              `{"runs":[{"id":...,"path":".github/workflows/validate.yml"}],
#                "jobs":[...]}`, and split on run_id -> path. This mirrors the
#              live path exactly, keeping run.path as the only split key.
#   cheaper    read `.workflow_name` from each job and match it against the
#              workflow argument on the fixture path. It works, but the fixture
#              path and the live path would then split on different fields, and
#              the 1-extractor rule in the script header exists to stop that.
# With either, the case is: 1 fixture whose repo-wide quartile and
# requested-workflow quartile differ enough to move a verdict.
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
estimator_clears_the_warm_start_cluster
known_limitation_quartile_rises_when_most_jobs_wait
a_skipped_job_leaves_the_sample_and_the_verdicts
a_job_in_flight_feeds_the_floor_but_gets_no_verdict
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

# For a case that must read the exit code without pinning the sensitivity. 0 and
# 1 are both verdicts; 2, 3 and 127 mean the verb never reached one.
expect_verdict_rc() { # <why>
  if [ "$rc" -eq 0 ] || [ "$rc" -eq 1 ]; then
    return 0
  fi
  bad "exit $rc is not a verdict, want 0 or 1 — $1"
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

# The reported floor is the only window onto the estimator, so C3 asks for it in
# a shape a test can read. `floor_seconds` is empty when the contract is broken,
# and the 2 bound checks below then say nothing more, because a missing number
# has 1 cause and deserves 1 message.
floor_seconds=""

parse_floor() {
  local line
  floor_seconds=""
  line="$(printf '%s\n' "$out" | grep -E 'dispatch floor' | head -1)"
  if [ -z "$line" ]; then
    bad "no 'dispatch floor' line in the output (C3)"
    return 0
  fi
  case "$line" in
    *sample*) : ;;
    *) bad "the 'dispatch floor' line names no sample size: $line (C3)" ;;
  esac
  floor_seconds="$(printf '%s\n' "$line" |
    sed -n 's/.*dispatch floor[^0-9]*\([0-9][0-9]*\)s.*/\1/p')"
  if [ -z "$floor_seconds" ]; then
    bad "the 'dispatch floor' line carries no <N>s figure: $line (C3)"
  fi
}

# The sharpest half of the floor-versus-median question. A median estimator
# cannot report a low number on a contended window; a floor estimator must.
expect_floor_at_most() { # <max-seconds> <why>
  parse_floor
  [ -n "$floor_seconds" ] || return 0
  if [ "$floor_seconds" -gt "$1" ]; then
    bad "dispatch floor is ${floor_seconds}s, want at most ${1}s — $2"
  fi
}

# The floor-versus-minimum question. The minimum of a bimodal sample is the
# warm-start cost, and an alarm built on it fires on the healthy cold starts.
expect_floor_at_least() { # <min-seconds> <why>
  parse_floor
  [ -n "$floor_seconds" ] || return 0
  if [ "$floor_seconds" -lt "$1" ]; then
    bad "dispatch floor is ${floor_seconds}s, want at least ${1}s — $2"
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

# 7. THE SECOND DISCRIMINATOR: a floor is not the minimum. This window is the
# real bimodal shape of the pool — 5 of 25 jobs found an idle runner pod and
# started in 1 to 7 s, the other 20 waited 9 to 12 s for a pod to start. NOTHING
# here is contended, so the verb must stay silent.
#   lower quartile  9s -> alarm 27s -> silent. Correct.
#   minimum         1s -> alarm  3s -> 20 of 25 healthy jobs fire.
# The first 6 cases cannot tell those 2 estimators apart, because no fixture of
# theirs holds a warm start: their minimum and their lower quartile are the same
# number. Without this case the most consequential choice in the rule is
# unpinned, and a refactor back to the minimum stays green while it alarms on
# 4 of every 5 healthy jobs.
test_estimator_clears_the_warm_start_cluster() {
  run_fixture warm-and-cold-starts
  expect_rc 0 "a warm start is dispatch too, not a reason to alarm (C1)"
  expect_no_line 'FAIL[[:space:]]+[0-9]{6,}' \
    "no job in this window waited for anybody"
  expect_floor_at_least 8 \
    "the minimum here is 1s, the warm-start cost. The floor must clear it (C6)"
  expect_floor_at_most 16 \
    "16s is the longest measured queue with no contention. Above it, a floor
      is no longer a floor (C6)"
}

# 8. A KNOWN LIMITATION, WRITTEN DOWN AS A RUNNING CASE. Limitation 3 in the
# header of verify-runner-queue.sh: when more than 3 of 4 jobs in the window are
# contended, the lower quartile lands INSIDE the contended cluster and the alarm
# goes quiet. This window is 16 of 20, which is 80%.
#
# READ THIS BEFORE YOU CHANGE THE CASE. It asserts what the rule DOES today, not
# what it SHOULD do. A window where 16 jobs waited between 400 s and 900 s is
# saturated, and the quiet is the price of a quartile. When a wider sample lands
# this case goes red. REWRITE it to assert the alarm. Do not delete it.
#
# IT ASSERTS THE MECHANISM, NEVER THE SENSITIVITY. An earlier version of this
# case demanded exit 0, and that made it the ONLY thing in the suite that
# forbade ALARM_FACTOR=2 — a strictly MORE sensitive alarm, which on this very
# fixture starts catching the contention the case exists to describe as
# uncaught. A case that records a weakness must never be the thing that blocks
# the weakness being fixed. So:
#
#   asserted      the floor is dragged into the contended cluster. That is the
#                 mechanism, it is computed before the factor is applied, and it
#                 is true for every choice of factor.
#   asserted      the SMALLEST wait in the cluster escapes. At a floor of 410 s
#                 the alarm is at or above 410 s for any factor of 1 or more, so
#                 a job that waited 400 s against a true 10 s floor is invisible
#                 here whatever the factor is. That is the limitation, stated in
#                 a way no sensitivity choice can satisfy or veto.
#   NOT asserted  how many of the other 15 are caught. That is the factor's
#                 business, and this case has no opinion on it.
#
# It also prices the estimator honestly. The minimum, which case 7 rejects,
# would keep a 9 s floor here and would fire. The quartile buys quiet on healthy
# short jobs and pays for it exactly on this shape.
test_known_limitation_quartile_rises_when_most_jobs_wait() {
  run_fixture mostly-contended
  expect_verdict_rc "a window of 20 finished jobs must produce a verdict"
  expect_floor_at_least 300 \
    "the mechanism: 80% contended drags the quartile into the contended cluster"
  expect_no_line 'FAIL[[:space:]]+[0-9]{6,}[[:space:]]+contended-1[[:space:]]' \
    "the limitation: a 400 s wait sits below its own inflated floor and escapes"
}

# 9. A SKIPPED JOB IS NOT A SAMPLE. GitHub never sent it to a runner, so it has
# no queue and no execution, and it reports every timestamp at the same instant.
# That reads as a queue of 0 s. 8 of those zeros in a sample of 24 pull the
# lower quartile to 0 s and the alarm down with it, so the exclusion is
# load-bearing on the FLOOR and not only on the count.
#   skipped excluded  floor 10s -> alarm 30s -> silent, which is correct
#   skipped counted   floor  0s -> alarm  0s -> all 16 healthy jobs fire
# Both branches of the verdict loop had no coverage at all before this case and
# case 10. A commit message claimed a fixture for them; no such fixture existed.
test_a_skipped_job_leaves_the_sample_and_the_verdicts() {
  run_fixture skipped-jobs
  expect_rc 0 "16 healthy cold starts and 8 skips are not a saturated pool (C1)"
  expect_no_line 'FAIL[[:space:]]+[0-9]{6,}' "nothing here waited for anybody"
  expect_floor_at_least 8 \
    "a skipped job reports a 0 s queue. It must not enter the floor sample"
  expect_line 'skipped=8' "the 8 skips must be counted as skipped"
  expect_line 'checked=16' "and must not be counted as checked"
  expect_no_line '(PASS|FAIL)[[:space:]]+[0-9]{6,}[[:space:]]+skipped-' \
    "a job that never reached a runner gets no verdict"
}

# 10. A JOB STILL IN FLIGHT GETS NO VERDICT, BUT ITS QUEUE STILL COUNTS. It has
# no execution yet, so there is nothing to judge. Its QUEUE is already final, so
# it belongs in the floor sample. That asymmetry is what keeps saturation
# visible: a saturated pool is full of jobs that have not finished, and dropping
# them from the sample takes the healthy short queues out with them and lifts
# the floor over the very waits we are looking for. Here the 12 unfinished jobs
# are the only healthy ones in the window.
#   queues counted   floor  10s -> alarm   30s -> the 8 real waits fire
#   queues dropped   floor 470s -> alarm 1410s -> nothing fires. Silence.
test_a_job_in_flight_feeds_the_floor_but_gets_no_verdict() {
  run_fixture jobs-in-flight
  expect_rc 1 "8 jobs waited 400 s and more on a 10 s floor (C1)"
  expect_floor_at_most 60 \
    "the unfinished jobs hold the floor down. Their queue is already final"
  expect_line 'FAIL.*waited-1[[:space:]]' "the shortest real wait must fire"
  expect_line 'FAIL.*waited-8' "and so must the longest"
  expect_line 'in-flight-1[[:space:]]+still in flight' \
    "an unfinished job is reported, not judged"
  expect_line 'pending=12' "all 12 unfinished jobs must be counted as pending"
  expect_line 'checked=8' "and none of them as checked"
  expect_no_line '(PASS|FAIL)[[:space:]]+[0-9]{6,}[[:space:]]+in-flight-' \
    "a job with no execution yet cannot be judged against its queue"
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
