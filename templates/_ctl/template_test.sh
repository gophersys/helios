#!/usr/bin/env bash
#
# libs/templates/_ctl/template_test.sh — prove that the template's phase-gate can FAIL.
#
# `_gate_run` in template.sh invokes the verb as `if ( set -Eeuo pipefail; "$@" ); then`.
# A command used as an `if` condition runs with errexit SUPPRESSED, and bash propagates
# that suppression into the subshell and into the function the subshell calls — the
# re-armed `set -Eeuo pipefail` inside the parentheses does not restore it. So a verb
# whose failure is carried only by errexit (`go_in_app build ./...` then `log_success`)
# runs straight through to `log_success` and returns 0, and the gate records PASS.
#
# Measured, 2026-08-12, ghcr.io/gophersys/base:latest, over a fixture whose only Go file
# does not compile:
#
#   bash ./ctl.sh build              -> [info] build … / compile error / EXIT=1
#   bash ./ctl.sh phase-gate testing -> FAIL … [build failed] / [ok] test: OK / PASS test
#                                      [ok] phase-gate testing: GREEN / EXIT=0
#
# `go/_ctl/lib.sh` already names this defect and already fixes it (lib.sh:1009-1020: run the
# subshell in a NEUTRAL position with errexit locally disabled, then read `$?` on the next
# line). The fix never crossed to template.sh because the two gate libraries are two homes
# for one concept (10 §9) — which is what this feature unifies.
#
# 2 phases, after go/_ctl/lib_test.sh and ctl_test.sh:
#
#   phase 1  behaviour      — each test asserts what the template gate must do.
#   phase 2  discrimination — each test is re-run against the counter-stimulus declared for
#                             it, and must FAIL. A test that passes both ways read nothing.
#
# Every test drives template.sh through a THROWAWAY fixture under `mktemp -d` whose PATH
# holds recording stubs for the gate tools, so the exit code under test is CHOSEN instead of
# waited for and no assertion depends on the state of this repository. The stubs record
# their own argv, so a test can assert what a verb actually handed the tool.
#
# Usage: bash templates/_ctl/template_test.sh [test-name]
#
# shellcheck shell=bash
set -Eeuo pipefail
IFS=$'\n\t'

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="$HERE/template.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# The gate tools template.sh reaches for. Every one is stubbed on every run, so a verb can
# never reach a real tool and no test depends on what this host happens to have installed.
TOOLS=(go gofumpt golangci-lint govulncheck gosec gitleaks hnslint rg oapi-codegen)

# The ordinary utilities template.sh and the fixture dispatcher call. The sandbox PATH holds
# ONLY these and the stubs — never the host PATH — so an "absent tool" stimulus is a real
# absence rather than a stub the real binary shadows from further down the path.
COREUTILS=(dirname basename mktemp cat tail head rm cp mkdir touch chmod ln sed awk grep tr sort wc find env printf)

# TOOL_RC is the exit code the stubs return; ABSENT_TOOL, when set, is left OFF the sandbox
# PATH entirely (the FAIL-NOT-SKIP stimulus). The driver repoints them between the phases.
# The hnslint stub always mimics the PINNED gophersys/hnslint v0.1.0, whose whole interface is
# `hnslint <dir> [dir...]`: it has no flags, exits 2 on no arguments, and exits 1 with
# "<arg>: not a directory" for a non-directory — the SAME code a real finding uses. Verified
# against the pinned binary in ghcr.io/gophersys/base:latest on 2026-08-12.
TOOL_RC=0
ABSENT_TOOL=""
# OUT, RC and ARGV hold the last run_gate result.
OUT=""
RC=0
ARGV=""

info() { printf '\033[0;36m[test]\033[0m %s\n' "$*"; }
ok()   { printf '\033[0;32m  ok  \033[0m %s\n' "$*"; }
bad()  { printf '\033[0;31m FAIL \033[0m %s\n' "$*" >&2; }
die()  { printf '\033[0;31m[test]\033[0m %s\n' "$*" >&2; exit 1; }
# fail ends the test it is called from. Each test runs in its own subshell.
fail() { printf '       %s\n' "$*" >&2; exit 1; }

# FAIL-NOT-SKIP (ADR-0020): a missing tool is a failure that names the tool, never a skip.
for _tool in mktemp grep printf; do
  command -v "$_tool" >/dev/null || die "this host has no $_tool; the suite cannot run"
done
# `mapfile` and `set -e` inside a re-armed subshell both need bash 4+; this host's bash is the
# suite's substrate, so an old one is a failure that says so rather than a wrong answer.
[[ "${BASH_VERSINFO[0]}" -ge 4 ]] ||
  die "this host's bash is $BASH_VERSION; the suite (and ctl.sh) need bash 4+ — run it in ghcr.io/gophersys/base"
