#!/usr/bin/env bash
#
# _ctl/tests/notify-failure.test.sh — the notifier is EXECUTED, not read.
#
# Hermetic: a stub `gh` first on PATH, and a JSON world this file writes. No
# API, no credential, no network.
#
# ============================================================================
# THE DEFECT THIS FILE EXISTS FOR
# ============================================================================
#
# `.ci/notify-failure.sh` is the reason the nightly scan is worth running: a
# scheduled run has no author watching it, so the red only reaches a human
# because that script files an issue about it, and the issue only closes
# because a later green run closes it. Until this file existed, 287 checks
# pointed at that script and every one of them read it as a FILENAME. The
# suite asserted it exists, that it is executable, that the workflow calls it
# under the right guard — and nothing ever ran a line of it.
#
# What that missed, measured: revert the 2 tokens of the close-every-issue fix
# back to the shipped defect — `--limit 100` to `--limit 1`, and
# `'.[].number'` to `'.[0].number // empty'` — and `bash ./ctl.sh validate`
# and `bash ./ctl.sh test` both stay fully green. The behaviour the rule at
# .claude/rules/00-identity.md:176 states in prose ("a green run closes EVERY
# open issue carrying that label") had no enforcement at all, which is the
# shape that rule itself condemns 200 lines later: a rule that nothing checks
# is a rule that drifts.
#
# So every clause below DRIVES the script. It sets a world, runs the real
# file, and reads the calls the script made and the status it returned. A
# clause that reads the source text of the notifier does not belong here —
# `scheduled-workflows.test.sh` already holds the text, and holding text is
# what left this hole.
#
# ============================================================================
# THE STUB ANSWERS WITH THE CALLER'S OWN QUERY
# ============================================================================
#
# `_ctl/tests/stubs/gh` does not answer `issue list` with a canned pair of
# numbers. It reads the JSON world, truncates it to the caller's own
# `--limit`, and applies the caller's own `--jq` expression to what is left —
# gh's order, gh's semantics. Both tokens are therefore UNDER TEST, and that
# is the only reason the ratchet below can go red: a canned answer would agree
# with `--limit 1` exactly as happily as with `--limit 100`.
#
# The stub exits 64 on a subcommand it does not model, so a notifier that
# starts calling gh in a way this file does not describe stops the run loudly
# instead of collecting a cheerful 0 from a stub that understood nothing.
#
# ============================================================================
# EVERY CASE FEEDS THE NOTIFIER /dev/null ON STDIN
# ============================================================================
#
# On purpose, and it is load-bearing. One accepted fix for the stdin clause
# below is to stop the loop handing its issue list to the child at all — an
# array loop, where the child inherits the stdin of the SCRIPT. If this file
# let the notifier inherit the stdin of the test run, that fix would be judged
# against whatever the terminal or the CI runner happened to have on fd 0, and
# the case would mean a different thing on 2 machines. /dev/null is the 1
# stdin that is the same everywhere.
#
# Usage: bash _ctl/tests/notify-failure.test.sh
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

TEST_NAME="notify-failure.test.sh"

NOTIFIER="$REPO_ROOT/.ci/notify-failure.sh"
STUB_GH="$TESTS_DIR/stubs/gh"

# The label the notifier files under. A literal here, deliberately: a test that
# read the value out of the script it checks agrees with any value, a wrong one
# included.
ISSUE_LABEL="ci-nightly-red"

# The context every case runs the notifier with.
REPOSITORY="gophersys/.devcontainer"
RUN_ID="17"
RUN_URL="https://github.com/${REPOSITORY}/actions/runs/${RUN_ID}"

# The 2 lines the workflow really passes, post-substitution. The verdict of the
# 2 needed jobs, 1 row each.
FAILED_LEGS=(
  "image scan: failure"
  "base-OS currency: failure"
)

# 1 temporary root for the whole file: each case gets a numbered directory
# under it holding its JSON world, its call log and its issue bodies.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
SCENARIO=0

# The state the last run left behind.
NOTIFY_OUTPUT=""
NOTIFY_STATUS=0
GH_CALLS=""
ISSUE_BODIES=""

