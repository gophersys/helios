#!/usr/bin/env bash
# Assert that no job waited for a runner because another job held the pool.
#
# WHY THIS EXISTS
# `timeout-minutes` counts EXECUTION only. A job can wait 18 minutes for a free
# runner, then run for 151 seconds, and then report success. The pool was full
# for those 18 minutes, and every dashboard stayed green. No other check in this
# repo can see that state. This one can.
#
# THE MODEL
#
#   queue = dispatch    the fixed cost to give the job a runner. A property of
#                       the pool and of the image, not of the job.
#         + contention  the variable part. The job waited for somebody else.
#
# Only contention is a defect. The rule before this one was `FAIL when queue >
# execution`, and on 2026-08-13 it fired on 17 of 36 arc-org jobs, all of them
# false. A pod start costs about 10 s and an arc-org job runs for 7 to 10 s, so
# that rule compared a fixed cost against a variable one and fired whenever the
# work was short.
#
# HOW THE DISPATCH COST IS MEASURED, AND WHY IT IS A FLOOR
# The script measures dispatch as a LOW PERCENTILE of the observed queue times,
# over the whole sample. A job that got a runner immediately still paid
# dispatch, so the bottom of the distribution IS the dispatch cost, measured
# instead of invented. The rule then follows the pool: a faster image lowers the
# floor and the alarm with it, and no constant in this file has to change.
#
# NEVER the median. A median holds contention inside it, so the median rises
# under load and a median-based alarm lifts its own level exactly when the pool
# saturates.
#
# WHY THE LOWER QUARTILE AND NOT THE MINIMUM
# Measured on gophersys/infrastructure on 2026-08-13, over the last 40 runs of
# every workflow (82 jobs, pools arc-org and arc-review), the arc-org queue
# times are BIMODAL, not fixed:
#
#   1 to 7 s     14 of 69 jobs. A runner pod was already registered and idle,
#                so the job started at once. This is dispatch too.
#   9 to 16 s    51 of 69 jobs. A new pod had to start.
#   21, 53,      the tail. Only the last 3 are true waits.
#   65, 927 s
#
# The sample MINIMUM is therefore 1 s, which is the warm-start cost, not the
# pod-start cost. An alarm at 3 times that minimum sits at 3 s and fires on 57
# of the 69 healthy jobs — the same defect as the old rule, with the sign
# reversed. The LOWER QUARTILE is 9 s for arc-org and 8 s across both pools,
# which is the bottom of the pod-start cluster. It stays a floor statistic, and
# it tracks the cost that the alarm must clear.
#
# THE MARGIN
# A job is flagged when `queue > floor * 3`. With a floor of 9 s the alarm sits
# at 27 s. The measured budget behind the number 3:
#
#   16 s   the longest queue with no contention (a slow pod start), 1.8x floor
#   27 s   the alarm
#   53 s   the shortest true wait measured, 5.9x floor
#
# The factor sits between the worst dispatch and the mildest real wait, with
# margin on both sides. The script prints the floor, the sample size and the
# alarm level on every run, so a reader sees a measured budget and never a bare
# constant.
#
# WHERE THE FLOOR IS MEASURED, AND WHAT THAT STILL CANNOT SEE
# The floor comes from EVERY workflow in the window, through
# `/repos/{owner}/{repo}/actions/runs`, while the verdicts stay on the workflow
# you asked for. A floor measured inside 1 workflow, or inside 1 run, rises with
# that workflow or that run and hides the saturation it should report.
#
# Stated limitations. None of these is solved here:
#
#   1. The sample is 1 REPOSITORY. GitHub has no org-level runs endpoint and no
#      org-level jobs endpoint (`/orgs/{org}/actions/runners` lists runners
#      only), so a saturation that covers the whole org for longer than the
#      window lifts this floor with it and the alarm goes quiet.
#   2. The floor mixes every pool in the repo (today arc-org and arc-review,
#      whose floors are 9 s and 7 s). A pool with a much cheaper dispatch, for
#      example a GitHub-hosted runner at about 1 s, would pull the shared floor
#      down and make every self-hosted job look late. That failure is loud, not
#      silent. The fix, when a second kind of pool arrives, is 1 floor per
#      runner-label set.
#   3. A window in which more than 3 of 4 jobs are contended lifts the quartile
#      into the contended cluster. The window has to be widened to see that
#      state.
#
# BOTH TIMES COME FROM THE JOBS API. THIS IS NOT OPTIONAL.
#
#   queue     = job.started_at   - job.created_at
#   execution = job.completed_at - job.started_at
#
# Do NOT anchor the queue on a run-level time. Two run-level anchors were
# measured against gophersys/infrastructure pr-review.yml on 2026-08-13, and
# both give a wrong answer:
#
#   run.created_at      Stale after a re-run. It keeps the time of attempt 1,
#                       and the jobs API returns the LATEST attempt. Run
#                       31442113984 then reports 4353 s of "queue" against 64 s
#                       of execution. That job really waited 6 s. The other
#                       4347 s is the delay before a person started the re-run.
#                       4 of the 40 runs are re-runs, and this anchor reports a
#                       false signal on all 4.
#   run.run_started_at  Correct for the attempt, but wrong for a job that
#                       declares `needs:`. Such a job is created only when its
#                       dependency ends. In gophersys/eden run 31665921025 the
#                       `substrate` job waited 2 s; this anchor reports 301 s,
#                       because it counts the run time of the `fast` job as
#                       queue.
#
# job.created_at is the moment when THIS job became ready for a runner. It is
# correct for a re-run and for a dependent job. Use it.
#
# A job with conclusion `skipped` is not counted. GitHub never sent it to a
# runner, so it has no queue and no execution.
#
# WHAT THIS DOES NOT PROVE
# This reads HISTORY. It tells you that the pool WAS saturated in the window you
# asked for. It does not tell you that the pool is healthy now. A pass means one
# thing only: no finished job in that window waited past the alarm level.
#
# Usage:  verify-runner-queue.sh [repo] [workflow] [runs]
#           repo      owner/name              default gophersys/infrastructure
#           workflow  workflow file name      default pr-review.yml
#           runs      window size, 1 to 100   default 50
#
#         `runs` counts the last runs of EVERY workflow in the repo. They all
#         feed the dispatch floor. The verdicts cover the jobs of `workflow`
#         alone, so a rare workflow may need a larger window to appear at all.
#
# Set RUNNER_QUEUE_FIXTURE to a file that holds one jobs-API response
# (`{"jobs": [ ... ]}`) to measure data you control instead of the live API. The
# fixture feeds the same rows to the same arithmetic, so the floor, the rule,
# the table and the exit code are the ones the live path uses. Every job of the
# fixture is both the sample and the window.
#
# Exit 0   = no job waited past the alarm level.
# Exit 1   = at least one job did. The pool was saturated.
# Exit 2   = bad argument.
# Exit 3   = no verdict is available: the API failed, the window holds no job of
#            the workflow, or the sample is too small to estimate a floor.
# Exit 127 = a required tool is absent.
set -uo pipefail

