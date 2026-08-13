#!/usr/bin/env bash
#
# libs/go/_ctl/lib_test.sh — prove that lib.sh's gate can FAIL, and names the failure it had.
#
# Two defects, one suite, because both live in this file:
#
#   1. `cmd_lint` mis-reports a golangci-lint RUN failure as lint findings (tests 1-5).
#   2. `cmd_phase_gate`'s `all` arm records PASS for a verb whose tool exited non-zero
#      (tests 6-7). `phase_architecture || { _gate_summary; exit 1; }` (lib.sh:1187-1190)
#      puts the phase in the ||-LEFT position, where bash suppresses errexit — and the
#      suppression propagates through the phase into `_gate_run`'s `( set -e; "$@" )`
#      subshell, so a verb whose failure is carried only by errexit runs on to its own
#      `log_success` and returns 0. `phase-gate all` is the wired Nx target in all 16
#      go/*/project.json and the nightly CI verb `gate-all`, so this is the reading CI
#      trusts. lib.sh:1007-1020 already documents and fixes the trap INSIDE `_gate_run`;
#      the neutral position has to hold at the CALL SITE too, or the suppression comes
#      straight back.
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
# file under test. GO_BUILD_RC is the exit code the sandbox `go` stub returns for
# `go build` (and ONLY for `go build`); ABSENT_TOOL, when set, is left OFF the
# sandbox PATH entirely (the FAIL-NOT-SKIP stimulus). The driver repoints all four
# between phase 1 and phase 2.
STIMULUS=""
CONFIG="$SHARED_CONFIG"
GO_BUILD_RC=0
ABSENT_TOOL=""
# OUT and RC hold the last run_lint / run_phase_gate result; ARGV holds what the
# phase-gate sandbox's stubs recorded of their own invocations.
OUT=""
RC=0
ARGV=""

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

# ── the phase-gate sandbox ──────────────────────────────────────────────────
#
# `phase-gate all` reaches EVERY verb in lib.sh, so the sandbox stubs every gate tool and
# supplies the artifacts the four phases assert on (a frozen contract, .apibaseline, a bench
# baseline, a parseable coverage profile). Exactly ONE invocation is allowed to fail —
# `go build` — and that is the whole point: a counter-stimulus that breaks EVERY tool at once
# cannot find this defect, because any dimension carrying an explicit `exit` (cmd_lint,
# cover-floor, require_cmd) drags the phase red on its own and the blind path survives. Only
# `go build` fails, and cmd_build carries that failure through errexit alone.

# The gate tools lib.sh reaches for. Every one is stubbed on every run, so a verb can never
# reach a real tool and no assertion depends on what this host happens to have installed.
# `git` is stubbed too: `_eden_monorepo_root` shells out to it to locate the contract file.
GATE_TOOLS=(go gofumpt golangci-lint govulncheck gosec gitleaks hnslint benchstat gremlins git)

# The ordinary utilities lib.sh's verbs and its maintainability scans call. The sandbox PATH
# holds ONLY these and the stubs — never the host PATH — so an "absent tool" stimulus is a real
# absence rather than a stub the real binary shadows from further down the path.
GATE_COREUTILS=(dirname basename mktemp cat tail head rm cp mkdir touch chmod ln sed awk grep tr sort wc find env ls diff cut tee uniq)

