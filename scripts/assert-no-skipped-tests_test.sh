#!/usr/bin/env bash
#
# scripts/assert-no-skipped-tests_test.sh — behaviour test for scripts/assert-no-skipped-tests.sh.
#
# The gate must: exit 0 and say OK on an all-pass transcript, exit 1 and name the count on a
# `--- SKIP:` transcript, propagate the exit code of `go test` unchanged, never read `[no test
# files]` or the word SKIP in prose as a skipped test, and exit 2 on no arguments.
#
# It drives the subject against a stub `go` on PATH that prints a canned `go test -v` transcript,
# so no Go toolchain, no module and no network take part. Run it directly:
#   bash scripts/assert-no-skipped-tests_test.sh
# It exits non-zero when any assertion mismatches. shellcheck-clean at -S style.
set -Eeuo pipefail
IFS=$'\n\t'

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
subject="${here}/assert-no-skipped-tests.sh"

# --- assertion 0 — the environment must carry GNU mktemp ----------------------------------------
# The subject creates its log with mktemp. BSD mktemp accepts a `-t` prefix that GNU rejects, so on
# a BSD host every assertion below passes while the defect is present: the test could not fail.
# ADR-0020 FAIL-NOT-SKIP — a test that cannot run is a failure, never a skip. Name the environment.
mktemp_version="$(mktemp --version 2>&1)" && mktemp_version_status=0 || mktemp_version_status=$?
if [[ $mktemp_version_status -ne 0 || "$mktemp_version" != *"GNU coreutils"* ]]; then
  printf 'assert-no-skipped-tests_test: FAILED — GNU mktemp is required; this host has none.\n' >&2
  printf '  mktemp --version exited %d and said: %s\n' \
    "$mktemp_version_status" "${mktemp_version%%$'\n'*}" >&2
  printf '  BSD mktemp accepts the template GNU rejects, so this test cannot fail here.\n' >&2
  printf '  Run it in the eden devcontainer:\n' >&2
  printf '    bash .devcontainer/base/ctl.sh exec -- bash scripts/assert-no-skipped-tests_test.sh\n' >&2
  exit 1
fi

fails=0
work="$(mktemp -d -t assert-no-skipped-tests_test.XXXXXX)"
trap 'rm -rf "$work"' EXIT

# --- the stub `go` ------------------------------------------------------------------------------
stub_directory="${work}/bin"
mkdir -p "$stub_directory"
cat >"${stub_directory}/go" <<'STUB_GO'
#!/usr/bin/env bash
# Stub `go` for assert-no-skipped-tests_test.sh. It ignores its arguments, prints the canned
# transcript named by STUB_GO_TRANSCRIPT and exits with STUB_GO_STATUS.
set -Eeuo pipefail
cat -- "${STUB_GO_TRANSCRIPT}"
exit "${STUB_GO_STATUS:-0}"
STUB_GO
chmod +x "${stub_directory}/go"
PATH="${stub_directory}:${PATH}"
export PATH

# A PATH that still resolves the real toolchain would test something else entirely.
resolved_go="$(command -v go)"
if [[ "$resolved_go" != "${stub_directory}/go" ]]; then
  printf 'assert-no-skipped-tests_test: FAILED — the stub go is not first on PATH (got %s).\n' \
    "$resolved_go" >&2
  exit 1
fi

# --- the canned transcripts ---------------------------------------------------------------------
transcript_pass="${work}/pass.txt"
cat >"$transcript_pass" <<'TRANSCRIPT'
=== RUN   TestEnvelopeSealsAndOpens
--- PASS: TestEnvelopeSealsAndOpens (0.01s)
=== RUN   TestEnvelopeRejectsShortKey
--- PASS: TestEnvelopeRejectsShortKey (0.00s)
PASS
ok  	github.com/gophersys/eden/libs/go/envelope	0.312s
TRANSCRIPT

transcript_skip="${work}/skip.txt"
cat >"$transcript_skip" <<'TRANSCRIPT'
=== RUN   TestLiveHarnessDrain
    live_test.go:31: no live credential in the environment
