#!/usr/bin/env bash
#
# ctl_test.sh — prove that `ctl.sh validate` reads every dispatcher's REAL verb list.
#
# cmd_validate compares each project.json's targets against its sibling ctl.sh's
# usage block, and it obtains that block by SCRAPING THE SOURCE TEXT: an awk program
# that matches `^function usage() {` and `cat <<EOF`. Three dispatcher shapes in this
# repository are invisible to it:
#
#   * the POSIX `usage() {` form, no `function` keyword — persistence/ctl.sh:43 and
#     clients/go/ctl.sh:44 under templates/go/http-gateway/;
#   * the QUOTED heredoc `cat <<'EOF'` — the same 2 files;
#   * no local usage at all: `help` calls a function that arrives from a sourced file
#     — templates/go/http-gateway/ctl.sh calls template_usage from
#     templates/_ctl/template.sh:447.
#
# For each of those the scraper yields an EMPTY verb list, and an empty verb list makes
# the usage-to-targets half of the loop VACUOUSLY GREEN. So the check emits false
# "target X missing from ctl.sh usage" messages, and it has never once reported that
# templates/go/http-gateway/ctl.sh documents AND dispatches openapi, verify-openapi and
# gen-client with no matching project.json target. A parser that cannot see a verb
# cannot see a missing one.
#
# The fix asks the program instead of parsing it: run `<ctl> help` and take the verbs
# from its output — the rule .ci/ctl.sh:200 (cmd_list_verbs) already follows. A `help`
# that exits non-zero, or that yields no verbs, is then its OWN counted failure naming
# the script, never a silent empty list.
#
# 2 phases, after go/_ctl/lib_test.sh:
#
#   phase 1  behaviour      — each test asserts what the drift check must report.
#   phase 2  discrimination — each test is re-run against the counter-stimulus declared
#                             for it, and must FAIL. A test that passes both ways read
#                             nothing, and proves nothing.
#
# Every test plants its drift in a THROWAWAY tree under mktemp -d holding a copy of the
# ctl.sh under test, so PROJECT_ROOT resolves to the fixture: the assertions are about
# planted drift, never about the current state of this repository.
#
# Usage: bash ctl_test.sh [test-name]
#
set -Eeuo pipefail
IFS=$'\n\t'

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CTL="$HERE/ctl.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# VARIANT is the stimulus: "good" builds the fixture the test describes, "counter"
# builds the one declared to break it. The driver repoints it between the 2 phases.
VARIANT="good"
# OUT and RC hold the last run_validate result.
OUT=""
RC=0

info() { printf '\033[0;36m[test]\033[0m %s\n' "$*"; }
ok()   { printf '\033[0;32m  ok  \033[0m %s\n' "$*"; }
bad()  { printf '\033[0;31m FAIL \033[0m %s\n' "$*" >&2; }
die()  { printf '\033[0;31m[test]\033[0m %s\n' "$*" >&2; exit 1; }
# fail ends the test it is called from. Each test runs in its own subshell.
fail() { printf '       %s\n' "$*" >&2; exit 1; }

# ctl.sh uses mapfile, which bash 3.2 (the macOS /bin/bash) does not have. Running the
# suite there would exercise nothing, so it is a failure that names the reason.
type -t mapfile >/dev/null || die "this bash (${BASH_VERSION}) has no mapfile, so ctl.sh cannot run here; run the suite in the devcontainer"
# FAIL-NOT-SKIP (ADR-0020): a missing tool is a failure that names the tool.
for _tool in shellcheck jq timeout mktemp find awk grep; do
  command -v "$_tool" >/dev/null || die "this host has no $_tool; the suite cannot run"
done
# Resolved BEFORE any fixture plants a `timeout` shim on PATH, so the harness's own bound is
# always the real tool.
REAL_TIMEOUT="$(command -v timeout)"
[[ -f "$CTL" ]] || die "the script under test is missing: $CTL"

# ── the fixture builders ────────────────────────────────────────────────────

