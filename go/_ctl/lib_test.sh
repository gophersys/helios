#!/usr/bin/env bash
#
# libs/go/_ctl/lib_test.sh — prove that lib.sh's gate can FAIL, and names the failure it had.
#
# Three defects, one suite, because all three live in this file:
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
#   3. The substrate lanes state NO time budget (tests 8-17). `cmd_integration` runs
#      `go test -tags integration ./... -count=1` with no `-timeout`, so Go's own default
#      of 10 minutes PER PACKAGE applies silently. `workspaceprovider/kubernetesadapter`
#      stands up 8 clusters (6 k3d + 2 kind, one per test) and measures 601.3s isolated /
#      544.1s in-lane against that 600.0s wall — a coin flip at 91-100% of it, which is
#      why it reads as flake rather than as a budget. `_cover_profile` omits `-timeout`
#      the same way, and cover-floor is a dimension of BOTH `phase-gate testing` and
#      `phase-gate qa`, so the same 8 clusters run under the same silent default one verb
#      over. The budget has to be STATED (`EDEN_SUBSTRATE_TIMEOUT`), it has to be REFUSED
#      when it is unbounded — a lane with no budget cannot report a hang, and a hang is
#      exactly how a real-cluster suite fails — and it has to reach `go test`, not just
#      the log line. Test 10 is the one that proves the last part: it runs a REAL `go`
#      against a fixture that sleeps past its budget, so the timeout is proven by
#      BEHAVIOUR in seconds instead of by shape, or by waiting 10 minutes.
#
#      Tests 13-17 close 2 holes a verifier found in the first cut. `lifecycle`, `load`
#      and the `-v` flag were pinned ONLY by the verb-conservation goldens, and a golden
#      is the one check in this repository with a sanctioned "make it match" button:
#      deleting `-timeout` from `cmd_lifecycle` left `lib_test.sh` GREEN, reddened only
#      the goldens, and one `EDEN_CONSERVATION_RECORD=1` made the whole repository green
#      again. The `integration` lane never had that property, because its shape AND its
#      behaviour are asserted here. Tests 13-15 give the other two lanes and the flag the
#      same standing. Tests 16-17 pin the guard's SECOND arm: Go truncates a duration to
#      whole nanoseconds, so `0.4ns` parses, becomes 0, and 0 is NO LIMIT — and the arm
#      that refuses it is only sound if `1ns`, the smallest value the guard admits, really
#      bounds a run, which test 17 drives against a real `go` rather than assuming.
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
# LIB_SOURCE is the file under test as it stands in the tree; LIB is the copy the NEXT run
# drives. They are the same file for every behaviour run, and a `mutant:` counter-stimulus
# repoints LIB at a surgically mutated copy — the same shape as `typo_config` below, which
# has repointed CONFIG at a mutated .golangci.yml since this suite was written.
LIB_SOURCE="$HERE/lib.sh"
LIB="$LIB_SOURCE"
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
# SUBSTRATE_TIMEOUT_PRESENT distinguishes "EDEN_SUBSTRATE_TIMEOUT is not in the environment
# at all" (0 — the state of the 14 non-cluster libraries, which must keep Go's own default)
# from "it is set, possibly to the empty string" (1). SUBSTRATE_TIMEOUT is the value.
#
# The guard has TWO arms with DISTINCT messages, so each has its own value set and its own
# test, and each test asserts WHICH arm fired rather than merely that something failed:
#   REFUSE_VALUES   — empty, negative, or no non-zero digit  -> "is not a positive duration"
#   FRACTION_VALUES — carries a `.`                          -> "is fractional"
# The second arm exists because Go TRUNCATES a duration to whole nanoseconds: `0.4ns` parses,
# reaches `go test -timeout=0.4ns`, becomes 0, and 0 is NO LIMIT. Refusing every fraction is
# what makes "one digit in 1-9 and no dot" a proof that the budget is at least 1ns.
SUBSTRATE_TIMEOUT_PRESENT=0
SUBSTRATE_TIMEOUT=""
REFUSE_VALUES=("0" "0s" "" "0h0m0s" "-5m" "notaduration")
FRACTION_VALUES=("0.4ns" "0.0000000001s" "1.5h" "0.5s")
# OUT and RC hold the last run_lint / run_phase_gate / run_verb / run_real_lane result;
# ARGV holds what the sandbox's stubs recorded of their own invocations; ELAPSED_MS is the
# wall time of the last run_real_lane, so "reported in seconds" is a number, not an adjective.
OUT=""
RC=0
ARGV=""
ELAPSED_MS=0

info() { printf '\033[0;36m[test]\033[0m %s\n' "$*"; }
ok()   { printf '\033[0;32m  ok  \033[0m %s\n' "$*"; }
bad()  { printf '\033[0;31m FAIL \033[0m %s\n' "$*" >&2; }
die()  { printf '\033[0;31m[test]\033[0m %s\n' "$*" >&2; exit 1; }
# fail ends the test it is called from. Each test runs in its own subshell.
fail() { printf '       %s\n' "$*" >&2; exit 1; }

# FAIL-NOT-SKIP (ADR-0020): a missing tool is a failure that names the tool.
# `date` is required because test 10 MEASURES the wall time of a real timed-out lane.
for _tool in go golangci-lint mktemp awk grep date; do
  command -v "$_tool" >/dev/null || die "this host has no $_tool; the suite cannot run"
done
[[ -f "$LIB_SOURCE" ]]    || die "the library under test is missing: $LIB_SOURCE"
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

