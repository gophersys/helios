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
# (base-runner has since been retired — the pools that consumed it now run the
# `cloud` image — so do not go looking for that job. The measurement is kept as
# written because it is the evidence this file exists for, and the shape it
# describes is the shape every job of the workflow had.)
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
#           4 of those reds are a separate piece of work: base, mobile and the
#           2 images that are `embedded` now had no smoke step in this workflow
#           at all, which .ci/README.md already states in prose — "read a green
#           publish of those 4 images as 'the image built', never as 'the image
#           was checked'".
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
# linux/arm64 ARRIVED, AND THIS RULE SURVIVED IT. HOW, AND AT WHAT COST
# ============================================================================
#
# This paragraph was a WARNING until the set widened. It is an ANSWER now, and
# the answer is that the 2 builds of each job stopped naming the same platform
# list.
#
# `load: true` cannot take a multi-platform build. buildx produces a manifest
# LIST for 2 platforms and the docker image store holds a single image, so a
# 2-platform build with `load: true` fails rather than loading half of it. That
# fact did not change; what changed is which build carries the list.
#
#   - The GATE build names SMOKE_PLATFORM, `linux/amd64`, with `push: false` +
#     `load: true`. 1 platform, so the load works, and it is the architecture
#     the arc-build pool runs NATIVELY — which the smoke needs, because the
#     version checks the Dockerfiles dropped cannot execute under emulation.
#   - The PUBLISH build names the full PLATFORMS and runs after the smoke, from
#     the cache the gate build wrote.
#
# So NOTHING reaches ghcr.io before the smoke, and this rule is satisfied by
# construction rather than by exception. The NARROWING of the gate build is what
# preserved smoke-gates-publish through a widening of the publish. The fixture
# still carries a `push: false` step precisely so the detector is watched NOT to
# count it as a publish, and that is what makes the shape legal here.
#
# THE ROUTE THAT WAS NOT TAKEN, and why it is recorded rather than deleted:
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
#     Whoever takes that route has to change this test with it, and that change
#     is a decision about what "publish" means to this repository — not a line
#     to delete.
#
# THE COST, stated plainly because no check here can state it: the arm64 content
# of every image is NOT smoke-gated at publish time. The amd64 smoke gates the
# publish for both variants; the arm64 variant ships on the same build
# definition, the same pins and the same per-download digest comparison, and
# `_ctl/tests/verify-published.test.sh` holds the rule that the manifest carries
# both afterwards. Closing it means smoking arm64 out of the registry AFTER the
# push, which is the recorded follow-up and is a step this rule would have to
# learn to allow.
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

# ---------------------------------------------------------------------------
# THE JOB SET IS BUILD_ORDER, AND NOT A 5TH COPY OF IT
# ---------------------------------------------------------------------------
#
# This was a literal list of 6 names until 2026-08-17, justified the way
# platform-policy.test.sh justifies writing `linux/amd64` as a literal: a test
# that reads its expectation out of the file it is checking agrees with whatever
# that file happens to say. That justification does not survive contact with
# this particular set, for 2 reasons.
#
#   1. The expectation is NOT read out of the file being checked. The file being
#      checked is build-and-push.yml; the expectation comes from BUILD_ORDER in
#      ctl.sh, which is a different declaration made for a different purpose.
#      The property is AGREEMENT between 2 declarations of 1 set — exactly what
#      rule 7 of scheduled-workflows.test.sh already holds the scan matrix to,
#      and for the same stated reason: a literal written here is a THIRD copy,
#      and the next change to the image set only has to edit 1 more file.
#
#   2. .claude/rules/00-identity.md already states this as an invariant, and the
#      sentence has since got shorter: "The graph is declared ONCE, in
#      images.yaml at the repository root", with BUILD_ORDER in ctl.sh and in
#      .ci/ctl.sh, `needs:` in both copies of build-and-push.yml and the input
#      path table all DERIVED from it. A literal here does not check that
#      invariant; it checks a snapshot of it, taken by hand, on some past day.
#      Section 4 below is where a hand-kept literal earns its place, because
#      there the thing being compared is the declaration itself.
#
# Retiring an image is the measurement. base-runner leaves BUILD_ORDER in the
# change this comment is written for: the ARC pools repointed at `cloud`, so
# nothing consumes it any more. With the literal in place that retirement needs
# this test file edited, by an agent who owns no implementation, to describe a
# change made in files it does not own. A test that must be hand-edited to agree
# with a correct change is a test that gets hand-edited to agree with a wrong
# one.
#
# What the literal really bought was LIVENESS, and that half is kept below as
# REQUIRED_IMAGES: an anchor that makes the set non-empty, not an expectation.
# ---------------------------------------------------------------------------

# The 2 homes of BUILD_ORDER. ctl.sh is the declaration this file compares the
# workflow against; .ci/ctl.sh is the provider's copy of it, and the 2 are held
# to each other below.
#
# Both are read, and not just the one used. Until now nothing in `ctl.sh test`
# read the second copy at all: the agreement between them is asserted by a step
# of validate.yml, so it holds in CI and not in the local gate that this branch
# is being merged on. A test whose declaration has an unwatched twin is a test
# that agrees with half a change.
BUILD_ORDER_HOMES=(
  "ctl.sh"
  ".ci/ctl.sh"
)