# new_fixture prints a fresh tree holding a copy of the ctl.sh under test at its root,
# so PROJECT_ROOT resolves to the fixture. The tree carries one green *_test.sh because
# cmd_validate counts "zero suites found" as a failure of its own.
new_fixture() {
  local fix
  fix="$(mktemp -d "$WORK/fix.XXXXXX")"
  cp "$CTL" "$fix/ctl.sh"
  chmod +x "$fix/ctl.sh"
  cat > "$fix/suite_test.sh" <<'SUITE'
#!/usr/bin/env bash
#
# A green, shellcheck-clean suite. It exists so the fixture clears cmd_validate's
# floor of 1 test script, and it is never the failure under test.
set -Eeuo pipefail
printf 'fixture suite: ok\n'
SUITE
  printf '%s' "$fix"
}

# write_project_json <path> <target>... — the Nx wiring, reduced to what jq reads.
write_project_json() {
  local path="$1" target first=1
  shift
  mkdir -p "$(dirname "$path")"
  {
    printf '{\n  "name": "fixture-lib",\n  "projectType": "library",\n  "targets": {\n'
    for target in "$@"; do
      [[ "$first" -eq 1 ]] || printf ',\n'
      first=0
      printf '    "%s": {\n      "executor": "nx:run-commands",\n' "$target"
      printf '      "options": { "command": "bash ./ctl.sh %s", "cwd": "{projectRoot}" }\n    }' "$target"
    done
    printf '\n  }\n}\n'
  } > "$path"
}

# write_sourced_dispatcher <fix> <verb>... — the templates/go/http-gateway/ctl.sh shape:
# NO local usage; `help` calls a function that arrives from a sourced file.
write_sourced_dispatcher() {
  local fix="$1" verb
  shift
  mkdir -p "$fix/_ctl" "$fix/lib"
  {
    cat <<'HEAD'
#!/usr/bin/env bash
#
# Shared verb bodies, sourced by the dispatcher — the templates/_ctl/template.sh shape.
set -Eeuo pipefail

shared_usage() {
  cat <<'USAGE'
Usage: ./ctl.sh <command>

HEAD
    for verb in "$@"; do
      printf '  %-10s run the %s verb\n' "$verb" "$verb"
    done
    cat <<'TAIL'
  help       Show this message
USAGE
}

shared_main() {
  printf 'fixture: %s\n' "$1"
}
TAIL
  } > "$fix/_ctl/shared.sh"

  {
    cat <<'HEAD'
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=../_ctl/shared.sh
# shellcheck disable=SC1091
source "$PROJECT_ROOT/../_ctl/shared.sh"

case "${1:-help}" in
  help|"") shared_usage ;;
HEAD
    for verb in "$@"; do
      printf '  %s) shared_main %s ;;\n' "$verb" "$verb"
    done
    cat <<'TAIL'
  *) printf 'unknown command: %s\n' "$1" >&2; shared_usage; exit 1 ;;
esac
TAIL
  } > "$fix/lib/ctl.sh"
  chmod +x "$fix/lib/ctl.sh"
}

# write_posix_dispatcher <fix> <verb>... — the persistence/ and clients/go/ shape: a
# LOCAL usage in POSIX form (no `function` keyword) whose body is a QUOTED heredoc.
write_posix_dispatcher() {
  local fix="$1" verb
  shift
  mkdir -p "$fix/lib"
  {
    cat <<'HEAD'
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

run_verb() { printf 'fixture: %s\n' "$1"; }

usage() {
  cat <<'EOF'
Usage: ./ctl.sh <command>

HEAD
    for verb in "$@"; do
      printf '  %-10s run the %s verb\n' "$verb" "$verb"
    done
    cat <<'MID'
  help       Show this message
EOF
}

case "${1:-help}" in
MID
    for verb in "$@"; do
      printf '  %s) run_verb %s ;;\n' "$verb" "$verb"
    done
    cat <<'TAIL'
  help|"") usage ;;
  *) printf 'unknown command: %s\n' "$1" >&2; usage; exit 1 ;;
