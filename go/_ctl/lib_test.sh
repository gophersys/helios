#!/usr/bin/env bash
#
# libs/go/_ctl/lib_test.sh — prove that lib.sh's gate can FAIL, and names the failure it had.
#
# Four defects, one suite, because all four live in this file:
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
#   4. A library REQUIRES a sibling library at `v0.0.0` and declares NO `replace` for it
#      (tests 18-20). `v0.0.0` is unpublished, so the module cannot resolve at all: the
#      library builds ONLY inside eden's `go.work`, and every gate verb runs standalone
#      (`GOWORK=unset`) on purpose, because a library that compiles only inside its parent
#      workspace is a package of the parent, not a library. A 16-library sweep of
#      `phase-gate implementation` found `agentruntime` and `edenhttp` failing ALL 5
#      dimensions on `missing go.sum entry` for exactly this reason, and nothing in the
#      repository said so — the nightly gates only the projects a change touched, and
#      neither library had been touched.
#
#      The check is PER MODULE, and the two obvious formulations are both wrong:
#        - counting requires against replaces flags 13 of 16, because a `=> ../x` line also
#          matches the requires pattern and double-counts;
#        - subtracting the replaces still flags 5, because `envelope`, `forge` and
#          `objectstorage` legitimately carry MORE replaces than requires — a replace may
#          cover a requirement declared somewhere else in the graph.
#      Only "for every sibling this go.mod REQUIRES, a replace exists for THAT module"
#      selects the 2 the sweep found red. A count is wrong in both directions: it false-
#      alarms on 11 libraries AND it stays green when a library replaces the WRONG module,
#      which is the state `tree:repaired-wrong-module` builds and test 20 pins.
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
# note is info on STDERR. The failing-path summary uses it so it lands next to the failures it
# summarises: stdout is block-buffered when the run is redirected to a file and stderr is not, so
# an `info` there prints AFTER the `die` it was written before.
note() { printf '\033[0;36m[test]\033[0m %s\n' "$*" >&2; }
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

# ── the sibling-replace scan (tests 18-20) ──────────────────────────────────
#
# Defect 4 is not in lib.sh at all — it is in the go.mod manifests, so the subject under test
# is the TREE of `go/<lib>/go.mod` files. MODULE_TREE_SOURCE is the tree as it stands;
# MODULE_TREE is the tree the NEXT run reads. They are the same directory for the behaviour
# run, and a `tree:` counter-stimulus repoints MODULE_TREE at a throwaway copy — exactly the
# LIB_SOURCE/LIB split above, for the same reason.
SIBLING_PREFIX="github.com/gophersys/libs/go/"
MODULE_TREE_SOURCE="$REPO_ROOT/go"
MODULE_TREE="$MODULE_TREE_SOURCE"
[[ -d "$MODULE_TREE_SOURCE" ]] || die "the module tree under test is missing: $MODULE_TREE_SOURCE"

# The anchor the two breaking tree mutants are built on. It is a REQUIRED sibling of a REAL
# library, so the mutants die loudly if that requirement ever goes away rather than mutating
# nothing and reporting a pass. The decoy is a real sibling that WRONG_REPLACE_LIB does NOT
# require, which is what makes `repaired-wrong-module` keep the replace COUNT identical while
# pointing it at the wrong module.
WRONG_REPLACE_LIB="agentruntime"
WRONG_REPLACE_MODULE="observability"
WRONG_REPLACE_DECOY="gitrepository"

# The anchor for `repaired-with-a-moved-version`. It must be a NON-sibling requirement, so moving
# it cannot perturb the sibling scan and the only assertion left to fire is the replace-only one.
MOVED_VERSION_LIB="agentruntime"
MOVED_VERSION_MODULE="go.uber.org/goleak"
MOVED_VERSION_TO="v9.9.9"

# The anchor for `transitive-replace-dropped`: a replace for a module the library reaches THROUGH
# a dependency (agentruntime -> secrets -> envelope) and does not require directly. Dropping it
# leaves every direct-requirement check green and breaks the module graph.
TRANSITIVE_LIB="agentruntime"
TRANSITIVE_MODULE="envelope"

# ── the full-module-graph exemption table (test 21) ─────────────────────────
#
# `go list -m all` is red for 4 of the 16 libraries on this tree, and this table names every one
# of them, with what does not resolve and the reason. It is a DEBT REGISTER, not a mute button,
# and it is enforced in BOTH directions by t_every_library_resolves_its_full_module_graph:
#   - a library that is red and NOT listed here fails the gate;
#   - a library that is listed here and now RESOLVES also fails the gate, naming the stale entry.
# So the list can only ever shrink, and it cannot outlive the defect it records.
#
# THE RULE THE TABLE IS GOVERNED BY: an exemption may hold only a defect of a DIFFERENT class
# from the one the change fixes. A same-class defect gets fixed, never tabled — six tabled
# same-class entries would have made this change's central claim false the moment it merged.
# The table started at 8. Four were the same class (an unreplaced `envelope`, reached through
# `secrets`, one line each) and were FIXED in b3be25e: agentsession, forge, gitrepository and
# workspaceprovider now resolve, and this test is what said so — it refused to stay quiet and
# failed on its own stale entries until they were deleted.
#
# AND THE REASON IS AN ASSERTION, NOT A COMMENT. This is the defect the table itself had, and it
# is the most interesting thing this suite has caught. Two entries recorded a DIFFERENT-class
# reason — a `kr/pretty` go.sum gap and a `pgx` bump — while the error those libraries ACTUALLY
# produced was the SAME-class `envelope@v0.0.0: invalid version`. The prose described the error
# that would appear AFTER the fix. So when an implementer added the missing `envelope` replace to
# both, NOTHING changed: they stayed red, stayed legitimately exempt, and the census line was
# byte-identical either side of the change. A same-class defect wearing a different-class label
# was invisible to every check here.
#
# Each entry now carries an ANCHOR: a substring the library's observed error MUST contain. Three
# arms police it, and two of them read the OBSERVATION rather than anything written by hand:
#   reason-mismatch  the observed error does not contain the anchor -> the entry is describing a
#                    defect this library does not have.
#   same-class       the observed error names a SIBLING at v0.0.0 -> the closure defect this
#                    change exists to fix. NOT EXEMPTIBLE, whatever the anchor says. This is the
#                    mechanical form of "an exemption may hold only a defect of a DIFFERENT
#                    class", and it is what would have caught the two above with no reliance on
#                    the prose being honest.
#   phantom          the entry names a library the scan never walked (renamed, deleted, typo'd).
#
# WHY THE ANCHOR IS A MODULE PATH WHERE ONE EXISTS. Go rewords its prose between releases —
# "missing go.sum entry" gained "for go.mod file" — but the module path inside an error is DATA:
# it is the identity of the thing that failed, and it is the exact discriminator that separates
# `envelope` from `kr/pretty`. Where the error names no module at all (orchestrator prints only
# `updates to go.mod needed`) the anchor is Go's own error string, which is the most stable
# identifier available. Both are measured from a real run, never guessed.
#
# WHAT THIS DOES NOT FIX, stated plainly: the anchor is still typed by a human. What changed is
# that it is now MECHANICALLY REFUTED on every run — a wrong anchor fails immediately, and the
# same-class arm needs no anchor to be honest at all. The one residual hole is an anchor so
# generic it matches anything, which the minimum length below closes for the degenerate cases.
#
# FORMAT: <library> | <anchor> | <reason>
MODULE_GRAPH_EXEMPT_SOURCE=(
  "objectstorage | github.com/kr/pretty      | go.sum drift, task #37 — needs a go.sum write, which this change's guards forbid; also RED for go build"
  "orchestrator  | updates to go.mod needed  | manifest drift, task #37 — the residual is the pgx/v5 5.7.6 -> 5.10.0 bump; also RED for go build"
  "dependencies  | github.com/stretchr/testify | go.sum drift, task #37 — go build, vet and test are green, so only this test sees it"
  "errors        | github.com/stretchr/testify | go.sum drift, task #37 — go build, vet and test are green, so only this test sees it"
)
MODULE_GRAPH_EXEMPT=("${MODULE_GRAPH_EXEMPT_SOURCE[@]}")

