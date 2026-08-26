#!/usr/bin/env bash
#
# scripts/assert-no-skipped-tests.sh — run `go test -v <arguments>` and FAIL when any test skipped.
#
# A gate that must prove something cannot accept a skip. `t.Skip` reports success while the code
# under test never ran. That is the exact defect the harness-conformance job carried: an absent
# live credential made the live tests skip, and the job went green.
# assert-harness-conformance-preconditions.sh removes that cause. This removes the class: after
# this, ANY skip inside a gate lane is loud.
#
# Usage, from the module directory:
#   bash scripts/assert-no-skipped-tests.sh -tags integration -race ./... -count=1
# `-v` is added here. Do not pass it again.
set -Eeuo pipefail
IFS=$'\n\t'

if [[ $# -eq 0 ]]; then
  printf 'assert-no-skipped-tests: usage: %s <go test arguments...>\n' "$0" >&2
  exit 2
fi

log="$(mktemp -t assert-no-skipped-tests.XXXXXX)"
trap 'rm -f "$log"' EXIT

# tee keeps the live output; PIPESTATUS keeps the real `go test` exit code.
set +e
go test -v "$@" 2>&1 | tee "$log"
status=${PIPESTATUS[0]}
set -e

if [[ $status -ne 0 ]]; then
  exit "$status"
fi

# SKIP_REGISTER — the shrink-only exemption list, same pattern as the frozen-contract gate's
# DRAFT_REGISTER. A row is a test name whose skip is a RECORDED HUMAN RULING, not an environment
# accident, and each row carries its citation here. An unregistered skip still fails the lane; a
# registered test that RUNS (appears as PASS or FAIL) is a STALE ROW and fails the lane until the
# row is deleted — the register may only shrink.
#   TestIntegration_LiveOmp_Gated — Mateo, 2026-08-26, verbatim: "skip the omp, as lomg as claude
#   works thats waht we really actaulyl acre about". The omp live arm is deliberately ungated;
#   the known omp 17.2.5 rpc deadlock is task #24, and the skip in ompadapter's integration_test
#   quotes the same ruling as its re-entry point. The claude live arm remains fully gated.
SKIP_REGISTER="TestIntegration_LiveOmp_Gated"

# `--- SKIP: <name>` is emitted for a t.Skip or t.Skipf only. A package that holds no test file
# prints `?  <package> [no test files]` and is deliberately NOT matched: it is not a skipped test.
skipped="$(grep -E '^[[:space:]]*--- SKIP: ' "$log" || true)"
unregistered=""
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  name="$(printf '%s' "$line" | sed -E 's/^[[:space:]]*--- SKIP: ([^ ]+).*/\1/')"
  if ! grep -qw "$name" <<<"$SKIP_REGISTER"; then
    unregistered+="${line}"$'\n'
  fi
done <<<"$skipped"
if [[ -n "$unregistered" ]]; then
  printf 'assert-no-skipped-tests: FAILED — unregistered test skip(s); a gate lane may not skip:\n' >&2
  printf '%s' "$unregistered" >&2
  exit 1
fi

# A registered test that actually RAN means the ruling's condition ended: delete the row.
for reg in $SKIP_REGISTER; do
  if grep -qE "^[[:space:]]*--- (PASS|FAIL): ${reg}( |$)" "$log"; then
    printf 'assert-no-skipped-tests: FAILED — %s is in SKIP_REGISTER but RAN; the register may only shrink: delete its row\n' "$reg" >&2
    exit 1
  fi
done

registered_count="$(printf '%s\n' "$skipped" | grep -c . || true)"
if [[ "$registered_count" -gt 0 ]]; then
  printf 'assert-no-skipped-tests: OK — no unregistered skip (%s registered ruling skip(s), citations in SKIP_REGISTER above)\n' "$registered_count"
else
  printf 'assert-no-skipped-tests: OK — no test skipped\n'
fi