esac
TAIL
  } > "$fix/lib/ctl.sh"
  chmod +x "$fix/lib/ctl.sh"
}

# write_usage_stream_dispatcher <fix> <stdout|stderr> <verb>... — a dispatcher that documents
# its verbs on the named stream. `help` exits 0 either way, so on stderr it is the shape that
# LOOKS healthy and yields nothing: the verbs never reach the reader of its stdout.
write_usage_stream_dispatcher() {
  local fix="$1" stream="$2" verb redirect=""
  shift 2
  if [[ "$stream" == "stderr" ]]; then
    redirect=' >&2'
  fi
  mkdir -p "$fix/lib"
  {
    cat <<'HEAD'
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

run_verb() { printf 'fixture: %s\n' "$1"; }

usage() {
HEAD
    printf "  cat <<'EOF'%s\n" "$redirect"
    printf 'Usage: ./ctl.sh <command>\n\n'
    for verb in "$@"; do
      printf '  %-10s run the %s verb\n' "$verb" "$verb"
    done
    cat <<'MID'
  help       Show this message
EOF
}

case "${1:-help}" in
MID
    for verb in "$@"; do
      printf '  %s) run_verb %s ;;\n' "$verb" "$verb"
    done
    cat <<'TAIL'
  help|"") usage ;;
  *) printf 'unknown command: %s\n' "$1" >&2; usage; exit 1 ;;
esac
TAIL
  } > "$fix/lib/ctl.sh"
  chmod +x "$fix/lib/ctl.sh"
}

# write_slow_help_dispatcher <fix> <sleep-seconds> <verb>... — `help` PRINTS its verbs and then
# blocks. A reader that waits forever hangs the whole gate on one bad dispatcher, so the verb list
# has to be bounded. The sleep's own output goes to /dev/null: an orphan that inherited the
# captured pipe would hold the harness open long after the dispatcher was killed.
write_slow_help_dispatcher() {
  local fix="$1" seconds="$2" verb
  shift 2
  mkdir -p "$fix/lib"
  {
    cat <<'HEAD'
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

run_verb() { printf 'fixture: %s\n' "$1"; }

usage() {
  cat <<'EOF'
Usage: ./ctl.sh <command>

HEAD
    for verb in "$@"; do
      printf '  %-10s run the %s verb\n' "$verb" "$verb"
    done
    cat <<'MID'
  help       Show this message
EOF
}

case "${1:-help}" in
MID
    for verb in "$@"; do
      printf '  %s) run_verb %s ;;\n' "$verb" "$verb"
    done
    if [[ "$seconds" -gt 0 ]]; then
      printf '  help|"") usage; sleep %s >/dev/null 2>&1 ;;\n' "$seconds"
    else
      printf '  help|"") usage ;;\n'
    fi
    cat <<'TAIL'
  *) printf 'unknown command: %s\n' "$1" >&2; usage; exit 1 ;;
esac
TAIL
  } > "$fix/lib/ctl.sh"
  chmod +x "$fix/lib/ctl.sh"
}

# write_timeout_shim <fix> — a `timeout` that keeps the real tool's semantics and shortens the
# budget, so the hang branch is driven in ~1 second instead of the 10 a dispatcher is allowed.
# It shims the TOOL, never the script under test: the call has to come from ctl.sh for the shim
# to run at all, and a ctl.sh that stopped bounding `help` would leave the hang unbounded — which
# the outer bound in run_validate_bounded turns into a failed assertion instead of a hung suite.
write_timeout_shim() {
  local fix="$1"
  mkdir -p "$fix/bin"
  {
    printf '#!/usr/bin/env bash\n'
    printf '# Drop the duration the caller asked for; keep every other argument.\n'
    printf 'shift\n'
    printf 'exec %s 1 "$@"\n' "$REAL_TIMEOUT"
  } > "$fix/bin/timeout"
  chmod +x "$fix/bin/timeout"
}

