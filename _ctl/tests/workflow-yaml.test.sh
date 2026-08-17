#!/usr/bin/env bash
#
# _ctl/tests/workflow-yaml.test.sh — every workflow file PARSES.
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
  else
    fail_check "${relative}_parses_as_yaml" \
      "the parser exited ${parse_status} — GitHub refuses a workflow it cannot parse," \
      "so this file does not run at all, and a file that never runs never fails" \
      "yq (${mode}) said:" "${parse_output:-<nothing>}"
  fi
done <<< "$files"

test_summary "$TEST_NAME"