--- SKIP: TestLiveHarnessDrain (0.00s)
PASS
ok  	github.com/gophersys/eden/libs/go/agentsession	0.104s
TRANSCRIPT

transcript_prose="${work}/prose.txt"
cat >"$transcript_prose" <<'TRANSCRIPT'
?   	github.com/gophersys/eden/libs/go/agentsession/internal	[no test files]
=== RUN   TestHarnessDrain
    harness_test.go:88: the remote leg would SKIP without a credential; it has one
--- PASS: TestHarnessDrain (0.02s)
=== RUN   TestSkipListParses
--- PASS: TestSkipListParses (0.00s)
PASS
ok  	github.com/gophersys/eden/harnesses	0.421s
TRANSCRIPT

# --- the harness --------------------------------------------------------------------------------
run_status=0
run_output=''

# run_subject <transcript> <stub-status> [subject arguments...]
run_subject() {
  local transcript="$1" stub_status="$2"
  shift 2
  export STUB_GO_TRANSCRIPT="$transcript" STUB_GO_STATUS="$stub_status"
  run_output="$( ( bash "$subject" "$@" ) 2>&1 )" && run_status=0 || run_status=$?
}

# expect_case <name> <want status> <text that must appear> <text that must not appear|empty>
expect_case() {
  local name="$1" want_status="$2" want_present="$3" want_absent="$4"
  local problems=()
  if [[ $run_status -ne $want_status ]]; then
    problems+=("exit status got=${run_status} want=${want_status}")
  fi
  if [[ -n "$want_present" && "$run_output" != *"$want_present"* ]]; then
    problems+=("output does not contain: ${want_present}")
  fi
  if [[ -n "$want_absent" && "$run_output" == *"$want_absent"* ]]; then
    problems+=("output must not contain: ${want_absent}")
  fi
  if [[ ${#problems[@]} -ne 0 ]]; then
    printf '  FAIL  %s\n' "$name" >&2
    local problem
    for problem in "${problems[@]}"; do
      printf '          %s\n' "$problem" >&2
    done
    printf '        --- subject output ---\n' >&2
    printf '        %s\n' "$run_output" >&2
    printf '        ----------------------\n' >&2
    fails=$((fails + 1))
  else
    printf '  ok    %s\n' "$name"
  fi
}

# An all-pass transcript is a pass: exit 0, and the gate says so.
run_subject "$transcript_pass" 0 -race ./... -count=1
expect_case 'pass: all-pass transcript -> exit 0 and OK' \
  0 'assert-no-skipped-tests: OK — no test skipped' ''

# A `--- SKIP:` line is the whole point of the gate: exit 1 and name the count.
run_subject "$transcript_skip" 0 -tags integration ./...
expect_case 'skip: a --- SKIP: line -> exit 1 and 1 test(s) SKIPPED' \
  1 '1 test(s) SKIPPED' 'OK — no test skipped'

# The exit code of `go test` propagates unchanged. A regression from PIPESTATUS[0] to $? would
# read tee's status here and report 0.
run_subject "$transcript_pass" 2 ./...
expect_case 'propagation: go test exits 2 -> exit 2, transcript still shown' \
  2 '--- PASS: TestEnvelopeSealsAndOpens' 'OK — no test skipped'

# `[no test files]` is not a skipped test, and the word SKIP inside a log line is not one either.
run_subject "$transcript_prose" 0 ./...
expect_case 'no false positive: [no test files] and SKIP in prose -> exit 0' \
  0 'assert-no-skipped-tests: OK — no test skipped' 'SKIPPED'

# No arguments is a usage error, and it is exit 2 (not 1) so a caller can tell it from a skip.
run_subject "$transcript_pass" 0
expect_case 'usage: no arguments -> exit 2 and a usage line' \
  2 'usage:' ''

if [[ $fails -ne 0 ]]; then
  printf '\nassert-no-skipped-tests_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi
printf '\nassert-no-skipped-tests_test: all assertions passed\n'
