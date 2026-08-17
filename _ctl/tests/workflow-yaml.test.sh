#!/usr/bin/env bash
#
# _ctl/tests/workflow-yaml.test.sh — the rules that need a PARSER.
#
# Rule 1: every workflow file of both directories parses.
# Rule 2: no job runs on a BILLED runner, and no step runs a hosted-only action.
#
# ============================================================================
# THE DEFECT THIS FILE EXISTS FOR
# ============================================================================
#
# `.github/workflows/security-nightly.yml` reached a green pull request gate
# carrying a `run:` line that YAML cannot parse:
#
#   run: bash .ci/notify-failure.sh "image scan: ${{ needs.scan.result }}"
#
# The value is a PLAIN scalar holding a colon followed by a space, so the parser
# reads that colon as the start of a mapping value where a mapping cannot start,
# and the whole document is rejected. GitHub refuses a workflow it cannot parse.
# The nightly would therefore never have run at all — and a workflow that never
# runs also never fails, so the silence would have read exactly like a clean
# scan every morning.
#
# Every check that this repository had already pointed at that file passed. They
# are awk and grep readers, and they were all correct: the schedule key is
# there, the cron is there, `issues: write` is there, the notifier call is there
# under `if: failure()`, the trivy flags are there. Each token was on the right
# line, spelled right. A token reader cannot see a document that does not parse,
# so the defect was not a missed rule — it was a missing CLASS of rule.
#
# This file is that class, and it is deliberately the whole class rather than
# 1 more rule about 1 more token: EVERY file of both workflow directories has to
# parse, so the next unparseable file is caught the day it is written, whatever
# made it unparseable.
#
# ============================================================================
# WHY THIS IS A SIBLING FILE AND NOT A SECTION OF scheduled-workflows.test.sh
# ============================================================================
#
# 2 reasons, and either alone is enough.
#
#   1. That file states a property of itself, in a boxed section headed NO YAML
#      LIBRARY: its readers are awk and bash, and it needs no tool the gate does
#      not already run. This rule needs a PARSER — that is the entire point of
#      it — so putting it there would make that file's own header false. The
#      tool dependency is quarantined in 1 file instead.
#
#   2. The scope is different. That file is keyed on the SCHEDULE trigger, and
#      it judges the scheduled subset. This rule has nothing to do with a
#      trigger: `validate.yml` and `pr-review.yml` must parse for exactly the
#      same reason, and they run on a pull request.
#
# ============================================================================
# WHY THE BILLED-RUNNER RULE IS IN THIS FILE AND NOT IN A THIRD ONE
# ============================================================================
#
# Because it needs the parser, and this is the file that has one.
#
# `runs-on` and `uses` are STRUCTURE. A grep for `ubuntu-latest` reports the
# comment that explains why the job left ubuntu-latest, and a grep for
# `jlumbroso/free-disk-space` reports the comment that records the deleted step.
# Both of those comments are wanted — platform-policy.test.sh states the same
# principle about `linux/arm64`: a file must stay free to say the words while it
# explains why the thing was dropped. A rule that forbade the explanation along
# with the defect would be deleted by the first person who needed to write one.
#
# So the reader asks yq for `.jobs[].runs-on` and `.jobs[].steps[].uses`, which
# are the values GitHub itself acts on. A comment is not one of them, by
# construction rather than by a comment-stripping pass that has to be right.
#
# THE DEFECT IT EXISTS FOR: this account spent 1805 of its 2000 GitHub Actions
# minutes with a $0 budget behind them. At 0 remaining, a workflow scheduled on
# a hosted runner does not fail — it never STARTS, so it attaches no failing
# check to any pull request and files no issue, and the nightly security scan
# reads exactly like a clean night. The homelab pools (`arc-*`) cost nothing and
# are already what validate.yml and pr-review.yml run on. This rule is what
# stops a 7th workflow, or a 7th job, from being written against the meter.
#
# The second half is the same move in the other direction: an action written FOR
# a GitHub-hosted image is a defect on a homelab node. jlumbroso/free-disk-space
# deletes the preinstalled SDKs of a hosted image to reclaim ~25-30 GB. A runner
# pod shares its node's filesystem with every other pod on it, so on `arc-build`
# the same step deletes the node's caches and takes the other tenants with it.
# The 2 halves are 1 rule — "this workflow assumes a GitHub-hosted machine" — so
# they are checked together and named together.
#
# ============================================================================
# THE PARSER, AND WHY A MISSING ONE IS A FAILURE
# ============================================================================
#
# The resolution mirrors `hadolint_resolve` in ./ctl.sh: use the tool on PATH
# when it is usable, else run the pinned version through docker, and FAIL naming
# the tool when neither route exists. A missing tool is never a skip — a skipped
# parser is a green result that read no file at all, which is the shape this
# repository has already shipped once (validate reported OK while linting no
# Dockerfile on a host with no hadolint).
#
# It differs from hadolint's resolution in 1 way, on purpose. hadolint is
# accepted only at the EXACT pin, because hadolint's VERDICT depends on its
# version: 2.15.1 raises DL3064 and DL3066 on Dockerfiles that 2.14.0 passes, so
# a gate whose answer depends on what the operator installed is not a gate. yq
# is used here as a PARSER and nothing else. The question asked of it is "does
# this document parse", the answer is YAML 1.2's, and it does not move across
# 4.x point releases. So any 4.x on PATH is accepted, and the pin
# (`YQ_VERSION` in versions.env, the version the images ship) governs the
# container route. Major 4 is required rather than "some yq": the other yq
# (kislyuk/yq, a jq wrapper, at 3.x) takes a different command line and would
# fail for a reason that says nothing about the document.
#
# In the pull request gate this always takes the host route: validate.yml runs
# on `arc-org`, whose image is this repository's own base + runner layer, and
# that image ships yq at exactly YQ_VERSION.
#
# Usage: bash _ctl/tests/workflow-yaml.test.sh
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