# make_gate_sandbox prints the path of a fresh sandbox holding bin/ (the stubs), proj/ (a
# fixture library whose ctl.sh sources lib.sh exactly as a real per-lib ctl.sh does) and mono/
# (the monorepo root the git stub reports, where the frozen contract lives).
make_gate_sandbox() {
  local sb tool utility path
  sb="$(mktemp -d "$WORK/gate.XXXXXX")"
  mkdir -p "$sb/bin" "$sb/gopath/bin" "$sb/proj/.benchbaseline" "$sb/mono/docs/architecture/contracts"
  ln -s "$(command -v bash)" "$sb/bin/bash"
  for utility in "${GATE_COREUTILS[@]}"; do
    # FAIL-NOT-SKIP: a utility the sandbox cannot provide is named, never worked around.
    path="$(command -v "$utility")" ||
      die "this host has no $utility; the phase-gate sandbox cannot be built"
    ln -s "$path" "$sb/bin/$utility"
  done
  : > "$sb/argv"

  for tool in "${GATE_TOOLS[@]}"; do
    [[ "$tool" == "$ABSENT_TOOL" ]] && continue
    {
      printf '#!/usr/bin/env bash\n'
      printf 'printf "%%s\\t%%s\\n" "%s" "$*" >> "%s"\n' "$tool" "$sb/argv"
      case "$tool" in
        go)
          # `go env GOPATH` answers have_cmd's fallback and must never hang. `go list` feeds
          # _api_snapshot and prints nothing, which matches the empty .apibaseline below.
          # `go build` is THE failing invocation.
          # shellcheck disable=SC2016 # the stub body is emitted verbatim, expanded when it runs
          printf 'case "${1:-}" in\n'
          printf '  env)   printf "%%s\\n" "%s/gopath"; exit 0 ;;\n' "$sb"
          printf '  list)  exit 0 ;;\n'
          printf '  build) exit %s ;;\n' "$GO_BUILD_RC"
          printf 'esac\n'
          # cover-floor exits 1 when it parses NO package out of the profile, so `go test
          # -coverprofile=<path>` must write one — otherwise the phase goes red for the
          # FIXTURE instead of for the defect, and the run proves nothing. 1 covered
          # statement in 1 package = 100%, clear of the 80% floor.
          # shellcheck disable=SC2016 # the stub body is emitted verbatim, expanded when it runs
          printf '%s\n' 'for a in "$@"; do case "$a" in -coverprofile=*)' \
            '  printf "%s\n" "mode: atomic" "example.com/gatefixture/fixture.go:5.20,7.2 1 1" > "${a#-coverprofile=}" ;;' \
            'esac; done'
          ;;
        git)
          # _eden_monorepo_root asks for the superproject working tree, then the toplevel.
          printf 'case "$*" in\n'
          printf '  *rev-parse*) printf "%%s\\n" "%s" ;;\n' "$sb/mono"
          printf 'esac\n'
          ;;
        gremlins)
          # cmd_mutate parses Killed/Lived/efficacy and FAILS a run that produced no killable
          # mutant, so the stub speaks gremlins' own summary shape.
          printf 'printf "%%s\\n" "Killed: 8, Lived: 0, Not covered: 0" "Mutator coverage: 100.00%%" "Test efficacy: 100.00%%"\n'
          ;;
        benchstat)
          # cmd_bench_guard scans the report for a "+N%%" delta; a no-change table has none.
          printf 'printf "%%s\\n" "goos: linux" "geomean   ~ (p=1.000 n=10)"\n'
          ;;
      esac
      printf 'exit 0\n'
    } > "$sb/bin/$tool"
    chmod +x "$sb/bin/$tool"
  done

  # The fixture library. `go` is stubbed, so this file is never compiled; it exists because
  # lib.sh's maintainability scans read Go source, and a lib holding none makes their greps
  # exit non-zero for the FIXTURE rather than for the code under test.
  printf '%s\n' \
    '// Package gatefixture is the library the phase-gate sandbox drives.' \
    'package gatefixture' \
    '' \
    '// Fixture is the one exported type of the sandbox library.' \
    'type Fixture struct{}' \
    '' \
    '// Value returns the fixture value.' \
    'func (Fixture) Value() int { return 1 }' > "$sb/proj/fixture.go"
  # The artifacts the gate asserts on: a frozen contract (phase 1), the recorded exported
  # surface (phases 1, 2 and 4 — empty, matching the empty `go list`), a bench baseline (phase 3).
  printf '%s\n' '# gatefixture' '' '> Status: Frozen (the sandbox contract)' \
    > "$sb/mono/docs/architecture/contracts/gatefixture.md"
  : > "$sb/proj/.apibaseline"
  printf '%s\n' 'goos: linux' 'BenchmarkValue-8   1000000   1.0 ns/op   0 B/op   0 allocs/op' \
    > "$sb/proj/.benchbaseline/hotpaths.txt"

  {
    printf '#!/usr/bin/env bash\n'
    printf 'set -Eeuo pipefail\n'
    printf "IFS=\$'\\\\n\\\\t'\n"
    # shellcheck disable=SC2016 # the fixture's own body, expanded when the fixture runs
    printf '%s\n' 'PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"' 'export PROJECT_ROOT'
    printf 'EDEN_LIB_NAME="gatefixture"\n'
    printf 'EDEN_LIB_LEAF="true"\n'
    printf 'EDEN_COVERAGE_FLOOR="80"\n'
    printf 'EDEN_HOT_PATHS="."\n'
    printf 'EDEN_INTEGRATION_CMDS="go"\n'
    printf 'export EDEN_LIB_NAME EDEN_LIB_LEAF EDEN_COVERAGE_FLOOR EDEN_HOT_PATHS EDEN_INTEGRATION_CMDS\n'
    # shellcheck disable=SC2016 # the fixture resolves these at run time, not here
    printf '%s\n' 'source "$EDEN_LIB_UNDER_TEST"' 'lib_main "$@"'
  } > "$sb/proj/ctl.sh"
  chmod +x "$sb/proj/ctl.sh"

  printf '%s' "$sb"
}