# The liveness anchor, and NOT the expectation. Everything below is derived from
# BUILD_ORDER, so an emptied or truncated BUILD_ORDER would agree with a
# workflow that had lost the same jobs, and both would be green. These 2 names
# are the roots of the dependency graph — `base` is the parent of the base
# family and `cloud` FROMs ubuntu directly — so the set cannot be empty and
# cannot have lost a whole family without a visible line in this diff.
REQUIRED_IMAGES=(
  "base"
  "cloud"
)

# The publishing jobs that run NO smoke step today. Every entry is a defect, not
# an exception — see .ci/README.md, "Which images CI smokes". Delete an entry
# the moment its job gains a smoke step; the ratchet below fails if you do not.
#
# The list is EMPTY, and the 4 names that were here are the work of smoke-v2:
# base, mobile, and the 2 images that are `embedded` now. Each one published
# with 1 `push: true`
# step and asserted nothing about the image it shipped. The list is emptied FIRST,
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
AFFECTED_FIXTURE="$TESTS_DIR/fixtures/publish-order/affected-filters.yml"

# The 1 home of the affected-only decision. Every job asks it, and the input
# paths of every image are declared in it — see section 3.
AFFECTED_SCRIPT=".ci/affected.sh"

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
  local uncommented=""
  uncommented="$(sed -e '/^[[:space:]]*#/d' <<< "$slice")"
  if grep -qE -- "$pattern" <<< "$uncommented"; then
    printf '1'
  else
    printf '0'
  fi
}

# step_affected_image <slice> — the image `.ci/affected.sh` is asked about in
# this step, empty when the step does not call it.
#
# The comment strip is the same rule step_flag applies, and it is watched:
# no-filter-at-all in the fixture names the script inside a comment.
#
# No `| head -1`. grep writing into a reader that exits early gets EPIPE, and
# under `set -o pipefail` the pipeline then reports failure for a needle that IS
# present — the defect harness.sh records at length. The first line is taken in
# bash instead, where there is no second process to kill.
function step_affected_image() {
  local slice="$1" uncommented hit=""
  uncommented="$(sed -e '/^[[:space:]]*#/d' <<< "$slice")"
  hit="$(grep -oE -- '\.ci/affected\.sh[[:space:]]+[A-Za-z0-9_.-]+' <<< "$uncommented")" || hit=""
  hit="${hit%%$'\n'*}"
  [[ -z "$hit" ]] && return 0
  printf '%s' "${hit##*[[:space:]]}"
}

