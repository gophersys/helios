#!/usr/bin/env bash
#
# scripts/workflow-timeouts_test.sh — repository rule (blueprint P0-5): every eden CI job declares
# a `timeout-minutes`, and no eden job runs on `ubuntu-latest`.
#
# WHY THIS FILE EXISTS. A job with no `timeout-minutes` inherits GitHub's 360-minute default, so a
# hung step holds a runner for six hours. Eden's runners are a small self-hosted pool
# (`arc-org`, `arc-review`), and one zombie starves every repository in the organization — that
# already cost 47 minutes on 2026-08-11 with nothing detecting it (`.claude/rules/git-process.md`
# and the /dev skill both carry the incident). Measured on this tree: 11 jobs across 6 workflows,
# and only 2 of them declare a job timeout.
#
# `ubuntu-latest` is the second half of the same rule. Eden's lanes run inside
# `ghcr.io/gophersys/base` on the self-hosted pool; a job that reaches for a GitHub-hosted runner
# is either an unbilled surprise or a lane running on a substrate the gate toolchain is not on.
# One job does it today: `harness-upgrade-check.yml:20`.
#
# A GREP CANNOT HOLD THIS RULE, AND THAT IS WHY THIS FILE PARSES. `grep -c timeout-minutes` reports
# 3 for `pr-review.yml`, which has exactly ONE job: the other 2 are STEP-level timeouts, which do
# not bound the job at all. A count of matching lines and a count of jobs that are bounded are
# different numbers, and only the second one is the rule. So every verdict here comes from `yq`
# walking `.jobs`, and a `timeout-minutes:` written inside a `run:` heredoc or a comment cannot
# reach it.
#
# IT ASSERTS OVER BOTH TREES, and that is deliberate. `.ci/providers/README.md` requires every
# workflow to exist twice, byte-identically, and `scripts/workflow-twins_test.sh` proves that
# equality — but it runs AFTER this file in the `collect_scripts` glob order, and `scripts/ctl.sh
# test` stops at the first failure. An assertion that leans on a proof that has not run yet is a
# green resting on a promise. Scanning 12 files instead of 6 costs nothing and needs no promise.
#
# WHAT A GREEN RUN PROVES:
#   - every job in every workflow of BOTH trees declares `timeout-minutes`, as an integer in
#     [1, 360];
#   - no job's `runs-on` names `ubuntu-latest`, whatever shape it takes (string, sequence, or the
#     group/labels map);
#   - `ubuntu-latest` appears on no executable line of any workflow — a matrix value, a container
#     image or a `${{ }}` expression is caught even though it is not a `runs-on` scalar;
#   - the scan really read the tree: both trees, at least 6 workflows each, at least 11 jobs each.
#
# SCOPE — read this before you read a green run as more than it is.
#   COVERED: *.yml and *.yaml in .github/workflows/ and in .ci/providers/github/.
#   NOT COVERED: whether a timeout VALUE is right for the work its job does; step-level timeouts;
#     whether GitHub accepts the workflow; any other provider directory; the runner label being
#     one that exists. A whole-line comment mentioning `ubuntu-latest` is deliberately allowed, so
#     the ban can be explained in the file it governs.
#
# It reads files only. It runs no workflow and no CI system. `yq` is REQUIRED: it is pinned in
# `.devcontainer/versions.env` (`YQ_VERSION`) and baked into `ghcr.io/gophersys/base`, so an absent
# yq is a broken environment and this file FAILS rather than skipping (FAIL-NOT-SKIP, ADR-0020).
#
# Run it directly:  bash scripts/workflow-timeouts_test.sh
# It exits non-zero on any failure. shellcheck-clean at -S style.
set -Eeuo pipefail
IFS=$'\n\t'

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "${here}/.." && pwd)"

workflow_trees=(
  ".github/workflows"
  ".ci/providers/github"
)

# The tree holds 6 workflows and 11 jobs per side. A scan that reads fewer has lost a file or lost
# its glob, and a rule asserted over 0 jobs is the green that proves nothing.
minimum_workflows=6
minimum_jobs=11

# GitHub's own maximum job timeout on a hosted runner, and the value it defaults to. A declaration
# above it is a number that never fires, which is the same green-that-checks-nothing this file
# exists to prevent — so it is judged, not merely counted.
maximum_timeout_minutes=360

# The runner label eden never uses.
banned_runner="ubuntu-latest"

fails=0
report_fail() {
  local name="$1"; shift
  printf '  FAIL  %s\n' "$name" >&2
  local problem
  for problem in "$@"; do printf '          %s\n' "$problem" >&2; done
  fails=$((fails + 1))
}
report_ok() { printf '  ok    %s\n' "$1"; }

# --- the tool gate — FAIL, never skip -------------------------------------------------------------
if ! command -v yq >/dev/null 2>&1; then
  printf 'workflow-timeouts_test: FAILED — required tool(s) missing: yq\n' >&2
  printf '          yq is pinned by YQ_VERSION in .devcontainer/versions.env and is baked into\n' >&2
  printf '          ghcr.io/gophersys/base. Its absence is a broken environment, not a reason to skip.\n' >&2
  exit 1
