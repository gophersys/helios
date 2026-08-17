#!/usr/bin/env bash
#
# _ctl/tests/publish-order.test.sh — the gate must run before the publish.
#
# Static means static: this file reads files. It starts no container, it calls
# no daemon and it reaches no network, so it runs identically on a laptop and on
# a CI runner — and, unlike .ci/smoke.sh, it runs in the PULL REQUEST gate.
# There is no image to build to check the ORDER OF STEPS in a YAML file, and a
# test that built one would be checking something else.
#
# ============================================================================
# THE DEFECT
# ============================================================================
#
# .github/workflows/build-and-push.yml, the base-runner job, measured:
#
#     line 148   push: true                    <- the image reaches ghcr.io
#     line 157   verify the published manifest
#     line 162   smoke test (native amd64)
#     line 167   run: bash .ci/smoke.sh base-runner
#
# The gate runs AFTER the irreversible action. When the smoke test fails, the
# broken image is already published under :latest and under its SHA tag, and
# every consumer can already pull it. Nothing in this repository rolls that
# back — `grep -rn "delete\|untag\|rollback" .github/workflows/` finds no such
# step in any job. So the job turns red and the image stays.
#
# The consequence is that every content assertion this repository owns is a
# REPORT and not a GATE. Together with the fact that .ci/smoke.sh does not run
# at pull request time at all, the real coverage is: a pull request that breaks
# an image passes its own gate, the image publishes on merge, and the failure
# lands on whoever pushes next.
#
# ============================================================================
# THE RULE THIS FILE ENCODES, AND THE ONE IT IS NOT
# ============================================================================
#
# Presence is not the property. "The workflow has a smoke step somewhere" is
# true TODAY, while the defect is live — so a presence test would be green on a
# broken file, which is the one result this repository has already shipped and
# does not want again. ORDER is the property.
#
# There were 2 rules available, and they are not variants of each other:
#
#   WEAK    "in a job that smokes, the smoke must precede the publish."
#           Red today for 1 job, green forever after 1 fix. It says NOTHING
#           about a job that publishes and never smokes, so the 4 image jobs
#           that ship unchecked stay invisible to the gate, and a 6th image job
#           can be added tomorrow that ships unchecked with this gate agreeing.
#
#   STRONG  "every job that publishes must smoke, and every smoke step must
#           precede every publishing step."
#           This is the rule worth having. It is red today for all 5 jobs, and
#           4 of those reds are a separate piece of work: base, flutter, zephyr
#           and zephyr-devbox have no smoke step in this workflow at all, which
#           .ci/README.md already states in prose — "read a green publish of
#           those 4 images as 'the image built', never as 'the image was
#           checked'".
#
# This file encodes the STRONG rule and writes the 4 known gaps down as a named
# debt list, UNSMOKED_TODAY, rather than weakening the rule to fit them. The
# list is a ratchet, checked in both directions:
#
#   - a publishing job that neither smokes nor appears in the list FAILS, so a
#     6th image job cannot be added unchecked;
#   - an entry that HAS gained a smoke step FAILS, asking for its deletion, so
#     the list cannot go stale and cannot describe the workflow as worse than
#     it is;
#   - an entry naming a job that no longer exists FAILS.
#
# It can therefore only shrink, and the whole array goes when it is empty.
#
# This is NOT the allowlist that dockerfile-args.test.sh refused to open. That
# one would have suppressed the rule on input that was CORRECT, and it would
# have grown with every new tool. This one names input that is WRONG, every
# entry is a defect somebody still owes, and the ratchet makes growth a visible
# line in a diff rather than a quiet exception.
#
# ============================================================================
# WHAT MUST STILL BE ALLOWED TO RUN AFTER THE PUSH
# ============================================================================
#
# `verify the published manifest` reads the manifest back out of the registry.
# It cannot run before the push, because before the push there is nothing to
# read. A rule that said "every check precedes the publish" would be
# unsatisfiable, so this file does not say that: it constrains the SMOKE step
# only, and it separately pins verify-published to stay AFTER the publish. That
# second clause exists so the first cannot be satisfied by the wrong fix —
# hoisting every step above the push would silence the smoke rule and break the
# manifest check at the same time.
#
# ============================================================================
# WHAT BREAKS THIS RULE WHEN linux/arm64 ARRIVES — read this before widening
# SANCTIONED_PLATFORMS
# ============================================================================
#
# SANCTIONED_PLATFORMS holds 1 platform today, so the cheap remedy is available:
# build with `push: false` + `load: true`, smoke the loaded local image, then
# publish. The fixture carries a `push: false` step precisely so the detector is
# watched NOT to count it as a publish, which is what makes that remedy legal
# here.
#
# `load: true` cannot take a multi-platform build. buildx produces a manifest
# LIST for 2 platforms and the docker image store holds a single image, so the
# build fails rather than loading half of it. The day a second architecture is
# sanctioned — which is the direction the buildx work in this branch exists to
# enable — the load-and-smoke shape stops working, and what is left is:
#
#   - push to a THROWAWAY tag, smoke each platform out of the registry, then
#     push the real tags. THIS RULE REPORTS THAT AS A VIOLATION, because the
#     throwaway push is a `push: true` step that runs before the smoke. The
#     report would be a FALSE RED. That is measured and not predicted — the
#     shape was built in a throwaway copy of this workflow and run:
#
#         base-runner: the image ships at step 6 and is not checked until step 7
#           publishes   step 6   .github/workflows/build-and-push.yml:143
#           smokes      step 7   .github/workflows/build-and-push.yml:155
#
#   - build to a local registry or `--output type=oci`, smoke from there, then
#     publish. This rule is satisfied, because nothing reaches ghcr.io before
#     the smoke.
#
# So the rule survives the arm64 switch only if the remedy chosen there does not
# publish to ghcr.io before smoking. Whoever takes the throwaway-tag route has
# to change this test with it, and that change is a decision about what
# "publish" means to this repository — not a line to delete.
#
# Usage: bash _ctl/tests/publish-order.test.sh
#
set -Eeuo pipefail
IFS=$'\n\t'

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
PROJECT_ROOT="$REPO_ROOT"