# step_identifier <slice> — the step's `id:`, empty when it declares none. Only
# a step with an id can be read by an `if:` further down the job.
function step_identifier() {
  awk '
    {
      line = $0
      sub(/^[[:space:]]+/, "", line)
      sub(/^-[[:space:]]+/, "", line)
      if (line ~ /^#/) { next }
      if (line !~ /^id:/) { next }
      sub(/^id:[[:space:]]*/, "", line)
      sub(/[[:space:]]*#.*$/, "", line)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
      if (line != "") { print line }
      exit
    }
  ' <<< "$1"
}

# step_gate_reference <slice> — the `steps.<id>.outputs.<key>` that an `if:` on
# this step reads, empty when the step carries no `if:` or its condition reads
# no step output.
#
# The search is confined to the `if:` line. `${{ steps.sha.outputs.short }}`
# appears in the `tags:` of every publish step in this repository, and a reader
# that looked at the whole step would read that as a guard and report every
# ungated push as gated.
function step_gate_reference() {
  local slice="$1" conditions hit=""
  conditions="$(awk '
    {
      line = $0
      sub(/^[[:space:]]+/, "", line)
      sub(/^-[[:space:]]+/, "", line)
      if (line ~ /^#/) { next }
      if (line ~ /^if:/) { print line }
    }
  ' <<< "$slice")"
  [[ -z "$conditions" ]] && return 0
  hit="$(grep -oE -- 'steps\.[A-Za-z0-9_-]+\.outputs\.[A-Za-z0-9_-]+' <<< "$conditions")" || hit=""
  printf '%s' "${hit%%$'\n'*}"
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
#   job|index|line|publish|smoke|verify|affected|id|gate|label
#
# where index is the 1-based position of the step within its job and line is the
# line the step starts on. Position is the whole point of this file, so it is
# carried explicitly rather than inferred from the order of the records.
#
# `label` stays LAST because a step name is the one field that can hold
# anything, `|` included, and `IFS='|' read` puts every leftover field in the
# variable it fills last. `gate` is a `steps.<id>.outputs.<key>` token and
# `affected` is an image name, so neither can carry the separator; the raw `if:`
# condition is deliberately NOT a column, because `failure() || success()` would
# split a record in half.
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
  local slice publish smoke verify label slice_line affected identifier gate
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
      affected="$(step_affected_image "$slice")"
      identifier="$(step_identifier "$slice")"
      gate="$(step_gate_reference "$slice")"
      label="$(step_label "$slice")"
      out="${out:+${out}
}${open_job}|${open_index}|${open_start}|${publish}|${smoke}|${verify}|${affected}|${identifier}|${gate}|${label}"
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
  local job index line publish smoke verify affected identifier gate label flag
  while IFS='|' read -r job index line publish smoke verify affected identifier gate label; do
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

# ---------------------------------------------------------------------------
# The affected-filter readers.
#
# A warm rebuild of the whole image set measured ~35 minutes on every push to
# main, and most pushes to main touch 1 image or none. So each job now asks
# `.ci/affected.sh <image>` whether this commit changes that image's inputs and
# gates its work on the answer.
#
# That optimisation reaches straight into the property this file exists for. A
# job whose SMOKE is gated and whose PUSH is not publishes, on every unaffected
# commit, an image this run never built and never checked — the same defect the
# ordering rule catches, arriving through a new door. And a job that asks about
# the WRONG image is silent in the other direction: the run is green and that
# image simply stops being rebuilt on the commits that change it.
# ---------------------------------------------------------------------------

# job_filter_steps <table> <job> — `<index>:<line>:<image>:<id>` for every step
# of that job that calls .ci/affected.sh. Silent when the job calls it nowhere.
function job_filter_steps() {
  local table="$1" want_job="$2"
  local job index line publish smoke verify affected identifier gate label
  while IFS='|' read -r job index line publish smoke verify affected identifier gate label; do
    [[ -z "$job" ]] && continue
    [[ "$job" == "$want_job" ]] || continue
    [[ -n "$affected" ]] || continue
    printf '%s:%s:%s:%s\n' "$index" "$line" "$affected" "${identifier:-<no id>}"
  done <<< "$table"
  return 0
}

# ungated_acting_steps <table> <job> <gate reference> — `<index>:<line>:<label>
# (<what it does>)` for every step of that job that smokes, publishes or reads
# back a manifest without being guarded by that exact reference.
#
# The 3 kinds are the ones that must not happen for an image this run did not
# build: the smoke asserts against a local ref that was never loaded, the push
# ships an unchecked image, and the manifest read looks for a `:<sha>` tag that
# was never created. The `push: false` load step is deliberately NOT one of
# them — an ungated load wastes minutes and cannot ship anything.
function ungated_acting_steps() {
  local table="$1" want_job="$2" want_gate="$3"
  local job index line publish smoke verify affected identifier gate label kind
  while IFS='|' read -r job index line publish smoke verify affected identifier gate label; do
    [[ -z "$job" ]] && continue
    [[ "$job" == "$want_job" ]] || continue
    kind=""
    if [[ "$publish" == "1" ]]; then kind="publishes"; fi
    if [[ "$smoke" == "1" ]]; then kind="${kind:+${kind}+}smokes"; fi
    if [[ "$verify" == "1" ]]; then kind="${kind:+${kind}+}reads the manifest"; fi
    [[ -n "$kind" ]] || continue
    [[ "$gate" == "$want_gate" ]] && continue
    printf '%s:%s:%s (%s, guarded by %s)\n' \
      "$index" "$line" "$label" "$kind" "${gate:-no if: at all}"
  done <<< "$table"
  return 0
}

# affected_defects <table> <file label> — 1 block per job whose filter is
# missing, doubled, unreadable, asked about the wrong image, or not the guard on
# every step that acts. Silent when every job is correct.
function affected_defects() {
  local table="$1" file_label="$2"
  local job filters filter_total record index line image identifier
  local ungated out=""

  while IFS= read -r job; do
    [[ -z "$job" ]] && continue
    filters="$(job_filter_steps "$table" "$job")"
    filter_total="$(grep -c . <<< "$filters")" || filter_total=0

    if [[ "$filter_total" -eq 0 ]]; then
      out="${out:+${out}
}${job}: no step asks .ci/affected.sh whether this commit changes ${job}"
      continue
    fi
    if [[ "$filter_total" -gt 1 ]]; then
      out="${out:+${out}
}${job}: ${filter_total} steps call .ci/affected.sh, so which answer guards the job is undecided
${filters}"
      continue
    fi

    record="${filters%%$'\n'*}"
    IFS=':' read -r index line image identifier <<< "$record"

    if [[ "$image" != "$job" ]]; then
      out="${out:+${out}
}${job}: the filter at ${file_label}:${line} asks about '${image}', not about '${job}'
  a job that asks about another image stops being rebuilt on the commits that change IT,
  and the run stays green while it happens"
      continue
    fi

    if [[ "$identifier" == "<no id>" ]]; then
      out="${out:+${out}
}${job}: the filter step at ${file_label}:${line} declares no 'id:', so no other step can read its answer"
      continue
    fi

    ungated="$(ungated_acting_steps "$table" "$job" "steps.${identifier}.outputs.build")"
    [[ -z "$ungated" ]] && continue
    out="${out:+${out}
}${job}: these steps act without reading the filter's answer:
${ungated}
  want on each: if: \${{ steps.${identifier}.outputs.build == 'true' }}"
  done <<< "$(table_jobs "$table")"

  printf '%s' "$out"
}