[[ -f "$LIB" ]] || die "the library under test is missing: $LIB"

# ── the sandbox ─────────────────────────────────────────────────────────────

# make_sandbox prints the path of a fresh sandbox holding bin/ (the stubs) and proj/ (a
# fixture template whose ctl.sh sources template.sh, exactly as a real template does).
make_sandbox() {
  local sb tool utility path
  sb="$(mktemp -d "$WORK/sb.XXXXXX")"
  mkdir -p "$sb/bin" "$sb/proj/contract" "$sb/proj/internal" "$sb/proj/cmd"
  ln -s "$(command -v bash)" "$sb/bin/bash"
  for utility in "${COREUTILS[@]}"; do
    path="$(command -v "$utility")" ||
      die "this host has no $utility; the sandbox cannot be built (FAIL-NOT-SKIP)"
    ln -s "$path" "$sb/bin/$utility"
  done
  : > "$sb/proj/contract/openapi.yaml"
  : > "$sb/argv"

  for tool in "${TOOLS[@]}"; do
    [[ "$tool" == "$ABSENT_TOOL" ]] && continue
    {
      printf '#!/usr/bin/env bash\n'
      printf 'printf "%%s\\t%%s\\n" "%s" "$*" >> "%s"\n' "$tool" "$sb/argv"
      # `go env GOPATH` is called by have_cmd's fallback and must answer, never hang.
      if [[ "$tool" == "go" ]]; then
        # shellcheck disable=SC2016 # the stub body is emitted verbatim, expanded when it runs
        printf 'if [[ "${1:-}" == "env" ]]; then printf "%%s\\n" "%s/gopath"; exit 0; fi\n' "$sb"
      fi
      if [[ "$tool" == "hnslint" ]]; then
        # gophersys/hnslint v0.1.0: `hnslint <dir> [dir...]`. A non-directory argument is
        # exit 1 with this exact text — the SAME code a real finding uses.
        # shellcheck disable=SC2016 # likewise: the stub body is emitted verbatim
        printf 'for a in "$@"; do [[ -d "$a" ]] || { printf "%%s: not a directory\\n" "$a"; exit 1; }; done\n'
      fi
      printf 'exit %s\n' "$TOOL_RC"
    } > "$sb/bin/$tool"
    chmod +x "$sb/bin/$tool"
  done

  {
    printf '#!/usr/bin/env bash\n'
    printf 'set -Eeuo pipefail\n'
    printf "IFS=\$'\\\\n\\\\t'\n"
    # shellcheck disable=SC2016 # the fixture's own body, expanded when the fixture runs
    printf 'PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
    printf 'export PROJECT_ROOT\n'
    printf 'EDEN_TEMPLATE_NAME="gatefixture"\n'
    printf 'EDEN_INTEGRATION_CMDS="go"\n'
    printf 'export EDEN_TEMPLATE_NAME EDEN_INTEGRATION_CMDS\n'
    # shellcheck disable=SC2016 # the fixture resolves this at run time, not here
    printf '%s\n' 'source "$EDEN_LIB_UNDER_TEST"'
    # shellcheck disable=SC2016 # likewise
    printf '%s\n' 'template_main "$@"'
  } > "$sb/proj/ctl.sh"
  chmod +x "$sb/proj/ctl.sh"

  printf '%s' "$sb"
}

# sandbox_env prints the `env -i` prefix arguments for a sandbox: a hermetic environment in
# which the only reachable tools are the stubs, and neither EDEN_GOWORK nor
# EDEN_GOLANGCI_CONFIG makes template.sh shell out to git.
sandbox_env() {
  local sb="$1"
  printf '%s\n' \
    "PATH=$sb/bin" "HOME=$sb" "TMPDIR=$sb" \
    "EDEN_GOWORK=$sb/absent.go.work" \
    "EDEN_GOLANGCI_CONFIG=$sb/absent.golangci.yml" \
    "EDEN_LIB_UNDER_TEST=$LIB"
}

# run_gate_step <verb-function> — drive ONE verb through template.sh's `_gate_run`, the way
# every phase does, and set OUT / RC / ARGV. This is the unit under test: `_gate_run` is what
# converts a verb's exit status into a PASS or FAIL row.
run_gate_step() {
  local verb="$1" sb env_args=()
  [[ -n "$verb" ]] || die "run_gate_step needs a verb function name"
  sb="$(make_sandbox)"
  {
    # shellcheck disable=SC2016 # resolved by the runner, not here
    printf '%s\n' 'source "$EDEN_LIB_UNDER_TEST"'
    printf '_gate_run "%s" %s\n' "${verb#cmd_}" "$verb"
    printf 'printf "GATE_RUN_RC=%%s\\n" "$?"\n'
  } > "$sb/run.sh"
  mapfile -t env_args < <(sandbox_env "$sb")
  RC=0
  OUT="$(env -i "${env_args[@]}" PROJECT_ROOT="$sb/proj" \
    bash "$sb/run.sh" 2>&1)" || RC=$?
  ARGV="$(cat "$sb/argv")"
  assert_harness_intact
}