# The logging lives in _ctl/lib.sh, 1 time only — the same source line every
# other script in this repository uses.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../lib.sh
source "$REPO_ROOT/_ctl/lib.sh"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=harness.sh
source "$TESTS_DIR/harness.sh"

TEST_NAME="publish-order.test.sh"

# Both copies of the publishing workflow. The provider file is the source of
# truth for the GitHub provider and platform-policy.test.sh compares the 2 with
# `cmp`, so reading both here is redundant WHILE that check is healthy. It is
# read anyway: a test that only holds when another test file is healthy is a
# test with an undeclared dependency, and the 2 files have already drifted twice.
WORKFLOWS=(
  ".github/workflows/build-and-push.yml"
  ".ci/providers/github/build-and-push.yml"
)

# The jobs the publishing workflow declares, written as a literal for the reason
# platform-policy.test.sh writes the sanctioned platform as a literal: a test
# that reads its expectation out of the file it is checking agrees with whatever
# that file happens to say, a wrong thing included. This list is also what makes
# a parser that has stopped matching fail loudly instead of reporting a clean
# file it never read.
EXPECTED_JOBS=(
  "base"
  "base-runner"
  "flutter"
  "zephyr"
  "zephyr-devbox"
  "cloud"
)

# The publishing jobs that run NO smoke step today. Every entry is a defect, not
# an exception — see .ci/README.md, "Which images CI smokes". Delete an entry
# the moment its job gains a smoke step; the ratchet below fails if you do not.
#
# The list is EMPTY, and the 4 names that were here are the work of smoke-v2:
# base, flutter, zephyr and zephyr-devbox. Each one publishes with 1 `push: true`
# step and asserts nothing about the image it ships. The list is emptied FIRST,
# so check 2d reports those 4 jobs in both copies of the workflow until each job
# builds with `push: false` + `load: true`, smokes the loaded image, and then
# publishes from the cache — the shape base-runner and cloud already use.
#
# The array stays declared while it is empty. It is the ratchet, and check 2e
# reads it in the other direction: a name that returns here has to be a visible
# line in a diff.
UNSMOKED_TODAY=()

# The counter-stimulus. A detector that has only ever seen correct input has
# never been observed to fire.
FIXTURE="$TESTS_DIR/fixtures/publish-order/build-and-push.yml"