fi
# It must be Mike Farah's yq v4: the python `yq` is a different program with a different expression
# language, and it would answer every query below with silence rather than with an error.
yq_probe=''
yq_probe_rc=0
set +e
yq_probe="$(printf 'jobs:\n  probe:\n    timeout-minutes: 7\n' | yq e '.jobs.probe."timeout-minutes"' - 2>&1)"
yq_probe_rc=$?
set -e
if [[ $yq_probe_rc -ne 0 || "$yq_probe" != "7" ]]; then
  printf 'workflow-timeouts_test: FAILED — yq is present but does not answer a v4 expression.\n' >&2
  printf '          probe exited %d and said: %s\n' "$yq_probe_rc" "$yq_probe" >&2
  printf '          expected 7 from: yq e '\''.jobs.probe."timeout-minutes"'\''\n' >&2
  exit 1
fi

for tree in "${workflow_trees[@]}"; do
  if [[ ! -d "${repository_root}/${tree}" ]]; then
    printf 'workflow-timeouts_test: FAILED — the directory does not exist: %s\n' "$tree" >&2
    exit 1
  fi
done

# workflow_files <directory> — every *.yml / *.yaml in it, sorted. An unmatched glob stays literal
# under bash, so each candidate is tested before it is used.
workflow_files() {
  local directory="$1" candidate
  for candidate in "$directory"/*.yml "$directory"/*.yaml; do
    [[ -f "$candidate" ]] || continue
    printf '%s\n' "$candidate"
  done | sort
}

total_jobs=0
total_files=0
reusable_jobs=0

# Every scratch path this file writes lives here, never beside the workflow it reads. A temp file
# written into .github/workflows/ would be scanned by the next run, and by every other tool that
# globs that directory — the residue class scripts/mktemp-template_test.sh exists because of.
work_dir=""
interrupted=0
sweep() {
  local rc=$?
  [[ -n "$work_dir" ]] && rm -rf "$work_dir"
  if [[ $interrupted -ne 0 ]]; then
    printf 'workflow-timeouts_test: INTERRUPTED before it finished — reporting %d, never success\n' \
      "$interrupted" >&2
    exit "$interrupted"
  fi
  return "$rc"
}
trap sweep EXIT
trap 'interrupted=130; exit 130' INT
trap 'interrupted=143; exit 143' TERM
trap 'interrupted=129; exit 129' HUP
work_dir="$(mktemp -d -t eden-workflow-timeouts.XXXXXX)"
job_list_file="${work_dir}/jobs.txt"

for tree in "${workflow_trees[@]}"; do
  printf -- '-- %s --\n' "$tree"
  tree_files=()
  mapfile -t tree_files < <(workflow_files "${repository_root}/${tree}")
  tree_jobs=0

  if [[ ${#tree_files[@]} -lt $minimum_workflows ]]; then
    report_fail "scan guard: ${tree} holds at least ${minimum_workflows} workflow(s)" \
      "read ${#tree_files[@]}" \
      'a rule asserted over too few files is a green that proves nothing'
  fi

  for file in "${tree_files[@]+"${tree_files[@]}"}"; do
    relative="${file#"${repository_root}/"}"
    total_files=$((total_files + 1))

    job_names=()
    yq_error=''
    : > "$job_list_file"
    # The status is yq's own. Read after `|| true` it would always be 0 and an unparsable workflow
    # would be judged as a workflow with no jobs — a green over nothing.
    set +e
    yq_error="$(yq e '.jobs | keys | .[]' "$file" 2>&1 >"$job_list_file")"
    yq_rc=$?
    set -e
    if [[ $yq_rc -ne 0 ]]; then
      report_fail "${relative}: the jobs map reads" \
        "yq exited ${yq_rc}: ${yq_error}" \
        'a workflow whose jobs cannot be enumerated is judged by nothing below'
      continue
    fi
    mapfile -t job_names < "$job_list_file"

    if [[ ${#job_names[@]} -eq 0 ]]; then
      report_fail "${relative}: the workflow declares at least 1 job" \
        'it declares none, so every assertion about its jobs would pass vacuously'
      continue
    fi

    for job in "${job_names[@]}"; do
      [[ -n "$job" ]] || continue
      # A job name this file cannot address safely is a FAILURE, not something to step over: an
      # unaddressable job is an unjudged job.
      if [[ ! "$job" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]]; then
        report_fail "${relative}: job name '${job}' is addressable by this scan" \
          'it holds a character this file will not interpolate into a yq path, so it was not judged'
        continue
      fi
      total_jobs=$((total_jobs + 1))
      tree_jobs=$((tree_jobs + 1))

      calls_reusable="$(yq e ".jobs[\"${job}\"] | has(\"uses\")" "$file")"
      has_timeout="$(yq e ".jobs[\"${job}\"] | has(\"timeout-minutes\")" "$file")"
      timeout_value="$(yq e ".jobs[\"${job}\"][\"timeout-minutes\"]" "$file")"
      runs_on_text="$(yq e -o=json -I=0 ".jobs[\"${job}\"][\"runs-on\"]" "$file")"

      if [[ "$calls_reusable" == "true" ]]; then
        # GitHub REJECTS `timeout-minutes` on a job that calls a reusable workflow, so requiring one
        # there would ask the implementer for a file GitHub will not accept. Zero eden jobs are of
        # this shape today; the branch exists so a future one is reported rather than mis-failed.
        reusable_jobs=$((reusable_jobs + 1))
        report_ok "${relative}: job '${job}' calls a reusable workflow — timeout-minutes is not accepted on it"
        continue
      fi

      if [[ "$has_timeout" != "true" ]]; then
        report_fail "${relative}: job '${job}' declares timeout-minutes" \
          'it declares none, so it inherits GitHub 360-minute default and a hung step holds a runner for six hours' \
          'a step-level timeout does not bound the job — this is the job-level key'
      elif [[ ! "$timeout_value" =~ ^[0-9]+$ ]]; then
        report_fail "${relative}: job '${job}' declares timeout-minutes as an integer" \
          "it declares: ${timeout_value}"
      elif [[ "$timeout_value" -lt 1 || "$timeout_value" -gt $maximum_timeout_minutes ]]; then
        report_fail "${relative}: job '${job}' timeout-minutes is in [1, ${maximum_timeout_minutes}]" \
          "it declares ${timeout_value}; ${maximum_timeout_minutes} is GitHub's own maximum, so a larger number never fires"
      else
        report_ok "${relative}: job '${job}' timeout-minutes=${timeout_value}"
      fi

      if [[ "$runs_on_text" == "null" ]]; then
        report_fail "${relative}: job '${job}' declares runs-on" \
          'it declares neither runs-on nor uses, so it names no runner at all'
      elif [[ "$runs_on_text" == *"$banned_runner"* ]]; then
        report_fail "${relative}: job '${job}' does not run on ${banned_runner}" \
          "runs-on is ${runs_on_text}" \
          'eden lanes run on the self-hosted pool (arc-org / arc-review) inside ghcr.io/gophersys/base'
      else
        report_ok "${relative}: job '${job}' runs-on=${runs_on_text}"
      fi
    done

    # The TEXTUAL half. The structural clause above reads `runs-on` only, so a `ubuntu-latest` in a
    # matrix value, a container image or a `${{ }}` expression would pass it. A whole-line comment
    # is exempt on purpose: the ban should be explainable in the file it governs.
    # The status is grep's own, and its stderr is read rather than discarded. rc=1 is legitimate —
    # it means the file names the banned runner nowhere — and anything above 1 means the file was
    # never read, which is not a statement about the runner either.
    set +e
    banned_matches="$(grep -n -F -e "$banned_runner" -- "$file" 2>&1)"
    grep_rc=$?
    set -e
    if [[ $grep_rc -gt 1 ]]; then
      report_fail "${relative}: the file reads for the ${banned_runner} scan" \
        "grep exited ${grep_rc}: ${banned_matches}"
      continue
    fi
    banned_lines=()
    if [[ $grep_rc -eq 0 ]]; then
      while IFS= read -r numbered; do
        [[ -n "$numbered" ]] || continue
        content="${numbered#*:}"
        trimmed="${content#"${content%%[![:space:]]*}"}"
        [[ "$trimmed" == '#'* ]] && continue
        banned_lines+=("$numbered")
      done <<< "$banned_matches"
    fi
    if [[ ${#banned_lines[@]} -ne 0 ]]; then
      report_fail "${relative}: no executable line names ${banned_runner}" \
        "${banned_lines[@]}"
    else
      report_ok "${relative}: no executable line names ${banned_runner}"
    fi
  done

  if [[ $tree_jobs -lt $minimum_jobs ]]; then
    report_fail "scan guard: ${tree} holds at least ${minimum_jobs} job(s)" \
      "read ${tree_jobs}" \
      'a rule asserted over too few jobs is a green that proves nothing'
  else
    report_ok "scan guard: ${tree} — ${#tree_files[@]} workflow(s), ${tree_jobs} job(s) judged"
  fi
done

if [[ $total_files -lt $(( minimum_workflows * ${#workflow_trees[@]} )) ]]; then
  report_fail 'scan guard: both trees were scanned' \
    "read ${total_files} file(s) across ${#workflow_trees[@]} tree(s)"
fi

printf '\n'
if [[ $fails -ne 0 ]]; then
  printf 'workflow-timeouts_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi
printf 'workflow-timeouts_test: all assertions passed (%d file(s), %d job(s), %d reusable-workflow call(s))\n' \
  "$total_files" "$total_jobs" "$reusable_jobs"