REPO="${1:-gophersys/infrastructure}"
WORKFLOW="${2:-pr-review.yml}"
RUNS="${3:-50}"
FIXTURE="${RUNNER_QUEUE_FIXTURE:-}"

# The 3 numbers of the rule, together, so a reader finds the whole budget in one
# place. The derivation of each one is in the header.
FLOOR_PERCENTILE=25   # the lower quartile: a floor, and above the warm starts
ALARM_FACTOR=3        # a queue above floor*3 is a wait, not a dispatch
MIN_SAMPLE=2          # 1 job cannot separate a floor from a wait

case "$REPO" in
  -h|--help|help)
    sed -n '/^# Usage:/,/^# Exit 127/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 0 ;;
esac

missing=""
for tool in gh jq; do
  command -v "$tool" >/dev/null 2>&1 || missing="${missing:+$missing }$tool"
done
if [ -n "$missing" ]; then
  echo "verify-runner-queue: missing required tool(s): $missing" >&2
  exit 127
fi

case "$RUNS" in
  ''|*[!0-9]*) echo "verify-runner-queue: runs must be a whole number, got '$RUNS'" >&2; exit 2 ;;
esac
if [ "$RUNS" -lt 1 ] || [ "$RUNS" -gt 100 ]; then
  echo "verify-runner-queue: runs must be 1 to 100 (the API page size), got '$RUNS'" >&2
  exit 2