# ---------------------------------------------------------------------------
# The reader.
#
# 3 kinds of step matter, and each is recognised by what it DOES rather than by
# what it is called. A step name is prose: "smoke test (native amd64)" can be
# renamed in a pull request that means nothing by it, and a rule keyed on the
# name would then read a workflow with no smoke step at all as clean.
#
#   publish   the step block carries `push: true`. Not "uses
#             docker/build-push-action" — the expected fix adds a SECOND
#             build-push step with `push: false`, and counting that as a publish
#             would forbid the fix.
#   smoke     the step block invokes .ci/smoke.sh.
#   verify    the step block invokes `ctl.sh verify-published`.
# ---------------------------------------------------------------------------

# step_flag <slice> <extended regex> — 1 when a NON-COMMENT line of the step
# matches, else 0. A comment is prose and not an instruction, the same rule
# dockerfile-args.test.sh applies to a Dockerfile; the fixture carries a comment
# naming .ci/smoke.sh so this is watched rather than assumed.
function step_flag() {
  local slice="$1" pattern="$2"
  if printf '%s\n' "$slice" | sed -e '/^[[:space:]]*#/d' | grep -qE -- "$pattern"; then
    printf '1'
  else
    printf '0'
  fi
}

# step_label <slice> — how a reader of the failure will find the step: its
# `name:` when it has one, otherwise its `uses:`.
function step_label() {
  local slice="$1"
  local line body name="" uses=""
  while IFS= read -r line; do
    body="${line#"${line%%[![:space:]]*}"}"
    body="${body#- }"
    case "$body" in
      name:*) if [[ -z "$name" ]]; then name="${body#name:}"; fi ;;
      uses:*) if [[ -z "$uses" ]]; then uses="${body#uses:}"; fi ;;
    esac
  done <<< "$slice"
  if [[ -n "$name" ]]; then
    printf '%s' "${name# }"
  elif [[ -n "$uses" ]]; then
    printf '%s' "${uses# }"
  else
    printf '(unnamed step)'
  fi
}

# step_table <file> — 1 record per step of every job, in file order:
#
#   job|index|line|publish|smoke|verify|label
#
# where index is the 1-based position of the step within its job and line is the
# line the step starts on. Position is the whole point of this file, so it is
# carried explicitly rather than inferred from the order of the records.
#
# The walk is a small indentation state machine over the real workflow's shape:
# `jobs:` at column 0, a job name at 2, a job key at 4, a step dash at 6. No
# YAML library is used, because this repository ships none on the path that runs
# `ctl.sh test`, and a hermetic test that needs a tool the gate does not install
# is a test that skips. Every assumption the machine makes is checked below —
# the job list, a step count per job, and at least 1 step of each kind — so a
# shape it cannot read fails loudly instead of reporting an empty clean file.
function step_table() {
  local file="$1"
  local text stripped indent boundary
  local line_number in_jobs=0 in_steps=0
  local job="" index=0
  local open=0 open_job="" open_index=0 open_start=0
  local slice publish smoke verify label slice_line
  local lines=()
  local out=""

  # The file is read once, into memory. A `sed -n "a,bp" "$file"` per step reads
  # the same file the walk is reading, which shellcheck reports as SC2094 and
  # which `ctl.sh validate` fails on. Both of these workflows are ~350 lines.
  while IFS= read -r text || [[ -n "$text" ]]; do
    lines+=("$text")
  done < "$file"
  # A synthetic column-0 line past the end. It closes the last step exactly the
  # way a real boundary closes every other one, so the flush below is written
  # once instead of once for the loop and once for end-of-file.
  lines+=("end-of-file:")

  for ((line_number = 1; line_number <= ${#lines[@]}; line_number++)); do
    text="${lines[line_number - 1]}"
    stripped="${text#"${text%%[![:space:]]*}"}"
    [[ -z "$stripped" ]] && continue
    # A comment can never be structure. Deciding this before the indentation is
    # read keeps an 8-column comment inside a step from closing the step.
    case "$stripped" in '#'*) continue ;; esac
    indent=$(( ${#text} - ${#stripped} ))

    boundary="none"
    if [[ "$indent" -eq 0 ]]; then
      boundary="root"
    elif [[ "$in_jobs" -eq 1 && "$indent" -eq 2 && "$stripped" =~ ^[A-Za-z0-9_.-]+:[[:space:]]*$ ]]; then
      boundary="job"
    elif [[ "$in_jobs" -eq 1 && -n "$job" && "$indent" -eq 4 ]]; then
      boundary="job_key"
    elif [[ "$in_steps" -eq 1 && "$indent" -eq 6 && "$stripped" == "- "* ]]; then
      boundary="step"
    fi
    [[ "$boundary" == "none" ]] && continue

    # Every boundary closes the step that was open, and the step ends on the
    # line before this one.
    if [[ "$open" -eq 1 ]]; then
      slice=""
      for ((slice_line = open_start; slice_line < line_number; slice_line++)); do
        slice="${slice}${lines[slice_line - 1]}"$'\n'
      done
      publish="$(step_flag "$slice" '^[[:space:]]+push:[[:space:]]*true[[:space:]]*$')"
      smoke="$(step_flag "$slice" '\.ci/smoke\.sh')"
      verify="$(step_flag "$slice" 'ctl\.sh[[:space:]]+verify-published')"
      label="$(step_label "$slice")"
      out="${out:+${out}
}${open_job}|${open_index}|${open_start}|${publish}|${smoke}|${verify}|${label}"
      open=0
    fi

    case "$boundary" in
      root)
        job=""
        index=0
        in_steps=0
        if [[ "$stripped" == "jobs:"* ]]; then in_jobs=1; else in_jobs=0; fi
        ;;
      job)
        job="${stripped%%:*}"
        index=0
        in_steps=0
        ;;
      job_key)
        if [[ "$stripped" == "steps:"* ]]; then in_steps=1; else in_steps=0; fi
        ;;
      step)
        index=$((index + 1))
        open=1
        open_job="$job"
        open_index="$index"
        open_start="$line_number"
        ;;
      *) ;;
    esac
  done

  printf '%s' "$out"
}