# run_verb <verb> — drive ONE verb through the per-lib dispatcher in the same sandbox, exactly
# as `./ctl.sh <verb>` does. The sandbox already records every stub's ARGV, which is what makes
# "the lane states its budget" an assertion about the command that RAN rather than about the
# sentence lib.sh printed. Sets OUT, RC and ARGV.
run_verb() {
  local verb="$1" sb
  [[ -n "$verb" ]] || die "run_verb needs a verb"
  sb="$(make_gate_sandbox)"
  # env -i means EDEN_SUBSTRATE_TIMEOUT is genuinely ABSENT unless this run sets it, so the
  # default-budget test measures the state every non-cluster library is in.
  local -a env_extra=()
  if [[ "$SUBSTRATE_TIMEOUT_PRESENT" -eq 1 ]]; then
    env_extra+=("EDEN_SUBSTRATE_TIMEOUT=$SUBSTRATE_TIMEOUT")
  fi
  RC=0
  OUT="$(env -i PATH="$sb/bin" HOME="$sb" TMPDIR="$sb" \
    EDEN_GOWORK="$sb/absent.go.work" EDEN_LIB_UNDER_TEST="$LIB" \
    ${env_extra[@]+"${env_extra[@]}"} \
    bash "$sb/proj/ctl.sh" "$verb" 2>&1)" || RC=$?
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

# ── the real-substrate-lane fixture (test 10) ───────────────────────────────
#
# A stub `go` can be handed any flag and will exit 0, so a stubbed run proves the flag was
# SPELLED, never that it was OBEYED. Test 10 therefore drives a REAL `go` over a throwaway
# module whose one integration-tagged test sleeps past every budget it is given.
#
# The numbers, and why these numbers. Measured inside ghcr.io/gophersys/base (amd64) on an
# arm64 host, so every second below is a QEMU-EMULATED second — the slow direction:
#   cold build of the fixture           2.56s
#   warm lane at -timeout=2s            2.70s  (exit 1, "test timed out after 2s")
#   warm lane with NO -timeout          5.39s  (exit 0 — the counter-stimulus's behaviour)
# make_real_lane_fixture WARMS the build cache before the measured run, so the wall time is
# the lane's, not the compiler's. The ceiling is 6000ms:
#   - 2.1x the 2.8s measured warm run, which is the margin against a loaded/emulated host;
#   - and strictly BELOW the fixture's own 10s sleep, so a lane that ignored its budget
#     cannot slip under the ceiling even if it somehow exited non-zero for another reason.
# The sleep is 10s rather than 5s for that second property: it buys the ceiling 4s of room
# underneath the un-budgeted wall while costing the suite 10s once, in phase 2.
HANG_SLEEP_SECONDS=10
HANG_BUDGET=2s
HANG_CEILING_MS=6000

# make_real_lane_fixture prints the path of a throwaway module + per-lib ctl.sh, with the test
# binary already built (a build failure here is a HARNESS failure and aborts the suite, because
# a cold compile inside the measured window would report the compiler as if it were the lane).
make_real_lane_fixture() {
  local sb rc=0
  sb="$(mktemp -d "$WORK/hang.XXXXXX")"
  mkdir -p "$sb/proj"
  printf '%s\n' 'module example.com/hangfixture' '' 'go 1.24' > "$sb/proj/go.mod"
  printf '%s\n' \
    '// Package hangfixture is the throwaway module the substrate-budget test drives.' \
    'package hangfixture' > "$sb/proj/doc.go"
  printf '%s\n' \
    '//go:build integration' \
    '' \
    'package hangfixture' \
    '' \
    'import (' \
    '	"testing"' \
    '	"time"' \
    ')' \
    '' \
    '// TestSleepsPastTheBudget outlives every budget the lane is given, so the only way this' \
    '// test ends is the timeout the lane must impose on it.' \
    'func TestSleepsPastTheBudget(t *testing.T) {' \
    "	time.Sleep(${HANG_SLEEP_SECONDS} * time.Second)" \
    '}' > "$sb/proj/hang_test.go"

  {
    printf '#!/usr/bin/env bash\n'
    printf 'set -Eeuo pipefail\n'
    printf "IFS=\$'\\\\n\\\\t'\n"
    # shellcheck disable=SC2016 # the fixture's own body, expanded when the fixture runs
    printf '%s\n' 'PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"' 'export PROJECT_ROOT'
    printf 'EDEN_LIB_NAME="hangfixture"\n'
    printf 'EDEN_INTEGRATION_CMDS="go"\n'
    printf 'export EDEN_LIB_NAME EDEN_INTEGRATION_CMDS\n'
    # shellcheck disable=SC2016 # the fixture resolves these at run time, not here
    printf '%s\n' 'source "$EDEN_LIB_UNDER_TEST"' 'lib_main "$@"'
  } > "$sb/proj/ctl.sh"
  chmod +x "$sb/proj/ctl.sh"

  ( cd "$sb/proj" && env GOWORK=off go test -tags integration -c -o "$sb/warm.test" . ) || rc=$?
  [[ "$rc" -eq 0 ]] ||
    die "the hang fixture does not build (exit $rc); a run from here would measure the harness, not the budget"
  printf '%s' "$sb"
}

# run_real_lane <fixture> — `./ctl.sh integration` against a REAL go, timed. Sets OUT, RC and
# ELAPSED_MS. The environment is inherited (PATH, HOME, GOCACHE) because the point is the real
# toolchain; only GOWORK is pinned off, so no ambient go.work can redirect the module.
run_real_lane() {
  local fixture="$1" started ended
  [[ -n "$fixture" ]] || die "run_real_lane needs a fixture"
  local -a env_extra=()
  if [[ "$SUBSTRATE_TIMEOUT_PRESENT" -eq 1 ]]; then
    env_extra+=("EDEN_SUBSTRATE_TIMEOUT=$SUBSTRATE_TIMEOUT")
  fi
  started="$(date +%s%N)"
  RC=0
  OUT="$(env GOWORK=off EDEN_GOWORK="$fixture/absent.go.work" EDEN_LIB_UNDER_TEST="$LIB" \
    ${env_extra[@]+"${env_extra[@]}"} \
    bash "$fixture/proj/ctl.sh" integration 2>&1)" || RC=$?
  ended="$(date +%s%N)"
  ELAPSED_MS=$(( (ended - started) / 1000000 ))
}

# ── the lib.sh mutants (the counter-stimuli for tests 8-12) ─────────────────
#
# The defect lives INSIDE lib.sh, so its counter-stimulus is a mutated lib.sh — the same shape
# as `typo_config`, which mutates .golangci.yml for the same reason. Each mutant is surgical
# and spelling-independent: it is anchored on the INVOCATION (the line that runs `go test`,
# never a `log_*` line or a comment), so it survives any reasonable spelling of the fix.
#
# Every mutant DIES if it changed nothing. A counter-stimulus that mutated nothing proves
# nothing, and the message names the anchor it could not find — which, before the fix lands,
# is exactly the true statement "lib.sh has no such argument yet".
mutant_lib() {
  local spec="$1" dir dst rc=0
  dir="$(mktemp -d "$WORK/mut.XXXXXX")"
  dst="$dir/lib.sh"
  # is_log: a log_* call or a comment DESCRIBES the lane; it does not run it. Mutating those
  # would let a fix that only prints the budget survive, which is the very thing test 10 exists
  # to catch — so the invocation-only anchor is load-bearing, not cosmetic.
  local common='
    function is_log(l) { return (l ~ /log_(info|success|error|warn|dim)/ || l ~ /^[[:space:]]*#/) }
  '
  case "$spec" in
    # THE COUNTER FOR "the lane states its budget" AND FOR "a hang is reported in seconds":
    # drop -timeout from the integration INVOCATION and leave the log line boasting about it.
    integration-untimed)
      awk "$common"'
        /-tags[[:space:]]*"?integration/ && !is_log($0) {
          if (sub(/[[:space:]]+-timeout(=[^[:space:]]+|[[:space:]]+[^[:space:]]+)/, "")) changed++
        }
        { print }
        END { if (!changed) exit 3 }
      ' "$LIB_SOURCE" > "$dst" || rc=$?
      [[ "$rc" -eq 0 ]] ||
        die "the '$spec' mutant changed nothing: no non-log line in $LIB_SOURCE runs '-tags integration' with a -timeout, so the counter-stimulus cannot be applied"
      ;;
    # THE SECOND COUNTER FOR "the lane states its budget": keep -timeout, but hard-code Go's
    # 10m instead of reading the knob. The log line still says 7m, so only a test that reads
    # the ARGV catches it.
    integration-hardcoded)
      awk "$common"'
        /-tags[[:space:]]*"?integration/ && !is_log($0) {
          if (sub(/-timeout(=[^[:space:]]+|[[:space:]]+[^[:space:]]+)/, "-timeout=10m")) changed++
        }
        { print }
        END { if (!changed) exit 3 }
      ' "$LIB_SOURCE" > "$dst" || rc=$?
      [[ "$rc" -eq 0 ]] ||
        die "the '$spec' mutant changed nothing: no non-log line in $LIB_SOURCE runs '-tags integration' with a -timeout, so the counter-stimulus cannot be applied"
      ;;
    # THE COUNTERS FOR THE OTHER TWO SUBSTRATE LANES. These 2 lanes are pinned by the
    # verb-conservation GOLDENS as well — but a golden is the one check in this repository with a
    # sanctioned "make it match" button, so `EDEN_CONSERVATION_RECORD=1` turns a deletion here
    # green everywhere. An assertion has no such button. That asymmetry is why these exist.
    lifecycle-untimed)
      awk "$common"'
        /-tags[[:space:]]*"?lifecycle[[:space:]]+\.\/\.\.\./ && !is_log($0) {
          if (sub(/[[:space:]]+-timeout(=[^[:space:]]+|[[:space:]]+[^[:space:]]+)/, "")) changed++
        }
        { print }
        END { if (!changed) exit 3 }
      ' "$LIB_SOURCE" > "$dst" || rc=$?
      [[ "$rc" -eq 0 ]] ||
        die "the '$spec' mutant changed nothing: no non-log line in $LIB_SOURCE runs '-tags lifecycle ./...' with a -timeout, so the counter-stimulus cannot be applied"
      ;;
    load-untimed)
      awk "$common"'
        /-tags[[:space:]]*"?load[[:space:]]+\.\/\.\.\./ && !is_log($0) {
          if (sub(/[[:space:]]+-timeout(=[^[:space:]]+|[[:space:]]+[^[:space:]]+)/, "")) changed++
        }
        { print }
        END { if (!changed) exit 3 }
      ' "$LIB_SOURCE" > "$dst" || rc=$?
      [[ "$rc" -eq 0 ]] ||
        die "the '$spec' mutant changed nothing: no non-log line in $LIB_SOURCE runs '-tags load ./...' with a -timeout, so the counter-stimulus cannot be applied"
      ;;
    # THE 2 COUNTERS FOR "-v is on integration AND ONLY on integration" — one per half. Dropping
    # it kills the per-test cost baseline the deferred fix needs; spreading it to another lane
    # makes the flag mean nothing, and both are one re-record away from invisible.
    integration-not-verbose)
      awk "$common"'
        /-tags[[:space:]]*"?integration/ && !is_log($0) {
          if (sub(/[[:space:]]+-v([[:space:]]|$)/, " ")) changed++
        }
        { print }
        END { if (!changed) exit 3 }
      ' "$LIB_SOURCE" > "$dst" || rc=$?
      [[ "$rc" -eq 0 ]] ||
        die "the '$spec' mutant changed nothing: no non-log line in $LIB_SOURCE runs '-tags integration' with a -v, so the counter-stimulus cannot be applied"
      ;;
    lifecycle-verbose)
      awk "$common"'
        /-tags[[:space:]]*"?lifecycle[[:space:]]+\.\/\.\.\./ && !is_log($0) {
          if (sub(/$/, " -v")) changed++
        }
        { print }
        END { if (!changed) exit 3 }
      ' "$LIB_SOURCE" > "$dst" || rc=$?
      [[ "$rc" -eq 0 ]] ||
        die "the '$spec' mutant changed nothing: no non-log line in $LIB_SOURCE runs '-tags lifecycle ./...', so the counter-stimulus cannot be applied"
      ;;
    # THE COUNTER FOR "a fractional budget is refused", and ONLY that arm. `guard-toothless`
    # disarms BOTH arms at once, so it cannot tell the fractional clause from the zero clause.
    # This one is anchored on the word the TEST reads out of the message — "fractional" — so it
    # neuters that arm's exit and leaves the zero arm intact.
    fraction-arm-disarmed)
      awk '
        /fractional/ { window = 8 }
        window > 0 {
          if (sub(/(exit|return)[[:space:]]+[1-9][0-9]*/, ":")) changed++
        }
        { if (window > 0) window--; print }
        END { if (!changed) exit 3 }
      ' "$LIB_SOURCE" > "$dst" || rc=$?
      [[ "$rc" -eq 0 ]] ||
        die "the '$spec' mutant changed nothing: no exit/return sits within 8 lines of the word 'fractional' in $LIB_SOURCE, so there is no fractional arm to disarm"
      ;;
    # THE COUNTER FOR "cover-floor carries the same budget": fix ONLY cmd_integration. This is
    # what turns the budget from a case into a rule.
    cover-untimed)
      awk "$common"'
        /-coverprofile=/ && !is_log($0) {
          if (sub(/[[:space:]]+-timeout(=[^[:space:]]+|[[:space:]]+[^[:space:]]+)/, "")) changed++
        }
        { print }
        END { if (!changed) exit 3 }
      ' "$LIB_SOURCE" > "$dst" || rc=$?
      [[ "$rc" -eq 0 ]] ||
        die "the '$spec' mutant changed nothing: no non-log line in $LIB_SOURCE runs -coverprofile= with a -timeout, so the counter-stimulus cannot be applied"
      ;;
    # THE COUNTER FOR "the default is 10m": move the default off Go's own, which is what would
    # change behaviour for the 14 libraries that never set the knob.
    default-25m)
      # `:?[=-]` covers all four default operators. `${VAR=10m}` — assign only when UNSET, so an
      # EXPLICITLY empty value still reaches the guard — is the spelling this defect wants, and
      # an anchor that only knew `:=` would have died on the very fix it exists to test. The
      # mutant normalises the operator to `:=`, which is irrelevant to the VALUE it changes.
      awk '
        /EDEN_SUBSTRATE_TIMEOUT:?[=-]/ {
          if (sub(/EDEN_SUBSTRATE_TIMEOUT:?[=-][^}"]*/, "EDEN_SUBSTRATE_TIMEOUT:=25m")) changed++
        }
        { print }
        END { if (!changed) exit 3 }
      ' "$LIB_SOURCE" > "$dst" || rc=$?
      [[ "$rc" -eq 0 ]] ||
        die "the '$spec' mutant changed nothing: $LIB_SOURCE declares no EDEN_SUBSTRATE_TIMEOUT default, so the counter-stimulus cannot be applied"
      ;;
    # THE COUNTER FOR "an unbounded budget is refused": pull the guard's teeth. Every `exit N` /
    # `return N` within 8 lines of a mention of the knob becomes `:`, so the guard still reads
    # the value, still logs, and no longer stops the lane. Anchoring on the knob's NAME rather
    # than on a function name is what makes this independent of how the guard is written.
    guard-toothless)
      awk '
        /EDEN_SUBSTRATE_TIMEOUT/ { window = 8 }
        window > 0 {
          if (sub(/(exit|return)[[:space:]]+[1-9][0-9]*/, ":")) changed++
        }
        { if (window > 0) window--; print }
        END { if (!changed) exit 3 }
      ' "$LIB_SOURCE" > "$dst" || rc=$?
      [[ "$rc" -eq 0 ]] ||
        die "the '$spec' mutant changed nothing: no exit/return sits within 8 lines of an EDEN_SUBSTRATE_TIMEOUT mention in $LIB_SOURCE, so there is no guard to disarm"
      ;;
    *) die "unknown lib.sh mutant: $spec" ;;
  esac
  if cmp -s "$LIB_SOURCE" "$dst"; then
    die "the '$spec' mutant reported a change but produced an identical file: $LIB_SOURCE"
  fi
  printf '%s' "$dst"
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