fi

red() { printf '\033[0;31m%s\033[0m' "$1"; }
grn() { printf '\033[0;32m%s\033[0m' "$1"; }
ylw() { printf '\033[0;33m%s\033[0m' "$1"; }

# One extractor for both sources, so the fixture path and the live path cannot
# disagree about which field is the queue. jq owns the date arithmetic: its
# fromdateiso8601 is portable, and `date` is not — BSD date needs -j -f and GNU
# date needs -d, and this verb must run on macOS and on the Linux runner image.
JOB_FIELDS='
  .jobs[]
  | [ .run_id,
      .name,
      (.created_at   // "" | if . == "" then -1 else fromdateiso8601 end),
      (.started_at   // "" | if . == "" then -1 else fromdateiso8601 end),
      (.completed_at // "" | if . == "" then -1 else fromdateiso8601 end),
      (.conclusion   // "pending"),
      ((.labels // []) | join(",") | if . == "" then "-" else . end)
    ] | @tsv'

# 2 files, because the 2 questions have 2 different samples. SAMPLE feeds the
# dispatch floor and holds every workflow. WINDOW gets the verdicts and holds
# the requested workflow alone. On the fixture path they are the same rows.
JOBS_SAMPLE="$(mktemp)"
JOBS_WINDOW="$(mktemp)"
JOBS_RUN="$(mktemp)"
QUEUES="$(mktemp)"
trap 'rm -f "$JOBS_SAMPLE" "$JOBS_WINDOW" "$JOBS_RUN" "$QUEUES"' EXIT

if [ -n "$FIXTURE" ]; then
  if [ ! -f "$FIXTURE" ]; then
    echo "verify-runner-queue: fixture not found: $FIXTURE" >&2
    exit 3
  fi
  if ! jq -r "$JOB_FIELDS" <"$FIXTURE" >"$JOBS_SAMPLE"; then
    echo "verify-runner-queue: fixture is not a jobs-API response: $FIXTURE" >&2
    exit 3
  fi
  cp "$JOBS_SAMPLE" "$JOBS_WINDOW"
  source_label="fixture $FIXTURE"
  window_label="every job of the fixture"
else
  # 1 call lists the runs of EVERY workflow. There is no endpoint that returns
  # the jobs of many runs, so the jobs still cost 1 call per run.
  if ! runs_tsv="$(gh api "repos/$REPO/actions/runs?per_page=$RUNS" \
                     --jq '.workflow_runs[] | [.id, .path] | @tsv' 2>&1)"; then
    echo "verify-runner-queue: cannot list the runs of $REPO: $runs_tsv" >&2
    exit 3
  fi
  if [ -z "$runs_tsv" ]; then
    echo "verify-runner-queue: $REPO has no workflow run at all" >&2
    exit 3
  fi
  while IFS=$'\t' read -r rid rpath; do
    if ! jobs_json="$(gh api "repos/$REPO/actions/runs/$rid/jobs?per_page=100" 2>&1)"; then
      echo "verify-runner-queue: cannot read the jobs of run $rid: $jobs_json" >&2
      exit 3
    fi
    if ! printf '%s' "$jobs_json" | jq -r "$JOB_FIELDS" >"$JOBS_RUN"; then
      echo "verify-runner-queue: cannot read the jobs of run $rid" >&2
      exit 3
    fi
    cat "$JOBS_RUN" >>"$JOBS_SAMPLE"
    case "$rpath" in
      */"$WORKFLOW"|"$WORKFLOW") cat "$JOBS_RUN" >>"$JOBS_WINDOW" ;;
    esac
  done <<<"$runs_tsv"
  source_label="$REPO, last $RUNS run(s) of every workflow"
  window_label="the jobs of $WORKFLOW"
fi

# The floor sample: every job that reached a runner, whatever workflow it
# belongs to. A job that is still running counts here, because its queue is
# already final even though its execution is not.
while IFS=$'\t' read -r _rid _name created started _completed concl _labels; do
  [ "$concl" = "skipped" ] && continue
  { [ "$created" -lt 0 ] || [ "$started" -lt 0 ]; } && continue
  echo $((started - created))
done <"$JOBS_SAMPLE" >"$QUEUES"

sample="$(wc -l <"$QUEUES" | tr -d ' ')"
if [ "$sample" -lt "$MIN_SAMPLE" ]; then
  echo "verify-runner-queue: the sample is too small to estimate a dispatch floor:" >&2
  echo "  $sample job(s) in $source_label, and $MIN_SAMPLE are needed." >&2
  echo "  A dispatch floor cannot be separated from a wait with fewer. No verdict." >&2
  exit 3
fi

# Nearest rank on the sorted sample, 1-based for sed. n=2 gives the minimum,
# which is the honest answer when the sample is that small.
rank=$(( sample * FLOOR_PERCENTILE / 100 + 1 ))
floor="$(sort -n <"$QUEUES" | sed -n "${rank}p")"
alarm=$(( floor * ALARM_FACTOR ))

echo "verifying that no job waited for the pool — $source_label"
echo "  dispatch floor ${floor}s — the lower quartile of a sample of $sample job(s), every workflow"
echo "  alarm above ${alarm}s — ${ALARM_FACTOR}x the floor. Below it, a queue is the cost of starting a runner."
echo "  verdicts cover $window_label. contention = queue - the floor."
echo

checked=0; fail=0; skipped=0; pending=0
worst_c=-1; worst_line=""

while IFS=$'\t' read -r rid name created started completed concl labels; do
  if [ "$concl" = "skipped" ]; then
    skipped=$((skipped + 1))
    continue
  fi
  if [ "$created" -lt 0 ] || [ "$started" -lt 0 ] || [ "$completed" -lt 0 ]; then
    printf '  %s %-11s %-28.28s still in flight (%s)\n' "$(ylw WAIT)" "$rid" "$name" "$concl"
    pending=$((pending + 1))
    continue
  fi

  queue=$((started - created))
  execution=$((completed - started))
  contention=$((queue - floor))
  [ "$contention" -lt 0 ] && contention=0

  checked=$((checked + 1))
  if [ "$queue" -gt "$alarm" ]; then
    printf '  %s %-11s %-28.28s queue=%-8s contention=%-8s exec=%-8s %s [%s]\n' \
      "$(red FAIL)" "$rid" "$name" "${queue}s" "${contention}s" "${execution}s" "$concl" "$labels"
    fail=$((fail + 1))
  else
    printf '  %s %-11s %-28.28s queue=%-8s contention=%-8s exec=%-8s %s [%s]\n' \
      "$(grn PASS)" "$rid" "$name" "${queue}s" "${contention}s" "${execution}s" "$concl" "$labels"
  fi

  if [ "$contention" -gt "$worst_c" ]; then
    worst_c="$contention"
    worst_line="$rid $name queue=${queue}s contention=${contention}s exec=${execution}s"
  fi
done <"$JOBS_WINDOW"

echo
[ -n "$worst_line" ] && echo "  worst: $worst_line"
echo "  checked=$checked fail=$fail skipped=$skipped pending=$pending"

# A window that checked nothing is not a pass. It is the absence of a verdict,
# and the empty case is exactly the one that reads as green and proves nothing.
if [ "$checked" -eq 0 ]; then
  echo "  no finished job of $WORKFLOW in this window, so nothing was verified." >&2
  echo "  Widen the window with the third argument, or name another workflow." >&2
  exit 3
fi

if [ "$fail" -gt 0 ]; then
  echo "  the pool was saturated: $fail job(s) waited past ${alarm}s, which is ${ALARM_FACTOR}x the ${floor}s dispatch floor"
fi
[ "$fail" -eq 0 ] || exit 1