# table_jobs <table> — the job names in file order, no repeats.
function table_jobs() {
  local table="$1" record job last=""
  while IFS= read -r record; do
    [[ -z "$record" ]] && continue
    job="${record%%|*}"
    if [[ "$job" != "$last" ]]; then
      printf '%s\n' "$job"
      last="$job"
    fi
  done <<< "$table"
}

# marked_steps <table> <job> <publish|smoke|verify> — `index:line:label` for each
# step of that job carrying the kind, in file order. Silent when there are none.
function marked_steps() {
  local table="$1" want_job="$2" kind="$3"
  local job index line publish smoke verify label flag
  while IFS='|' read -r job index line publish smoke verify label; do
    [[ -z "$job" ]] && continue
    [[ "$job" == "$want_job" ]] || continue
    case "$kind" in
      publish) flag="$publish" ;;
      smoke)   flag="$smoke" ;;
      verify)  flag="$verify" ;;
      *)       flag="0" ;;
    esac
    [[ "$flag" == "1" ]] || continue
    printf '%s:%s:%s\n' "$index" "$line" "$label"
  done <<< "$table"
}

# step_indices <records> — the index column of a `marked_steps` result, space
# separated, so a set of step POSITIONS can be compared as 1 string.
function step_indices() {
  local records="$1" record out=""
  while IFS= read -r record; do
    [[ -z "$record" ]] && continue
    out="${out:+${out} }${record%%:*}"
  done <<< "$records"
  printf '%s' "$out"
}

# describe_step <file label> <index:line:label> — 1 evidence line.
function describe_step() {
  local file_label="$1" record="$2"
  local index line label
  index="${record%%:*}"
  record="${record#*:}"
  line="${record%%:*}"
  label="${record#*:}"
  printf 'step %s   %s:%s   "%s"' "$index" "$file_label" "$line" "$label"
}

# ---------------------------------------------------------------------------
# The 3 rules, each a function of the table so the fixture and the real files
# are judged by the same code.
# ---------------------------------------------------------------------------