# An anchor shorter than this cannot identify anything: `go:` matches every error Go prints, and
# the empty string matches all of them. The shortest legitimate anchor in the table is 20
# characters, and Go's shortest useful error phrase is well over 8.
MODULE_GRAPH_ANCHOR_MINIMUM=8

# A sibling that does not resolve prints its own path at the unpublished version. `v0.0.0` is
# unpublished BY CONSTRUCTION here, so this pattern cannot match anything but the closure defect.
SIBLING_FAILURE_PATTERN="github\.com/gophersys/libs/go/[a-z]+@v0\.0\.0"

# ── telling a broken manifest from a broken network (test 21) ────────────────
#
# `go list -m all` returns the same non-zero for "a sibling is unreplaced" and "the proxy is
# unreachable", and the second is not a finding about this code. With no network every library
# goes red, twelve are not on the table, and the unexpected arm would hand a reader twelve
# confident instructions to add a `replace` for a THIRD-PARTY module — for which no replace is
# ever correct. This check runs on every push, so a CI network blip would produce twelve wrong
# remediations.
#
# The discriminator is the error itself, and the MANIFEST markers are tested FIRST. That ordering
# is load-bearing: an unreplaced private sibling fails THROUGH the network (`git ls-remote ...
# could not read Username`), so it carries transport text too — but it also carries `invalid
# version`, which no reachability failure produces. A missing go.sum entry is decided locally and
# never reaches the network at all, so it survives an outage unchanged.
MODULE_GRAPH_MANIFEST_MARKERS=(
  "missing go.sum entry"
  "invalid version"
  "updates to go.mod needed"
  "no required module provides"
  "checksum mismatch"
)
MODULE_GRAPH_TRANSPORT_MARKERS=(
  "dial tcp"
  "connection refused"
  "i/o timeout"
  "no such host"
  "TLS handshake"
  "connection reset"
  "Client.Timeout"
  "network is unreachable"
  "temporary failure in name resolution"
  "module lookup disabled"
  "server misbehaving"
)

# The anchor for the `exempt:stale` stimulus, and why it names a GREEN library rather than
# repairing a red one.
#
# The stimulus this replaces added the one missing replace to an exempt library. That worked
# exactly once: agentsession was fixed for real, the mutant could no longer change anything, and
# it took the whole suite down with it before the summary printed. Re-pointing it at another
# entry would buy the same trap again, and worse — NONE of the four that remain is repairable by
# adding a replace. Three are missing a go.sum HASH, which no go.mod edit supplies, and
# orchestrator needs a version bump as well. A stimulus whose premise is "this library can be
# repaired with one line" has no valid subject left in this tree.
#
# The arm under test is a predicate over the TABLE — "listed AND resolves" — so the stimulus
# belongs on the table, exactly as REFUSE_VALUES and FRACTION_VALUES are stimuli on a value set.
# It lists a library that ALREADY resolves. `configuration` is the anchor because it requires no
# sibling and replaces none (requires=0 replaces=0): no sibling edit anywhere in this tree can
# perturb its graph, so it is the most stable green there is. If it ever does go red, this
# stimulus stops breaking the test and the driver says so out loud — "still passed under
# exempt:stale" — rather than reporting a pass.
STALE_EXEMPTION_LIB="configuration"

# The anchors for the three remaining table stimuli. `WRONG_REASON_LIB` must be a library that is
# genuinely on the table and genuinely red, so the only thing the stimulus changes is whether the
# recorded anchor matches the observed error; `WRONG_REASON_ANCHOR` is a REAL module path from a
# REAL error in this same tree — objectstorage's — so the stimulus proves the anchor is matched
# against THIS library's error rather than against any error the tree happens to produce.
WRONG_REASON_LIB="errors"
WRONG_REASON_ANCHOR="github.com/kr/pretty"
PHANTOM_EXEMPTION_LIB="phantomlibrary"