# affected_calls_total <table> — how many steps of the whole file call
# .ci/affected.sh. The liveness reader: every clause above is keyed on finding
# that call, and a detector that stopped matching would report a workflow with
# no filters at all as a workflow whose filters are all correct.
function affected_calls_total() {
  local table="$1" total=0
  local job index line publish smoke verify affected identifier gate label
  while IFS='|' read -r job index line publish smoke verify affected identifier gate label; do
    [[ -n "$affected" ]] || continue
    total=$((total + 1))
  done <<< "$table"
  printf '%s' "$total"
}

# case_arm_labels stood here and is DELETED with the 2 tables it read. It parsed
# the case arms of image_own_paths in .ci/affected.sh and of image_check_groups
# in .ci/smoke.sh, and both functions are gone: each file derives its answer from
# images.yaml through _ctl/lib.sh now. A reader kept past its input is worse than
# a deleted one — it finds 0 rows and reports every image as dead, which is the
# red section 4 was rewritten to answer.

# joined <array element...> — 1 element per line, sorted, for a set comparison.
function joined() {
  printf '%s\n' "$@" | sort
}

# ---------------------------------------------------------------------------
# The declaration reader.
# ---------------------------------------------------------------------------

# BUILD_ORDER_OUTPUT / BUILD_ORDER_STATUS / BUILD_ORDER_STDERR — set by the
# reader below, the way run_library_probe in scheduled-workflows.test.sh
# publishes its 3 results.
BUILD_ORDER_OUTPUT=""
BUILD_ORDER_STATUS=0
BUILD_ORDER_STDERR=""

# read_build_order <relative ctl script> — print the BUILD_ORDER that script
# declares, 1 image per line.
#
# Read out of a RUNNING shell and not out of the text of a line: the value the
# shell ends up holding is the value the script builds with, and a line-reader
# agrees with a BUILD_ORDER that a later line rewrites. The `set --` clears the
# argv so the dispatcher at the foot of each script takes its help path and
# returns 0, instead of exiting 1 on an unknown command.
function read_build_order() {
  local relative="$1"
  local errors
  errors="$(mktemp)"
  BUILD_ORDER_STATUS=0
  BUILD_ORDER_OUTPUT="$(CTL_SCRIPT="$REPO_ROOT/$relative" bash -c '
    set --
    source "$CTL_SCRIPT" > /dev/null
    printf "%s\n" "${BUILD_ORDER[@]}"
  ' 2> "$errors")" || BUILD_ORDER_STATUS=$?
  BUILD_ORDER_STDERR="$(cat "$errors")"
  rm -f "$errors"
  printf '%s' "$BUILD_ORDER_OUTPUT"
}

printf '=== RUN  %s\n' "$TEST_NAME"

# -------- 0. the declaration: it is readable, it is alive, it is 1 value ------
# Every clause below compares the workflow against this set, so a set that could
# not be read would leave them all passing over nothing.
build_order=""
build_order="$(read_build_order "${BUILD_ORDER_HOMES[0]}")"
if [[ "$BUILD_ORDER_STATUS" -eq 0 && -n "$build_order" ]]; then
  pass_check "the_BUILD_ORDER_declaration_is_readable"
else
  fail_check "the_BUILD_ORDER_declaration_is_readable" \
    "sourcing ${BUILD_ORDER_HOMES[0]} and reading BUILD_ORDER exited ${BUILD_ORDER_STATUS}" \
    "it printed:" "${build_order:-<nothing>}" \
    "stderr was:" "${BUILD_ORDER_STDERR:-<nothing>}" \
    "with no declaration to compare against, every job clause below passes over an empty set"
fi

# THE LIVENESS CLAUSE. See REQUIRED_IMAGES above: an anchor, not an expectation.
missing_required=""
for required in "${REQUIRED_IMAGES[@]}"; do
  grep -qxF -- "$required" <<< "$build_order" || missing_required="${missing_required:+${missing_required}
}${required}"
done
if [[ -z "$missing_required" ]]; then
  pass_check "BUILD_ORDER_holds_the_roots_of_the_dependency_graph"
else
  fail_check "BUILD_ORDER_holds_the_roots_of_the_dependency_graph" \
    "these images are absent from BUILD_ORDER:" "$missing_required" \
    "BUILD_ORDER is:" "$(tr '\n' ' ' <<< "$build_order")" \
    "base is the parent of the base family and cloud FROMs ubuntu directly, so a set without" \
    "one of them is not a narrowed image set — it is a declaration that stopped being read," \
    "and every job clause below would then agree with a workflow that lost the same jobs"
fi

# The 2 homes hold 1 value. This is the clause a half-done retirement breaks:
# drop an image from ctl.sh alone and every other check in this file still
# passes, because every other check reads ctl.sh.
provider_build_order=""
provider_build_order="$(read_build_order "${BUILD_ORDER_HOMES[1]}")"
provider_status="$BUILD_ORDER_STATUS"
provider_stderr="$BUILD_ORDER_STDERR"
if [[ "$provider_status" -ne 0 || -z "$provider_build_order" ]]; then
  fail_check "both_BUILD_ORDER_homes_declare_the_same_set" \
    "sourcing ${BUILD_ORDER_HOMES[1]} and reading BUILD_ORDER exited ${provider_status}" \
    "it printed:" "${provider_build_order:-<nothing>}" \
    "stderr was:" "${provider_stderr:-<nothing>}"