TEST_NAME="workflow-yaml.test.sh"

# The 2 directories that hold a workflow. The provider directory is the source
# of truth and .github/workflows/ holds a copy of each of its files; both are
# read here, because a rule that only holds while another test file is healthy
# is a rule with an undeclared dependency.
WORKFLOW_DIRECTORIES=(
  ".github/workflows"
  ".ci/providers/github"
)

# The liveness anchor. Everything below is discovered by a walk of those
# directories, and a walk that stopped matching would report a clean parse of
# nothing at all. These 2 paths are what makes the set non-empty.
REQUIRED_FILES=(
  ".github/workflows/security-nightly.yml"
  ".ci/providers/github/security-nightly.yml"
)

# Where the pin lives.
PIN_HOME="versions.env"
PIN_NAME="YQ_VERSION"

# The counter-stimulus. A parser that has only ever seen documents that parse
# has never been observed to reject one.
YAML_FIXTURES="$TESTS_DIR/fixtures/workflow-yaml"

# THE POLICY, written here as a literal. Every job of this repository runs on a
# homelab pool, and every homelab pool is named `arc-<something>`: arc-org,
# arc-review, arc-build. A test that read the accepted prefix out of the
# workflows it judges would agree with `ubuntu-` on the day somebody wrote it.
SELF_HOSTED_RUNNER_PREFIX="arc-"

# The actions that only make sense on a GitHub-hosted image. Matched on the
# `<owner>/<repository>` half, so a version bump does not walk around the rule.
#
# 1 entry is not a list nobody will extend: `runner/` and `actions/cache` are
# the next candidates if the hosted assumptions turn up again, and the shape is
# already here for them.
HOSTED_ONLY_ACTIONS=(
  "jlumbroso/free-disk-space"
)

# ---------------------------------------------------------------------------
# The parser plumbing.
# ---------------------------------------------------------------------------