# THE SUBSTRATE-BUDGET DEFECT. The integration lane runs `go test -tags integration ./...
# -count=1` with no -timeout, so Go's silent 10m/package is the budget nobody chose. The
# recorded ARGV — not the sentence lib.sh prints — is what says the lane actually carries it.
t_the_substrate_lane_states_its_budget() {
  run_verb integration
  grep -qE '^go[[:space:]]+test[[:space:]].*-tags[[:space:]]+"?integration' <<< "$ARGV" ||
    fail "the integration lane never ran 'go test -tags integration', so this run proves nothing: [$ARGV]"
  grep -qE '^go[[:space:]]+test[[:space:]].*-timeout[= ]7m([[:space:]]|$)' <<< "$ARGV" ||
    fail "the lane ran with no 7m budget although EDEN_SUBSTRATE_TIMEOUT=7m — Go's silent 10m default still decides: [$ARGV]"
  grep -qE '\[info\].*integration.*7m' <<< "$OUT" ||
    fail "no [info] line states the 7m budget, so a reader waiting on the lane cannot know what it is: $OUT"
}

# An unbounded lane cannot report a hang, and a hang is exactly how a real-cluster suite fails.
# `0` is the value someone reaches for when the number is inconvenient; the empty string is the
# value a half-written per-lib override leaves behind. Both must be refused BY NAME, so the
# reader is sent to the knob instead of to a lane that never returns.
t_an_unbounded_budget_is_refused() {
  assert_every_value_is_refused 'is not a positive duration' "${REFUSE_VALUES[@]}"
}