# assert_harness_intact — a red produced by a broken sandbox is not evidence. A utility the
# sandbox failed to provide surfaces as "command not found", which would make almost any
# verb fail for a reason that has nothing to do with the code under test, so it aborts the
# suite instead of being read as a result.
assert_harness_intact() {
  if grep -q 'command not found' <<< "$OUT"; then
    die "the sandbox is missing a utility, so this run measured the harness, not template.sh: $OUT"
  fi
}

# run_phase_gate <phase> — drive the whole verb a human runs: `./ctl.sh phase-gate <phase>`.
run_phase_gate() {
  local phase="$1" sb env_args=()
  [[ -n "$phase" ]] || die "run_phase_gate needs a phase"
  sb="$(make_sandbox)"
  mapfile -t env_args < <(sandbox_env "$sb")
  RC=0
  OUT="$(env -i "${env_args[@]}" bash "$sb/proj/ctl.sh" phase-gate "$phase" 2>&1)" || RC=$?
  ARGV="$(cat "$sb/argv")"
  assert_harness_intact
}

# ── the tests ───────────────────────────────────────────────────────────────

# THE DEFECT. Each of the six verbs the gate is trusted to police carries its failure only
# through errexit, and errexit is suppressed at `_gate_run`'s call site. Every one is
# recorded PASS while its tool exited non-zero.
t_a_failing_verb_is_never_recorded_pass() {
  local verb
  for verb in cmd_build cmd_test cmd_vuln cmd_sast cmd_secretscan cmd_maintainability; do
    run_gate_step "$verb"
    [[ -n "$ARGV" ]] ||
      fail "${verb}: no gate tool was invoked at all, so this run proves nothing"
    if grep -q "^PASS" <<< "$OUT"; then
      fail "${verb}: the gate recorded PASS while its tool exited $TOOL_RC: $OUT"
    fi
    grep -q "GATE_RUN_RC=0" <<< "$OUT" &&
      fail "${verb}: _gate_run returned 0 while its tool exited $TOOL_RC: $OUT"
  done
}

# The same defect read end to end, at the verb a human types. `phase-gate testing` runs
# test → integration → cover, all three of which carry failure only through errexit.
t_a_failing_verb_makes_phase_gate_exit_non_zero() {
  run_phase_gate testing
  [[ -n "$ARGV" ]] || fail "phase-gate testing invoked no gate tool at all; the run proves nothing"
  [[ "$RC" -ne 0 ]] ||
    fail "phase-gate testing exited 0 while every tool it ran exited $TOOL_RC: $OUT"
  grep -q "GREEN" <<< "$OUT" &&
    fail "phase-gate testing reported GREEN over tools that exited $TOOL_RC: $OUT"
}

# CONSERVATION. The half that already works must keep working: a verb whose tools all
# succeed is recorded PASS and returns 0.
t_a_passing_verb_is_recorded_pass() {
  run_gate_step cmd_build
  grep -q "^PASS" <<< "$OUT" || fail "a clean build was not recorded PASS: $OUT"
  grep -q "GATE_RUN_RC=0" <<< "$OUT" || fail "_gate_run returned non-zero on a clean verb: $OUT"
  [[ "$RC" -eq 0 ]] || fail "the gate step exited $RC on a clean verb: $OUT"
}

# CONSERVATION. FAIL-NOT-SKIP (ADR-0020): an absent tool is a gate failure that NAMES the
# tool. `require_cmd` carries this with an explicit `exit 127`, which survives the errexit
# suppression that defeats every other verb — so this half is expected to hold today, and
# must still hold after the unification.
t_an_absent_tool_is_never_recorded_pass() {
  run_gate_step cmd_secretscan
  grep -q "^PASS" <<< "$OUT" && fail "the gate recorded PASS with ${ABSENT_TOOL:-a tool} absent: $OUT"
  grep -q "GATE_RUN_RC=0" <<< "$OUT" && fail "_gate_run returned 0 with ${ABSENT_TOOL:-a tool} absent: $OUT"
  grep -q "${ABSENT_TOOL:-gitleaks}" <<< "$OUT" ||
    fail "the failure never names the absent tool ${ABSENT_TOOL:-gitleaks}: $OUT"
}

