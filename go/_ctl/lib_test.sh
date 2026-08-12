#!/usr/bin/env bash
#
# libs/go/_ctl/lib_test.sh — prove that `ctl.sh lint` names the failure it had.
#
# `cmd_lint` reports EVERY non-zero golangci-lint exit as "golangci-lint found
# issues". golangci-lint 2.12.2 exits 0 clean, 1 for findings and 3 when the RUN
# failed — a lock collision between concurrent instances, an invalid config, a
# panic. So the single message a reader trusts is false for the whole of exit 3,
# and eden's nx `parallel: 10` produces exit 3 routinely.
#
# 2 phases, after review/review_test.sh in gophersys/cictl:
#
#   phase 1  behaviour      — each test asserts what the lint verb must do.
#   phase 2  discrimination — each test is re-run against the counter-stimulus
#                             declared for it, and must FAIL. A test that passes
#                             both ways read the message but not the exit code,
#                             and proves nothing.
#
# Tests 1-3 replace PATH with a sandbox holding stub `go`, `gofumpt` and
# `golangci-lint`, so the exit code under test is chosen instead of waited for.
# The stub output is text captured from real golangci-lint 2.12.2, not invented.
# Tests 4 and 5 use the REAL golangci-lint against the real shared config,
# because a stub can neither hold a file lock nor validate a schema.
#
# Usage: bash go/_ctl/lib_test.sh
#
# shellcheck shell=bash
set -Eeuo pipefail
IFS=$'\n\t'

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="$HERE/lib.sh"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
SHARED_CONFIG="$REPO_ROOT/.golangci.yml"
FIXTURE="$HERE/testdata/parallelfixture"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# STIMULUS is the golangci-lint exit code fed to cmd_lint; CONFIG is the config
# file under test. The driver repoints both between phase 1 and phase 2.
STIMULUS=""
CONFIG="$SHARED_CONFIG"
# OUT and RC hold the last run_lint result.
OUT=""
RC=0

info() { printf '\033[0;36m[test]\033[0m %s\n' "$*"; }
ok()   { printf '\033[0;32m  ok  \033[0m %s\n' "$*"; }
bad()  { printf '\033[0;31m FAIL \033[0m %s\n' "$*" >&2; }
die()  { printf '\033[0;31m[test]\033[0m %s\n' "$*" >&2; exit 1; }
# fail ends the test it is called from. Each test runs in its own subshell.
fail() { printf '       %s\n' "$*" >&2; exit 1; }

# FAIL-NOT-SKIP (ADR-0020): a missing tool is a failure that names the tool.
for _tool in go golangci-lint mktemp awk grep; do
  command -v "$_tool" >/dev/null || die "this host has no $_tool; the suite cannot run"
done
[[ -f "$LIB" ]]           || die "the library under test is missing: $LIB"
[[ -f "$SHARED_CONFIG" ]] || die "the shared config is missing: $SHARED_CONFIG"
[[ -f "$FIXTURE/go.mod" ]] || die "the parallel fixture module is missing: $FIXTURE"

# ── the sandbox ─────────────────────────────────────────────────────────────

# stub_output_for <code> prints golangci-lint 2.12.2 output for that exit code.
# Each string was captured from a real run, and each is reproducible:
#   0  the fixture module as it stands (`golangci-lint run ./...` in testdata/parallelfixture).
#   1  a THROWAWAY copy of the fixture with `func unusedThing() {}` appended, which
#      lands on line 8. The committed fixture stays clean on purpose: it is the
#      baseline for the concurrency test, where any non-zero exit must be
#      unambiguous, so the finding is provoked in a copy and discarded.
#   3  concurrent runs of the fixture module, one of which lost the lock. This one
#      no longer reproduces against the committed config, because
#      run.allow-parallel-runners now prevents it — that is the point of the fix.
#      To see it again, copy .golangci.yml with the key stripped and run 8 at once.
stub_output_for() {
  case "$1" in
    0) printf '0 issues.' ;;
    1) printf 'parallelfixture.go:8:6: func unusedThing is unused (unused)\n1 issues:\n* unused: 1' ;;
    3) printf 'Error: parallel golangci-lint is running\nThe command is terminated due to an error: parallel golangci-lint is running' ;;
    *) die "no real output is captured for golangci-lint exit $1" ;;
  esac
}

