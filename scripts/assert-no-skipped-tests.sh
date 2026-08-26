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

# `--- SKIP: <name>` is emitted for a t.Skip or t.Skipf only. A package that holds no test file
# prints `?  <package> [no test files]` and is deliberately NOT matched: it is not a skipped test.
skipped="$(grep -E '^[[:space:]]*--- SKIP: ' "$log" || true)"
if [[ -n "$skipped" ]]; then
  printf 'assert-no-skipped-tests: FAILED — %s test(s) SKIPPED; a gate lane may not skip:\n' \
    "$(printf '%s\n' "$skipped" | wc -l | tr -d ' ')" >&2
  printf '%s\n' "$skipped" >&2
  exit 1
fi

printf 'assert-no-skipped-tests: OK — no test skipped\n'