# write_legacy_dispatcher <fix> <help-exit-code> <verb>... — the ONE shape today's
# scraper does read (`function usage() {` + an unquoted `cat <<EOF`), so the scraper
# finds no drift in it. `help` PRINTS the usage and THEN exits with the given code:
# a reader that takes the verbs and ignores the exit status sees a healthy script.
write_legacy_dispatcher() {
  local fix="$1" code="$2" verb
  shift 2
  mkdir -p "$fix/lib"
  {
    cat <<'HEAD'
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

run_verb() { printf 'fixture: %s\n' "$1"; }

function usage() {
  cat <<EOF
Usage: ./ctl.sh <command>

HEAD
    for verb in "$@"; do
      printf '  %-10s run the %s verb\n' "$verb" "$verb"
    done
    cat <<'MID'
  help       Show this message
EOF
}

case "${1:-help}" in
MID
    for verb in "$@"; do
      printf '  %s) run_verb %s ;;\n' "$verb" "$verb"
    done
    printf '  help|"") usage; exit %s ;;\n' "$code"
    cat <<'TAIL'
  *) printf 'unknown command: %s\n' "$1" >&2; usage; exit 1 ;;
esac
TAIL
  } > "$fix/lib/ctl.sh"
  chmod +x "$fix/lib/ctl.sh"
}

# ── the harness ─────────────────────────────────────────────────────────────

# run_validate <fix> runs the copied ctl.sh over the fixture and sets OUT and RC.
# cmd_validate calls `exit 1`, so it is run as a separate bash.
run_validate() {
  RC=0
  OUT="$(bash "$1/ctl.sh" validate 2>&1)" || RC=$?
}

# run_validate_bounded <fix> is run_validate with the fixture's bin/ first on PATH and a hard
# outer bound of 30s. The bound is the harness's own safety: it is not the behaviour under test,
# it is what makes an UNBOUNDED help a failed assertion instead of a suite that never returns.
run_validate_bounded() {
  RC=0
  OUT="$(PATH="$1/bin:$PATH" "$REAL_TIMEOUT" 30 bash "$1/ctl.sh" validate 2>&1)" || RC=$?
}

out_has()  { grep -Fq -- "$1" <<< "$OUT"; }
out_hasE() { grep -Eq -- "$1" <<< "$OUT"; }

# assert_validate_ran refuses a vacuous pass: a run that died before the drift check
# proves nothing about drift.
assert_validate_ran() {
  [[ "$RC" -ne 127 ]] || fail "validate could not run — a missing tool (exit 127): $OUT"
  out_has 'checking target/usage drift' ||
    fail "validate never reached the drift check, so nothing under test ran: $OUT"
}

assert_no_drift_reported() {
  ! out_has 'missing from ctl.sh usage' ||
    fail "a target was reported missing from a usage block that documents it: $OUT"
  ! out_has 'missing from project.json targets' ||
    fail "a documented verb was reported missing from targets that declare it: $OUT"
}

# ── the tests ───────────────────────────────────────────────────────────────

# templates/go/http-gateway/ctl.sh holds no usage of its own: `help` delegates to
# template_usage from the sourced templates/_ctl/template.sh. It documents its verbs
# like any other dispatcher, so a documented verb with a matching target is not drift.
t_a_sourced_usage_is_not_drift() {
  local fix verbs=(build test)
  if [[ "$VARIANT" == "counter" ]]; then
    # The sourced usage documents a 3rd verb that no target declares: real drift.
    verbs=(build test deploy)
  fi
  fix="$(new_fixture)"
  write_sourced_dispatcher "$fix" "${verbs[@]}"
  write_project_json "$fix/lib/project.json" build test
  run_validate "$fix"
  assert_validate_ran
  assert_no_drift_reported
  [[ "$RC" -eq 0 ]] || fail "validate exited $RC on a tree that holds no drift: $OUT"
}