elif [[ "$build_order" == "$provider_build_order" ]]; then
  pass_check "both_BUILD_ORDER_homes_declare_the_same_set"
else
  fail_check "both_BUILD_ORDER_homes_declare_the_same_set" \
    "${BUILD_ORDER_HOMES[0]}:  $(tr '\n' ' ' <<< "$build_order")" \
    "${BUILD_ORDER_HOMES[1]}: $(tr '\n' ' ' <<< "$provider_build_order")" \
    ".claude/rules/00-identity.md: the graph is declared ONCE, in images.yaml, and both of these" \
    "arrays are filled from it at source time — so a difference here is 2 readers of 1 file" \
    "disagreeing, and the manifest is where you look before either script" \
    "the ORDER matters as well as the set: it is a build order, and base has to precede its children" \
    "until now only a step of validate.yml compared these 2, so a local gate could not see the drift"
fi

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

# -------- 1b. the counter-stimulus for the affected filter, all 4 ways --------
if [[ ! -f "$AFFECTED_FIXTURE" ]]; then
  fail_check "counter_stimulus_affected_fixture_exists" \
    "the fixture this rule proves itself with is absent: ${AFFECTED_FIXTURE}"
else
  pass_check "counter_stimulus_affected_fixture_exists"

  affected_table="$(step_table "$AFFECTED_FIXTURE")"
  assert_equal "counter_stimulus_parses_the_affected_fixture_into_its_4_jobs" \
    "$(joined "gated-correctly" "ungated-publish" "asks-about-another-image" "no-filter-at-all")" \
    "$(printf '%s\n' "$(table_jobs "$affected_table")" | sort)" \
    "the reader did not find the shape it claims to read, so every verdict below is worthless"

  # The 3 new columns, read off the job that is correct. Each one is what a
  # separate defect below is recognised by, so each is watched on its own.
  assert_equal "counter_stimulus_reads_the_image_the_filter_asks_about" \
    "2:33:gated-correctly:filter" \
    "$(job_filter_steps "$affected_table" "gated-correctly")" \
    "the filter is step 2 of that job, it asks about gated-correctly, and it is called filter"
  assert_equal "counter_stimulus_does_not_read_a_commented_affected_call_as_a_call" \
    "" "$(job_filter_steps "$affected_table" "no-filter-at-all")" \
    "that job names .ci/affected.sh in a comment, and a comment runs nothing"

  affected_report="$(affected_defects "$affected_table" "fixture")"

  assert_not_contains "counter_stimulus_leaves_the_correctly_gated_job_alone" \
    "$affected_report" "gated-correctly:" \
    "every acting step of that job reads steps.filter.outputs.build" \
    "a detector that reports it forbids the only correct shape there is"
  assert_contains "counter_stimulus_reports_the_publish_that_reads_no_filter" \
    "$affected_report" "ungated-publish:" \
    "that job skips its smoke on an unaffected commit and pushes anyway, which is this file's" \
    "own defect arriving through the new door"
  assert_contains "counter_stimulus_reports_the_job_that_asks_about_another_image" \
    "$affected_report" "asks-about-another-image:" \
    "the copy-paste defect: the run is green and that image stops being rebuilt when it changes"
  assert_contains "counter_stimulus_reports_the_job_with_no_filter_at_all" \
    "$affected_report" "no-filter-at-all:" \
    "an unfiltered job rebuilds every image on every push, which is the ~35 minutes this exists to end"

  # The liveness reader, both directions. A count of 0 over a file that DOES
  # carry filters would make every clause above vacuous on the real workflow.
  assert_equal "counter_stimulus_counts_the_filter_calls_of_the_fixture" \
    "3" "$(affected_calls_total "$affected_table")" \
    "3 of the 4 jobs call it; the fourth names it only in a comment"
  assert_equal "counter_stimulus_counts_no_filter_call_in_the_ordering_fixture" \
    "0" "$(affected_calls_total "$(step_table "$FIXTURE")")" \
    "that fixture predates the filter and calls it nowhere, so a reader that found one there" \
    "would be matching something other than the call"
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

  # 2a. the reader found the shape it claims to read, and the workflow declares
  # 1 job per image BUILD_ORDER declares — no more, and no fewer.
  assert_equal "${relative}_declares_one_job_per_BUILD_ORDER_image" \
    "$(printf '%s\n' "$build_order" | sort)" \
    "$(printf '%s\n' "$jobs" | sort)" \
    "want: the images BUILD_ORDER declares in ${BUILD_ORDER_HOMES[0]}" \
    "got:  the jobs this workflow declares" \
    "either the 2 declarations of the image set disagree — retire an image in 1 of them and this" \
    "is the check that says so — or the reader in this test stopped matching," \
    "and a rule that reads no job passes every file, including a broken one"

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
  while IFS='|' read -r _job _index _line _publish record_smoke record_verify _affected _id _gate _label; do
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

  # 2g. THE AFFECTED FILTER. Its liveness clause first: every clause of the
  # rule is keyed on finding a call to the filter, and over a file with none
  # they are all green — including a file where the optimisation was reverted
  # and the gates were left behind.
  filter_total="$(affected_calls_total "$table")"
  if [[ "$filter_total" -ge 1 ]]; then
    pass_check "${relative}_carries_at_least_one_affected_filter_step"
  else
    fail_check "${relative}_carries_at_least_one_affected_filter_step" \
      "no step of this workflow runs ${AFFECTED_SCRIPT}" \
      "either every job builds unconditionally again — a warm all-image rebuild measured" \
      "~35 minutes on every push to main — or the filter detector in this test stopped matching," \
      "which would make the rule below pass on any file"
  fi

  affected="$(affected_defects "$table" "$relative")"
  if [[ -z "$affected" ]]; then
    pass_check "${relative}_every_job_gates_on_its_own_affected_answer"
  else
    fail_check "${relative}_every_job_gates_on_its_own_affected_answer" \
      "$affected" \
      "the rule is 1 sentence: a job asks ${AFFECTED_SCRIPT} about ITS OWN image, exactly once," \
      "from a step with an id, and every step that smokes, publishes or reads back a manifest" \
      "reads that answer" \
      "an ungated push on an unaffected commit ships an image this run never built and never" \
      "smoked, which is the defect at the top of this file wearing a new hat"
  fi
