#!/usr/bin/env bash
# Assert that no job waited for a runner longer than it used one.
#
# WHY THIS EXISTS
# `timeout-minutes` counts EXECUTION only. A job can wait 18 minutes for a free
# runner, then run for 151 seconds, and then report success. The pool was full
# for those 18 minutes, and every dashboard stayed green. No other check in this
# repo can see that state. This one can.
#
# THE RULE, AND WHY IT CARRIES NO MAGIC NUMBER
# A job that waited longer than it ran is a saturation signal. The rule compares
# a job against itself, so there is no threshold to tune. It stays correct when
# the runners become faster or slower, and a reader can agree with it without a
# table of constants. The script prints the queue, the execution and the ratio
# for EVERY job, because a check that speaks only when it is angry teaches
# nobody the normal range.
#
# WHAT THIS DOES NOT PROVE
# This reads HISTORY. It tells you that the pool WAS saturated in the window you
# asked for. It does not tell you that the pool is healthy now. A pass means one
# thing only: no finished job in that window waited longer than it ran.
# Do not read a green job duration as proof that the pool is healthy either.
# `timeout-minutes` cannot catch this class of defect at all, because the clock
# it holds starts after the wait is over.
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
# Usage:  verify-runner-queue.sh [repo] [workflow] [runs]
#           repo      owner/name              default gophersys/infrastructure
#           workflow  workflow file name      default pr-review.yml
#           runs      window size, 1 to 100   default 50
#
# Set RUNNER_QUEUE_FIXTURE to a file that holds one jobs-API response
# (`{"jobs": [ ... ]}`) to measure data you control instead of the live API.
# The fixture feeds the same rows to the same arithmetic, so the rule, the
# table and the exit code are the ones the live path uses.
#
# Exit 0   = no job waited longer than it ran.
# Exit 1   = at least one job did. The pool was saturated.
# Exit 2   = bad argument.
# Exit 3   = the data could not be read (API failure, or an empty window).
# Exit 127 = a required tool is absent.
set -uo pipefail

REPO="${1:-gophersys/infrastructure}"
WORKFLOW="${2:-pr-review.yml}"
RUNS="${3:-50}"
FIXTURE="${RUNNER_QUEUE_FIXTURE:-}"

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

JOBS_TSV="$(mktemp)"
trap 'rm -f "$JOBS_TSV"' EXIT

if [ -n "$FIXTURE" ]; then
  if [ ! -f "$FIXTURE" ]; then
    echo "verify-runner-queue: fixture not found: $FIXTURE" >&2
    exit 3
  fi
  if ! jq -r "$JOB_FIELDS" <"$FIXTURE" >"$JOBS_TSV"; then
    echo "verify-runner-queue: fixture is not a jobs-API response: $FIXTURE" >&2
    exit 3
  fi
  source_label="fixture $FIXTURE"
else
  if ! run_ids="$(gh api "repos/$REPO/actions/workflows/$WORKFLOW/runs?per_page=$RUNS" \
                    --jq '.workflow_runs[].id' 2>&1)"; then
    echo "verify-runner-queue: cannot list runs of $WORKFLOW in $REPO: $run_ids" >&2
    exit 3
  fi
  if [ -z "$run_ids" ]; then
    echo "verify-runner-queue: $REPO has no runs of $WORKFLOW" >&2
    exit 3
  fi
  while IFS= read -r rid; do
    if ! jobs_json="$(gh api "repos/$REPO/actions/runs/$rid/jobs?per_page=100" 2>&1)"; then
      echo "verify-runner-queue: cannot read the jobs of run $rid: $jobs_json" >&2
      exit 3
    fi
    if ! printf '%s' "$jobs_json" | jq -r "$JOB_FIELDS" >>"$JOBS_TSV"; then
      echo "verify-runner-queue: cannot read the jobs of run $rid" >&2
      exit 3
    fi
  done <<<"$run_ids"
  source_label="$REPO $WORKFLOW, last $RUNS run(s)"
fi

echo "verifying that no job waited longer than it ran — $source_label"
echo "  rule: FAIL when queue > execution. Both come from the jobs API."
echo

checked=0; fail=0; skipped=0; pending=0
# The worst job is kept as the pair (queue, execution), never as the printed
# ratio. A comparison by cross-multiplication is exact integer arithmetic, and it
# ranks a zero-second execution correctly. A comparison of the ratio strings
# would have to compare "inf", and awk reads "inf" as a number on some
# implementations and as text on others.
worst_q=-1; worst_e=1; worst_line=""

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

  # A job that finished in the same second it started divides by zero. It still
  # has an honest verdict: it waited longer than it ran whenever the queue is
  # above zero.
  if [ "$execution" -gt 0 ]; then
    ratio="$(awk -v q="$queue" -v e="$execution" 'BEGIN { printf "%.2f", q / e }')"
  elif [ "$queue" -eq 0 ]; then
    ratio="0.00"
  else
    ratio="inf"
  fi

  checked=$((checked + 1))
  if [ "$queue" -gt "$execution" ]; then
    printf '  %s %-11s %-28.28s queue=%-8s exec=%-8s ratio=%-6s %s [%s]\n' \
      "$(red FAIL)" "$rid" "$name" "${queue}s" "${execution}s" "$ratio" "$concl" "$labels"
    fail=$((fail + 1))
  else
    printf '  %s %-11s %-28.28s queue=%-8s exec=%-8s ratio=%-6s %s [%s]\n' \
      "$(grn PASS)" "$rid" "$name" "${queue}s" "${execution}s" "$ratio" "$concl" "$labels"
  fi

  if [ $((queue * worst_e)) -gt $((worst_q * execution)) ]; then
    worst_q="$queue"; worst_e="$execution"
    worst_line="$rid $name queue=${queue}s exec=${execution}s ratio=$ratio"
  fi
done <"$JOBS_TSV"

echo
[ -n "$worst_line" ] && echo "  worst: $worst_line"
echo "  checked=$checked fail=$fail skipped=$skipped pending=$pending"

if [ "$fail" -gt 0 ]; then
  echo "  the pool was saturated: $fail job(s) spent more time waiting than working"
fi
[ "$fail" -eq 0 ] || exit 1