# run_phase_gate <phase> — drive the whole verb a human types and CI runs: `./ctl.sh
# phase-gate <phase>`, through the per-lib dispatcher, not through an internal function.
# Sets OUT (stdout+stderr), RC and ARGV.
run_phase_gate() {
  local phase="$1" sb
  [[ -n "$phase" ]] || die "run_phase_gate needs a phase"
  sb="$(make_gate_sandbox)"
  RC=0
  OUT="$(env -i PATH="$sb/bin" HOME="$sb" TMPDIR="$sb" \
    EDEN_GOWORK="$sb/absent.go.work" EDEN_LIB_UNDER_TEST="$LIB" \
    bash "$sb/proj/ctl.sh" phase-gate "$phase" 2>&1)" || RC=$?
  ARGV="$(cat "$sb/argv")"
  assert_gate_harness_intact
}

# assert_gate_harness_intact — a red produced by a broken sandbox is not evidence. A utility
# the sandbox failed to provide surfaces as "command not found", which would make almost any
# verb fail for a reason that has nothing to do with lib.sh, so it aborts the suite instead of
# being read as a result.
assert_gate_harness_intact() {
  if grep -q 'command not found' <<< "$OUT"; then
    die "the sandbox is missing a utility, so this run measured the harness, not lib.sh: $OUT"
  fi
}

# ── the tests ───────────────────────────────────────────────────────────────
#
# HOUSE FORM FOR A NEGATIVE ASSERTION: `if <probe>; then fail "…"; fi` — never
# `<probe> && fail "…"`. The driver reads a test's RETURN STATUS as its verdict, and an
# AND-list whose left side does not match returns 1. As a function's last statement that 1
# becomes the test's return status, so the test reports FAIL in the very state it is meant to
# call a pass, and reports it SILENTLY because `fail` never ran. A POSITIVE assertion
# (`<probe> || fail "…"`) is safe in either form — its passing arm is the left side, which
# returns 0.

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