done

# ===========================================================================
# 3. THE FILTER ANSWERS FOR EVERY IMAGE, AND REFUSES THE ONES IT CANNOT
# ===========================================================================
# The workflow half above proves each job ASKS about itself. This half proves
# the thing being asked can answer, by RUNNING it: the filter is a script, and
# an assertion about a script that never ran it is an assertion about its text.
#
# Section 4 below reads the SOURCE the filter derives that answer from —
# images.yaml — for the direction no argument can probe: an entry for an image
# nobody builds, which running the filter with a name proves nothing about.
if [[ ! -f "$REPO_ROOT/$AFFECTED_SCRIPT" ]]; then
  fail_check "the_affected_filter_script_exists" \
    "absent: ${AFFECTED_SCRIPT}" \
    "every job of the publishing workflow calls it, so without it every job fails at 127"
  fail_check "every_BUILD_ORDER_image_has_an_input_path_row" \
    "absent: ${AFFECTED_SCRIPT}"
  fail_check "the_filter_refuses_an_image_it_declares_no_paths_for" \
    "absent: ${AFFECTED_SCRIPT}"
else
  pass_check "the_affected_filter_script_exists"

  # -- direction 1, behavioural: it answers for every image that is built --
  # workflow_dispatch is the manual all-images build, so the script answers
  # `build=true` and returns before it touches git. The input paths are resolved
  # BEFORE that branch, which is what makes this probe a test of the manifest
  # row and not of the trigger.
  unanswered=""
  while IFS= read -r image; do
    [[ -z "$image" ]] && continue
    probe_status=0
    probe_output=""
    probe_output="$(GITHUB_EVENT_NAME=workflow_dispatch GITHUB_REF="refs/heads/main" \
      bash "$REPO_ROOT/$AFFECTED_SCRIPT" "$image" 2>&1)" || probe_status=$?
    if [[ "$probe_status" -ne 0 ]]; then
      unanswered="${unanswered:+${unanswered}
}${image}: exited ${probe_status} — ${probe_output}"
    fi
  done <<< "$build_order"
  if [[ -z "$unanswered" ]]; then
    pass_check "every_BUILD_ORDER_image_has_an_input_path_row"
  else
    fail_check "every_BUILD_ORDER_image_has_an_input_path_row" \
      "$unanswered" \
      "BUILD_ORDER is:" "$(tr '\n' ' ' <<< "$build_order")" \
      "the job of an image with no row exits 2 at publish time, on main, after the merge" \
      "fix: give the image a non-empty 'paths' list in ${IMAGES_MANIFEST} — that is where the" \
      "input table lives, and ${AFFECTED_SCRIPT} derives its answer from it through _ctl/lib.sh"
  fi

  # -- the fallback fails CLOSED --
  # An answer of `build=true` for an unknown image would be worse than no
  # manifest at all: every image would build, and the entry that was deleted
  # would never be missed.
  refusal_status=0
  refusal_output=""
  refusal_output="$(GITHUB_EVENT_NAME=workflow_dispatch \
    bash "$REPO_ROOT/$AFFECTED_SCRIPT" "no-such-image" 2>&1)" || refusal_status=$?
  if [[ "$refusal_status" -eq 0 ]]; then
    fail_check "the_filter_refuses_an_image_it_declares_no_paths_for" \
      "want: a non-zero exit status for an image with no row" \
      "got:  0, with output:" "${refusal_output:-<nothing>}" \
      "a filter that answers for an image it knows nothing about answers for a deleted row too," \
      "and the probe above would then pass over a table with no rows in it at all"
  elif ! grep -qF -- "no-such-image" <<< "$refusal_output"; then
    fail_check "the_filter_refuses_an_image_it_declares_no_paths_for" \
      "it exited ${refusal_status} and its message never names the image it refused" \
      "output was:" "${refusal_output:-<nothing>}"
  else
    pass_check "the_filter_refuses_an_image_it_declares_no_paths_for"
  fi