# jq is the stub's reader for the caller's --jq expression. A missing tool is a
# FAILURE and never a skip: without it every case below would fail for a reason
# that says nothing about the notifier.
JQ_DIRECTORY=""
if command -v jq > /dev/null 2>&1; then
  JQ_DIRECTORY="$(cd "$(dirname "$(command -v jq)")" && pwd)"
fi

# The PATH every case runs with: the stub gh, then jq's own directory, then the
# 2 directories holding the standard utilities. The developer's own PATH is left
# out on purpose, so a real `gh` on this machine can never answer — and a real
# `gh` would answer with a real API call.
STUB_BIN="$WORK/bin"
mkdir -p "$STUB_BIN"
ln -s "$STUB_GH" "$STUB_BIN/gh"
NOTIFY_PATH="${STUB_BIN}:${JQ_DIRECTORY}:/usr/bin:/bin"

# The same PATH with no gh at all, for the absent-tool clause.
NO_GH_PATH="${JQ_DIRECTORY}:/usr/bin:/bin"

# run_notifier <issues json> [KEY=VALUE ...] -- <notifier argv ...>
#
# Writes the world, runs the real script against the stub, and leaves
# NOTIFY_STATUS, NOTIFY_OUTPUT, GH_CALLS and ISSUE_BODIES for the caller.
#
# The environment assignments of the case come AFTER the base ones, so a case
# that wants no token writes `GH_TOKEN=` and env's last-wins rule settles it.
function run_notifier() {
  local issues="$1"
  shift

  SCENARIO=$((SCENARIO + 1))
  local directory="$WORK/case-${SCENARIO}"
  mkdir -p "$directory"
  printf '%s\n' "$issues" > "$directory/issues.json"
  printf '[{"name":"%s"}]\n' "$ISSUE_LABEL" > "$directory/labels.json"
  : > "$directory/calls.log"
  : > "$directory/bodies.txt"

  local -a environment
  environment=(
    "PATH=$NOTIFY_PATH"
    "GH_TOKEN=stub-token"
    "GITHUB_TOKEN="
    "GITHUB_REPOSITORY=$REPOSITORY"
    "GITHUB_SERVER_URL=https://github.com"
    "GITHUB_RUN_ID=$RUN_ID"
    "GITHUB_WORKFLOW=security-nightly"
    "STUB_GH_LOG=$directory/calls.log"
    "STUB_GH_ISSUES=$directory/issues.json"
    "STUB_GH_LABELS=$directory/labels.json"
    "STUB_GH_BODY_LOG=$directory/bodies.txt"
  )
  while [[ "$#" -gt 0 && "$1" != "--" ]]; do
    environment+=("$1")
    shift
  done
  [[ "${1:-}" == "--" ]] && shift

  NOTIFY_STATUS=0
  NOTIFY_OUTPUT="$(env "${environment[@]}" bash "$NOTIFIER" "$@" < /dev/null 2>&1)" \
    || NOTIFY_STATUS=$?
  GH_CALLS="$(cat "$directory/calls.log")"
  ISSUE_BODIES="$(cat "$directory/bodies.txt")"
}

# calls_named <prefix> — how many logged gh calls start with <prefix>.
#
# awk and not `grep -c`: grep exits 1 on 0 matches, and 0 matches is the answer
# 2 clauses below are asking for. Under `set -e` that answer would end the file.
function calls_named() {
  awk -v needle="$1" 'index($0, needle) == 1 { total++ } END { print total + 0 }' \
    <<< "$GH_CALLS"
}

# closed_numbers — the issue number of every `gh issue close` call, in order.
function closed_numbers() {
  awk '$1 == "gh" && $2 == "issue" && $3 == "close" { print $4 }' <<< "$GH_CALLS"
}