# One go.mod parser, three outputs, so the scan and the repair can never disagree about what a
# manifest says. `-v mode=`:
#   report   SCANNED <lib> requires=<n> replaces=<n>      (the census, for the vacuity floor)
#            UNREPLACED <lib> -> <slug> [<slug>...]       (the report, only when something is)
#   missing  <slug> <version>                             (what a repair would have to add)
#   requires <module-path> <version>                      (EVERY require, in file order)
#
# go.mod has both a block form (`require (` … `)`) and a single-line form, and a replace's
# left-hand side may or may not carry a version — all four shapes appear in this tree, so the
# parser tracks the block instead of pattern-matching a line in isolation. The comparison is
# `index(path, prefix) == 1`, never a regex: a module path is full of dots, and a dot in a
# dynamic regex matches anything.
# shellcheck disable=SC2016 # the awk program is literal; $0 and $1 are awk's fields, not bash's
SIBLING_SCAN_AWK='
{
  line = $0
  sub(/\/\/.*/, "", line)
  gsub(/^[ \t]+/, "", line); gsub(/[ \t]+$/, "", line)
  if (line == "") next
  kind = ""
  if (block == "") {
    if (line ~ /^module[ \t]/)       { split(line, f, /[ \t]+/); self = f[2]; next }
    if (line ~ /^require[ \t]*\(/)   { block = "require"; next }
    if (line ~ /^replace[ \t]*\(/)   { block = "replace"; next }
    if (line ~ /^require[ \t]/)      { kind = "require"; sub(/^require[ \t]+/, "", line) }
    else if (line ~ /^replace[ \t]/) { kind = "replace"; sub(/^replace[ \t]+/, "", line) }
    else next
  } else {
    if (line ~ /^\)/) { block = ""; next }
    kind = block
  }
  if (kind == "require") {
    split(line, f, /[ \t]+/)
    every[++ne] = f[1] " " f[2]
    if (index(f[1], prefix) == 1 && f[1] != self) {
      slug = substr(f[1], length(prefix) + 1)
      required[slug] = 1
      version[slug] = f[2]
    }
    next
  }
  arrow = index(line, "=>")
  if (arrow == 0) next
  split(substr(line, 1, arrow - 1), f, /[ \t]+/)
  if (index(f[1], prefix) == 1 && f[1] != self) replaced[substr(f[1], length(prefix) + 1)] = 1
}
END {
  if (mode == "requires") {
    for (i = 1; i <= ne; i++) print every[i]
    exit 0
  }
  nr = 0; np = 0; nm = 0
  for (m in required) { nr++; if (!(m in replaced)) missing[++nm] = m }
  for (m in replaced) np++
  for (i = 1; i < nm; i++)
    for (j = i + 1; j <= nm; j++)
      if (missing[j] < missing[i]) { swap = missing[i]; missing[i] = missing[j]; missing[j] = swap }
  if (mode == "missing") {
    for (i = 1; i <= nm; i++) print missing[i] " " version[missing[i]]
    exit 0
  }
  printf "SCANNED %s requires=%d replaces=%d\n", lib, nr, np
  if (nm == 0) exit 0
  out = missing[1]
  for (i = 2; i <= nm; i++) out = out " " missing[i]
  printf "UNREPLACED %-12s -> %s\n", lib, out
}
'

# read_manifest <mode> <go.mod> — the parser above over one manifest.
read_manifest() {
  local mode="$1" manifest="$2" lib
  [[ -f "$manifest" ]] || die "read_manifest was handed no manifest: $manifest"
  lib="$(basename "$(dirname "$manifest")")"
  awk -v mode="$mode" -v lib="$lib" -v prefix="$SIBLING_PREFIX" "$SIBLING_SCAN_AWK" "$manifest"
}

# scan_sibling_replaces <tree> — the census and the report over every go/<lib>/go.mod in <tree>.
scan_sibling_replaces() {
  local tree="$1" manifest
  [[ -n "$tree" ]] || die "scan_sibling_replaces needs a tree"
  for manifest in "$tree"/*/go.mod; do
    [[ -f "$manifest" ]] || continue
    read_manifest report "$manifest"
  done
}

# copy_module_tree <tree> — prints the path of a throwaway copy of <tree>'s go.mod files, so a
# counter-stimulus never writes inside the repository.
#
# go.sum comes with go.mod. `go list -m all` (test 21) loads the FULL module graph, which means
# verifying the go.mod of every module in it, which means go.sum. A copy without it reports
# "missing go.sum entry" for every library and the tree measures the copier, not the manifests.
copy_module_tree() {
  local src="$1" dst lib manifest copied=0
  dst="$(mktemp -d "$WORK/tree.XXXXXX")"
  for manifest in "$src"/*/go.mod; do
    [[ -f "$manifest" ]] || continue
    lib="$(basename "$(dirname "$manifest")")"
    mkdir -p "$dst/$lib"
    cp "$manifest" "$dst/$lib/go.mod"
    if [[ -f "${manifest%.mod}.sum" ]]; then
      cp "${manifest%.mod}.sum" "$dst/$lib/go.sum"
    fi
    copied=$((copied + 1))
  done
  [[ "$copied" -gt 0 ]] ||
    die "no go.mod was copied out of $src, so every tree stimulus would be an empty directory"
  printf '%s' "$dst"
}

# repair_tree <tree> — appends, to each manifest, a replace for every sibling it requires and
# does not replace. This is the SCAN'S INVERSE, and it is here for exactly one purpose: to prove
# the property tests 18-19 assert is REACHABLE. A test that can only ever go red might be
# asserting something no tree can satisfy, and this is what refutes that. It proves nothing
# about the fix itself — the fix is the go.mod edit, and test 18 over the real tree is what
# reads it. Adding nothing is a legitimate outcome: over an already-correct tree the repair is
# a no-op, which is precisely the state test 18 goes green in.
repair_tree() {
  local tree="$1" manifest missing slug version
  for manifest in "$tree"/*/go.mod; do
    [[ -f "$manifest" ]] || continue
    missing="$(read_manifest missing "$manifest")"
    [[ -n "$missing" ]] || continue
    printf '\nreplace (\n' >> "$manifest"
    while IFS=' ' read -r slug version; do
      [[ -n "$slug" ]] || continue
      printf '\t%s%s %s => ../%s\n' "$SIBLING_PREFIX" "$slug" "$version" "$slug" >> "$manifest"
    done <<< "$missing"
    printf ')\n' >> "$manifest"
  done
}

# ── the module-tree stimuli (tests 18-21) ───────────────────────────────────
#
# Every mutant DIES if it changed nothing, the same discipline as mutant_lib: a counter-stimulus
# that mutated nothing proves nothing, and the message names the anchor it could not find.
#
# CENSUS_BEFORE_MUTATION is written into every mutated tree, holding the SCANNED lines as they
# stood BEFORE the breaking edit. Test 20 reads it to assert the edit was COUNT-NEUTRAL — the
# only formulation that proves a counting check is blind to the mutant. The earlier form
# asserted `requires == replaces`, which was never a property of this tree: the census already
# showed envelope, forge and objectstorage at 2 requires / 4 replaces, because a replace may
# legitimately cover a module reached THROUGH a dependency rather than required directly.
# Completing agentruntime's closure made it the fourth, and the guard went red for a tree that
# was more correct than before. Equality was an accident of the library the anchor picked;
# neutrality is the thing actually being claimed.
CENSUS_BEFORE_MUTATION=".census-before-mutation"

mutant_tree() {
  local spec="$1" tree manifest target rc=0
  tree="$(copy_module_tree "$MODULE_TREE_SOURCE")"
  case "$spec" in
    # An EMPTY tree. The scan reads no manifest, finds nothing unreplaced, and a test that only
    # looked for UNREPLACED lines would call that clean — the "0 tests ran, exit 0" class. This
    # is the counter that proves the vacuity floor is load-bearing rather than decorative.
    empty)
      rm -rf "${tree:?}"/*
      printf '%s' "$tree"
      return 0
      ;;
    repaired) repair_tree "$tree" ;;
    # THE COUNTER FOR "every required sibling is replaced": repair the tree, then take ONE
    # replace back out. The library then requires a sibling at v0.0.0 with nothing pointing at
    # it — the exact state agentruntime and edenhttp are in today.
    repaired-minus-one-replace)
      repair_tree "$tree"
      manifest="$tree/$WRONG_REPLACE_LIB/go.mod"
      target="$SIBLING_PREFIX$WRONG_REPLACE_MODULE"
      [[ -f "$manifest" ]] ||
        die "the '$spec' tree mutant has no $WRONG_REPLACE_LIB/go.mod to mutate in $tree"
      # This mutant is deliberately NOT count-neutral — it deletes a replace — and the census is
      # recorded for exactly that reason: it is what proves test 20's neutrality arm can fire.
      scan_sibling_replaces "$tree" > "$tree/$CENSUS_BEFORE_MUTATION"
      awk -v target="$target" '
        {
          arrow = index($0, "=>")
          at    = index($0, target)
          if (arrow == 0 || at == 0 || at > arrow) { print; next }
          changed++
        }
        END { if (!changed) exit 3 }
      ' "$manifest" > "$manifest.mutant" || rc=$?
      [[ "$rc" -eq 0 ]] ||
        die "the '$spec' tree mutant changed nothing: $WRONG_REPLACE_LIB declares no replace for $target, so the counter-stimulus cannot be applied"
      mv "$manifest.mutant" "$manifest"
      ;;
    # THE COUNTER THAT SEPARATES A PER-MODULE CHECK FROM A COUNTING ONE: repair the tree, then
    # aim one replace at a sibling the library does not require. The number of replaces is
    # UNCHANGED, so every count-based formulation still calls this clean, and the module the
    # replace used to cover is now unreplaced.
    repaired-wrong-module)
      repair_tree "$tree"
      manifest="$tree/$WRONG_REPLACE_LIB/go.mod"
      target="$SIBLING_PREFIX$WRONG_REPLACE_MODULE"
      [[ -f "$manifest" ]] ||
        die "the '$spec' tree mutant has no $WRONG_REPLACE_LIB/go.mod to mutate in $tree"
      scan_sibling_replaces "$tree" > "$tree/$CENSUS_BEFORE_MUTATION"
      awk -v target="$target" -v decoy="$SIBLING_PREFIX$WRONG_REPLACE_DECOY" \
          -v from="../$WRONG_REPLACE_MODULE" -v to="../$WRONG_REPLACE_DECOY" '
        function replace_once(s, old, new,   p) {
          p = index(s, old)
          if (p == 0) return s
          return substr(s, 1, p - 1) new substr(s, p + length(old))
        }
        {
          arrow = index($0, "=>")
          at    = index($0, target)
          if (arrow == 0 || at == 0 || at > arrow) { print; next }
          line = replace_once($0, target, decoy)
          line = replace_once(line, from, to)
          print line
          changed++
        }
        END { if (!changed) exit 3 }
      ' "$manifest" > "$manifest.mutant" || rc=$?
      [[ "$rc" -eq 0 ]] ||
        die "the '$spec' tree mutant changed nothing: $WRONG_REPLACE_LIB declares no replace for $target, so the counter-stimulus cannot be applied"
      mv "$manifest.mutant" "$manifest"
      ;;
    # THE COUNTER THAT REACHES assert_only_replace_directives_differ. Every other tree stimulus
    # trips an earlier assertion, so that one had never executed a failing path: a verifier
    # neutered it to `after="$before"` and the whole suite stayed green while still reporting
    # itself "proven able to fail". This mutant moves a VERSION and touches no sibling, so the
    # sibling scan is still clean and the replace-only assertion is the only thing left to fire.
    repaired-with-a-moved-version)
      repair_tree "$tree"
      manifest="$tree/$MOVED_VERSION_LIB/go.mod"
      [[ -f "$manifest" ]] ||
        die "the '$spec' tree mutant has no $MOVED_VERSION_LIB/go.mod to mutate in $tree"
      awk -v target="$MOVED_VERSION_MODULE " -v bumped="$MOVED_VERSION_MODULE $MOVED_VERSION_TO" '
        {
          at = index($0, target)
          if (at == 0 || index($0, "=>") > 0) { print; next }
          print substr($0, 1, at - 1) bumped
          changed++
        }
        END { if (!changed) exit 3 }
      ' "$manifest" > "$manifest.mutant" || rc=$?
      [[ "$rc" -eq 0 ]] ||
        die "the '$spec' tree mutant changed nothing: $MOVED_VERSION_LIB requires no $MOVED_VERSION_MODULE, so there is no version for the counter-stimulus to move"
      mv "$manifest.mutant" "$manifest"
      ;;
    # THE COUNTER FOR THE FULL-GRAPH ASSERTION, and the demonstration of the gap it closes. It
    # deletes ONE replace for a module the library does not require DIRECTLY — the exact edit
    # 62c87f3 made in reverse. The direct-requirement scan (tests 18-20) stays GREEN over this
    # tree, because nothing it reads changed; `go list -m all` goes red. That difference is why
    # test 21 exists: `go build` and the sibling scan both read a graph that has been PRUNED,
    # and both stayed green through the whole of this defect.
    transitive-replace-dropped)
      manifest="$tree/$TRANSITIVE_LIB/go.mod"
      target="$SIBLING_PREFIX$TRANSITIVE_MODULE"
      [[ -f "$manifest" ]] ||
        die "the '$spec' tree mutant has no $TRANSITIVE_LIB/go.mod to mutate in $tree"
      awk -v target="$target" '
        {
          arrow = index($0, "=>")
          at    = index($0, target)
          if (arrow == 0 || at == 0 || at > arrow) { print; next }
          changed++
        }
        END { if (!changed) exit 3 }
      ' "$manifest" > "$manifest.mutant" || rc=$?
      [[ "$rc" -eq 0 ]] ||
        die "the '$spec' tree mutant changed nothing: $TRANSITIVE_LIB declares no replace for $target, so the closure it completes cannot be reopened"
      mv "$manifest.mutant" "$manifest"
      ;;
    *) die "unknown module-tree mutant: $spec" ;;
  esac
  # `repaired` over an already-correct tree legitimately changes nothing, so only the BREAKING
  # mutants are held to "it must differ". A breaking mutant identical to its source would be
  # read as a discrimination pass having broken nothing.
  local touched
  case "$spec" in
    repaired-minus-one-replace | repaired-wrong-module) touched="$WRONG_REPLACE_LIB" ;;
    repaired-with-a-moved-version)                      touched="$MOVED_VERSION_LIB" ;;
    transitive-replace-dropped)                         touched="$TRANSITIVE_LIB" ;;
    *)                                                  touched="" ;;
  esac
  if [[ -n "$touched" ]]; then
    if cmp -s "$MODULE_TREE_SOURCE/$touched/go.mod" "$tree/$touched/go.mod"; then
      die "the '$spec' tree mutant reported a change but produced an identical $touched/go.mod"
    fi
  fi
  printf '%s' "$tree"
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

# assert_the_scan_is_not_vacuous <report> — the scan walks a glob and reports what it found, so
# BOTH of its empty states read as "clean": a tree with no go.mod at all, and a tree whose
# manifests parsed but yielded no sibling requirement (a parser that silently stopped matching
# go.mod's block form would look exactly like that). Neither is a pass. This floor runs before
# every UNREPLACED assertion below, and `tree:empty` is the counter-stimulus that proves it bites.
assert_the_scan_is_not_vacuous() {
  local report="$1" scanned requirements
  scanned="$(grep -c '^SCANNED ' <<< "$report" || true)"
  [[ "$scanned" -gt 0 ]] ||
    fail "the scan read no go.mod under $MODULE_TREE, so an empty report proves nothing: [$report]"
  requirements="$(awk '$1 == "SCANNED" { n = $0; sub(/.*requires=/, "", n); sub(/ .*/, "", n); total += n }
                       END { print total + 0 }' <<< "$report")"
  [[ "$requirements" -gt 0 ]] ||
    fail "the scan read $scanned go.mod file(s) under $MODULE_TREE and found NO sibling requirement in any of them; the parser, not the tree, is what this run measured: [$report]"
}

