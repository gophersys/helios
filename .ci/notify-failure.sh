#!/usr/bin/env bash
#
# .ci/notify-failure.sh — the failure notification of a SCHEDULED run.
#
# A scheduled run has no author watching it. Nobody opened a pull request at
# 09:00 UTC — 02:00 MST, the hour the nightly cron names — and nobody refreshes
# the Actions tab afterwards, so a red nightly is a red that reaches no human.
# This script is where that red becomes visible: it opens or updates ONE
# labelled issue naming the run and the jobs that failed, and a later green run
# closes that same issue.
#
# ONE issue, not one per night. A filer that opened an issue per run would turn
# a week of the same unpatched CVE into 7 issues, and 7 issues is a backlog
# nobody reads — the same silence, arrived at from the other side. The label
# below is what makes the issue findable again, so a second red run comments on
# it instead of opening another.
#
# Usage:
#   bash .ci/notify-failure.sh <line>...   open or update the issue
#   bash .ci/notify-failure.sh --resolve   close it, on a green run
#
# Each <line> is 1 row of the issue body. The caller passes what failed, because
# only the workflow knows.
#
# It reads its context out of the environment GitHub Actions sets:
#   GITHUB_TOKEN or GH_TOKEN   REQUIRED. The gh credential.
#   GITHUB_REPOSITORY          REQUIRED. owner/name.
#   GITHUB_SERVER_URL          the base URL. Default https://github.com.
#   GITHUB_RUN_ID              the run this notification is about.
#   GITHUB_WORKFLOW            the workflow name, for the issue title.
#
# FAIL-NOT-SKIP: an absent token, an absent gh, or a gh call that fails exits
# NON-ZERO and names what it could not do. A notifier that swallowed its own
# failure would report nothing while the run went green on the notification
# step, which is the exact defect this file exists to remove.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Set before the source line, the way .ci/smoke.sh sets it: the git fallback in
# _ctl/lib.sh reads the wrong root when this repository is a submodule worktree.
REPO_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"

# The logging and the tool gate live in _ctl/lib.sh, 1 time only.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../_ctl/lib.sh
source "$PROJECT_ROOT/../_ctl/lib.sh"

# The label that makes the issue findable. It is the whole mechanism for "1
# issue": every lookup below is a search for an OPEN issue carrying it.
ISSUE_LABEL="ci-nightly-red"
ISSUE_LABEL_COLOR="b60205"
ISSUE_LABEL_DESCRIPTION="A scheduled run of this repository is failing"

# The title of that 1 issue. It is a literal rather than the run number, so the
# issue keeps 1 identity across the nights it stays open.
ISSUE_TITLE="${GITHUB_WORKFLOW:-scheduled run} is red"

require_cmd gh

# gh reads GH_TOKEN first, then GITHUB_TOKEN. Both are checked here so the
# failure names the secret rather than letting gh fail with an authentication
# error 3 calls later.
if [[ -z "${GH_TOKEN:-}${GITHUB_TOKEN:-}" ]]; then
  log_error "neither GH_TOKEN nor GITHUB_TOKEN is set — this script cannot open, update or close an issue"
  log_error "the calling step must pass it: GITHUB_TOKEN: \${{ secrets.GITHUB_TOKEN }}"
  exit 1
fi

if [[ -z "${GITHUB_REPOSITORY:-}" ]]; then
  log_error "GITHUB_REPOSITORY is not set — this script has no repository to file against"
  exit 1
fi

SERVER_URL="${GITHUB_SERVER_URL:-https://github.com}"
if [[ -n "${GITHUB_RUN_ID:-}" ]]; then
  RUN_URL="${SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"
else
  RUN_URL="<no GITHUB_RUN_ID in the environment>"
fi

# open_issue_numbers — the number of EVERY open issue carrying the label, 1 per
# line, newest first. Empty when there is none.
#
# Every one, and not the newest alone. 2 issues can exist whenever 2 runs raced
# past the search, and a green run that closed only the newest would leave the
# older one open forever: no later run can ever reach it, so the label carries a
# red that nothing on earth retires, and the next real red is 1 more issue in a
# pile nobody reads. The limit is 100 rather than gh's default 30 because a
# truncated list is the same defect at a larger number.
function open_issue_numbers() {
  gh issue list \
    --repo "$GITHUB_REPOSITORY" \
    --label "$ISSUE_LABEL" \
    --state open \
    --limit 100 \
    --json number \
    --jq '.[].number'
}

# ensure_label — create the label when the repository does not carry it yet.
#
# `gh issue create --label` FAILS on a label the repository does not have, and
# that failure would arrive at 09:00 UTC with the red it was meant to report.
# The existence check comes first because `gh label create` on an existing label
# also fails, and `|| true` on either one would hide a real permission error.
function ensure_label() {
  local found=""
  found="$(gh label list --repo "$GITHUB_REPOSITORY" --search "$ISSUE_LABEL" --limit 100 \
    --json name --jq "map(select(.name == \"${ISSUE_LABEL}\")) | .[0].name // empty")"
  if [[ -n "$found" ]]; then
    return 0
  fi
  log_info "creating the label ${ISSUE_LABEL}"
  gh label create "$ISSUE_LABEL" \
    --repo "$GITHUB_REPOSITORY" \
    --color "$ISSUE_LABEL_COLOR" \
    --description "$ISSUE_LABEL_DESCRIPTION"
}

# issue_body <line>... — the body of the issue, or of the comment that updates
# it. It names the run URL first: a reader who opens this at 09:00 UTC needs the
# log before anything else.
function issue_body() {
  printf 'Run: %s\n\n' "$RUN_URL"
  if [[ "$#" -gt 0 ]]; then
    printf 'What failed:\n'
    printf -- '- %s\n' "$@"
    printf '\n'
  fi
  printf 'This issue is opened by .ci/notify-failure.sh and it stays open while the\n'
  printf 'scheduled run is red. A green run closes it.\n'
}

function notify_failure() {
  ensure_label
  local numbers=""
  numbers="$(open_issue_numbers)"
  local body
  body="$(issue_body "$@")"

  if [[ -n "$numbers" ]]; then
    # The newest is the one a comment belongs on; the next green run closes the
    # whole set, so a duplicate does not outlive it.
    local newest="${numbers%%$'\n'*}"
    log_info "the scheduled run is still red — commenting on issue #${newest}"
    gh issue comment "$newest" --repo "$GITHUB_REPOSITORY" --body "$body"
    return 0
  fi

  log_info "the scheduled run went red — opening an issue labelled ${ISSUE_LABEL}"
  gh issue create \
    --repo "$GITHUB_REPOSITORY" \
    --title "$ISSUE_TITLE" \
    --label "$ISSUE_LABEL" \
    --body "$body"
}

function resolve_failure() {
  local numbers=""
  numbers="$(open_issue_numbers)"
  if [[ -z "$numbers" ]]; then
    log_info "the scheduled run is green and no ${ISSUE_LABEL} issue is open — nothing to close"
    return 0
  fi
  local number
  while IFS= read -r number; do
    [[ -z "$number" ]] && continue
    log_info "the scheduled run is green — closing issue #${number}"
    gh issue close "$number" \
      --repo "$GITHUB_REPOSITORY" \
      --comment "Green again: ${RUN_URL}"
  done <<< "$numbers"
}

case "${1:-}" in
  --resolve)
    shift
    resolve_failure
    ;;
  "")
    log_error "usage: bash .ci/notify-failure.sh <line>... | --resolve"
    log_error "a notification with no text says a run failed and never says which part"
    exit 2
    ;;
  *)
    notify_failure "$@"
    ;;
esac