# yq_pin — the YQ_VERSION versions.env declares. Empty when there is none.
function yq_pin() {
  awk -v name="$PIN_NAME" '
    index($0, name "=") == 1 {
      value = substr($0, length(name) + 2)
      sub(/[[:space:]]*#.*$/, "", value)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      print value
      exit
    }
  ' "$REPO_ROOT/$PIN_HOME"
}

# yq_host_version — the version of the yq on PATH, empty when there is none.
#
# 2>&1 rather than 2>/dev/null, for the reason ctl.sh gives about hadolint: a yq
# that cannot report its own version is a yq whose output belongs on screen.
function yq_host_version() {
  local reported=""
  if command -v yq > /dev/null 2>&1; then
    reported="$(yq --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)" || reported=""
  fi
  printf '%s' "$reported"
}

# yq_resolve <pin> — print HOW to reach a parser, `host` or `container`.
#
# Its stdout is captured, so it logs nothing there: log_info writes to stdout in
# this repository and the caller would read the log line as the mode. It prints
# nothing at all and fails when neither route exists, because a workflow that no
# parser read must not report as a workflow that parses.
function yq_resolve() {
  local pin="$1" have=""
  have="$(yq_host_version)"
  if [[ "$have" =~ ^4\. ]]; then
    printf 'host'
    return 0
  fi
  if command -v docker > /dev/null 2>&1; then
    printf 'container'
    return 0
  fi
  log_error "a YAML parser is required and this host has yq ${have:-none}, with no docker to run mikefarah/yq:${pin}"
  log_error "run this inside the devcontainer, which ships yq ${pin}, or install yq 4.x"
  return 1
}

# yq_parse <mode> <pin> <file> — parse 1 document. Exit 0 when it parses;
# non-zero with the parser's own message on stdout when it does not.
#
# The document itself is thrown away (> /dev/null): the question is whether the
# file parses, and the content is every other test file's business.
function yq_parse() {
  local mode="$1" pin="$2" file="$3"
  case "$mode" in
    host)
      # The braces are what keeps the ERROR: the document goes to /dev/null and
      # the diagnostic is what reaches the caller. `> /dev/null 2>&1` would
      # discard the message as well, and the failure line would then say only
      # that the parse failed.
      { yq eval '.' "$file" > /dev/null; } 2>&1
      ;;
    container)
      # The same shape as hadolint_at_pin: mount the directory read-only, and
      # name the file by its basename inside the container.
      { docker run --rm -v "$(dirname "$file"):/w:ro" -w /w "mikefarah/yq:${pin}" \
        eval '.' "$(basename "$file")" > /dev/null; } 2>&1
      ;;
    *)
      printf 'yq_parse: unknown mode %s\n' "$mode"
      return 1
      ;;
  esac
}

# yq_query <mode> <pin> <file> <expression> — evaluate 1 expression over a
# document and print what it yields, 1 result per line.
#
# The same 2 routes yq_parse takes, for the same reason. It differs from
# yq_parse in what it does with the output: the document IS the answer here, so
# stdout is kept and only stderr is folded in — a query that fails has to say
# why on the same stream, or the caller reports an empty result as "the file
# declares none of these" when the truth is that nothing was read.
function yq_query() {
  local mode="$1" pin="$2" file="$3" expression="$4"
  case "$mode" in
    host)
      yq eval "$expression" "$file" 2>&1
      ;;
    container)
      docker run --rm -v "$(dirname "$file"):/w:ro" -w /w "mikefarah/yq:${pin}" \
        eval "$expression" "$(basename "$file")" 2>&1
      ;;
    *)
      printf 'yq_query: unknown mode %s\n' "$mode"
      return 1
      ;;
  esac
}

# runner_labels <mode> <pin> <file> — `<job>|<comma-joined runner labels>` for
# every job of the document, 1 record per job. A job that declares no `runs-on`
# at all yields an empty label half, which is an ANSWER and not an absence:
# GitHub cannot schedule such a job, and a reader that stayed silent about it
# would report a workflow with no runner as a workflow with no billed runner.
#
# `flatten` is what makes the 2 spellings 1 answer. `runs-on: arc-build` is a
# scalar and `runs-on: [self-hosted, arc-build]` is a sequence; a reader of the
# scalar form alone would report the list form as declaring no runner, and a
# reader of the list form alone would report every job in this repository that
# way. The join happens in the QUERY and the split happens in bash, because
# mikefarah's yq has no if/then/else — that is jq's — and a conditional written
# for the wrong dialect fails as a lexer error whose text looks like a label.
function runner_labels() {
  local mode="$1" pin="$2" file="$3"
  yq_query "$mode" "$pin" "$file" \
    '.jobs | to_entries | .[] |
       .key + "|" + ([.value.runs-on] | flatten | map(select(. != null)) | join(","))'
}