fi

# ===========================================================================
# 4. THE MANIFEST DECLARES THE SET, AND CARRIES EVERY ROW THE HOMES READ
# ===========================================================================
# This section read 2 case tables until images.yaml landed:
#
#   .ci/affected.sh  image_own_paths     what a rebuild of that image depends on
#   .ci/smoke.sh     image_check_groups  what the guest runs inside that image
#
# Both functions are DELETED. Each file derives its answer from images.yaml
# through _ctl/lib.sh now, so a case-arm reader over either one finds 0 rows and
# reports every image as dead — which is exactly what it did, and it is the red
# this rewrite answers.
#
# The properties did not go anywhere; they moved into the manifest, and they are
# read there. What changes is WHERE a defect can be:
#
#   before  2 hand-kept tables could each drift from BUILD_ORDER
#   after   1 manifest row per image, and the drift left to catch is between
#           that manifest and the hand-kept literal below
#
# THE LITERAL IS THE POINT, AND IT IS NOT A COPY THIS FILE FORGOT TO DELETE.
# Section 0 above deliberately refuses a literal job list, because there the
# expectation is AGREEMENT between 2 derived declarations — BUILD_ORDER and the
# workflow — and both are derived from this manifest, so a literal would be a
# third copy of a set nobody hand-writes any more.
#
# Here the manifest is not a derived home; it is the declaration itself, and
# nothing else in this repository states the image set by hand. A check that
# read the set out of images.yaml and then compared it to images.yaml would
# agree with any manifest, an emptied one included. So the set is written here,
# by hand, and what this file owes the manifest is set EQUALITY —
# .claude/rules/00-identity.md, "the policy tests keep their hand-kept literals":
# a literal list that no longer matches the manifest is a red test, and that is
# the check that replaces the hand-copying the 6 declarations used to need.
#
# Adding an image is therefore an images.yaml entry plus this array, in 1 change.
PUBLISHED_IMAGES=(
  "base"
  "mobile"
  "embedded"
  "cloud"
  "hardware"
  "ui"
)

# WHICH READER, AND WHY. The rows below are read with manifest_yq from
# _ctl/lib.sh — its RESOLUTION only (yq 4.x on PATH, else mikefarah/yq at the
# versions.env pin through docker, else a failure naming the tool). The
# EXPRESSION is written here, and the accessors are not used: image_names,
# image_own_paths and image_check_groups are the derivation under test, and a
# check that asked them what the manifest says would be asking the
# implementation to grade itself. A second yq resolver written into this file
# would be the duplication that _ctl/lib.sh exists to end — and it would be the
# half that breaks first, since only 1 of the 2 would learn the container route.
#
# The record shape is _ctl/lib.sh's own: `|` separated, the list fields joined
# with a space. No field of this manifest can hold a `|`.
manifest_status=0
manifest_records=""
manifest_records="$(manifest_yq '.images | to_entries | .[] |
  [.key, .value.parent, (.value.paths | join(" ")), (.value.groups | join(" "))] |
  join("|")' 2>&1)" || manifest_status=$?

manifest_names=""
if [[ "$manifest_status" -eq 0 && -n "$manifest_records" ]]; then
  manifest_names="$(cut -d'|' -f1 <<< "$manifest_records")"
fi

# The liveness clause, and it comes first: every clause below reads those
# records, and an unreadable manifest would leave them all passing over an empty
# set — the believed-and-empty check this repository refuses elsewhere.
if [[ -n "$manifest_names" ]]; then
  pass_check "the_image_manifest_is_readable"
else
  fail_check "the_image_manifest_is_readable" \
    "reading ${IMAGES_MANIFEST} exited ${manifest_status}" \
    "it printed:" "${manifest_records:-<nothing>}" \
    "the manifest is the ONE declaration of the image set, so nothing below it can be answered" \
    "without it — and every clause below would agree with a repository that has no images"
fi

if [[ -z "$manifest_names" ]]; then
  fail_check "the_manifest_declares_exactly_the_published_images" \
    "unreadable: ${IMAGES_MANIFEST}"
  fail_check "every_declared_image_has_its_own_input_paths" \
    "unreadable: ${IMAGES_MANIFEST}"
  fail_check "every_declared_image_inherits_its_parents_input_paths" \
    "unreadable: ${IMAGES_MANIFEST}"
  fail_check "every_declared_image_has_check_groups" \
    "unreadable: ${IMAGES_MANIFEST}"