# THE PHASE-GATE DEFECT. `cmd_phase_gate`'s `all` arm runs each phase in the ||-LEFT position,
# where errexit is suppressed all the way down into `_gate_run`'s subshell, so `cmd_build` runs
# on past a failed `go build` to its own `log_success` and the dimension is recorded PASS. The
# single-phase arms (`architecture)  phase_architecture ;;`) are in a neutral position and do
# fail — which is why nothing caught this: the existing gate suites drive one phase, never `all`.
t_phase_gate_all_never_records_pass_for_a_failing_verb() {
  local rows
  run_phase_gate all
  grep -qE '^go[[:space:]]+build' <<< "$ARGV" ||
    fail "phase-gate all never invoked 'go build', so this run proves nothing: [$ARGV]"
  rows="$(grep -E '^[[:space:]]*PASS[[:space:]].*go build' <<< "$OUT" || true)"
  if [[ -n "$rows" ]]; then
    fail "the gate recorded PASS for a dimension whose 'go build' exited ${GO_BUILD_RC}: [${rows}]"
  fi
  if grep -q 'build: OK' <<< "$OUT"; then
    fail "cmd_build reported its own success after 'go build' exited ${GO_BUILD_RC}: $OUT"
  fi
  if grep -q 'phase-gate all: GREEN' <<< "$OUT"; then
    fail "phase-gate all reported GREEN over a library whose 'go build' exited ${GO_BUILD_RC}: $OUT"
  fi
  [[ "$RC" -ne 0 ]] || fail "phase-gate all exited 0 while 'go build' exited ${GO_BUILD_RC}: $OUT"
}

# CONSERVATION. The other direction: with every tool green, `phase-gate all` must still run all
# four phases and report GREEN. A "fix" that makes the sequencer fail unconditionally satisfies
# the test above and destroys the verb; this is what stops it.
t_phase_gate_all_is_green_when_every_tool_passes() {
  run_phase_gate all
  grep -qE '^go[[:space:]]+build' <<< "$ARGV" ||
    fail "phase-gate all never invoked 'go build', so this run proves nothing: [$ARGV]"
  [[ "$RC" -eq 0 ]] || fail "phase-gate all exited $RC although every tool exited 0: $OUT"
  grep -q 'phase-gate all: GREEN' <<< "$OUT" ||
    fail "phase-gate all did not report GREEN although every tool exited 0: $OUT"
}

TESTS=(
  t_a_collision_is_not_reported_as_findings
  t_real_findings_are_still_reported_as_findings
  t_a_clean_run_passes
  t_concurrent_lints_do_not_collide
  t_the_shared_config_is_schema_valid
  t_phase_gate_all_never_records_pass_for_a_failing_verb
  t_phase_gate_all_is_green_when_every_tool_passes
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
    t_phase_gate_all_never_records_pass_for_a_failing_verb) printf 'gobuild:1' ;;
    t_phase_gate_all_is_green_when_every_tool_passes)       printf 'gobuild:0' ;;
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
    # A green `go build` makes the build dimension legitimately PASS, which is exactly the row
    # the test forbids — so a test that stopped reading the summary cannot survive this.
    t_phase_gate_all_never_records_pass_for_a_failing_verb) printf 'gobuild:0' ;;
    # NOT `gobuild:1`: that is the defect's own stimulus, and while the defect stands the gate
    # still reports GREEN under it, so the counter would not break this test. An absent hnslint
    # exits 127 through require_cmd's explicit `exit`, which survives the errexit suppression
    # that defeats every other verb — and it lands AFTER `go build`, so the argv floor still holds.
    t_phase_gate_all_is_green_when_every_tool_passes)       printf 'absent:hnslint' ;;
    *) die "no counter-stimulus is declared for $1; every test must state what makes it fail" ;;
  esac
}

# apply <spec> points the next run at the named stimulus. It returns 1 on a
# `none:` spec so the driver reports the reason instead of silently skipping.
apply() {
  STIMULUS=""
  CONFIG="$SHARED_CONFIG"
  GO_BUILD_RC=0
  ABSENT_TOOL=""
  case "$1" in
    exit:*)      STIMULUS="${1#exit:}" ;;
    config:typo) CONFIG="$(typo_config)" ;;
    gobuild:*)   GO_BUILD_RC="${1#gobuild:}" ;;
    absent:*)    ABSENT_TOOL="${1#absent:}" ;;
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