# step_actions <mode> <pin> <file> — `<job>|<uses value>` for every step that
# runs an action, 1 per line. Silent for a document with no jobs and for a job
# with no steps, both of which are legal.
function step_actions() {
  local mode="$1" pin="$2" file="$3"
  # `$job` is yq's variable and not bash's, so the single quotes are the point
  # rather than an oversight — the same note scheduled-workflows.test.sh writes
  # over its Dockerfile stimuli. Expanded by this shell it would be empty, and
  # every record would come back as `|<uses>` with no job name in it.
  # shellcheck disable=SC2016
  yq_query "$mode" "$pin" "$file" \
    '.jobs | to_entries | .[] |
       .key as $job |
       ([.value.steps[].uses] | flatten | map(select(. != null)) | .[]) |
       $job + "|" + .'
}

# billed_runner_report <records> — 1 evidence line per job whose runner labels
# name no homelab pool. Silent when every job names one.
#
# AT LEAST 1 label with the prefix, rather than every label: GitHub schedules a
# labelled job on a runner that carries ALL the labels, so `[self-hosted,
# arc-build]` is the arc-build pool spelled the long way and an every-label rule
# would report it. A set with no `arc-` label at all is reported whatever else
# it holds — `[self-hosted, linux]` names no pool this repository operates, and
# a job that names no pool is a job nobody can say the cost of.
function billed_runner_report() {
  local records="$1"
  local job labels label found out=""
  while IFS='|' read -r job labels; do
    [[ -z "$job" ]] && continue
    found=0
    while IFS= read -r label; do
      [[ -z "$label" ]] && continue
      case "$label" in
        "${SELF_HOSTED_RUNNER_PREFIX}"*) found=1 ;;
      esac
    done <<< "$(tr ',' '\n' <<< "$labels")"
    [[ "$found" -eq 1 ]] && continue
    out="${out:+${out}
}job ${job}: runs-on ${labels:-<none declared>}"
  done <<< "$records"
  printf '%s' "$out"
}

# hosted_only_report <records> — 1 evidence line per `<job>|<uses>` record that
# names a hosted-only action. The comparison is on the half before the `@`, so
# the rule survives a version bump of the action it forbids.
function hosted_only_report() {
  local records="$1"
  local job uses coordinate forbidden out=""
  while IFS='|' read -r job uses; do
    [[ -z "$job" ]] && continue
    coordinate="${uses%%@*}"
    for forbidden in "${HOSTED_ONLY_ACTIONS[@]}"; do
      [[ "$coordinate" == "$forbidden" ]] || continue
      out="${out:+${out}
}job ${job}: uses ${uses}"
    done
  done <<< "$records"
  printf '%s' "$out"
}

# workflow_files — every regular file of both directories, 1 per line, relative
# to the repository root.
#
# EVERY file, and not a *.yml glob. GitHub reads .yml and .yaml, and the
# provider directory is compared with .github/workflows/ byte for byte, so a
# file of any other kind in either place is already a defect — one that a glob
# would quietly walk past instead of parsing.
function workflow_files() {
  local directory file
  for directory in "${WORKFLOW_DIRECTORIES[@]}"; do
    [[ -d "$REPO_ROOT/$directory" ]] || continue
    while IFS= read -r file; do
      printf '%s\n' "${file#"$REPO_ROOT"/}"
    done < <(find "$REPO_ROOT/$directory" -type f | sort)
  done
}

printf '=== RUN  %s\n' "$TEST_NAME"