else
  # -- 4a. set equality, in both directions --
  # An image in the manifest and not here is an image that publishes with no
  # policy literal watching it. An image here and not in the manifest is a name
  # this file goes on believing after the manifest dropped it, and every
  # per-image clause below would then report it as a manifest defect.
  assert_equal "the_manifest_declares_exactly_the_published_images" \
    "$(joined "${PUBLISHED_IMAGES[@]}")" \
    "$(sort <<< "$manifest_names")" \
    "${IMAGES_MANIFEST} is the ONE declaration of the image set, and PUBLISHED_IMAGES in this" \
    "test is the hand-kept literal it owes set equality to — edit both in the same change" \
    "a literal that no longer matches the manifest is a red test, and that is what replaces" \
    "the 6 hand-copied declarations the graph used to live in"

  # -- 4b/4c/4d. the rows, for each image the LITERAL names --
  # Keyed on the literal and not on the manifest's own key list: a manifest that
  # lost an entry must fail the row clauses too, and a loop over its keys would
  # simply not visit the image that went missing.
  missing_paths=""
  missing_groups=""
  broken_inheritance=""
  for image in "${PUBLISHED_IMAGES[@]}"; do
    record="$(awk -F'|' -v want="$image" '$1 == want { print; exit }' <<< "$manifest_records")"
    if [[ -z "$record" ]]; then
      missing_paths="${missing_paths:+${missing_paths}
}${image}: no entry in ${IMAGES_MANIFEST} at all"
      missing_groups="${missing_groups:+${missing_groups}
}${image}: no entry in ${IMAGES_MANIFEST} at all"
      continue
    fi
    image_parent_name="$(cut -d'|' -f2 <<< "$record")"
    image_own="$(cut -d'|' -f3 <<< "$record")"
    image_groups="$(cut -d'|' -f4 <<< "$record")"

    # 4b. an image whose paths nothing can match never rebuilds, and the
    # affected-only gate reports that as "nothing changed" on every commit.
    if [[ -z "$image_own" ]]; then
      missing_paths="${missing_paths:+${missing_paths}
}${image}: an empty paths list"
    fi

    # 4d. an image with no groups gets a smoke that compares versions and
    # exercises nothing, which is not a smoke.
    if [[ -z "$image_groups" ]]; then
      missing_groups="${missing_groups:+${missing_groups}
}${image}: an empty groups list"
    fi

    # 4c. THE INCLUSION. A child's FULL input set has to CONTAIN its parent's
    # own paths: that is what makes "the parent built, so the child builds" true
    # by construction, and a missing edge publishes a layer on a parent that
    # moved under it.
    #
    # This is the 1 clause that reads a derived answer, because the derivation
    # IS the property: the manifest states a child's own paths WITHOUT its
    # parent's on purpose, so the inclusion exists only in image_input_paths.
    # The parent's rows come out of the manifest record, so the 2 sides of the
    # comparison are not the same function talking to itself.
    [[ -z "$image_parent_name" ]] && continue
    parent_record="$(awk -F'|' -v want="$image_parent_name" '$1 == want { print; exit }' <<< "$manifest_records")"
    if [[ -z "$parent_record" ]]; then
      broken_inheritance="${broken_inheritance:+${broken_inheritance}
}${image}: names parent '${image_parent_name}', which ${IMAGES_MANIFEST} does not declare"
      continue
    fi
    full_status=0
    full_paths=""
    full_paths="$(image_input_paths "$image" 2>&1)" || full_status=$?
    if [[ "$full_status" -ne 0 ]]; then
      broken_inheritance="${broken_inheritance:+${broken_inheritance}
}${image}: image_input_paths exited ${full_status} — ${full_paths}"
      continue
    fi
    # Split on the SPACE the record joins its list with, and not on IFS: this
    # file sets IFS to newline+tab, so an unquoted expansion would hand the
    # whole `base/ _build/ versions.env .dockerignore` field over as 1 path and
    # report every multi-path parent as missing. Measured while writing this
    # clause — the red named a path with 3 spaces in it.
    while IFS= read -r parent_path; do
      [[ -z "$parent_path" ]] && continue
      grep -qxF -- "$parent_path" <<< "$full_paths" && continue
      broken_inheritance="${broken_inheritance:+${broken_inheritance}
}${image}: its input set misses '${parent_path}', which its parent '${image_parent_name}' declares"
    done <<< "$(cut -d'|' -f3 <<< "$parent_record" | tr ' ' '\n')"
  done

  if [[ -z "$missing_paths" ]]; then
    pass_check "every_declared_image_has_its_own_input_paths"
  else
    fail_check "every_declared_image_has_its_own_input_paths" \
      "${IMAGES_MANIFEST} — the input paths that decide a rebuild:" \
      "$missing_paths" \
      "an image whose paths match nothing never rebuilds, and .ci/affected.sh reports that as" \
      "'nothing changed' on every commit — a job that is green because it did no work"
  fi

  if [[ -z "$broken_inheritance" ]]; then
    pass_check "every_declared_image_inherits_its_parents_input_paths"
  else
    fail_check "every_declared_image_inherits_its_parents_input_paths" \
      "${IMAGES_MANIFEST} — a child's input set must CONTAIN its parent's:" \
      "$broken_inheritance" \
      "that inclusion is what makes 'the parent built, so the child builds' true by construction" \
      "without it a child publishes a layer FROM a parent that moved under it in the same run"
  fi

  if [[ -z "$missing_groups" ]]; then
    pass_check "every_declared_image_has_check_groups"
  else
    fail_check "every_declared_image_has_check_groups" \
      "${IMAGES_MANIFEST} — the functional groups the guest runs:" \
      "$missing_groups" \
      "a smoke that compares versions and exercises nothing is not a smoke: the image would" \
      "publish having proven only that its tools report a number"
  fi
fi

test_summary "$TEST_NAME"