# THE SECOND GUARD ARM. Go TRUNCATES a duration to whole nanoseconds, so `0.4ns` parses, reaches
# `go test -timeout=0.4ns`, becomes 0 — and 0 is NO LIMIT. A digit-only filter passes it, because
# `0.4ns` does carry a non-zero digit; that is exactly how the first version of this guard read
# "bounded" over a lane that was not. Refusing every fraction is what makes "a digit in 1-9 and no
# dot" a proof rather than a hope, and it costs only the legitimate `1.5h`, which is written `90m`.
# The arm is asserted BY ITS OWN MESSAGE, so a value cannot be credited to the wrong clause.
t_a_fractional_budget_is_refused() {
  assert_every_value_is_refused 'is fractional' "${FRACTION_VALUES[@]}"
}

# assert_every_value_is_refused <message-fragment> <value...> — the shared body of the 2 refusal
# tests. Each value must be refused, must be refused BY THE NAMED ARM, must name the knob, and
# must reach NO `go` invocation at all: a budget that is going to be rejected must be rejected
# before the lane spends a substrate, not after.
assert_every_value_is_refused() {
  local expected="$1"; shift
  local value shown
  # A for-loop over an empty list returns 0, which would make this test report a pass having
  # asserted nothing — the "0 tests ran, exit 0" class this suite exists to delete.
  [[ $# -gt 0 ]] || fail "no budget values were supplied, so this run asserted nothing"
  for value in "$@"; do
    shown="${value:-<empty>}"
    SUBSTRATE_TIMEOUT_PRESENT=1
    SUBSTRATE_TIMEOUT="$value"
    run_verb integration
    [[ "$RC" -ne 0 ]] ||
      fail "EDEN_SUBSTRATE_TIMEOUT=${shown} was accepted (exit 0): the lane would run unbounded and could never report a hang: $OUT"
    grep -q 'EDEN_SUBSTRATE_TIMEOUT' <<< "$OUT" ||
      fail "the refusal of ${shown} never names EDEN_SUBSTRATE_TIMEOUT, so the reader cannot find the knob to fix: $OUT"
    grep -q "$expected" <<< "$OUT" ||
      fail "${shown} was refused, but not by the '${expected}' arm — a value credited to the wrong clause hides which check is doing the work: $OUT"
    if grep -qE '^go[[:space:]]' <<< "$ARGV"; then
      fail "${shown} was refused AFTER the lane had already invoked go: [$ARGV]"
    fi
  done
}

# THE ONE THAT PROVES BEHAVIOUR RATHER THAN SHAPE. A stub `go` accepts any flag and exits 0, so
# every other test here proves the budget was SPELLED. This one runs a REAL `go` over a module
# whose only test sleeps 10s, gives the lane 2s, and demands the failure arrive in seconds.
# A sibling feature shipped a guard tested by shape alone and the verifier caught it.
t_a_hang_is_reported_in_seconds() {
  local fixture
  fixture="$(make_real_lane_fixture)"
  SUBSTRATE_TIMEOUT_PRESENT=1
  SUBSTRATE_TIMEOUT="$HANG_BUDGET"
  run_real_lane "$fixture"
  info "the real lane returned in ${ELAPSED_MS}ms with rc=${RC}, against a ${HANG_SLEEP_SECONDS}s sleep and a ${HANG_BUDGET} budget"
  [[ "$RC" -ne 0 ]] ||
    fail "the lane exited 0 although its only test sleeps ${HANG_SLEEP_SECONDS}s under a ${HANG_BUDGET} budget: the budget reached the log line but never 'go test': $OUT"
  grep -q "test timed out after ${HANG_BUDGET}" <<< "$OUT" ||
    fail "the lane failed without reporting a timeout, so it did not fail for the budget: $OUT"
  [[ "$ELAPSED_MS" -lt "$HANG_CEILING_MS" ]] ||
    fail "the hang was reported after ${ELAPSED_MS}ms, over the ${HANG_CEILING_MS}ms ceiling and near the ${HANG_SLEEP_SECONDS}s the test would have slept — a budget reported in minutes is the defect"
}

# The same landmine sits one verb over: _cover_profile omits -timeout too, and cover-floor is a
# dimension of BOTH `phase-gate testing` and `phase-gate qa`, so the same clusters run under the
# same silent default twice more. This is the test that makes the budget a RULE, not a case.
t_cover_floor_carries_the_same_budget() {
  run_verb cover-floor
  grep -qE '^go[[:space:]]+test[[:space:]].*-coverprofile=' <<< "$ARGV" ||
    fail "cover-floor never ran a coverage 'go test', so this run proves nothing: [$ARGV]"
  grep -qE '^go[[:space:]]+test[[:space:]](.*-timeout[= ]7m.*-coverprofile=|.*-coverprofile=.*-timeout[= ]7m)' <<< "$ARGV" ||
    fail "the coverage lane carries no 7m budget, so cover-floor still runs the cluster suites under Go's silent 10m: [$ARGV]"
}

# CONSERVATION. With the knob absent — the state of every library that does not override it —
# the budget must be Go's own 10m, so the 14 non-cluster libraries change behaviour not at all;
# only the number stops being implied. And it must be STATED, or it is implied again.
t_the_default_budget_is_ten_minutes_and_is_stated() {
  run_verb integration
  grep -qE '^go[[:space:]]+test[[:space:]].*-tags[[:space:]]+"?integration' <<< "$ARGV" ||
    fail "the integration lane never ran 'go test -tags integration', so this run proves nothing: [$ARGV]"
  grep -qE '^go[[:space:]]+test[[:space:]].*-timeout[= ]10m([[:space:]]|$)' <<< "$ARGV" ||
    fail "with no override the lane does not carry Go's own 10m, so the 14 non-cluster libraries changed behaviour: [$ARGV]"
  grep -qE '\[info\].*integration.*10m' <<< "$OUT" ||
    fail "no [info] line states the default 10m budget, so it is implied again: $OUT"
}

# THE OTHER TWO SUBSTRATE LANES. `lifecycle` and `load` were carried into this feature by the
# verb-conservation goldens alone, and a golden has a sanctioned `EDEN_CONSERVATION_RECORD=1`
# button: deleting -timeout from either lane left the whole repository green after one re-record.
# An assertion has no such button. These 2 tests are the difference between a recorded fact and
# a stated intent.
t_the_lifecycle_lane_states_its_budget() {
  run_verb lifecycle
  grep -qE '^go[[:space:]]+test[[:space:]].*-tags[[:space:]]+"?lifecycle[[:space:]]' <<< "$ARGV" ||
    fail "the lifecycle lane never ran 'go test -tags lifecycle', so this run proves nothing: [$ARGV]"
  grep -qE '^go[[:space:]]+test[[:space:]].*-timeout[= ]7m([[:space:]]|$)' <<< "$ARGV" ||
    fail "the lifecycle lane carries no 7m budget although EDEN_SUBSTRATE_TIMEOUT=7m: [$ARGV]"
}

t_the_load_lane_states_its_budget() {
  run_verb load
  grep -qE '^go[[:space:]]+test[[:space:]].*-tags[[:space:]]+"?load[[:space:]]' <<< "$ARGV" ||
    fail "the load lane never ran 'go test -tags load', so this run proves nothing: [$ARGV]"
  grep -qE '^go[[:space:]]+test[[:space:]].*-timeout[= ]7m([[:space:]]|$)' <<< "$ARGV" ||
    fail "the load lane carries no 7m budget although EDEN_SUBSTRATE_TIMEOUT=7m: [$ARGV]"
}

# `-v` is deliberate and NARROW: it makes `go test` print each test's own elapsed time, which is
# the per-test cost baseline the deferred shared-cluster fix needs before it can prove it worked.
# Both halves matter. Without it on integration the baseline never exists; spread across the other
# lanes it stops meaning "this is the lane we are costing" and buries every other lane's output.
t_only_the_integration_lane_is_verbose() {
  local lane
  run_verb integration
  grep -qE '^go[[:space:]]+test[[:space:]].*-tags[[:space:]]+"?integration' <<< "$ARGV" ||
    fail "the integration lane never ran 'go test -tags integration', so this run proves nothing: [$ARGV]"
  grep -qE '^go[[:space:]]+test[[:space:]].* -v([[:space:]]|$)' <<< "$ARGV" ||
    fail "the integration lane carries no -v, so CI records no per-test cost and the deferred fix has no baseline: [$ARGV]"
  for lane in lifecycle load cover-floor; do
    run_verb "$lane"
    if grep -qE '^go[[:space:]]+test[[:space:]].* -v([[:space:]]|$)' <<< "$ARGV"; then
      fail "the $lane lane also carries -v; the flag marks the ONE lane being costed, and on every lane it marks nothing: [$ARGV]"
    fi
  done
}

# `1ns` is the boundary the guard's proof rests on: "no dot, and a digit in 1-9" is only sound if
# the smallest value it admits REALLY bounds a run. So the smallest admissible budget is driven
# against a REAL go and a test that sleeps 10s. If this fails, the guard is arithmetic about a
# property Go does not have.
t_one_nanosecond_is_accepted_and_bounds_the_lane() {
  local fixture
  fixture="$(make_real_lane_fixture)"
  SUBSTRATE_TIMEOUT_PRESENT=1
  SUBSTRATE_TIMEOUT="1ns"
  run_real_lane "$fixture"
  info "the smallest admissible budget returned in ${ELAPSED_MS}ms with rc=${RC}, against a ${HANG_SLEEP_SECONDS}s sleep"
  if grep -q 'EDEN_SUBSTRATE_TIMEOUT' <<< "$OUT"; then
    fail "1ns was REFUSED, but the guard admits it — the proof that 'a digit in 1-9 and no dot' means >= 1ns rests on 1ns being usable: $OUT"
  fi
  [[ "$RC" -ne 0 ]] ||
    fail "the lane exited 0 under a 1ns budget although its test sleeps ${HANG_SLEEP_SECONDS}s: the smallest value the guard admits does not bound anything: $OUT"
  grep -q 'test timed out after 1ns' <<< "$OUT" ||
    fail "the lane failed under 1ns without reporting a timeout, so it did not fail for the budget: $OUT"
  [[ "$ELAPSED_MS" -lt "$HANG_CEILING_MS" ]] ||
    fail "1ns took ${ELAPSED_MS}ms, over the ${HANG_CEILING_MS}ms ceiling and near the ${HANG_SLEEP_SECONDS}s the test would have slept — it did not bound the run"
}

TESTS=(
  t_a_collision_is_not_reported_as_findings
  t_real_findings_are_still_reported_as_findings
  t_a_clean_run_passes
  t_concurrent_lints_do_not_collide
  t_the_shared_config_is_schema_valid
  t_phase_gate_all_never_records_pass_for_a_failing_verb
  t_phase_gate_all_is_green_when_every_tool_passes
  t_the_substrate_lane_states_its_budget
  t_an_unbounded_budget_is_refused
  t_a_hang_is_reported_in_seconds
  t_cover_floor_carries_the_same_budget
  t_the_default_budget_is_ten_minutes_and_is_stated
  t_the_lifecycle_lane_states_its_budget
  t_the_load_lane_states_its_budget
  t_only_the_integration_lane_is_verbose
  t_a_fractional_budget_is_refused
  t_one_nanosecond_is_accepted_and_bounds_the_lane
)

# ── the stimulus tables ─────────────────────────────────────────────────────

# stimulus_for <test> — what phase 1 drives the test with.
stimulus_for() {
  case "$1" in
    t_a_collision_is_not_reported_as_findings)      printf 'exit:3\n' ;;
    t_real_findings_are_still_reported_as_findings) printf 'exit:1\n' ;;
    t_a_clean_run_passes)                           printf 'exit:0\n' ;;
    t_concurrent_lints_do_not_collide)              printf 'real\n'   ;;
    t_the_shared_config_is_schema_valid)            printf 'real\n'   ;;
    t_phase_gate_all_never_records_pass_for_a_failing_verb) printf 'gobuild:1\n' ;;
    t_phase_gate_all_is_green_when_every_tool_passes)       printf 'gobuild:0\n' ;;
    t_the_substrate_lane_states_its_budget)                 printf 'substrate:7m\n' ;;
    t_an_unbounded_budget_is_refused)                       printf 'refuse:unbounded\n' ;;
    # The budget is supplied by the test itself (HANG_BUDGET), because the fixture's sleep and
    # the budget are one calibrated pair — splitting them across the table would let one drift.
    t_a_hang_is_reported_in_seconds)                        printf 'real\n' ;;
    t_cover_floor_carries_the_same_budget)                  printf 'substrate:7m\n' ;;
    t_the_default_budget_is_ten_minutes_and_is_stated)      printf 'substrate:absent\n' ;;
    t_the_lifecycle_lane_states_its_budget)                 printf 'substrate:7m\n' ;;
    t_the_load_lane_states_its_budget)                      printf 'substrate:7m\n' ;;
    # The default budget, because -v must not depend on the knob's value at all.
    t_only_the_integration_lane_is_verbose)                 printf 'substrate:absent\n' ;;
    t_a_fractional_budget_is_refused)                       printf 'fraction:truncating\n' ;;
    # 1ns is supplied by the test: it is the exact boundary the guard's proof rests on, not a
    # value the table may drift away from it.
    t_one_nanosecond_is_accepted_and_bounds_the_lane)       printf 'real\n' ;;
    *) die "no phase-1 stimulus is declared for $1" ;;
  esac
}