# persistence/ctl.sh:43 and clients/go/ctl.sh:44 declare `usage() {` with no `function`
# keyword and quote the heredoc word. Both are ordinary bash, and both document exactly
# the verbs their project.json declares.
t_a_posix_quoted_heredoc_usage_is_not_drift() {
  local fix targets=(generate verify)
  if [[ "$VARIANT" == "counter" ]]; then
    # The usage still documents `verify`, but no target declares it: real drift.
    targets=(generate)
  fi
  fix="$(new_fixture)"
  write_posix_dispatcher "$fix" generate verify
  write_project_json "$fix/lib/project.json" "${targets[@]}"
  run_validate "$fix"
  assert_validate_ran
  assert_no_drift_reported
  [[ "$RC" -eq 0 ]] || fail "validate exited $RC on a tree that holds no drift: $OUT"
}

# The direction that is vacuously green today, and the one that matters most: a verb the
# dispatcher documents AND dispatches, with no target to invoke it through, must be named.
# This is the live defect — templates/go/http-gateway/ctl.sh has 3 of them and the check
# has never said so. A parser that follows a sourced usage could just as easily become
# blind to the real drift, which would be worse than the defect it replaces.
t_a_verb_with_no_target_is_drift() {
  local fix targets=(build)
  if [[ "$VARIANT" == "counter" ]]; then
    # The missing target is declared, so the drift is gone and the test must fail.
    targets=(build openapi)
  fi
  fix="$(new_fixture)"
  write_sourced_dispatcher "$fix" build openapi
  write_project_json "$fix/lib/project.json" "${targets[@]}"
  run_validate "$fix"
  assert_validate_ran
  out_has "usage entry 'openapi' missing from project.json targets" ||
    fail "the documented verb 'openapi' has no target and was not reported: $OUT"
  ! out_has "target 'build' missing from ctl.sh usage" ||
    fail "'build' is documented and declared, yet was reported as drift: $OUT"
  [[ "$RC" -eq 1 ]] || fail "validate exited $RC although a verb has no target: $OUT"
}

# The opposite direction, and the half that produces today's false messages: a target
# with no documented verb must be named, and a target the usage DOES document must not.
t_a_target_with_no_verb_is_drift() {
  local fix verbs=(generate)
  if [[ "$VARIANT" == "counter" ]]; then
    # `verify` becomes documented, so the drift is gone and the test must fail.
    verbs=(generate verify)
  fi
  fix="$(new_fixture)"
  write_posix_dispatcher "$fix" "${verbs[@]}"
  write_project_json "$fix/lib/project.json" generate verify
  run_validate "$fix"
  assert_validate_ran
  out_has "target 'verify' missing from ctl.sh usage" ||
    fail "the target 'verify' is documented nowhere and was not reported: $OUT"
  ! out_has "target 'generate' missing from ctl.sh usage" ||
    fail "'generate' is declared and documented, yet was reported as drift: $OUT"
  [[ "$RC" -eq 1 ]] || fail "validate exited $RC although a target has no verb: $OUT"
}

# Asking the program means the answer can fail. A `help` that exits non-zero is a broken
# dispatcher, and the verb list it printed cannot be trusted, so it is a counted failure
# naming the script — never a silent empty list that makes the drift check vacuous.
t_a_help_that_fails_is_a_counted_failure() {
  local fix code=3
  if [[ "$VARIANT" == "counter" ]]; then
    # `help` succeeds, so there is no failure to report and the test must fail.
    code=0
  fi
  fix="$(new_fixture)"
  write_legacy_dispatcher "$fix" "$code" build
  write_project_json "$fix/lib/project.json" build
  run_validate "$fix"
  assert_validate_ran
  out_hasE "(lib/ctl\.sh.*help|help.*lib/ctl\.sh)" ||
    fail "lib/ctl.sh exits $code from help, and validate never reported it: $OUT"
  [[ "$RC" -eq 1 ]] || fail "validate exited $RC although a dispatcher's help failed: $OUT"
}