# run_lint <code> calls cmd_lint with a golangci-lint that exits <code>, and sets
# OUT (stdout+stderr) and RC. PROJECT_ROOT is an empty directory and EDEN_GOWORK
# is preset to an absent path, so sourcing lib.sh never reaches its `git` call.
# cmd_lint calls `exit 1`, so it runs in a subshell inside a separate bash.
run_lint() {
  local code="$1" sb
  [[ -n "$code" ]] || die "run_lint needs a golangci-lint exit code"
  sb="$(mktemp -d "$WORK/sb.XXXXXX")"
  mkdir -p "$sb/bin" "$sb/proj"
  ln -s "$(command -v bash)" "$sb/bin/bash"
  printf '#!/bin/sh\nexit 0\n' > "$sb/bin/go"
  printf '#!/bin/sh\nexit 0\n' > "$sb/bin/gofumpt"
  {
    printf '#!/bin/sh\n'
    if [[ "$code" -eq 3 ]]; then
      printf 'printf %%s\\\\n "%s" >&2\n' "$(stub_output_for "$code")"
    else
      printf 'printf %%s\\\\n "%s"\n' "$(stub_output_for "$code")"
    fi
    printf 'exit %s\n' "$code"
  } > "$sb/bin/golangci-lint"
  chmod +x "$sb/bin/go" "$sb/bin/gofumpt" "$sb/bin/golangci-lint"
  # shellcheck disable=SC2016 # the runner resolves the path at run time, not here
  printf '%s\n' 'source "$EDEN_LIB_UNDER_TEST"' '( cmd_lint )' > "$sb/run.sh"

  RC=0
  OUT="$(env -i PATH="$sb/bin" HOME="$sb" PROJECT_ROOT="$sb/proj" \
    EDEN_GOWORK="$sb/absent.go.work" EDEN_LIB_UNDER_TEST="$LIB" \
    bash "$sb/run.sh" 2>&1)" || RC=$?
}

# typo_config prints a copy of the shared config carrying the misspelled key.
# YAML accepts `allow-parallel-runner` silently and golangci-lint then exits 3,
# so this is the mistake that only `config verify` can catch.
typo_config() {
  local dst
  dst="$(mktemp -d "$WORK/cfg.XXXXXX")/.golangci.yml"
  awk '{ print } /^run:$/ { print "  allow-parallel-runner: true" }' "$SHARED_CONFIG" > "$dst"
  if cmp -s "$SHARED_CONFIG" "$dst"; then
    die "the typo mutant changed nothing: $SHARED_CONFIG has no top-level run: block"
  fi
  printf '%s' "$dst"
}

# ── the tests ───────────────────────────────────────────────────────────────

# A collision is exit 3. The verb must still fail, and must not name a cause it
# never checked. This is the defect.
t_a_collision_is_not_reported_as_findings() {
  run_lint "$STIMULUS"
  [[ "$RC" -ne 0 ]] || fail "cmd_lint exited 0 although golangci-lint failed to run"
  if grep -q 'golangci-lint found issues' <<< "$OUT"; then
    fail "a run failure was reported as lint findings: $OUT"
  fi
  grep -Eq 'exit[^0-9]*3' <<< "$OUT" || fail "the failure never names exit code 3: $OUT"
}

# The opposite lie: after the fix, findings must not be reported as a run failure.
t_real_findings_are_still_reported_as_findings() {
  run_lint "$STIMULUS"
  [[ "$RC" -ne 0 ]] || fail "cmd_lint exited 0 although golangci-lint reported findings"
  grep -q 'golangci-lint found issues' <<< "$OUT" || fail "findings were not reported as findings: $OUT"
}

t_a_clean_run_passes() {
  run_lint "$STIMULUS"
  [[ "$RC" -eq 0 ]] || fail "cmd_lint exited $RC on a clean golangci-lint run: $OUT"
  grep -q 'lint: OK' <<< "$OUT" || fail "a clean run did not report success: $OUT"
}

# The real tool, the real config, several instances at once. EDEN_LINT_PARALLEL_N
# runs are started together; none may exit 3 and none may print the lock message.
t_concurrent_lints_do_not_collide() {
  local n="${EDEN_LINT_PARALLEL_N:-8}" dir resolved i run_failures=0 collisions=0 rc
  # `config path` prints to STDERR, and it prints a path relative to the module.
  resolved="$( cd "$FIXTURE" && GOWORK=off golangci-lint config path 2>&1 )" ||
    fail "golangci-lint config path failed in $FIXTURE: $resolved"
  resolved="${resolved##*$'\n'}"
  [[ -n "$resolved" ]] || fail "golangci-lint named no config file for $FIXTURE"
  resolved="$( cd "$FIXTURE" && cd "${resolved%/*}" && pwd )/${resolved##*/}"
  [[ "$resolved" == "$SHARED_CONFIG" ]] ||
    fail "the fixture inherits $resolved, not $SHARED_CONFIG; a clean run here would prove nothing"

  dir="$(mktemp -d "$WORK/par.XXXXXX")"
  for ((i = 1; i <= n; i++)); do
    ( cd "$FIXTURE" && GOWORK=off golangci-lint run --timeout=180s ./... > "$dir/$i.out" 2>&1
      printf '%s' "$?" > "$dir/$i.rc" ) &
  done
  wait
  for ((i = 1; i <= n; i++)); do
    [[ -f "$dir/$i.rc" ]] || fail "run $i of $n never recorded an exit code; the runs did not happen"
    rc="$(cat "$dir/$i.rc")"
    if [[ "$rc" -eq 3 ]]; then
      run_failures=$((run_failures + 1))
    fi
    if grep -q 'parallel golangci-lint is running' "$dir/$i.out"; then
      collisions=$((collisions + 1))
    fi
  done
  [[ "$run_failures" -eq 0 ]] || fail "$run_failures of $n concurrent runs exited 3 (a run failure, not findings)"
  [[ "$collisions" -eq 0 ]] || fail "$collisions of $n concurrent runs hit the golangci-lint lock"
}

