#!/usr/bin/env bash
#
# .githooks/lib/branchname_test.sh — regression test for hook_check_branch_name (doc-13 §2).
#
# Asserts the branch-name grammar gate: grammar-valid branches PASS, off-grammar AGENT
# branches (carrying /run-<id>) BLOCK, off-grammar human branches only WARN (so pre-existing
# human branches such as init/seed are never blocked — doc-13 §2 Q3). Run it directly:
#   bash .githooks/lib/branchname_test.sh
# It exits non-zero on the first mismatch. shellcheck-clean (the hooks authoring contract).
set -Eeuo pipefail
IFS=$'\n\t'

# shellcheck source-path=SCRIPTDIR
# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

fails=0

# classify <branch> -> echoes "pass" | "warn" | "block" by observing exit code + warn output.
classify() {
  local out rc
  out="$( ( hook_check_branch_name "$1" ) 2>&1 )" && rc=0 || rc=$?
  if [[ $rc -ne 0 ]]; then
    printf 'block\n'
  elif printf '%s' "$out" | grep -q 'off the doc-13 grammar'; then
    printf 'warn\n'
  else
    printf 'pass\n'
  fi
}

expect() {
  local branch="$1" want="$2" got
  got="$(classify "$branch")"
  if [[ "$got" != "$want" ]]; then
    printf '  FAIL  %-34s got=%-6s want=%s\n' "$branch" "$got" "$want" >&2
    fails=$((fails + 1))
  else
    printf '  ok    %-34s %s\n' "$branch" "$got"
  fi
}

# Grammar-valid branches (every class) pass silently.
expect "docs/charter-personas"            pass
expect "arch/connector-fleet"             pass
expect "impl/secrets-vault-adapter"       pass
expect "infra/k3d-overlay"                pass
expect "fix/REQ-0023-replay-gap"          pass
expect "release/eden-v0.2.0"              pass
expect "ws3/observability"                pass
expect "impl/agent-session/run-abc123"    pass   # a well-formed agent branch
# Off-grammar AGENT branches (carry /run-<id>) BLOCK.
expect "garbage/foo/run-xyz9"             block  # bad class
expect "Impl/BadCase/run-zzz"             block  # uppercase class + slug
expect "impl//run-empty"                  block  # empty slug
# Off-grammar HUMAN branches only WARN (never block — init/seed must keep working).
expect "init/seed"                        warn
expect "random-human-branch"              warn
expect "wip/quick-thing"                  warn
# A detached HEAD has no name to validate -> pass (no-op).
expect "HEAD"                             pass
expect ""                                 pass

if [[ $fails -ne 0 ]]; then
  printf '\nbranchname_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi
printf '\nbranchname_test: all assertions passed\n'