# assert_every_required_sibling_is_replaced — the property, over whatever MODULE_TREE points at.
# The failure NAMES the library and every module it left unreplaced, because "a replace is
# missing somewhere" sends a reader at 3am into 16 manifests to find out which.
#
# AND IT STATES ITS OWN LIMIT. This scan reads DIRECT requirements only, and Go IGNORES a replace
# declared in a dependency's go.mod: only the MAIN module's replaces apply. So a library must
# replace every sibling in its transitive closure, not just the ones it names — and this scan
# cannot see the difference. Commit 5d78346 followed the earlier version of this message to the
# letter, turned it green, and left the gate RED, because agentruntime reaches `envelope` through
# `secrets` and replaced only what it required directly. A reader who stops here gets a green
# test over a library that does not build. The message now sends them to test 21's command.
assert_every_required_sibling_is_replaced() {
  local report unreplaced
  report="$(scan_sibling_replaces "$MODULE_TREE")"
  assert_the_scan_is_not_vacuous "$report"
  unreplaced="$(grep '^UNREPLACED ' <<< "$report" || true)"
  if [[ -n "$unreplaced" ]]; then
    fail "$(printf '%s\n' \
      "a library requires a sibling at v0.0.0 and declares no replace for it. v0.0.0 is" \
      "unpublished, so the module resolves only inside eden's go.work and every gate verb —" \
      "which runs standalone, GOWORK=unset — fails on 'missing go.sum entry':" \
      "" \
      "$unreplaced" \
      "" \
      "each line names the library and every module it must add 'replace <module> v0.0.0 =>" \
      "../<slug>' for. Move no version and run no go mod tidy." \
      "" \
      "THAT IS NECESSARY AND NOT SUFFICIENT. This scan reads DIRECT requirements, and Go applies" \
      "only the MAIN module's replaces — a replace inside a dependency's go.mod is ignored — so" \
      "the library must also replace every sibling in its TRANSITIVE CLOSURE. Adding exactly the" \
      "modules listed above is what commit 5d78346 did, and the gate stayed red. The command that" \
      "actually proves the closure is complete, and the one test 21 runs:" \
      "" \
      "    cd go/<lib> && GOWORK=off go list -m all")"
  fi
}