# assert_closed_exactly <name> <want, 1 number per line>
#
# The set AND the status, as 1 check, and the evidence NAMES the issues that
# were left open. "the close set differs" sends the reader back to the log to
# work out which issue this repository would have carried a false red on until
# somebody closed it by hand.
function assert_closed_exactly() {
  local name="$1" want="$2"
  local got missing extra number
  got="$(closed_numbers)"

  missing=""
  for number in $(printf '%s\n' "$want"); do
    [[ -z "$number" ]] && continue
    grep -qxF -- "$number" <<< "$got" || missing="${missing:+${missing} }#${number}"
  done
  extra=""
  for number in $(printf '%s\n' "$got"); do
    [[ -z "$number" ]] && continue
    grep -qxF -- "$number" <<< "$want" || extra="${extra:+${extra} }#${number}"
  done

  if [[ "$NOTIFY_STATUS" -ne 0 ]]; then
    fail_check "$name" \
      "want: exit 0 — every close succeeded in this world" \
      "got:  ${NOTIFY_STATUS}" \
      "output was:" "${NOTIFY_OUTPUT:-<none>}"
  elif [[ -n "$missing" ]]; then
    fail_check "$name" \
      "these issues were NEVER closed: ${missing}" \
      "no later run can reach them: the notifier only ever looks at OPEN issues," \
      "so each one carries a red this repository can no longer retire" \
      "closes attempted:" "${got:-<none>}" \
      "the gh calls were:" "${GH_CALLS:-<none>}"
  elif [[ -n "$extra" ]]; then
    fail_check "$name" \
      "these closes were not asked for: ${extra}" \
      "closes attempted:" "${got:-<none>}" \
      "the gh calls were:" "${GH_CALLS:-<none>}"
  else
    pass_check "$name"
  fi
}

# assert_failed_naming <name> <needle> [needle...]
#
# The status AND every name, as 1 check. A bare "the status is non-zero" passes
# on a run that died before it did anything: an absent file exits 127, and 127
# is non-zero. That reading is the one this whole directory exists to prevent.
function assert_failed_naming() {
  local name="$1"
  shift
  local needle missing_names=""
  for needle in "$@"; do
    if ! grep -qF -- "$needle" <<< "$NOTIFY_OUTPUT"; then
      missing_names="${missing_names:+${missing_names}
}${needle}"
    fi
  done
  if [[ "$NOTIFY_STATUS" -eq 0 ]]; then
    fail_check "$name" \
      "want: a non-zero exit status" \
      "got:  0 — the notifier reported success" \
      "output was:" "${NOTIFY_OUTPUT:-<none>}" \
      "a notifier that swallows its own failure reports nothing while the step goes green," \
      "which is the exact defect that file exists to remove"
  elif [[ -n "$missing_names" ]]; then
    fail_check "$name" \
      "the notifier exited ${NOTIFY_STATUS} and its message never names:" "$missing_names" \
      "output was:" "${NOTIFY_OUTPUT:-<none>}" \
      "the reader of a 09:00 UTC failure needs the name, or the next step is to guess"
  else
    pass_check "$name"
  fi
}

printf '=== RUN  %s\n' "$TEST_NAME"

# ===========================================================================
# 0. THE HARNESS ITSELF — the tools are here, and the stub answers the QUERY
# ===========================================================================

if [[ -n "$JQ_DIRECTORY" ]]; then
  pass_check "a_json_reader_is_reachable"
else
  fail_check "a_json_reader_is_reachable" \
    "jq is not on PATH, and the stub gh runs the caller's --jq expression with it" \
    "a missing tool is a FAILURE and never a skip: without jq every case below fails" \
    "for a reason that says nothing about the notifier"
fi

if [[ -x "$STUB_GH" ]]; then
  pass_check "the_gh_stub_is_executable"
else
  fail_check "the_gh_stub_is_executable" \
    "not executable: ${STUB_GH}" \
    "PATH resolution skips a file it cannot execute, so a real gh would answer instead"
fi

# -------- the counter-stimulus: the stub honours --limit and --jq -----------
# Everything below rests on this. If the stub ignored either token, the ratchet
# would agree with the defect it exists to catch, and the whole file would be
# 15 green checks over nothing.
STUB_WORLD="$WORK/counter-stimulus.json"
printf '[{"number":77},{"number":42},{"number":11}]\n' > "$STUB_WORLD"