# late_smoke_report <table> <file label> — a block per job whose LAST smoke step
# runs after its FIRST publishing step. First publish and last smoke on purpose:
# the property is that the image is checked before ANY of it ships, so it is the
# earliest publish and the latest check that have to be compared. Silent when
# every job is clean.
function late_smoke_report() {
  local table="$1" file_label="$2"
  local job publish_steps smoke_steps first_publish last_smoke
  local publish_index smoke_index out=""

  while IFS= read -r job; do
    [[ -z "$job" ]] && continue
    publish_steps="$(marked_steps "$table" "$job" publish)"
    smoke_steps="$(marked_steps "$table" "$job" smoke)"
    [[ -n "$publish_steps" && -n "$smoke_steps" ]] || continue

    first_publish="${publish_steps%%$'\n'*}"
    last_smoke="${smoke_steps##*$'\n'}"
    publish_index="${first_publish%%:*}"
    smoke_index="${last_smoke%%:*}"
    [[ "$smoke_index" -gt "$publish_index" ]] || continue

    out="${out:+${out}
}${job}: the image ships at step ${publish_index} and is not checked until step ${smoke_index}
  publishes   $(describe_step "$file_label" "$first_publish")
  smokes      $(describe_step "$file_label" "$last_smoke")"
  done <<< "$(table_jobs "$table")"

  printf '%s' "$out"
}

# unsmoked_publishers <table> — the name of every job that publishes and runs no
# smoke step, 1 per line.
function unsmoked_publishers() {
  local table="$1"
  local job
  while IFS= read -r job; do
    [[ -z "$job" ]] && continue
    [[ -n "$(marked_steps "$table" "$job" publish)" ]] || continue
    [[ -z "$(marked_steps "$table" "$job" smoke)" ]] || continue
    printf '%s\n' "$job"
  done <<< "$(table_jobs "$table")"
}

# early_verify_report <table> <file label> — a block per job that reads back the
# published manifest BEFORE the push that would create it.
function early_verify_report() {
  local table="$1" file_label="$2"
  local job publish_steps verify_steps first_publish first_verify
  local publish_index verify_index out=""

  while IFS= read -r job; do
    [[ -z "$job" ]] && continue
    publish_steps="$(marked_steps "$table" "$job" publish)"
    verify_steps="$(marked_steps "$table" "$job" verify)"
    [[ -n "$publish_steps" && -n "$verify_steps" ]] || continue

    first_publish="${publish_steps%%$'\n'*}"
    first_verify="${verify_steps%%$'\n'*}"
    publish_index="${first_publish%%:*}"
    verify_index="${first_verify%%:*}"
    [[ "$verify_index" -lt "$publish_index" ]] || continue

    out="${out:+${out}
}${job}: the manifest is read at step ${verify_index}, before the push at step ${publish_index} creates it
  verifies    $(describe_step "$file_label" "$first_verify")
  publishes   $(describe_step "$file_label" "$first_publish")"
  done <<< "$(table_jobs "$table")"

  printf '%s' "$out"
}

# joined <array element...> — 1 element per line, sorted, for a set comparison.
function joined() {
  printf '%s\n' "$@" | sort
}

printf '=== RUN  %s\n' "$TEST_NAME"

# -------- 1. the counter-stimulus: all 3 detectors FIRE, and stay quiet --------
# This runs before the real files on purpose. A verdict on the real workflow
# means nothing until the same functions have been watched to report a file that
# is broken AND to leave the correct shape alone.
if [[ ! -f "$FIXTURE" ]]; then
  fail_check "counter_stimulus_fixture_exists" \
    "the fixture this test proves itself with is absent: ${FIXTURE}"