# ===========================================================================
# 1. THE PARSER — it is pinned, it is reachable, and it FIRES
# ===========================================================================
pin="$(yq_pin)"
if [[ "$pin" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  pass_check "the_yaml_parser_version_is_pinned"
else
  fail_check "the_yaml_parser_version_is_pinned" \
    "no '${PIN_NAME}=<semver>' row in ${PIN_HOME}" \
    "got: '${pin:-<no such pin>}'" \
    "the container route needs a version to run, and an unpinned parser is a parser" \
    "whose answer depends on what the registry served that morning"
fi

host_version="$(yq_host_version)"
mode=""
resolve_output=""
resolve_status=0
resolve_output="$(yq_resolve "$pin" 2>&1)" || resolve_status=$?
if [[ "$resolve_status" -eq 0 ]]; then
  mode="$resolve_output"
  pass_check "a_yaml_parser_is_reachable"
else
  fail_check "a_yaml_parser_is_reachable" \
    "no yq 4.x on PATH and no docker to run mikefarah/yq:${pin}" \
    "the resolver said:" "${resolve_output:-<nothing>}" \
    "a missing tool is a FAILURE and never a skip: a parser that never ran would leave" \
    "every clause below green over a file it did not read"
fi

if [[ -n "$mode" ]]; then
  log_info "yaml parser: ${mode} route (pin ${PIN_NAME}=${pin}, yq on PATH reports ${host_version:-none})"
fi

# -------- the counter-stimulus: the parser accepts, and the parser rejects ---
VALID_FIXTURE="$YAML_FIXTURES/valid.yml"
INVALID_FIXTURE="$YAML_FIXTURES/invalid-run-scalar.yml"

missing_fixtures=""
for fixture in "$VALID_FIXTURE" "$INVALID_FIXTURE"; do
  [[ -f "$fixture" ]] || missing_fixtures="${missing_fixtures:+${missing_fixtures}
}${fixture}"
done

if [[ -n "$missing_fixtures" ]]; then
  fail_check "counter_stimulus_yaml_fixtures_exist" \
    "the fixtures this test proves its parser with are absent:" \
    "$missing_fixtures"
elif [[ -z "$mode" ]]; then
  fail_check "counter_stimulus_yaml_fixtures_exist" \
    "the fixtures are present and no parser is reachable, so they were never read"
else
  pass_check "counter_stimulus_yaml_fixtures_exist"

  fixture_output=""
  fixture_status=0
  fixture_output="$(yq_parse "$mode" "$pin" "$VALID_FIXTURE")" || fixture_status=$?
  if [[ "$fixture_status" -eq 0 ]]; then
    pass_check "counter_stimulus_the_parser_accepts_a_valid_workflow"
  else
    fail_check "counter_stimulus_the_parser_accepts_a_valid_workflow" \
      "the parser exited ${fixture_status} on a file that parses:" "$VALID_FIXTURE" \
      "it said:" "${fixture_output:-<nothing>}" \
      "a parser that reports a correct file reports every file, and the rule below is then noise"
  fi

  fixture_output=""
  fixture_status=0
  fixture_output="$(yq_parse "$mode" "$pin" "$INVALID_FIXTURE")" || fixture_status=$?
  if [[ "$fixture_status" -eq 0 ]]; then
    fail_check "counter_stimulus_the_parser_reports_the_unquoted_run_scalar" \
      "want: a non-zero exit status on ${INVALID_FIXTURE}" \
      "got:  0, with output:" "${fixture_output:-<nothing>}" \
      "that fixture holds the exact defect this file exists for — a plain run: scalar" \
      "carrying ': ' — so a parser quiet on it is quiet on the real workflow too"
  elif ! grep -qF -- "mapping values are not allowed" <<< "$fixture_output"; then
    fail_check "counter_stimulus_the_parser_reports_the_unquoted_run_scalar" \
      "the parser rejected the fixture and its message does not name the reason" \
      "it said:" "${fixture_output:-<nothing>}" \
      "want a message naming: mapping values are not allowed" \
      "the reader of a red gate needs the line and the reason, or the next step is to parse by hand"
  elif ! grep -qF -- "line 45" <<< "$fixture_output"; then
    fail_check "counter_stimulus_the_parser_reports_the_unquoted_run_scalar" \
      "the message does not name line 45, which is the unparseable run: line of the fixture" \
      "it said:" "${fixture_output:-<nothing>}"
  else
    pass_check "counter_stimulus_the_parser_reports_the_unquoted_run_scalar"
  fi
fi

# ===========================================================================
# 2. THE RULE — every file of both directories parses
# ===========================================================================
files="$(workflow_files)"

if [[ -z "$files" ]]; then
  fail_check "the_workflow_directories_hold_at_least_one_file" \
    "no file under: ${WORKFLOW_DIRECTORIES[*]}" \
    "either the directories moved, or the walk in this test stopped matching"
else
  pass_check "the_workflow_directories_hold_at_least_one_file"
fi

# The liveness clause. The rule is a walk, so it covers a workflow added
# tomorrow with no edit here — and it is vacuous over a set that lost its
# members. These 2 paths make the set non-empty by name.
for required in "${REQUIRED_FILES[@]}"; do
  if grep -qxF -- "$required" <<< "$files"; then
    pass_check "the_walk_finds_${required}"
  else
    fail_check "the_walk_finds_${required}" \
      "this file is absent, or the walk no longer reaches it" \
      "the files found were:" "${files:-<none>}"
  fi
done

# The files that really parsed. Rule 2 below reads STRUCTURE out of a document,
# so it can only be asked about a document that parses — and a file that does
# not parse has already failed above. Judging it a second time for a runner it
# does not declare would add a red that says nothing new.
parsed_files=""

while IFS= read -r relative; do
  [[ -z "$relative" ]] && continue
  if [[ -z "$mode" ]]; then
    fail_check "${relative}_parses_as_yaml" \
      "no parser was reachable, so this file was never read" \
      "a green result here would mean the gate parsed nothing"
    continue
  fi

  parse_output=""
  parse_status=0
  parse_output="$(yq_parse "$mode" "$pin" "$REPO_ROOT/$relative")" || parse_status=$?
  if [[ "$parse_status" -eq 0 ]]; then
    pass_check "${relative}_parses_as_yaml"
    parsed_files="${parsed_files:+${parsed_files}
}${relative}"
  else
    fail_check "${relative}_parses_as_yaml" \
      "the parser exited ${parse_status} — GitHub refuses a workflow it cannot parse," \
      "so this file does not run at all, and a file that never runs never fails" \
      "yq (${mode}) said:" "${parse_output:-<nothing>}"
  fi