# The anti-vacuity guard, and the reason the whole approach is safe: an EMPTY verb list makes the
# usage-to-targets half of the drift loop vacuous, which IS the original defect. So "help said
# nothing" must be a counted failure of its own, never a clean sheet. The fixture documents its
# verbs on STDERR — the drift a real dispatcher could acquire without anyone noticing, since its
# help still looks right on a terminal and still exits 0.
t_a_help_that_documents_no_verbs_is_a_counted_failure() {
  local fix stream=stderr
  if [[ "$VARIANT" == "counter" ]]; then
    # The same verbs on stdout: the list is no longer empty and the test must fail.
    stream=stdout
  fi
  fix="$(new_fixture)"
  write_usage_stream_dispatcher "$fix" "$stream" generate verify
  write_project_json "$fix/lib/project.json" generate verify
  run_validate "$fix"
  assert_validate_ran
  out_hasE "(lib/ctl\.sh.*no verbs|no verbs.*lib/ctl\.sh)" ||
    fail "lib/ctl.sh printed its verbs on $stream, so help yielded none, and validate never said so: $OUT"
  # Without the guard the empty list turns every declared target into invented drift, which names
  # the wrong file and hides the real fault.
  ! out_has "target 'generate' missing from ctl.sh usage" ||
    fail "an empty verb list was reported as drift in project.json instead of as a broken help: $OUT"
  [[ "$RC" -eq 1 ]] || fail "validate exited $RC although a dispatcher documented no verbs: $OUT"
}

# A dispatcher that blocks must not block the gate. `help` here PRINTS a correct verb list and
# THEN hangs, so a reader that takes the verbs and ignores how the process ended sees a healthy
# script. The fixture puts a `timeout` on PATH that keeps the real tool and shortens its budget
# to 1 second, so the branch is driven for real in about a second instead of ten.
t_a_help_that_hangs_is_a_counted_failure() {
  local fix seconds=600
  if [[ "$VARIANT" == "counter" ]]; then
    # help returns at once, nothing is killed, and the test must fail.
    seconds=0
  fi
  fix="$(new_fixture)"
  write_timeout_shim "$fix"
  write_slow_help_dispatcher "$fix" "$seconds" generate
  write_project_json "$fix/lib/project.json" generate
  run_validate_bounded "$fix"
  [[ "$RC" -ne 124 ]] ||
    fail "validate did not return within 30s: the dispatcher's help is not bounded at all: $OUT"
  assert_validate_ran
  out_hasE "(lib/ctl\.sh.*124|124.*lib/ctl\.sh)" ||
    fail "lib/ctl.sh hangs in help and validate never reported the timeout: $OUT"
  [[ "$RC" -eq 1 ]] || fail "validate exited $RC although a dispatcher's help had to be killed: $OUT"
}

# The shell suites are the only mechanical proof of the ctl verbs, and nothing checks
# the suites themselves: find_all_ctl_scripts covers ctl.sh and <lang>/_ctl/*.sh only.
# A *_test.sh can therefore carry a real finding, exit 0, and be reported as ok.
# shellcheck disable=SC2016 # the emitted script must hold a literal $WORKDIR, not its value
t_a_test_script_is_shellchecked() {
  local fix cd_line='cd "$WORKDIR"'
  if [[ "$VARIANT" == "counter" ]]; then
    # The cd is guarded, shellcheck is clean, and the test must fail.
    cd_line='cd "$WORKDIR" || exit 1'
  fi
  fix="$(new_fixture)"
  write_posix_dispatcher "$fix" generate
  write_project_json "$fix/lib/project.json" generate
  # No `set -e`: shellcheck suppresses SC2164 when errexit is on, and a suite without
  # errexit is exactly the one that reaches `exit 0` while its cd silently failed.
  {
    printf '#!/usr/bin/env bash\n#\n'
    printf '# A suite that EXITS 0 while carrying an SC2164 finding.\n'
    printf 'WORKDIR="$(mktemp -d)"\n'
    printf '%s\n' "$cd_line"
    printf 'printf "probe: ok\\n"\n'
    printf 'rm -rf "$WORKDIR"\n'
    printf 'exit 0\n'
  } > "$fix/probe_test.sh"
  run_validate "$fix"
  assert_validate_ran
  out_has 'ok: probe_test.sh' ||
    fail "the fixture suite did not exit 0, so its shellcheck finding is not the thing under test: $OUT"
  out_hasE 'shellcheck.*probe_test\.sh' ||
    fail "probe_test.sh carries an SC2164 finding and validate reported no shellcheck failure: $OUT"
  [[ "$RC" -eq 1 ]] || fail "validate exited $RC although a test script fails shellcheck: $OUT"
}