# THE DEFECT, over the tree as it stands. `agentruntime` and `edenhttp` require siblings at
# v0.0.0 with no replace, which is why a 16-library sweep found both failing all 5 gate
# dimensions while every project-scoped nightly stayed green.
t_every_required_sibling_is_replaced() {
  assert_every_required_sibling_is_replaced
}

# CONSERVATION, and the refutation of "this assertion can only ever be red". A test proven only
# in the failing direction might be asserting something no tree can satisfy — a sibling feature
# shipped exactly that and the verifier caught it. So the same assertion is driven over a tree
# repaired by the scan's own inverse, where it must be GREEN, and the repair is held to changing
# nothing but replace directives: no require moved, no version moved, no `go mod tidy`, which is
# the whole shape the fix is allowed to have.
t_a_repaired_module_tree_is_clean() {
  assert_every_required_sibling_is_replaced
  assert_only_replace_directives_differ
}

# assert_only_replace_directives_differ — every manifest in MODULE_TREE must carry the same
# requires, in the same order, at the same versions, as the tree it was copied from.
assert_only_replace_directives_differ() {
  local manifest lib before after compared=0
  for manifest in "$MODULE_TREE_SOURCE"/*/go.mod; do
    [[ -f "$manifest" ]] || continue
    lib="$(basename "$(dirname "$manifest")")"
    [[ -f "$MODULE_TREE/$lib/go.mod" ]] ||
      fail "the repaired tree has no $lib/go.mod, so it is not the tree it claims to be a repair of"
    before="$(read_manifest requires "$manifest")"
    after="$(read_manifest requires "$MODULE_TREE/$lib/go.mod")"
    [[ "$before" == "$after" ]] ||
      fail "$(printf '%s\n' "the repair changed $lib's requirements, so it is not a replace-only change:" "--- before" "$before" "--- after" "$after")"
    compared=$((compared + 1))
  done
  # A for-loop over an empty glob returns 0, which would make this assertion report a pass
  # having compared nothing.
  [[ "$compared" -gt 0 ]] ||
    fail "no manifest was compared against $MODULE_TREE_SOURCE, so this run asserted nothing"
}

# THE ONE THAT SEPARATES A PER-MODULE CHECK FROM A COUNTING ONE. The tree it runs over has ONE
# replace aimed at a sibling the library does not require, and one required module now covered by
# nothing. The report must name that module and name it ALONE.
#
# The proof that a counting check is blind here is COUNT-NEUTRALITY: the mutation must leave both
# the requires and the replaces count exactly where the un-mutated tree had them, so no
# formulation that counts, subtracts or compares them can see it. The earlier version asserted
# `requires == replaces` instead, which was never true of this tree — envelope, forge and
# objectstorage carry 2 requires against 4 replaces, legitimately, because a replace may cover a
# module reached through a dependency. Completing agentruntime's closure made it 6 against 7 and
# the guard failed on a tree that had just been made MORE correct. Equality was an accident of
# the anchor; neutrality is the claim.
t_the_report_names_the_library_and_only_the_unreplaced_module() {
  local report line modules baseline before after
  report="$(scan_sibling_replaces "$MODULE_TREE")"
  assert_the_scan_is_not_vacuous "$report"
  line="$(grep "^UNREPLACED ${WRONG_REPLACE_LIB}[[:space:]]" <<< "$report" || true)"
  [[ -n "$line" ]] ||
    fail "$WRONG_REPLACE_LIB replaces $WRONG_REPLACE_DECOY instead of the $WRONG_REPLACE_MODULE it requires, and the scan reported it clean: [$report]"
  modules="${line#*-> }"
  [[ "$modules" == "$WRONG_REPLACE_MODULE" ]] ||
    fail "the report names [$modules]; exactly $WRONG_REPLACE_MODULE is unreplaced in this tree, so any other module here means the check is not reading the module a replace points AT"

  baseline="$MODULE_TREE/$CENSUS_BEFORE_MUTATION"
  [[ -f "$baseline" ]] ||
    fail "the tree stimulus recorded no pre-mutation census at $baseline, so count-neutrality cannot be established and this run proves nothing about the per-module form"
  before="$(grep "^SCANNED ${WRONG_REPLACE_LIB}[[:space:]]" "$baseline" || true)"
  after="$(grep "^SCANNED ${WRONG_REPLACE_LIB}[[:space:]]" <<< "$report" || true)"
  [[ -n "$before" && -n "$after" ]] ||
    fail "no census line for $WRONG_REPLACE_LIB before [$before] or after [$after] the mutation"
  [[ "$before" == "$after" ]] ||
    fail "the mutation moved a COUNT: before [$before] after [$after]. It must be count-neutral, or a counting check would have flagged this tree too and the run says nothing about which formulation is doing the work"
}

# THE ONE THAT READS THE GRAPH GO ACTUALLY RESOLVES. `go build` and the sibling scan above both
# read a PRUNED module graph, and both stayed GREEN through the entire agentruntime defect —
# green while its closure was broken, and green while a break-test reproduced `missing go.sum
# entry`. `go list -m all` loads the FULL graph, so an unreplaced v0.0.0 anywhere in the closure
# is an error rather than a module nobody happened to look at. It is the assertion that would
# have caught it, and it is one command per library.
#
# Measured inside ghcr.io/gophersys/base (amd64) on an arm64 host, so every number is a
# QEMU-emulated second: 21.4s for all 16 libraries, of which ~17s is the 7 exempt ones falling
# through the proxy to a `git ls-remote` that cannot authenticate. The 9 resolving libraries cost
# 2.1s between them. That is the price of the register being enumerated rather than skipped, and
# it shrinks to ~2s the moment the table is empty.
t_every_library_resolves_its_full_module_graph() {
  local manifest lib out rc entry anchor reason sibling scanned=0 red=0
  local -a walked=() unexpected=() stale=() mismatched=() same_class=()
  for manifest in "$MODULE_TREE"/*/go.mod; do
    [[ -f "$manifest" ]] || continue
    lib="$(basename "$(dirname "$manifest")")"
    scanned=$((scanned + 1))
    walked+=("$lib")
    rc=0
    # GOWORK=off is the whole point: eden's go.work would resolve every sibling by directory and
    # this assertion would be about the workspace instead of about the library.
    out="$( cd "$(dirname "$manifest")" && GOWORK=off go list -m all 2>&1 )" || rc=$?
    [[ "$rc" -eq 0 ]] || assert_the_module_graph_error_is_about_the_code "$lib" "$out"
    # An `if` context, never a bare assignment: under errexit a plain `entry="$(...)"` whose
    # substitution returns 1 — which is what "not exempt" IS — would kill the test outright.
    entry=""
    anchor=""
    reason=""
    if entry="$(module_graph_exemption "$lib")"; then
      anchor="${entry%%$'\t'*}"
      reason="${entry#*$'\t'}"
    fi
    if [[ "$rc" -eq 0 ]]; then
      if [[ -n "$entry" ]]; then
        stale+=("$lib — the table says: $reason")
      fi
      continue
    fi
    red=$((red + 1))
    # THE SAME-CLASS ARM, and the only one that reads NOTHING written by hand. An unresolved
    # sibling at v0.0.0 is the defect this whole change exists to fix; no exemption may hold it.
    sibling="$(grep -oE "$SIBLING_FAILURE_PATTERN" <<< "$out" || true)"
    sibling="${sibling%%$'\n'*}"
    if [[ -n "$sibling" ]]; then
      if [[ -n "$entry" ]]; then
        same_class+=("$lib -> $sibling  (EXEMPT as: $reason)")
      else
        same_class+=("$lib -> $sibling")
      fi
      continue
    fi
    if [[ -z "$entry" ]]; then
      unexpected+=("$(printf '%s (exit %s): %s' "$lib" "$rc" "$(head -2 <<< "$out")")")
      continue
    fi
    # THE REASON ARM. An exempt library must fail for the reason the table records.
    if ! grep -qF -- "$anchor" <<< "$out"; then
      mismatched+=("$(printf '%s — recorded [%s], observed: %s' "$lib" "$anchor" "$(head -2 <<< "$out")")")
    fi
  done
  # A glob that matched nothing leaves every list empty and every arm silent.
  [[ "$scanned" -gt 0 ]] ||
    fail "no go.mod was read under $MODULE_TREE, so no module graph was loaded and this run asserted nothing"
  info "go list -m all: $scanned librar(y|ies) read, $red red, ${#MODULE_GRAPH_EXEMPT[@]} on the exemption table"
  assert_every_exemption_names_a_real_library "${walked[@]}"

  if [[ ${#same_class[@]} -gt 0 ]]; then
    fail "$(printf '%s\n' \
      "a library's module graph fails on an UNRESOLVED SIBLING at v0.0.0. That is the very defect" \
      "this change exists to fix, so it is NOT EXEMPTIBLE — an exemption may hold only a defect of" \
      "a DIFFERENT class, and an entry that covers this one makes the change's own claim false:" \
      "" \
      "${same_class[@]}" \
      "" \
      "add 'replace <module> v0.0.0 => ../<slug>' to THIS library's go.mod. A replace in a" \
      "dependency's go.mod is ignored; only the main module's apply.")"
  fi
  if [[ ${#mismatched[@]} -gt 0 ]]; then
    fail "$(printf '%s\n' \
      "an exemption records a defect the library does not have. The anchor is the substring the" \
      "observed error MUST contain, and these do not — so the entry is describing something else," \
      "which is exactly how two same-class defects sat on this table wearing a different-class" \
      "label while every arm stayed quiet:" \
      "" \
      "${mismatched[@]}" \
      "" \
      "correct the anchor in MODULE_GRAPH_EXEMPT_SOURCE to the module path the error names, or" \
      "fix the library. Do not widen the anchor to make it match.")"
  fi
  if [[ ${#unexpected[@]} -gt 0 ]]; then
    fail "$(printf '%s\n' \
      "a library's FULL module graph does not resolve, and it is not on the exemption table." \
      "'go build' will not tell you this: it reads the pruned graph. Reproduce with" \
      "  cd go/<lib> && GOWORK=off go list -m all" \
      "" \
      "${unexpected[@]}" \
      "" \
      "no fix is prescribed here: the module named is not a sibling, so a replace is NOT the" \
      "answer. Read the error — a go.sum gap needs a go.sum write, a version conflict needs a bump.")"
  fi
  if [[ ${#stale[@]} -gt 0 ]]; then
    fail "$(printf '%s\n' \
      "a library on the MODULE_GRAPH_EXEMPT table now resolves its full graph. The table is a" \
      "debt register that may only shrink; an entry that outlives its defect is a check that" \
      "has quietly stopped reading a library. Delete these entries from MODULE_GRAPH_EXEMPT_SOURCE:" \
      "" \
      "${stale[@]}")"
  fi
}

# assert_the_module_graph_error_is_about_the_code <lib> <output> — a HARNESS failure, not a
# finding. `go list -m all` cannot reach the proxy and `go list -m all` found a broken manifest
# are the same non-zero exit, and reporting the first as the second is how a network blip turns
# into twelve confident, wrong instructions to add a replace for a third-party module.
#
# Manifest markers are tested FIRST and win. An unreplaced private sibling fails THROUGH the
# network, so its error carries transport text as well — but it also carries `invalid version`,
# which no reachability failure produces.
assert_the_module_graph_error_is_about_the_code() {
  local lib="$1" out="$2" marker
  # An emptied marker list would make this classifier silently answer "manifest" to everything,
  # which is the un-fixed behaviour wearing the fix's name.
  [[ ${#MODULE_GRAPH_MANIFEST_MARKERS[@]} -gt 0 && ${#MODULE_GRAPH_TRANSPORT_MARKERS[@]} -gt 0 ]] ||
    die "the module-graph marker lists are empty, so every error would be classified by default and nothing would be classified at all"
  for marker in "${MODULE_GRAPH_MANIFEST_MARKERS[@]}"; do
    if grep -qF -- "$marker" <<< "$out"; then
      return 0
    fi
  done
  for marker in "${MODULE_GRAPH_TRANSPORT_MARKERS[@]}"; do
    if grep -qF -- "$marker" <<< "$out"; then
      die "$(printf '%s\n' \
        "HARNESS FAILURE, not a finding: the module proxy is unreachable, so this run measured" \
        "the network rather than $lib's manifest. Every library would go red here and the" \
        "remediation for each would be wrong. CHANGE NO go.mod." \
        "" \
        "$lib: $(head -3 <<< "$out")" \
        "" \
        "the transport marker matched was: $marker")"
    fi
  done
  return 0
}

# assert_every_exemption_names_a_real_library <walked...> — the PHANTOM arm. Every other arm is
# driven by a library the scan walked, so an entry whose library was renamed, deleted or typo'd is
# reached by nothing and lives forever: the table reports one more debt than it holds and the
# stale arm can never retire it. This one walks the TABLE instead of the tree.
#
# It also enforces the entry's SHAPE. An entry with no anchor would make the reason arm's
# `grep -F ""` match every error ever printed — a check that cannot fail, dressed as one that can.
assert_every_exemption_names_a_real_library() {
  local -a walked=("$@")
  local entry name anchor found lib
  [[ ${#walked[@]} -gt 0 ]] ||
    fail "no library was walked, so no exemption could be checked against one"
  for entry in ${MODULE_GRAPH_EXEMPT[@]+"${MODULE_GRAPH_EXEMPT[@]}"}; do
    name="$(trim_field "${entry%%|*}")"
    anchor="$(module_graph_exemption_anchor "$entry")"
    [[ -n "$name" ]] || fail "an exemption entry names no library: [$entry]"
    [[ "${#anchor}" -ge "$MODULE_GRAPH_ANCHOR_MINIMUM" ]] ||
      fail "the exemption for '$name' carries the anchor [$anchor], under the $MODULE_GRAPH_ANCHOR_MINIMUM-character floor. An anchor that short matches any error Go prints, so the reason arm could never fail: [$entry]"
    found=0
    for lib in "${walked[@]}"; do
      if [[ "$lib" == "$name" ]]; then
        found=1
        break
      fi
    done
    [[ "$found" -eq 1 ]] ||
      fail "the exemption table names '$name', which is not a library in $MODULE_TREE. Every other arm is driven by a library the scan walked, so a phantom entry is reached by nothing and can never be retired — the register would report a debt that does not exist: [$entry]"
  done
}

# trim_field <text> — strips the surrounding blanks the table's column alignment introduces.
trim_field() {
  local text="$1"
  text="${text#"${text%%[![:space:]]*}"}"
  printf '%s' "${text%"${text##*[![:space:]]}"}"
}

# module_graph_exemption_anchor <entry> — field 2 of `<library> | <anchor> | <reason>`. A `|`
# separator rather than whitespace, because an anchor may hold spaces: orchestrator's error names
# no module at all and its anchor is Go's own phrase, `updates to go.mod needed`.
module_graph_exemption_anchor() {
  local rest="${1#*|}"
  trim_field "${rest%%|*}"
}

# module_graph_exemption <lib> — prints "<anchor><TAB><reason>" and returns 0 when <lib> is
# exempt, 1 otherwise.
module_graph_exemption() {
  local lib="$1" entry name rest
  for entry in ${MODULE_GRAPH_EXEMPT[@]+"${MODULE_GRAPH_EXEMPT[@]}"}; do
    name="$(trim_field "${entry%%|*}")"
    if [[ "$name" == "$lib" ]]; then
      rest="${entry#*|}"
      printf '%s\t%s' "$(module_graph_exemption_anchor "$entry")" "$(trim_field "${rest#*|}")"
      return 0
    fi
  done
  return 1
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
  t_every_required_sibling_is_replaced
  t_a_repaired_module_tree_is_clean
  t_the_report_names_the_library_and_only_the_unreplaced_module
  t_every_library_resolves_its_full_module_graph
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
    # The tree AS IT STANDS. This is the only test in the suite whose subject is the repository's
    # own manifests rather than a sandbox, because that is where the defect lives.
    t_every_required_sibling_is_replaced)                   printf 'tree:real\n' ;;
    t_a_repaired_module_tree_is_clean)                      printf 'tree:repaired\n' ;;
    t_the_report_names_the_library_and_only_the_unreplaced_module) printf 'tree:repaired-wrong-module\n' ;;
    # The tree AS IT STANDS again, and for the same reason: the module graph this repository
    # actually resolves is the subject, not a copy of it.
    t_every_library_resolves_its_full_module_graph)         printf 'tree:real\n' ;;
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
    # THREE counters, because there are three ways this assertion could be believed and be
    # hollow. `repaired-minus-one-replace` is the defect itself, planted. `repaired-wrong-module`
    # keeps the replace COUNT identical and aims one at the wrong sibling — the state every
    # count-based formulation calls clean. `empty` hands the scan no manifest at all, which is
    # the shape a check that silently does nothing takes.
    t_every_required_sibling_is_replaced)
      printf 'tree:repaired-minus-one-replace\n'
      printf 'tree:repaired-wrong-module\n'
      printf 'tree:empty\n' ;;
    # The same three, plus the one that reaches assert_only_replace_directives_differ. Without
    # that fourth, the replace-only assertion never executed a failing path in this suite: every
    # other stimulus trips an earlier arm, and discrimination is scored per TEST, so it counted
    # as proven while a verifier could neuter it to `after="$before"` and keep the suite green.
    # `repaired-with-a-moved-version` moves a version and touches no sibling, so the sibling scan
    # stays clean and that assertion is the only thing left that can fire.
    t_a_repaired_module_tree_is_clean)
      printf 'tree:repaired-minus-one-replace\n'
      printf 'tree:repaired-wrong-module\n'
      printf 'tree:repaired-with-a-moved-version\n'
      printf 'tree:empty\n' ;;
    # ONE COUNTER PER ARM. The repaired tree names nothing, so every assertion about WHAT the
    # report names loses its subject — that is what stops the test being satisfied by a report it
    # never read. `repaired-minus-one-replace` names the same module by the same line and is NOT
    # count-neutral (a replace is gone), so it is the counter the NEUTRALITY arm itself fails
    # under; without it that arm would be an assertion no stimulus ever executes.
    t_the_report_names_the_library_and_only_the_unreplaced_module)
      printf 'tree:repaired\n'
      printf 'tree:repaired-minus-one-replace\n' ;;
    # ONE COUNTER PER ARM, and this test has six. The claim was made before it was true: the
    # comment said "one per arm" while the vacuity floor, the phantom arm and the reason arm had
    # no stimulus at all — three assertions that had never executed a failing path in this suite.
    #   exempt:none                      four red libraries, none tabled        -> unexpected
    #   tree:transitive-replace-dropped  a dropped sibling closure, not tabled  -> same-class
    #   exempt:stale                     a green library that IS tabled         -> stale
    #   exempt:same-class                a sibling defect, tabled with an
    #                                    HONEST anchor                          -> same-class
    #   exempt:wrong-reason              a real entry, an anchor its library's
    #                                    error does not contain                 -> reason
    #   exempt:phantom                   an entry naming no library in the tree -> phantom
    #   exempt:empty-anchor              an entry whose anchor matches anything -> shape
    #   tree:empty                       no manifest at all                     -> vacuity floor
    t_every_library_resolves_its_full_module_graph)
      printf 'exempt:none\n'
      printf 'tree:transitive-replace-dropped\n'
      printf 'exempt:stale\n'
      printf 'exempt:same-class\n'
      printf 'exempt:wrong-reason\n'
      printf 'exempt:phantom\n'
      printf 'exempt:empty-anchor\n'
      printf 'tree:empty\n' ;;
    *) die "no counter-stimulus is declared for $1; every test must state what makes it fail" ;;
  esac
}

# apply <spec> points the next run at the named stimulus. THREE outcomes, and the driver reads
# all three, because they mean different things:
#
#   0   the stimulus is in place
#   1   a `none:` spec — this test states, out loud, that it declares no counter-stimulus
#   2   THE STIMULUS COULD NOT BE BUILT
#
# The 2 is new, and it exists because the 4th arm of an `exempt-library-repaired` stimulus went
# stale the moment an implementer fixed the library it repaired. The mutant could no longer change
# anything, it called `die`, and `die` exits — so the SUITE went down mid-phase-2 and never printed
# its summary. A harness that fails silently in its own scaffolding is the same defect class this
# suite exists to catch: nothing said which assertions had and had not run. An unbuildable stimulus
# is now a FAILING assertion that names the spec, and the remaining cases still run.
apply() {
  local apply_entry apply_replaced
  STIMULUS=""
  CONFIG="$SHARED_CONFIG"
  GO_BUILD_RC=0
  ABSENT_TOOL=""
  LIB="$LIB_SOURCE"
  SUBSTRATE_TIMEOUT_PRESENT=0
  SUBSTRATE_TIMEOUT=""
  MODULE_TREE="$MODULE_TREE_SOURCE"
  MODULE_GRAPH_EXEMPT=("${MODULE_GRAPH_EXEMPT_SOURCE[@]}")
  REFUSE_VALUES=("0" "0s" "" "0h0m0s" "-5m" "notaduration")
  FRACTION_VALUES=("0.4ns" "0.0000000001s" "1.5h" "0.5s")
  case "$1" in
    exit:*)      STIMULUS="${1#exit:}" ;;
    # A `die` inside a command substitution exits only the SUBSHELL, so its message reaches the
    # reader and the caller sees a non-zero return. Turning that into `return 2` — never a `die`
    # here — is what keeps an unbuildable stimulus a reported failure instead of an abort.
    config:typo) CONFIG="$(typo_config)" || return 2 ;;
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
      LIB="$(mutant_lib "${1#mutant:}")" || return 2
      [[ -f "$LIB" ]] || return 2 ;;
    # The repository's own manifests. Not a copy: the point of test 18 is the tree that ships.
    tree:real)   MODULE_TREE="$MODULE_TREE_SOURCE" ;;
    tree:*)
      MODULE_TREE="$(mutant_tree "${1#tree:}")" || return 2
      [[ -d "$MODULE_TREE" ]] || return 2 ;;
    # THE STALE-EXEMPTION STIMULUS. It lists a library that already resolves, which is the exact
    # predicate the arm forbids — an entry outliving its defect. It mutates the TABLE, not the
    # tree, so it can never go stale the way its predecessor did: it has no dependency on any
    # library staying broken.
    exempt:stale)
      MODULE_GRAPH_EXEMPT+=("$STALE_EXEMPTION_LIB | it already resolves, so no anchor can match | the stimulus, not a real debt") ;;
    # THE PHANTOM. An entry naming a library the scan never walks is reached by no other arm, so
    # it can never be retired: the register reports a debt that does not exist.
    exempt:phantom)
      MODULE_GRAPH_EXEMPT+=("$PHANTOM_EXEMPTION_LIB | github.com/kr/pretty | the stimulus: this library does not exist") ;;
    # THE COUNTER FOR THE UNEXPECTED ARM, and it needs its own because the sibling stimulus no
    # longer reaches it: a dropped closure is now claimed by the more specific same-class arm,
    # which is the right message but leaves `unexpected` — a red library that is simply not
    # tabled — with nothing driving it. Emptying the table puts all four real debts in exactly
    # that state, and none of their errors names a sibling.
    exempt:none) MODULE_GRAPH_EXEMPT=() ;;
    # THE EMPTY ANCHOR. `grep -F ""` matches every error ever printed, so an entry with no anchor
    # turns the reason arm into a check that cannot fail while still looking like one that can.
    exempt:empty-anchor)
      MODULE_GRAPH_EXEMPT+=("$WRONG_REASON_LIB |  | the stimulus: no anchor at all") ;;
    # THE WRONG REASON. One real entry keeps its library and loses its anchor to a module path
    # taken from a DIFFERENT library's real error in this same tree. This is the prose defect,
    # planted: an entry that describes a defect its library does not have.
    exempt:wrong-reason)
      apply_replaced=0
      MODULE_GRAPH_EXEMPT=()
      for apply_entry in "${MODULE_GRAPH_EXEMPT_SOURCE[@]}"; do
        if [[ "$(trim_field "${apply_entry%%|*}")" == "$WRONG_REASON_LIB" ]]; then
          MODULE_GRAPH_EXEMPT+=("$WRONG_REASON_LIB | $WRONG_REASON_ANCHOR | the stimulus: an anchor this library's error does not contain")
          apply_replaced=$((apply_replaced + 1))
        else
          MODULE_GRAPH_EXEMPT+=("$apply_entry")
        fi
      done
      # A stimulus that replaced nothing planted nothing. Reported as unbuildable, never as a pass.
      if [[ "$apply_replaced" -eq 0 ]]; then
        printf '\033[0;31m[test]\033[0m the exemption table holds no entry for %s, so the wrong-reason stimulus has no subject\n' "$WRONG_REASON_LIB" >&2
        return 2
      fi
      ;;
    # THE SAME-CLASS EXEMPTION: reopen agentruntime's closure AND table it, which is precisely the
    # state two entries were in — a same-class defect wearing a different-class label. The anchor
    # is honest here, so only the same-class arm can fire; that is what makes this stimulus prove
    # the arm reads the OBSERVED error rather than the recorded prose.
    exempt:same-class)
      MODULE_TREE="$(mutant_tree transitive-replace-dropped)" || return 2
      [[ -d "$MODULE_TREE" ]] || return 2
      MODULE_GRAPH_EXEMPT+=("$TRANSITIVE_LIB | $SIBLING_PREFIX$TRANSITIVE_MODULE | the stimulus: a same-class defect, exempted") ;;
    real)        : ;;
    none:*)      return 1 ;;
    *) printf '\033[0;31m[test]\033[0m unknown stimulus spec: %s\n' "$1" >&2; return 2 ;;
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
  # `rc=$?` off a bare `apply` would trip errexit before it could be read, so the call is made in
  # a condition context and the status taken from the ||-arm.
  apply_rc=0
  apply "$(stimulus_for "$t")" || apply_rc=$?
  if [[ "$apply_rc" -ne 0 ]]; then
    bad "$t — its phase-1 stimulus could not be built (apply exit $apply_rc); the behaviour of $t was NOT measured on this run"
    failures=$((failures + 1))
    continue
  fi
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
  # The list is captured BEFORE the loop. Read through a process substitution, a `die` inside
  # counter_for would exit only that subshell: the loop would read nothing, run zero cases, and
  # the test would be scored unproven in silence.
  counters=""
  counters_rc=0
  counters="$(counter_for "$t")" || counters_rc=$?
  if [[ "$counters_rc" -ne 0 || -z "$counters" ]]; then
    bad "$t declares no counter-stimulus that could be read (exit $counters_rc); a test whose counter list is empty is scored proven having been driven by nothing"
    failures=$((failures + 1))
    continue
  fi
  while IFS= read -r spec || [[ -n "$spec" ]]; do
    [[ -n "$spec" ]] || continue
    apply_rc=0
    apply "$spec" || apply_rc=$?
    case "$apply_rc" in
      0) ;;
      # A stated `none:` — the test says out loud that it has no counter.
      1) info "$t — no counter-stimulus: ${spec#none:}"
         unproven=$((unproven + 1))
         continue ;;
      # THE SCAFFOLDING FAILED. Not a skip, not an abort: a named failure that leaves the rest of
      # the run to report itself. This is the arm that used to take the whole suite down.
      *) bad "$t — the '$spec' counter-stimulus could not be built (apply exit $apply_rc, see the message above); a stimulus that cannot be built discriminates nothing"
         failures=$((failures + 1))
         continue ;;
    esac
    stimuli=$((stimuli + 1))
    if ( set -Eeuo pipefail; "$t" ); then
      bad "$t still passed under $spec; it does not read what it claims to read"
      failures=$((failures + 1))
    else
      ok "$t fails under $spec"
      broke=1
    fi
  done <<< "$counters"
  proven=$((proven + broke))
done

if [[ "$failures" -ne 0 ]]; then
  # The summary prints FIRST, then the failure count. A run that ends without saying how much of
  # itself executed is a run nobody can act on — which is exactly what a `die` inside a stimulus
  # builder used to produce.
  note "${#TESTS[@]} test(s) driven; $proven of ${#TESTS[@]} proven able to fail across $stimuli counter-stimuli; $unproven stated no counter"
  die "$failures failure(s) across both phases"
fi
# The summary is COUNTED, never asserted. An earlier version ended with "each is
# proven able to fail", which was false for any test carrying a `none:` counter —
# a summary that overstates its own rigour is the defect this suite exists to catch.
info "${#TESTS[@]} test(s) hold; $proven of ${#TESTS[@]} proven able to fail across $stimuli counter-stimuli; $unproven stated no counter"