done <<< "$files"

# ===========================================================================
# 3. NO BILLED RUNNER, AND NO HOSTED-ONLY ACTION
# ===========================================================================
SELF_HOSTED_FIXTURE="$YAML_FIXTURES/self-hosted-runner.yml"
HOSTED_FIXTURE="$YAML_FIXTURES/hosted-runner.yml"

# -------- the counter-stimulus: both detectors FIRE, and both stay quiet -----
missing_fixtures=""
for fixture in "$SELF_HOSTED_FIXTURE" "$HOSTED_FIXTURE"; do
  [[ -f "$fixture" ]] || missing_fixtures="${missing_fixtures:+${missing_fixtures}
}${fixture}"
done

if [[ -n "$missing_fixtures" ]]; then
  fail_check "counter_stimulus_runner_fixtures_exist" \
    "the fixtures this rule proves its readers with are absent:" \
    "$missing_fixtures"
elif [[ -z "$mode" ]]; then
  fail_check "counter_stimulus_runner_fixtures_exist" \
    "the fixtures are present and no parser is reachable, so they were never read"
else
  pass_check "counter_stimulus_runner_fixtures_exist"

  # -- the reader finds the shape it claims to read --
  assert_equal "counter_stimulus_reads_every_runner_label_of_the_fixture" \
    "$(printf 'build|arc-build\ngate|arc-org')" \
    "$(runner_labels "$mode" "$pin" "$SELF_HOSTED_FIXTURE")" \
    "a reader that found no label would report every workflow in this repository as clean"

  # -- the billed-runner detector, both directions --
  assert_equal "counter_stimulus_leaves_the_self_hosted_workflow_alone" \
    "" "$(billed_runner_report "$(runner_labels "$mode" "$pin" "$SELF_HOSTED_FIXTURE")")" \
    "every job of that fixture runs on a homelab pool, and it names ubuntu-latest in a COMMENT" \
    "a reader of prose reports it, and this rule would then forbid the sentence that explains the move"

  hosted_runner_report="$(billed_runner_report "$(runner_labels "$mode" "$pin" "$HOSTED_FIXTURE")")"
  assert_contains "counter_stimulus_reports_the_billed_runner" \
    "$hosted_runner_report" "job build: runs-on ubuntu-latest" \
    "that job is scheduled on a GitHub-hosted machine, which is billed by the minute"
  assert_not_contains "counter_stimulus_does_not_report_the_homelab_job_beside_it" \
    "$hosted_runner_report" "gate" \
    "the gate job of that fixture runs on arc-org; a detector that reports it reports everything," \
    "and the failure line then says nothing about which job to fix"

  # -- the hosted-only-action detector, both directions --
  assert_equal "counter_stimulus_leaves_a_workflow_without_a_hosted_only_action_alone" \
    "" "$(hosted_only_report "$(step_actions "$mode" "$pin" "$SELF_HOSTED_FIXTURE")")" \
    "that fixture carries the deleted step's own 'uses:' line inside a comment block" \
    "a comment runs nothing, and the rule is about what the workflow RUNS"

  assert_contains "counter_stimulus_reports_the_hosted_only_action" \
    "$(hosted_only_report "$(step_actions "$mode" "$pin" "$HOSTED_FIXTURE")")" \
    "job build: uses jlumbroso/free-disk-space@v1.3.1" \
    "that action deletes the preinstalled SDKs of a GitHub-hosted image; on a homelab node it" \
    "deletes the node's caches, and every other pod on that node pays for it"

  # A version bump of the forbidden action must not walk around the rule. The
  # input is 1 string, so it is written here rather than kept as a third fixture.
  assert_contains "counter_stimulus_reports_the_hosted_only_action_at_any_version" \
    "$(hosted_only_report "build|jlumbroso/free-disk-space@v9.9.9")" \
    "jlumbroso/free-disk-space@v9.9.9" \
    "the rule is about the action and not about the tag it is pinned at"

  # -- the 2 shapes no file in this repository holds today --
  # Written as strings and not as a fifth fixture, the way section 5 of
  # scheduled-workflows.test.sh writes its digest stimuli: the input is 1 record,
  # and a file on disk would only hide it.
  assert_equal "counter_stimulus_accepts_the_long_spelling_of_a_pool" \
    "" "$(billed_runner_report "build|self-hosted,arc-build")" \
    "GitHub schedules a labelled job on a runner carrying ALL the labels, so that set IS arc-build" \
    "a rule that demanded every label start with the prefix would forbid the correct long spelling"
  assert_contains "counter_stimulus_reports_the_job_that_declares_no_runner_at_all" \
    "$(billed_runner_report "build|")" "<none declared>" \
    "GitHub cannot schedule such a job, and silence about it reads as 'no billed runner here'"