# counter_for <test> — what must BREAK the test, ONE SPEC PER LINE. A test may declare several,
# and then EVERY one must break it: a defect with two ways of being half-fixed needs a counter
# for each half. A `none:` entry states its reason out loud, so a test can never lose its
# counter quietly.
counter_for() {
  case "$1" in
    t_a_collision_is_not_reported_as_findings)      printf 'exit:1\n' ;;
    t_real_findings_are_still_reported_as_findings) printf 'exit:3\n' ;;
    t_a_clean_run_passes)                           printf 'exit:3\n' ;;
    t_the_shared_config_is_schema_valid)            printf 'config:typo\n' ;;
    t_concurrent_lints_do_not_collide)              printf 'none:the counter is a config without the key, and a lock race is probabilistic; it is measured in phase 1, never asserted here\n' ;;
    # A green `go build` makes the build dimension legitimately PASS, which is exactly the row
    # the test forbids — so a test that stopped reading the summary cannot survive this.
    t_phase_gate_all_never_records_pass_for_a_failing_verb) printf 'gobuild:0\n' ;;
    # NOT `gobuild:1`: that is the defect's own stimulus, and while the defect stands the gate
    # still reports GREEN under it, so the counter would not break this test. An absent hnslint
    # exits 127 through require_cmd's explicit `exit`, which survives the errexit suppression
    # that defeats every other verb — and it lands AFTER `go build`, so the argv floor still holds.
    t_phase_gate_all_is_green_when_every_tool_passes)       printf 'absent:hnslint\n' ;;
    # TWO counters, because there are two ways to half-fix this: not passing the budget at all,
    # and passing a hard-coded one while the log line still reads the knob. A test that read
    # only the log line survives the second; a test that read only "some -timeout is present"
    # survives it too. Both must go red.
    t_the_substrate_lane_states_its_budget)
      printf 'mutant:integration-untimed\n'
      printf 'mutant:integration-hardcoded\n' ;;
    # TWO counters again. `refuse:bounded` proves the test reads the exit code and the message
    # rather than always failing — a bounded 7m must be ACCEPTED. `mutant:guard-toothless`
    # proves it reads the GUARD: the lane then runs -timeout=0 and exits 0.
    t_an_unbounded_budget_is_refused)
      printf 'refuse:bounded\n'
      printf 'mutant:guard-toothless\n' ;;
    # Exactly the brief's counter: let the budget reach log_info and not `go test`. The fixture
    # then sleeps its full 10s and the lane exits 0 — which is what a test written against the
    # message instead of the behaviour would have called a pass.
    t_a_hang_is_reported_in_seconds)                  printf 'mutant:integration-untimed\n' ;;
    # Fix only cmd_integration and leave the coverage lane silent.
    t_cover_floor_carries_the_same_budget)            printf 'mutant:cover-untimed\n' ;;
    # Move the default off Go's own 10m: the one change that would alter behaviour for the 14
    # libraries which never set the knob.
    t_the_default_budget_is_ten_minutes_and_is_stated) printf 'mutant:default-25m\n' ;;
    # The 2 deletions that a single `EDEN_CONSERVATION_RECORD=1` used to make invisible.
    t_the_lifecycle_lane_states_its_budget)            printf 'mutant:lifecycle-untimed\n' ;;
    t_the_load_lane_states_its_budget)                 printf 'mutant:load-untimed\n' ;;
    # ONE COUNTER PER HALF of "on integration, and only there".
    t_only_the_integration_lane_is_verbose)
      printf 'mutant:integration-not-verbose\n'
      printf 'mutant:lifecycle-verbose\n' ;;
    # `fraction:bounded` proves the test reads the exit code and the message rather than always
    # failing — a whole 90m must be ACCEPTED. `mutant:fraction-arm-disarmed` proves it reads the
    # FRACTIONAL arm specifically: `guard-toothless` would disarm both arms at once and could not
    # tell which clause was doing the work.
    t_a_fractional_budget_is_refused)
      printf 'fraction:bounded\n'
      printf 'mutant:fraction-arm-disarmed\n' ;;
    # Not passing the budget to `go test` leaves 1ns unenforced: the fixture then sleeps its full
    # 10s and the lane exits 0, which is what "the guard admits 1ns" would have meant on its own.
    t_one_nanosecond_is_accepted_and_bounds_the_lane)  printf 'mutant:integration-untimed\n' ;;
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
  LIB="$LIB_SOURCE"
  SUBSTRATE_TIMEOUT_PRESENT=0
  SUBSTRATE_TIMEOUT=""
  REFUSE_VALUES=("0" "0s" "" "0h0m0s" "-5m" "notaduration")
  FRACTION_VALUES=("0.4ns" "0.0000000001s" "1.5h" "0.5s")
  case "$1" in
    exit:*)      STIMULUS="${1#exit:}" ;;
    # A `die` inside a command substitution exits only the SUBSHELL, and apply is called from a
    # condition context where the driver reads a non-zero return as "this test declared no
    # counter-stimulus". Re-raise it here, or a stimulus that could not be built is reported as
    # a clean skip — the exact shape of check this suite exists to delete.
    config:typo) CONFIG="$(typo_config)" || die "the 'config:typo' stimulus could not be built (see the message above)" ;;
    gobuild:*)   GO_BUILD_RC="${1#gobuild:}" ;;
    absent:*)    ABSENT_TOOL="${1#absent:}" ;;
    substrate:absent) SUBSTRATE_TIMEOUT_PRESENT=0 ;;
    substrate:*) SUBSTRATE_TIMEOUT_PRESENT=1; SUBSTRATE_TIMEOUT="${1#substrate:}" ;;
    refuse:unbounded) REFUSE_VALUES=("0" "0s" "" "0h0m0s" "-5m" "notaduration") ;;
    refuse:bounded)   REFUSE_VALUES=("7m") ;;
    # `1.5h` is the legitimate value this arm costs, and it is IN the refused set on purpose: the
    # message tells the reader to write `90m`, and `90m` is what the counter proves is accepted.
    fraction:truncating) FRACTION_VALUES=("0.4ns" "0.0000000001s" "1.5h" "0.5s") ;;
    fraction:bounded)    FRACTION_VALUES=("90m") ;;
    mutant:*)
      LIB="$(mutant_lib "${1#mutant:}")" ||
        die "the '${1#mutant:}' counter-stimulus could not be built (see the message above)"
      [[ -f "$LIB" ]] || die "the '${1#mutant:}' counter-stimulus produced no lib.sh" ;;
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
stimuli=0
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

# A test may declare MORE THAN ONE counter-stimulus, one per line, and every one of them must
# break it. `broke` records whether this test was proven able to fail AT ALL, so the summary
# still counts TESTS proven, not counter-stimuli fired — those are counted separately.
info "phase 2 — discrimination: each test under every counter-stimulus it declares must fail"
for t in "${TESTS[@]}"; do
  broke=0
  while IFS= read -r spec || [[ -n "$spec" ]]; do
    [[ -n "$spec" ]] || continue
    if ! apply "$spec"; then
      info "$t — no counter-stimulus: ${spec#none:}"
      unproven=$((unproven + 1))
      continue
    fi
    stimuli=$((stimuli + 1))
    if ( set -Eeuo pipefail; "$t" ); then
      bad "$t still passed under $spec; it does not read what it claims to read"
      failures=$((failures + 1))
    else
      ok "$t fails under $spec"
      broke=1
    fi
  done < <(counter_for "$t")
  proven=$((proven + broke))
done

if [[ "$failures" -ne 0 ]]; then
  die "$failures failure(s) across both phases"
fi
# The summary is COUNTED, never asserted. An earlier version ended with "each is
# proven able to fail", which was false for any test carrying a `none:` counter —
# a summary that overstates its own rigour is the defect this suite exists to catch.
info "${#TESTS[@]} test(s) hold; $proven of ${#TESTS[@]} proven able to fail across $stimuli counter-stimuli; $unproven stated no counter"