# The config must ENABLE parallel runners, and must spell the key in a way the
# schema accepts. Either half alone is a check that cannot fail for the defect.
t_the_shared_config_is_schema_valid() {
  local out rc=0
  out="$(golangci-lint config verify -c "$CONFIG" 2>&1)" || rc=$?
  [[ "$rc" -eq 0 ]] || fail "config verify rejected $CONFIG (exit $rc): $out"
  grep -Eq '^[[:space:]]+allow-parallel-runners:[[:space:]]*true[[:space:]]*$' "$CONFIG" ||
    fail "$CONFIG does not set run.allow-parallel-runners: true, so concurrent lints still collide"
}

TESTS=(
  t_a_collision_is_not_reported_as_findings
  t_real_findings_are_still_reported_as_findings
  t_a_clean_run_passes
  t_concurrent_lints_do_not_collide
  t_the_shared_config_is_schema_valid
)

# ── the stimulus tables ─────────────────────────────────────────────────────

# stimulus_for <test> — what phase 1 drives the test with.
stimulus_for() {
  case "$1" in
    t_a_collision_is_not_reported_as_findings)      printf 'exit:3' ;;
    t_real_findings_are_still_reported_as_findings) printf 'exit:1' ;;
    t_a_clean_run_passes)                           printf 'exit:0' ;;
    t_concurrent_lints_do_not_collide)              printf 'real'   ;;
    t_the_shared_config_is_schema_valid)            printf 'real'   ;;
    *) die "no phase-1 stimulus is declared for $1" ;;
  esac
}

# counter_for <test> — what must BREAK the test. A `none:` entry states its
# reason out loud, so a test can never lose its counter quietly.
counter_for() {
  case "$1" in
    t_a_collision_is_not_reported_as_findings)      printf 'exit:1' ;;
    t_real_findings_are_still_reported_as_findings) printf 'exit:3' ;;
    t_a_clean_run_passes)                           printf 'exit:3' ;;
    t_the_shared_config_is_schema_valid)            printf 'config:typo' ;;
    t_concurrent_lints_do_not_collide)              printf 'none:the counter is a config without the key, and a lock race is probabilistic; it is measured in phase 1, never asserted here' ;;
    *) die "no counter-stimulus is declared for $1; every test must state what makes it fail" ;;
  esac
}

# apply <spec> points the next run at the named stimulus. It returns 1 on a
# `none:` spec so the driver reports the reason instead of silently skipping.
apply() {
  STIMULUS=""
  CONFIG="$SHARED_CONFIG"
  case "$1" in
    exit:*)      STIMULUS="${1#exit:}" ;;
    config:typo) CONFIG="$(typo_config)" ;;
    real)        : ;;
    none:*)      return 1 ;;
    *) die "unknown stimulus spec: $1" ;;
  esac
}

# ── the driver ──────────────────────────────────────────────────────────────

# An argument selects 1 test by name, so a single red can be read on its own. A
# name that matches nothing is a hard error: a filter that silently selects 0
# tests is a suite that exits 0 having checked nothing.
if [[ $# -gt 0 ]]; then
  selected=()
  for t in "${TESTS[@]}"; do
    if [[ "$t" == "$1" ]]; then
      selected+=("$t")
    fi
  done
  [[ ${#selected[@]} -gt 0 ]] || die "no test is named '$1'; the suite has: ${TESTS[*]}"
  TESTS=("${selected[@]}")
fi

failures=0
proven=0
unproven=0
t=""

info "phase 1 — behaviour: ${#TESTS[@]} test(s) against go/_ctl/lib.sh and .golangci.yml"
for t in "${TESTS[@]}"; do
  apply "$(stimulus_for "$t")" || die "phase 1 has no stimulus for $t"
  if ( set -Eeuo pipefail; "$t" ); then
    ok "$t"
  else
    bad "$t"
    failures=$((failures + 1))
  fi
done

info "phase 2 — discrimination: each test under its counter-stimulus must fail"
for t in "${TESTS[@]}"; do
  spec="$(counter_for "$t")"
  if ! apply "$spec"; then
    info "$t — no counter-stimulus: ${spec#none:}"
    unproven=$((unproven + 1))
    continue
  fi
  if ( set -Eeuo pipefail; "$t" ); then
    bad "$t still passed under $spec; it does not read what it claims to read"
    failures=$((failures + 1))
  else
    ok "$t fails under $spec"
    proven=$((proven + 1))
  fi
done

if [[ "$failures" -ne 0 ]]; then
  die "$failures failure(s) across both phases"
fi
# The summary is COUNTED, never asserted. An earlier version ended with "each is
# proven able to fail", which was false for any test carrying a `none:` counter —
# a summary that overstates its own rigour is the defect this suite exists to catch.
info "${#TESTS[@]} test(s) hold; $proven of ${#TESTS[@]} proven able to fail; $unproven stated no counter"