TESTS=(
  t_a_sourced_usage_is_not_drift
  t_a_posix_quoted_heredoc_usage_is_not_drift
  t_a_verb_with_no_target_is_drift
  t_a_target_with_no_verb_is_drift
  t_a_help_that_fails_is_a_counted_failure
  t_a_help_that_documents_no_verbs_is_a_counted_failure
  t_a_help_that_hangs_is_a_counted_failure
  t_a_test_script_is_shellchecked
)

# ── the stimulus tables ─────────────────────────────────────────────────────

# stimulus_for <test> — what phase 1 drives the test with. Every test builds the tree it
# describes; the table exists so a test can never run without a declared stimulus.
stimulus_for() {
  case "$1" in
    t_a_sourced_usage_is_not_drift|\
    t_a_posix_quoted_heredoc_usage_is_not_drift|\
    t_a_verb_with_no_target_is_drift|\
    t_a_target_with_no_verb_is_drift|\
    t_a_help_that_fails_is_a_counted_failure|\
    t_a_help_that_documents_no_verbs_is_a_counted_failure|\
    t_a_help_that_hangs_is_a_counted_failure|\
    t_a_test_script_is_shellchecked) printf 'good' ;;
    *) die "no phase-1 stimulus is declared for $1" ;;
  esac
}

# counter_for <test> — the single change that must BREAK the test. Each is a real edit to
# the fixture, never a stubbed answer, so what it proves is what a reviewer would do.
counter_for() {
  case "$1" in
    t_a_sourced_usage_is_not_drift)
      printf "counter:the sourced usage documents 'deploy', which no target declares" ;;
    t_a_posix_quoted_heredoc_usage_is_not_drift)
      printf "counter:the 'verify' target is dropped while the usage still documents it" ;;
    t_a_verb_with_no_target_is_drift)
      printf "counter:the missing 'openapi' target is added to project.json" ;;
    t_a_target_with_no_verb_is_drift)
      printf "counter:the usage is extended to document 'verify'" ;;
    t_a_help_that_fails_is_a_counted_failure)
      printf 'counter:help exits 0 instead of 3' ;;
    t_a_help_that_documents_no_verbs_is_a_counted_failure)
      printf 'counter:the same usage is printed on stdout instead of stderr' ;;
    t_a_help_that_hangs_is_a_counted_failure)
      printf 'counter:help returns at once instead of blocking' ;;
    t_a_test_script_is_shellchecked)
      printf 'counter:the cd in probe_test.sh is guarded, so shellcheck is clean' ;;
    *) die "no counter-stimulus is declared for $1; every test must state what makes it fail" ;;
  esac
}

# apply <spec> points the next run at the named stimulus. It returns 1 on a `none:` spec
# so the driver reports the reason instead of silently skipping.
apply() {
  case "$1" in
    good)     VARIANT="good" ;;
    counter:*) VARIANT="counter" ;;
    none:*)   return 1 ;;
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

info "phase 1 — behaviour: ${#TESTS[@]} test(s) against $CTL"
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
    bad "$t still passed under ${spec#counter:}; it does not read what it claims to read"
    failures=$((failures + 1))
  else
    ok "$t fails when ${spec#counter:}"
    proven=$((proven + 1))
  fi
done

if [[ "$failures" -ne 0 ]]; then
  die "$failures failure(s) across both phases"
fi
# The summary is COUNTED, never asserted: a summary that overstates its own rigour is the
# defect this suite exists to catch.
info "${#TESTS[@]} test(s) hold; $proven of ${#TESTS[@]} proven able to fail; $unproven stated no counter"