else
  pass_check "counter_stimulus_fixture_exists"

  fixture_table="$(step_table "$FIXTURE")"
  fixture_jobs="$(table_jobs "$fixture_table")"
  assert_equal "counter_stimulus_parses_into_its_4_jobs" \
    "$(joined "ships-then-smokes" "ships-unsmoked" "smokes-then-ships" "verifies-too-early")" \
    "$(printf '%s\n' "$fixture_jobs" | sort)" \
    "the reader did not find the shape it claims to read, so every verdict below is worthless"

  fixture_late="$(late_smoke_report "$fixture_table" "fixture")"
  assert_contains "counter_stimulus_reports_the_job_that_ships_before_it_smokes" \
    "$fixture_late" "ships-then-smokes" \
    "that job publishes at step 2 and smokes at step 4"
  assert_not_contains "counter_stimulus_leaves_the_correctly_ordered_job_alone" \
    "$fixture_late" "smokes-then-ships" \
    "that job smokes a loaded local image and only then publishes; a rule that reports it forbids its own fix"
  # The half that keeps the eventual fix legal, asserted on the detector itself
  # rather than on the report it feeds. `push: false` is a build, not a publish;
  # a detector that could not tell the 2 apart would make the load-and-smoke
  # shape unable to satisfy this rule, and the test would forbid its own fix.
  # smokes-then-ships is: 1 checkout, 2 build push:false, 3 smoke, 4 push:true,
  # 5 verify.
  assert_equal "counter_stimulus_does_not_read_push_false_as_a_publish" \
    "4" "$(step_indices "$(marked_steps "$fixture_table" "smokes-then-ships" publish)")" \
    "step 2 of that job builds with push: false and must not count as a publish" \
    "step 4 is the push: true that really ships the image"
  assert_equal "counter_stimulus_finds_the_smoke_step_at_its_real_position" \
    "3" "$(step_indices "$(marked_steps "$fixture_table" "smokes-then-ships" smoke)")" \
    "position is the whole property this file checks, so the reader has to get it exactly right"

  fixture_unsmoked="$(unsmoked_publishers "$fixture_table")"
  assert_contains "counter_stimulus_reports_the_job_that_publishes_unsmoked" \
    "$fixture_unsmoked" "ships-unsmoked" \
    "that job publishes and runs no smoke step"
  # ships-unsmoked names .ci/smoke.sh inside a COMMENT. A detector that reads
  # prose calls it smoked, and the check above would then pass for no reason.
  assert_not_contains "counter_stimulus_does_not_read_a_commented_smoke_as_a_smoke" \
    "$fixture_unsmoked" "smokes-then-ships" \
    "smokes-then-ships really does smoke and must never be reported as unsmoked"

  fixture_early="$(early_verify_report "$fixture_table" "fixture")"
  assert_contains "counter_stimulus_reports_the_manifest_read_before_the_push" \
    "$fixture_early" "verifies-too-early" \
    "that job reads the published manifest at step 2 and pushes at step 4"
  assert_not_contains "counter_stimulus_leaves_a_verify_after_the_push_alone" \
    "$fixture_early" "smokes-then-ships" \
    "verify-published cannot run before the push, so this direction must stay legal"
fi