stub_output=""
stub_status=0
stub_output="$(env PATH="$NOTIFY_PATH" STUB_GH_ISSUES="$STUB_WORLD" \
  gh issue list --repo "$REPOSITORY" --label "$ISSUE_LABEL" --state open \
  --limit 100 --json number --jq '.[].number' 2>&1)" || stub_status=$?
if [[ "$stub_status" -eq 0 && "$stub_output" == "77
42
11" ]]; then
  pass_check "counter_stimulus_the_stub_answers_the_wide_query_with_every_issue"
else
  fail_check "counter_stimulus_the_stub_answers_the_wide_query_with_every_issue" \
    "want: 77, 42 and 11, on 3 lines, at exit 0" \
    "got:  exit ${stub_status}, output:" "${stub_output:-<none>}"
fi

stub_output=""
stub_status=0
stub_output="$(env PATH="$NOTIFY_PATH" STUB_GH_ISSUES="$STUB_WORLD" \
  gh issue list --repo "$REPOSITORY" --label "$ISSUE_LABEL" --state open \
  --limit 1 --json number --jq '.[0].number // empty' 2>&1)" || stub_status=$?
if [[ "$stub_status" -eq 0 && "$stub_output" == "77" ]]; then
  pass_check "counter_stimulus_the_stub_answers_the_narrow_query_with_one_issue"
else
  fail_check "counter_stimulus_the_stub_answers_the_narrow_query_with_one_issue" \
    "want: 77 alone, at exit 0 — the query that shipped the orphaned-issue defect" \
    "got:  exit ${stub_status}, output:" "${stub_output:-<none>}" \
    "the stub must DISAGREE with the wide query above, or no clause here can go red"
fi

stub_output=""
stub_status=0
stub_output="$(env PATH="$NOTIFY_PATH" gh pr list 2>&1)" || stub_status=$?
if [[ "$stub_status" -eq 64 ]]; then
  pass_check "counter_stimulus_the_stub_refuses_a_subcommand_it_does_not_model"
else
  fail_check "counter_stimulus_the_stub_refuses_a_subcommand_it_does_not_model" \
    "want: exit 64 on a gh subcommand the stub does not know" \
    "got:  exit ${stub_status}, output:" "${stub_output:-<none>}" \
    "a stub that exits 0 on a call it did not understand hands every clause here a" \
    "success for something that never happened"
fi

# ===========================================================================
# 1. A GREEN RUN CLOSES **EVERY** OPEN ISSUE
# ===========================================================================
#
# 2 issues can exist whenever 2 runs raced past the search. The one a green run
# cannot reach stays open for the life of the repository — no later run ever
# looks at it again, because every lookup is a search for an OPEN issue and the
# next red run comments on the newest of them.
#
# This is the clause the shipped defect broke, and the reverted-mutation drill
# for it is the pair of tokens named in the header.
run_notifier '[{"number":77},{"number":42}]' -- --resolve
assert_closed_exactly "resolve_closes_every_open_issue" "77
42"

# ===========================================================================
# 2. AND IT STILL CLOSES EVERY ONE WHEN THE CLOSE COMMAND READS STDIN
# ===========================================================================
#
# The loop feeds its issue list to the child as the loop's own stdin
# (`done <<< "$numbers"`). Any child that reads fd 0 therefore eats the issue
# numbers that have not been read yet, the loop sees EOF, and it exits 0 having
# closed 1 issue of 3 — the orphaned-issue defect restored, with no diagnostic
# and a green step above it.
#
# `gh issue close --comment` does not read stdin TODAY. That is the whole
# hazard: the correctness of this loop is a property of a tool this repository
# does not own and does not pin, and nothing here would notice the day it
# changed. The fix is 1 token — `< /dev/null` on the close, or an array loop
# that never puts the list on fd 0 at all.
run_notifier '[{"number":77},{"number":42},{"number":11}]' \
  "STUB_GH_CLOSE_DRAIN=1" -- --resolve
assert_closed_exactly "resolve_closes_every_issue_when_the_close_reads_stdin" "77
42
11"

# ===========================================================================
# 3. FAIL-LOUD — a close that is REFUSED fails the notifier
# ===========================================================================
#
# A run that could not close the issue must not report that it closed it. The
# next night's red would then comment on an issue the reader believes was
# retired, and the notification would read as stale rather than as new.
run_notifier '[{"number":77},{"number":42}]' "STUB_GH_CLOSE_FAIL=42" -- --resolve
assert_failed_naming "a_refused_close_fails_the_notifier_naming_the_issue" \
  "403" "#42"

# ===========================================================================
# 4. FAIL-LOUD — the missing credential, the missing argument, the missing tool
# ===========================================================================

# -------- no token: name BOTH variables --------
# gh reads GH_TOKEN first and GITHUB_TOKEN second, so a message naming 1 of them
# sends the reader to set a variable that may not be the one the calling step
# passes.
run_notifier '[]' "GH_TOKEN=" "GITHUB_TOKEN=" -- --resolve
assert_failed_naming "an_absent_token_fails_naming_both_variables" \
  "GH_TOKEN" "GITHUB_TOKEN"

# -------- no argument: exit 2, not exit 0 --------
# A notification with no text says a run failed and never says which part. The
# status is 2 and not 1 on purpose: it separates "you called me wrong" from
# "I could not do the thing you asked".
run_notifier '[]' --
if [[ "$NOTIFY_STATUS" -eq 2 ]]; then
  pass_check "no_argument_exits_two_with_the_usage"
else
  fail_check "no_argument_exits_two_with_the_usage" \
    "want: exit 2 on an argv carrying no line and no --resolve" \
    "got:  ${NOTIFY_STATUS}" \
    "output was:" "${NOTIFY_OUTPUT:-<none>}"
fi

# -------- gh absent: exit 127, naming gh --------
# The tool gate has to fire BEFORE the first call. Without it the reader gets
# bash's own "command not found" from whichever gh call happened to be first,
# and the run that failed is the one nobody is watching.
if command -v gh > /dev/null 2>&1 && env PATH="$NO_GH_PATH" command -v gh > /dev/null 2>&1; then
  fail_check "an_absent_gh_exits_127_naming_the_tool" \
    "a real gh is reachable at $(env PATH="$NO_GH_PATH" command -v gh) under the reduced PATH" \
    "this case cannot state its own precondition, and a run against a real gh would" \
    "reach the API with a stub token — it is a FAILURE here and never a skip"
else
  run_notifier '[]' "PATH=$NO_GH_PATH" -- --resolve
  assert_failed_naming "an_absent_gh_exits_127_naming_the_tool" \
    "missing required tool" "gh"
  if [[ "$NOTIFY_STATUS" -eq 127 ]]; then
    pass_check "an_absent_gh_exits_the_tool_gate_status"
  else
    fail_check "an_absent_gh_exits_the_tool_gate_status" \
      "want: exit 127 — the status require_cmd uses for an absent tool" \
      "got:  ${NOTIFY_STATUS}" \
      "output was:" "${NOTIFY_OUTPUT:-<none>}"
  fi
fi

# ===========================================================================
# 5. THE QUIET CASES — a green run with nothing open touches nothing
# ===========================================================================
#
# The counter-stimulus to clause 1. A notifier that closed something here would
# be closing an issue it never found, which is what `.[0].number` without the
# `// empty` guard does: jq answers `null` on an empty array, the string is not
# empty, and the loop closes issue #null every green night.
run_notifier '[]' -- --resolve
close_calls="$(calls_named "gh issue close")"
if [[ "$NOTIFY_STATUS" -eq 0 && "$close_calls" -eq 0 ]]; then
  pass_check "resolve_with_no_open_issue_closes_nothing"
else
  fail_check "resolve_with_no_open_issue_closes_nothing" \
    "want: exit 0 and 0 close calls over an empty issue list" \
    "got:  exit ${NOTIFY_STATUS} and ${close_calls} close call(s)" \
    "the gh calls were:" "${GH_CALLS:-<none>}" \
    "output was:" "${NOTIFY_OUTPUT:-<none>}"
fi

# ===========================================================================
# 6. THE RED PATH — ONE issue, opened once and commented on after that
# ===========================================================================

# -------- nothing open: exactly 1 issue is created --------
run_notifier '[]' -- "${FAILED_LEGS[@]}"
create_calls="$(calls_named "gh issue create")"
comment_calls="$(calls_named "gh issue comment")"
if [[ "$NOTIFY_STATUS" -eq 0 && "$create_calls" -eq 1 && "$comment_calls" -eq 0 ]]; then
  pass_check "the_red_path_opens_exactly_one_issue"
else
  fail_check "the_red_path_opens_exactly_one_issue" \
    "want: exit 0, 1 create call, 0 comment calls" \
    "got:  exit ${NOTIFY_STATUS}, ${create_calls} create call(s), ${comment_calls} comment call(s)" \
    "the gh calls were:" "${GH_CALLS:-<none>}" \
    "output was:" "${NOTIFY_OUTPUT:-<none>}"
fi

# -------- the body carries the run and EVERY leg it was told about ----------
# The workflow passes 1 string per needed job. A body that dropped 1 of them
# would send the reader to a run URL to find out which half of the night failed.
body_missing=""
for line in "Run: ${RUN_URL}" "- ${FAILED_LEGS[0]}" "- ${FAILED_LEGS[1]}"; do
  grep -qF -- "$line" <<< "$ISSUE_BODIES" || body_missing="${body_missing:+${body_missing}
}${line}"
done
if [[ -z "$body_missing" ]]; then
  pass_check "the_issue_body_names_the_run_and_every_failed_leg"
else
  fail_check "the_issue_body_names_the_run_and_every_failed_leg" \
    "the body does not name:" "$body_missing" \
    "the body was:" "${ISSUE_BODIES:-<none>}"
fi

# -------- one already open: comment, and open NO second issue --------
# ONE issue, not one per night. A filer that opened an issue per run would turn
# a week of the same unpatched CVE into 7 issues, and 7 issues is a backlog
# nobody reads — the same silence, arrived at from the other side.
run_notifier '[{"number":77}]' -- "${FAILED_LEGS[@]}"
create_calls="$(calls_named "gh issue create")"
comment_calls="$(calls_named "gh issue comment 77")"
if [[ "$NOTIFY_STATUS" -eq 0 && "$create_calls" -eq 0 && "$comment_calls" -eq 1 ]]; then
  pass_check "the_red_path_comments_on_the_open_issue_and_opens_no_second_one"
else
  fail_check "the_red_path_comments_on_the_open_issue_and_opens_no_second_one" \
    "want: exit 0, 0 create calls, 1 comment call on #77" \
    "got:  exit ${NOTIFY_STATUS}, ${create_calls} create call(s), ${comment_calls} comment call(s) on #77" \
    "the gh calls were:" "${GH_CALLS:-<none>}" \
    "output was:" "${NOTIFY_OUTPUT:-<none>}"
fi

# -------- the label is created when the repository does not carry it --------
# `gh issue create --label` FAILS on a label the repository does not have, and
# that failure would arrive at 09:00 UTC carrying the red it was meant to report.
SCENARIO_LABELS_EMPTY="$WORK/no-labels.json"
printf '[]\n' > "$SCENARIO_LABELS_EMPTY"
run_notifier '[]' "STUB_GH_LABELS=$SCENARIO_LABELS_EMPTY" -- "${FAILED_LEGS[@]}"
label_calls="$(calls_named "gh label create ${ISSUE_LABEL}")"
create_calls="$(calls_named "gh issue create")"
if [[ "$NOTIFY_STATUS" -eq 0 && "$label_calls" -eq 1 && "$create_calls" -eq 1 ]]; then
  pass_check "the_red_path_creates_the_label_before_it_files"
else
  fail_check "the_red_path_creates_the_label_before_it_files" \
    "want: exit 0, 1 'label create ${ISSUE_LABEL}' call, then 1 issue create" \
    "got:  exit ${NOTIFY_STATUS}, ${label_calls} label create call(s), ${create_calls} create call(s)" \
    "the gh calls were:" "${GH_CALLS:-<none>}" \
    "output was:" "${NOTIFY_OUTPUT:-<none>}"
fi

test_summary "$TEST_NAME"