fi

# THE LIVENESS CLAUSE. The rule below is a walk over whatever the 2 directories
# hold, so it covers a workflow added tomorrow with no edit here — and a walk
# that read no label at all would report a clean set of nothing.
all_labels=""
if [[ -n "$mode" ]]; then
  while IFS= read -r relative; do
    [[ -z "$relative" ]] && continue
    label_records="$(runner_labels "$mode" "$pin" "$REPO_ROOT/$relative")"
    [[ -z "$label_records" ]] && continue
    all_labels="${all_labels:+${all_labels}
}${label_records}"
  done <<< "$parsed_files"
fi

if [[ -n "$all_labels" ]]; then
  pass_check "the_runner_rule_reads_at_least_one_runs_on_label"
else
  fail_check "the_runner_rule_reads_at_least_one_runs_on_label" \
    "no job of any file in ${WORKFLOW_DIRECTORIES[*]} declares a runs-on" \
    "either every workflow lost its jobs, or the reader in this test stopped matching," \
    "and a rule over an empty set of labels passes on a repository that runs everything on the meter"
fi

# THE RATCHET. Keyed on the files, not on a list of job names, so a job added
# tomorrow is covered the day it is added.
while IFS= read -r relative; do
  [[ -z "$relative" ]] && continue
  file="$REPO_ROOT/$relative"

  runner_report="$(billed_runner_report "$(runner_labels "$mode" "$pin" "$file")")"
  if [[ -z "$runner_report" ]]; then
    pass_check "${relative}_runs_on_no_billed_runner"
  else
    fail_check "${relative}_runs_on_no_billed_runner" \
      "$runner_report" \
      "want: every runs-on starting '${SELF_HOSTED_RUNNER_PREFIX}' — the homelab pools, which cost nothing" \
      "this account has spent 1805 of 2000 GitHub Actions minutes against a \$0 budget, and at 0" \
      "a hosted run does not fail: it never starts, attaches no check and files no issue," \
      "so a nightly that stopped running reads exactly like a clean night"
  fi

  action_report="$(hosted_only_report "$(step_actions "$mode" "$pin" "$file")")"
  if [[ -z "$action_report" ]]; then
    pass_check "${relative}_runs_no_hosted_only_action"
  else
    fail_check "${relative}_runs_no_hosted_only_action" \
      "$action_report" \
      "these actions exist to reshape a GitHub-hosted image, and this workflow no longer runs on one" \
      "jlumbroso/free-disk-space deletes ~25-30 GB of preinstalled SDKs. A runner pod shares its" \
      "node's filesystem with every other pod, so on a homelab node it deletes the node" \
      "fix: delete the step — the reason it existed left with the hosted runner"
  fi
done <<< "$parsed_files"

test_summary "$TEST_NAME"