# -------- 2. the real workflow, and the provider copy of it --------
for relative in "${WORKFLOWS[@]}"; do
  file="$REPO_ROOT/$relative"

  if [[ ! -f "$file" ]]; then
    fail_check "${relative}_exists" \
      "the file list in this test is stale; this path is named but absent"
    continue
  fi
  pass_check "${relative}_exists"

  table="$(step_table "$file")"
  jobs="$(table_jobs "$table")"

  # 2a. the reader found the shape it claims to read.
  assert_equal "${relative}_declares_the_expected_jobs" \
    "$(joined "${EXPECTED_JOBS[@]}")" \
    "$(printf '%s\n' "$jobs" | sort)" \
    "either the workflow gained or lost a job, or the reader in this test stopped matching" \
    "a rule that reads no job passes every file, including a broken one"

  # 2b. every job the reader found really publishes. A job in the PUBLISHING
  # workflow that publishes nothing is either a real change to the workflow or a
  # detector that stopped matching, and a publish detector that matches nothing
  # makes the ordering rule below pass on every file.
  #
  # A job with no steps at all needs no separate clause: it produces no record,
  # so it is absent from the job list and 2a above reports it.
  non_publishing=""
  while IFS= read -r job; do
    [[ -z "$job" ]] && continue
    if [[ -z "$(marked_steps "$table" "$job" publish)" ]]; then
      non_publishing="${non_publishing:+${non_publishing}
}${job}"
    fi
  done <<< "$jobs"
  if [[ -n "$non_publishing" ]]; then
    fail_check "${relative}_every_job_has_a_publishing_step" \
      "these jobs carry no 'push: true' step:" \
      "$non_publishing" \
      "either a job in the publishing workflow stopped publishing — which is fine, and this list is what you edit —" \
      "or the publish detector stopped matching, which would make the ordering rule below pass on any file"
  else
    pass_check "${relative}_every_job_has_a_publishing_step"
  fi

  # The smoke and verify detectors need the same liveness proof. If either stops
  # matching, its rule below becomes vacuous and reports a clean file.
  smoke_total=0
  verify_total=0
  while IFS='|' read -r _job _index _line _publish record_smoke record_verify _label; do
    if [[ "$record_smoke" == "1" ]]; then
      smoke_total=$((smoke_total + 1))
    fi
    if [[ "$record_verify" == "1" ]]; then
      verify_total=$((verify_total + 1))
    fi
  done <<< "$table"
  if [[ "$smoke_total" -ge 1 ]]; then
    pass_check "${relative}_carries_at_least_one_smoke_step"
  else
    fail_check "${relative}_carries_at_least_one_smoke_step" \
      "no step in this workflow invokes .ci/smoke.sh" \
      "either every content check was deleted, or the smoke detector in this test stopped matching"
  fi
  if [[ "$verify_total" -ge 1 ]]; then
    pass_check "${relative}_carries_at_least_one_verify_published_step"
  else
    fail_check "${relative}_carries_at_least_one_verify_published_step" \
      "no step in this workflow invokes 'ctl.sh verify-published'" \
      "either the manifest check was deleted, or the verify detector in this test stopped matching"
  fi

  # 2c. THE RULE. Nothing ships before it is checked.
  late="$(late_smoke_report "$table" "$relative")"
  if [[ -z "$late" ]]; then
    pass_check "${relative}_smoke_precedes_every_publish"
  else
    fail_check "${relative}_smoke_precedes_every_publish" \
      "$late" \
      "the push is irreversible and no job in this workflow has a rollback step, so a smoke test placed" \
      "after it can report a broken image but cannot stop one reaching a consumer" \
      "fix: build with 'push: false' + 'load: true', run the smoke against the loaded local image, then" \
      "publish in a second step — the build is cached, so the publish costs a layer copy" \
      "read the arm64 note at the top of this file before choosing any remedy that pushes first"
  fi

  # 2d. coverage: a job that publishes must smoke, or be named debt.
  unsmoked="$(unsmoked_publishers "$table")"
  undeclared=""
  while IFS= read -r job; do
    [[ -z "$job" ]] && continue
    known=0
    # `${a[@]+"${a[@]}"}` and not `"${a[@]}"`: bash 3.2 reads an EMPTY array as an
    # unbound variable under `set -u`, and the file runs on the mac host too.
    for debt in ${UNSMOKED_TODAY[@]+"${UNSMOKED_TODAY[@]}"}; do
      if [[ "$debt" == "$job" ]]; then
        known=1
      fi
    done
    if [[ "$known" -eq 0 ]]; then
      undeclared="${undeclared:+${undeclared}
}${job}"
    fi
  done <<< "$unsmoked"
  if [[ -z "$undeclared" ]]; then
    pass_check "${relative}_no_new_job_publishes_without_a_smoke_step"
  else
    fail_check "${relative}_no_new_job_publishes_without_a_smoke_step" \
      "these jobs publish an image and assert nothing about its content:" \
      "$undeclared" \
      "give the job a smoke step that runs BEFORE its push" \
      "adding the name to UNSMOKED_TODAY in this test is not the fix; that list records debt that already existed"
  fi

  # 2e. the ratchet. The debt list must shrink, and it must never be stale.
  stale=""
  for debt in ${UNSMOKED_TODAY[@]+"${UNSMOKED_TODAY[@]}"}; do
    still_owed=0
    while IFS= read -r job; do
      if [[ "$job" == "$debt" ]]; then
        still_owed=1
      fi
    done <<< "$unsmoked"
    if [[ "$still_owed" -eq 0 ]]; then
      stale="${stale:+${stale}
}${debt}"
    fi
  done
  if [[ -z "$stale" ]]; then
    pass_check "${relative}_the_unsmoked_debt_list_is_current"
  else
    fail_check "${relative}_the_unsmoked_debt_list_is_current" \
      "these names are in UNSMOKED_TODAY and are no longer unsmoked publishers:" \
      "$stale" \
      "delete each one from UNSMOKED_TODAY in this test — the list may only shrink, and it goes when it is empty" \
      "a debt list that describes the workflow as worse than it is stops being read"
  fi

  # 2f. reading the manifest back still has to happen after the push.
  early="$(early_verify_report "$table" "$relative")"
  if [[ -z "$early" ]]; then
    pass_check "${relative}_the_manifest_is_read_after_the_push"
  else
    fail_check "${relative}_the_manifest_is_read_after_the_push" \
      "$early" \
      "verify-published reads the manifest the registry holds, so before the push there is nothing to read" \
      "moving every step above the push satisfies the smoke rule by breaking this one"
  fi
done

test_summary "$TEST_NAME"