# hnslint takes DIRECTORIES: `hnslint <dir> [dir...]`. template.sh hands it `./...`, a Go
# package pattern, so hnslint answers "./...: not a directory" and exits 1 without inspecting
# anything — and the verb reports OK over it. The verb must not hand hnslint a package
# pattern, and must never report OK over a run that inspected nothing.
#
# This test pins the CURRENT contract: `maintainability` runs hnslint. The plan's open
# escalation may replace that with a DECLARED, counted skip; if it does, this test is
# rewritten in the same change, which is visible — never silently satisfied by a verb that
# stopped calling hnslint at all. That is what the argv floor below enforces.
t_maintainability_never_reports_ok_over_an_hnslint_argument_error() {
  run_gate_step cmd_maintainability
  grep -q "^hnslint" <<< "$ARGV" ||
    fail "cmd_maintainability never invoked hnslint at all, so this run proves nothing: [$ARGV]"
  if grep -q '^hnslint.*\.\.\.' <<< "$ARGV"; then
    fail "hnslint was handed a Go package pattern, which it reports as 'not a directory': [$ARGV]"
  fi
  if grep -q "not a directory" <<< "$OUT" && grep -q "maintainability: OK" <<< "$OUT"; then
    fail "hnslint reported an argument error and the verb still reported OK: $OUT"
  fi
}

TESTS=(
  t_a_failing_verb_is_never_recorded_pass
  t_a_failing_verb_makes_phase_gate_exit_non_zero
  t_a_passing_verb_is_recorded_pass
  t_an_absent_tool_is_never_recorded_pass
  t_maintainability_never_reports_ok_over_an_hnslint_argument_error
)

# ── the stimulus tables ─────────────────────────────────────────────────────

# stimulus_for <test> — what phase 1 drives the test with.
stimulus_for() {
  case "$1" in
    t_a_failing_verb_is_never_recorded_pass)          printf 'tools:1' ;;
    t_a_failing_verb_makes_phase_gate_exit_non_zero)  printf 'tools:1' ;;
    t_a_passing_verb_is_recorded_pass)                printf 'tools:0' ;;
    t_an_absent_tool_is_never_recorded_pass)          printf 'absent:gitleaks' ;;
    t_maintainability_never_reports_ok_over_an_hnslint_argument_error) printf 'tools:0' ;;
    *) die "no phase-1 stimulus is declared for $1" ;;
  esac
}

# counter_for <test> — what must BREAK the test. A `none:` entry states its reason out loud,
# so a test can never lose its counter quietly.
counter_for() {
  case "$1" in
    t_a_failing_verb_is_never_recorded_pass)          printf 'tools:0' ;;
    t_a_failing_verb_makes_phase_gate_exit_non_zero)  printf 'tools:0' ;;
    # NOT `tools:1`: that is the defect's own stimulus, and while the defect stands a failing
    # verb IS recorded PASS, so the counter would not break this test. An absent tool exits
    # 127 explicitly, which no version of _gate_run records as PASS.
    t_a_passing_verb_is_recorded_pass)                printf 'absent:go' ;;
    t_an_absent_tool_is_never_recorded_pass)          printf 'tools:0' ;;
    # NOT a lenient hnslint: that removes the argument error the test reads, and a test that
    # cannot go vacuous is what this counter proves. With hnslint ABSENT the verb never runs
    # it, the argv floor fires, and the test fails — so a verb that quietly stopped calling
    # hnslint can never satisfy this test by having nothing to complain about.
    t_maintainability_never_reports_ok_over_an_hnslint_argument_error) printf 'absent:hnslint' ;;
    *) die "no counter-stimulus is declared for $1; every test must state what makes it fail" ;;
  esac
}

# apply <spec> points the next run at the named stimulus. It returns 1 on a `none:` spec so
# the driver reports the reason instead of silently skipping.
apply() {
  TOOL_RC=0
  ABSENT_TOOL=""
  case "$1" in
    tools:*)          TOOL_RC="${1#tools:}" ;;
    absent:*)         ABSENT_TOOL="${1#absent:}" ;;
    none:*)           return 1 ;;
    *) die "unknown stimulus spec: $1" ;;
  esac
}

# ── the driver ──────────────────────────────────────────────────────────────

# An argument selects 1 test by name, so a single red can be read on its own. A name that
# matches nothing is a hard error: a filter that silently selects 0 tests is a suite that
# exits 0 having checked nothing.
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

info "phase 1 — behaviour: ${#TESTS[@]} test(s) against templates/_ctl/template.sh"
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
# The summary is COUNTED, never asserted: a summary that overstates its own rigour is the
# defect this suite exists to catch.
info "${#TESTS[@]} test(s) hold; $proven of ${#TESTS[@]} proven able to fail; $unproven stated no counter"
