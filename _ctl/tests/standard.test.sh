#!/usr/bin/env bash
#
# _ctl/tests/standard.test.sh — _ctl/standard.sh, the PORTABLE core of the
# ctl.sh standard, and the one-home rule that makes it a standard rather than a
# fifth copy.
#
# Static and hermetic: this file reads files and runs short probe scripts in
# fresh `bash` processes with a stub `docker` first on PATH. It starts no
# container, it calls no daemon and it reaches no network, so it runs
# identically on a laptop and on a CI runner — and it runs in the PULL REQUEST
# gate.
#
# ============================================================================
# THE DEFECT
# ============================================================================
#
# Four repositories — eden, libs, infrastructure and this one — each carry their
# own spelling of the same four loggers and the same tool gate. The standard
# exists as PRACTICE in four copies and as a rule nowhere, so the copies drifted
# and nothing could report it:
#
#   - `_ctl/lib.sh` defines log_info / log_warn / log_error and require_cmd, and
#     defines NO log_success at all (measured 2026-08-26: 0 occurrences of the
#     name anywhere in this repository).
#   - `require_cmd` here uses `command -v`, which reports a shell FUNCTION as a
#     present tool. `gophersys/libs` `.ci/ctl.sh:64-83` already moved to
#     `type -t` and states the measurement: with a `cictl()` function injected by
#     `export -f`, the tier printed git's own `fatal:` and still exited 0 with
#     "all 1 affected project(s) green". A function has a BODY, and only its last
#     command's status survives — so a gate that reads the TOOL's exit status
#     reads a shell body's instead. This file holds that reasoning here.
#   - `_ctl/lib.sh` cannot be sourced by a consumer that has configured nothing:
#     line 55 is `: "${PROJECT_ROOT:?...}"`, which is CORRECT for this
#     repository's dispatchers and fatal for anybody who wants only the loggers.
#     Measured: `bash -c 'unset PROJECT_ROOT; source _ctl/lib.sh'` exits 1.
#
# `_ctl/standard.sh` is the answer: C1 (`set -Eeuo pipefail`, `IFS=$'\n\t'`), C4
# (the four printf loggers, warn and error on stderr), C5 (`require_cmd` exiting
# 127 and naming EVERY missing tool), I7 (a repository-root finder that walks up
# to a MARKER FILE) — and NO PROJECT_ROOT assertion, so it sources unconfigured.
#
# ============================================================================
# THE CONTRACT THIS FILE FIXES, BECAUSE A TEST CANNOT ASK FOR A SHAPE
# ============================================================================
#
# Every name and status below is a decision this file makes and the
# implementation must satisfy. They are written as literals: a test that reads
# the value it checks out of the file under test agrees with a wrong value too.
#
#   log_info <text>       stdout
#   log_warn <text>       stderr
#   log_error <text>      stderr
#   log_success <text>    stdout
#   require_cmd <tool>... exit 127 naming EVERY tool that is not an executable
#                         FILE. A function, an alias and a builtin of that name
#                         do not satisfy it.
#   find_repository_root [start-directory]
#                         prints the first ancestor of <start-directory>
#                         (default $PWD) that holds a `.git` entry and exits 0.
#                         `.git` is a DIRECTORY in a normal clone and a FILE in a
#                         submodule and in a worktree — this repository is
#                         checked out both ways, so both must answer.
#                         With no marker up to `/`: NOTHING on stdout, a message
#                         on stderr, and a non-zero status.
#
# ============================================================================
# THE I7 FAILURE MODE THIS FILE IS WRITTEN AGAINST
# ============================================================================
#
# `iotea-archive/libs/bash/source.sh:17-18` is the shape:
#
#     WORKSPACE_ROOT=$(find_workspace_root)
#     if [ $? -ne 0 ]; then
#
# A root finder that returned 0 with an empty answer, or printed a path it had
# not verified, would sail through that guard, and every path built from
# WORKSPACE_ROOT would then be wrong in a way no line reports. So the not-found
# case is asserted in exactly that caller shape — `set +e`, assign, read `$?`,
# `set -e` — and it asserts BOTH halves: a non-zero status AND an empty answer.
# One half alone passes on the defect.
#
# (What the blueprint says about that line is refuted by measurement and the
# refutation is kept, because it changes what the test must assert. It reads
# "checks `$?` after an assignment, so its guard can never fire". On bash 5.3
# `V=$(false); echo $?` prints 1 — a PLAIN assignment does carry the
# substitution's status, and that guard does fire. The never-fires shape is
# `local V=$(false)`, which reports `local`'s own status, 0. The bug class is
# real and the cited line is not an instance of it, so this file asserts the
# PROPERTY of the function rather than reproducing a caller bug.)
#
# ============================================================================
# WHAT IS A CONSERVATION GUARD HERE, STATED RATHER THAN FAKED
# ============================================================================
#
# Two groups below are GREEN from the first run, before `_ctl/standard.sh`
# exists. They are stated rather than dressed up as red:
#
#   `counter_stimulus_*`   — each one proves the STIMULUS of the check beside it
#                            is real. `_ctl/lib.sh` REFUSES to source
#                            unconfigured; if that ever passes, the
#                            unconfigured-source check above it proves nothing,
#                            because sourcing anything would then succeed.
#   `every_lib_consumer_*` — the in-repo scripts that source `_ctl/lib.sh` still
#                            load and still reach a line of their own. Deleting
#                            lib.sh's four copies is what could break them, and
#                            `log_info: command not found` under
#                            `set -Eeuo pipefail` is what that looks like. It is
#                            a CONSERVATION guard: it goes red on the change
#                            that gets the deletion half wrong.
#
# `no_second_home_defines_a_symbol_the_standard_owns` is NOT one of them. It is
# RED today and names `_ctl/lib.sh`'s 4 live definitions — the deletion half of
# the one-home rule is work this feature owes, not a property it conserves.
#
# Everything else in this file is RED until `_ctl/standard.sh` exists.
#
# ============================================================================
# WHAT THIS FILE DOES NOT PROVE
# ============================================================================
#
# That eden, libs and infrastructure source it. They are separate repositories
# and `.devcontainer` is a submodule of eden alone, so no check here can reach
# them. It also does not prove the standard is WRITTEN DOWN correctly in
# docs/ctl-standard.md — prose is not executable, and a test that grepped a
# document for its own headings would agree with a wrong document.
#
# Usage: bash _ctl/tests/standard.test.sh
#
set -Eeuo pipefail
IFS=$'\n\t'

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
PROJECT_ROOT="$REPO_ROOT"

# The logging lives in _ctl/lib.sh, 1 time only — the same source line every
# other script in this repository uses. It is deliberately the OLD home: this
# file must run before _ctl/standard.sh exists, and a test that could not load
# until its subject landed would be a test nobody could watch fail.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../lib.sh
source "$REPO_ROOT/_ctl/lib.sh"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=harness.sh
source "$TESTS_DIR/harness.sh"

TEST_NAME="standard.test.sh"

STANDARD_RELATIVE="_ctl/standard.sh"
LIB_RELATIVE="_ctl/lib.sh"
STANDARD_SH="${REPO_ROOT}/${STANDARD_RELATIVE}"
LIB_SH="${REPO_ROOT}/${LIB_RELATIVE}"
STUB_BIN="$TESTS_DIR/stubs"

# The five symbols _ctl/standard.sh owns. Named one by one, because the
# one-home rule is a statement about each of them and a loop over a glob of
# "everything that looks like a logger" would agree with a file that defines
# none of them.
STANDARD_SYMBOLS=("log_info" "log_warn" "log_error" "log_success" "require_cmd")

# Every file of this repository that may NOT define one of those five. The list
# is the 8 in-repo consumers of _ctl/lib.sh named in its own header, plus
# _ctl/lib.sh itself, plus _ctl/generate.sh which sources the library through
# ctl.sh. Named and not globbed, for the reason platform-policy.test.sh gives:
# a glob that stops matching leaves a green result that read nothing.
SECOND_HOME_CANDIDATES=(
  "_ctl/lib.sh"
  "_ctl/generate.sh"
  "ctl.sh"
  ".ci/ctl.sh"
  ".ci/smoke.sh"
  ".ci/affected.sh"
  ".ci/notify-failure.sh"
  ".ci/buildx-node.sh"
  ".ci/mirror-buildkit.sh"
  "_build/resolve-upstream.sh"
)

# The 8 scripts _ctl/lib.sh's header names as its consumers, with an argv that
# reaches a line of the script's OWN and stops there, and the status that argv
# produces today. Measured 2026-08-26 with the stub docker first on PATH.
#
# `.ci/buildx-node.sh` and `.ci/mirror-buildkit.sh` carry no such argv — both go
# straight to docker at load, and buildx-node.sh then waits 60s for a buildkitd
# that the stub never starts. They are covered by the FILE half of the one-home
# rule and by nothing dynamic, and this sentence is that admission.
CONSUMER_PROBES=(
  "ctl.sh|help|0"
  ".ci/ctl.sh|help|0"
  ".ci/smoke.sh||2"
  ".ci/affected.sh||2"
  ".ci/notify-failure.sh||1"
  "_build/resolve-upstream.sh||2"
)

# The payloads the logger-stream check writes. Unique strings, so
# assert_not_contains has something to be wrong about: the `[info]` prefix
# appears in more than one logger's neighbourhood and would make the negative
# half of every stream assertion unfalsifiable.
PAYLOAD_INFO="payload-info-4f1a"
PAYLOAD_WARN="payload-warn-9c3e"
PAYLOAD_ERROR="payload-error-2b7d"
PAYLOAD_SUCCESS="payload-success-6e58"

# The tool require_cmd must ACCEPT: a real executable file, written by this test
# into a directory it puts first on PATH. A host tool would make the check a
# statement about the machine.
PRESENT_TOOL="standard-probe-tool"

# The tools require_cmd must REFUSE. Two of them, because "names all of them" is
# the clause, and one missing tool cannot tell a reader whether the loop stopped
# at the first.
ABSENT_TOOL_ONE="definitely-not-a-tool"
ABSENT_TOOL_TWO="also-definitely-not-a-tool"

# The line every refusal probe writes AFTER the gate, and no refusal check may
# ever find. A gate that reported a missing tool and returned would print it.
CONTINUATION_MARKER="the-gate-did-not-stop"

# The shadow case. `sqlc` on purpose: it is the tool eden's persistence gate
# demands, PR-A pins it, and after it is installed a function of that name still
# shadows the binary — `type -t` reports what the next call would really run, so
# this case stays able to fail on an image that HAS sqlc.
SHADOW_TOOL="sqlc"

SCRATCH="$(mktemp -d)"
function cleanup_scratch() {
  rm -rf "$SCRATCH"
}
trap cleanup_scratch EXIT

PROBE_BIN="${SCRATCH}/bin"
PROBE_STDERR_FILE="${SCRATCH}/stderr"
mkdir -p "$PROBE_BIN"
printf '#!/usr/bin/env bash\nprintf "the probe tool\\n"\n' > "${PROBE_BIN}/${PRESENT_TOOL}"
chmod 755 "${PROBE_BIN}/${PRESENT_TOOL}"

# The stub docker goes first even though nothing here needs docker, so an
# unexpected docker call reaches a stub instead of a daemon — the shape
# tripwire.test.sh uses.
PROBE_PATH="${PROBE_BIN}:${STUB_BIN}:${PATH}"

# ---------------------------------------------------------------------------
# The probe runner.
# ---------------------------------------------------------------------------

PROBE_STATUS=0
PROBE_STDOUT=""
PROBE_STDERR=""
PROBE_BOTH=""

# write_probe <name> — write the script on stdin to the scratch directory. A
# heredoc with a QUOTED delimiter, so the text below reaches bash unexpanded,
# and the linter reads it as data rather than as this file's own code.
function write_probe() {
  cat > "${SCRATCH}/${1}.sh"
}

# run_probe <name> [KEY=VALUE ...] — run one probe in a fresh bash.
#
# stdout and stderr are kept APART, because half the assertions in this file are
# about which of the two a logger wrote to. PROBE_BOTH is the join, for the
# checks that only need to find a string.
function run_probe() {
  local name="$1"
  shift
  PROBE_STATUS=0
  PROBE_STDOUT="$(env \
    PATH="$PROBE_PATH" \
    STANDARD_SH="$STANDARD_SH" \
    LIB_SH="$LIB_SH" \
    "$@" bash "${SCRATCH}/${name}.sh" 2>"$PROBE_STDERR_FILE")" || PROBE_STATUS=$?
  PROBE_STDERR="$(<"$PROBE_STDERR_FILE")"
  PROBE_BOTH="${PROBE_STDOUT}
${PROBE_STDERR}"
}

# definition_count <file> <symbol> — how many times a file DEFINES a function of
# that name, in either spelling (`function name()` and `name()`).
#
# The bracket classes are not decoration. `\\(` in an awk `-v` assignment is an
# unknown escape, awk drops the backslash, and the regex then ends in an EMPTY
# GROUP that matches every line beginning with the symbol's name — measured here
# on the first run, which reported 8 files as second homes of log_info. `[(][)]`
# survives every layer of quoting.
function definition_count() {
  local file="$1" symbol="$2"
  if [[ ! -r "$file" ]]; then
    printf 'unreadable'
    return 0
  fi
  awk -v re="^[[:space:]]*(function[[:space:]]+)?${symbol}[[:space:]]*[(][)]" \
    '$0 ~ re { n++ } END { print n + 0 }' "$file"
}

# assert_gate_refused <check name> <wanted status> <needle> [evidence...]
#
# THREE things as 1 check — the STATUS, the NAME in the message, and the ABSENCE
# of the line the probe writes after the gate. This is the shape
# functional-groups.test.sh argues for and states the reason: split into 3, a
# reader can see 2 of them green and believe the gate is guarded. It is not an
# abstract worry here. Every negative half of this file passed VACUOUSLY on its
# first run — `_ctl/standard.sh` was absent, the probe printed nothing at all,
# and "the output must NOT name X" is true of an empty string. 6 checks read
# PASS while asserting nothing whatsoever.
function assert_gate_refused() {
  local name="$1" want_status="$2" needle="$3"
  shift 3
  if [[ "$PROBE_STATUS" -ne "$want_status" ]]; then
    fail_check "$name" \
      "want: exit ${want_status}, with a message naming ${needle}" \
      "got:  ${PROBE_STATUS}" "$@" "output was:" "$PROBE_BOTH"
  elif ! grep -qF -- "$needle" <<< "$PROBE_STDERR"; then
    fail_check "$name" \
      "the run exited ${want_status}, but its STDERR never names ${needle}" \
      "a caller that cannot read which tool is missing has been told nothing" \
      "$@" "stderr was:" "${PROBE_STDERR:-<nothing>}"
  elif grep -qF -- "$CONTINUATION_MARKER" <<< "$PROBE_STDOUT"; then
    fail_check "$name" \
      "the gate reported the tool and the probe kept running" \
      "a gate that names a defect and returns has named it and not stopped it" \
      "$@" "stdout was:" "$PROBE_STDOUT"
  else
    pass_check "$name"
  fi
}

# assert_on_stream <check name> <payload> <stdout|stderr> [evidence...]
#
# 1 check per logger, both directions, for the same reason. `log_warn` writing
# to BOTH streams passes a positive-only half, and a caller piping stdout to a
# file then gets every warning twice.
function assert_on_stream() {
  local name="$1" payload="$2" want="$3"
  shift 3
  local on_stdout="no" on_stderr="no"
  if grep -qF -- "$payload" <<< "$PROBE_STDOUT"; then on_stdout="yes"; fi
  if grep -qF -- "$payload" <<< "$PROBE_STDERR"; then on_stderr="yes"; fi
  local want_stdout="no" want_stderr="yes"
  if [[ "$want" == "stdout" ]]; then
    want_stdout="yes"
    want_stderr="no"
  fi
  if [[ "$on_stdout" == "$want_stdout" && "$on_stderr" == "$want_stderr" ]]; then
    pass_check "$name"
  else
    fail_check "$name" \
      "want: on stdout=${want_stdout}, on stderr=${want_stderr}" \
      "got:  on stdout=${on_stdout}, on stderr=${on_stderr}" \
      "the payload is ${payload}" "$@" \
      "stdout was:" "${PROBE_STDOUT:-<nothing>}" \
      "stderr was:" "${PROBE_STDERR:-<nothing>}"
  fi
}

printf '=== RUN  %s\n' "$TEST_NAME"

# ===========================================================================
# 0. THE SUBJECT, AND THE HARNESS THIS FILE STANDS ON
# ===========================================================================
# Every check below is a run of _ctl/standard.sh. Its absence is the whole
# feature, so it is a check with a name rather than a wall of identical
# failures with no diagnosis between them.
if [[ -r "$STANDARD_SH" ]]; then
  pass_check "the_shared_standard_file_exists"
else
  fail_check "the_shared_standard_file_exists" \
    "want: a readable file at ${STANDARD_RELATIVE}" \
    "got:  no file" \
    "it is the PORTABLE core of the ctl.sh standard: C1, the four C4 loggers," \
    "the C5 tool gate and the I7 root finder, with NO PROJECT_ROOT assertion" \
    "every check below runs it, so every one of them is red until it lands"
fi

if [[ -x "${PROBE_BIN}/${PRESENT_TOOL}" ]]; then
  pass_check "the_probe_tool_is_executable"
else
  fail_check "the_probe_tool_is_executable" \
    "not executable: ${PROBE_BIN}/${PRESENT_TOOL}" \
    "without it, require_cmd's ACCEPT case would be a statement about the host"
fi

if [[ -x "${STUB_BIN}/docker" ]]; then
  pass_check "the_docker_stub_is_executable"
else
  fail_check "the_docker_stub_is_executable" \
    "not executable: ${STUB_BIN}/docker" \
    "without it the real docker answers, and nothing below is hermetic"
fi

# ===========================================================================
# 1. IT SOURCES WITH NOTHING CONFIGURED
# ===========================================================================
# This is the property the whole standard rests on: a consumer that wants only
# the loggers must be able to take them without first inventing a PROJECT_ROOT.
# EVERY probe below opens with `set -Eeuo pipefail`, and that is load-bearing
# rather than habit. Without it a failed `source` is a non-fatal status, the
# probe runs on into the checks with none of its subject defined, and the script
# exits with the status of its LAST line — a `printf` that always succeeds. The
# first run of this file read PASS on 6 checks that way.
write_probe source-standard-unconfigured <<'PROBE'
set -Eeuo pipefail
unset PROJECT_ROOT REPO_ROOT IMAGE_NAME IMAGE_PLATFORMS
source "$STANDARD_SH"
PROBE

run_probe source-standard-unconfigured
assert_equal "the_standard_sources_with_PROJECT_ROOT_unset" "0" "$PROBE_STATUS" \
  "a consumer that has configured nothing must still be able to take the standard" \
  "output was:" "$PROBE_BOTH"

# The counter-stimulus, and it is GREEN today: _ctl/lib.sh:55 refuses. If this
# ever passes, the check above proves nothing, because sourcing ANY file would
# then succeed and the difference the standard exists for would be invisible.
write_probe source-lib-unconfigured <<'PROBE'
set -Eeuo pipefail
unset PROJECT_ROOT REPO_ROOT IMAGE_NAME IMAGE_PLATFORMS
source "$LIB_SH"
PROBE

run_probe source-lib-unconfigured
assert_status_nonzero "counter_stimulus_lib_sh_refuses_to_source_unconfigured" "$PROBE_STATUS" \
  "_ctl/lib.sh:55 is \`: \${PROJECT_ROOT:?...}\` and that is CORRECT for a dispatcher" \
  "it is also why a portable core had to be a second file" \
  "output was:" "$PROBE_BOTH"
assert_contains "counter_stimulus_lib_sh_names_PROJECT_ROOT_when_it_refuses" \
  "$PROBE_BOTH" "PROJECT_ROOT" \
  "a refusal that does not name the variable tells the caller nothing"

# ===========================================================================
# 2. THE C5 TOOL GATE
# ===========================================================================
write_probe require-cmd-one-missing <<'PROBE'
set -Eeuo pipefail
unset PROJECT_ROOT REPO_ROOT
source "$STANDARD_SH"
require_cmd "$ABSENT_TOOL_ONE"
printf '%s\n' "$CONTINUATION_MARKER"
PROBE

run_probe require-cmd-one-missing \
  ABSENT_TOOL_ONE="$ABSENT_TOOL_ONE" CONTINUATION_MARKER="$CONTINUATION_MARKER"
assert_gate_refused "require_cmd_exits_127_and_names_the_missing_tool" \
  "127" "$ABSENT_TOOL_ONE" \
  "127 is the tool-gate status of this repository — guard.test.sh already pins it for buildx" \
  "1 would read as a policy refusal, and a caller cannot tell the 2 apart"

write_probe require-cmd-many-missing <<'PROBE'
set -Eeuo pipefail
unset PROJECT_ROOT REPO_ROOT
source "$STANDARD_SH"
require_cmd "$ABSENT_TOOL_ONE" "$ABSENT_TOOL_TWO"
printf '%s\n' "$CONTINUATION_MARKER"
PROBE

run_probe require-cmd-many-missing \
  ABSENT_TOOL_ONE="$ABSENT_TOOL_ONE" ABSENT_TOOL_TWO="$ABSENT_TOOL_TWO" \
  CONTINUATION_MARKER="$CONTINUATION_MARKER"
assert_gate_refused "require_cmd_names_the_first_of_several_missing_tools" \
  "127" "$ABSENT_TOOL_ONE"
assert_gate_refused "require_cmd_names_the_last_of_several_missing_tools" \
  "127" "$ABSENT_TOOL_TWO" \
  "a gate that stops at the first absent tool sends the operator round the loop once per tool" \
  "the clause is EVERY missing tool in 1 message, and only the second name can prove it"

write_probe require-cmd-present <<'PROBE'
set -Eeuo pipefail
unset PROJECT_ROOT REPO_ROOT
source "$STANDARD_SH"
require_cmd "$PRESENT_TOOL"
printf 'accepted\n'
PROBE

run_probe require-cmd-present PRESENT_TOOL="$PRESENT_TOOL"
assert_equal "require_cmd_accepts_a_tool_that_is_an_executable_file" "0" "$PROBE_STATUS" \
  "the tool is a file this test wrote into a directory it put first on PATH" \
  "output was:" "$PROBE_BOTH"
assert_contains "require_cmd_returns_and_lets_the_caller_continue" "$PROBE_STDOUT" "accepted" \
  "a gate that exits 0 without returning would stop every caller after the first check"

# -------- the shadow case: a FUNCTION is not a tool -------------------------
# gophersys/libs .ci/ctl.sh:64-83 measured this and moved to `type -t`. The
# reason is not style: the tier reads the TOOL's exit status, and a shell
# function has a BODY whose earlier failures are discarded — a `cictl()` whose
# first command failed and whose last succeeded made the tier print git's own
# `fatal:` and exit 0 with "all 1 affected project(s) green".
#
# `command -v` — what _ctl/lib.sh:200 uses today — reports that function as a
# present tool. So this case is the discriminator between the two readers, and
# it fails on the CURRENT implementation for the reason the feature is about.
# The function is defined and probed BEFORE the source, so the counter-stimulus
# reports on the shell it is about even on a run where the source itself fails.
# After the source there would be no such run to report on.
write_probe require-cmd-function <<'PROBE'
set -Eeuo pipefail
unset PROJECT_ROOT REPO_ROOT
function sqlc() { return 0; }
printf 'shadow-probe=%s\n' "$(type -t "$SHADOW_TOOL")"
source "$STANDARD_SH"
require_cmd "$SHADOW_TOOL"
printf '%s\n' "$CONTINUATION_MARKER"
PROBE

run_probe require-cmd-function \
  SHADOW_TOOL="$SHADOW_TOOL" CONTINUATION_MARKER="$CONTINUATION_MARKER"
assert_contains "counter_stimulus_the_shadowing_function_really_is_defined" \
  "$PROBE_STDOUT" "shadow-probe=function" \
  "without this line the refusal below could come from a probe that defined nothing," \
  "and the check would pass while asserting nothing about shadowing"
assert_gate_refused "require_cmd_refuses_a_shell_function_of_the_tools_name" \
  "127" "$SHADOW_TOOL" \
  "command -v reports a function as present; type -t names what the next call would RUN" \
  "the gate reads the TOOL's exit status, and a shell body drops every status but its last"

# ===========================================================================
# 3. THE C4 LOGGERS — ALL FOUR, ON THE RIGHT STREAM
# ===========================================================================
# SYMBOL_LIST is NEWLINE-separated, never space-separated. C1 sets
# IFS=$'\n\t', so after the source a `for` over a space-separated string reads
# the whole string as 1 word and every symbol then looks undefined —
# version-coverage.test.sh:194-196 records the same measurement about its own
# class list.
write_probe symbols-defined <<'PROBE'
set -Eeuo pipefail
unset PROJECT_ROOT REPO_ROOT
source "$STANDARD_SH"
for symbol in $SYMBOL_LIST; do
  printf '%s=%s\n' "$symbol" "$(type -t "$symbol")"
done
PROBE

SYMBOL_LIST_TEXT="$(printf '%s\n' "${STANDARD_SYMBOLS[@]}")"

run_probe symbols-defined SYMBOL_LIST="$SYMBOL_LIST_TEXT"
for symbol in "${STANDARD_SYMBOLS[@]}"; do
  assert_contains "the_standard_defines_${symbol}" "$PROBE_STDOUT" "${symbol}=function" \
    "sourcing ${STANDARD_RELATIVE} must leave this name callable" \
    "log_success is the one that exists NOWHERE in this repository today (measured 2026-08-26)"
done

write_probe logger-streams <<'PROBE'
set -Eeuo pipefail
unset PROJECT_ROOT REPO_ROOT
source "$STANDARD_SH"
log_info    "$PAYLOAD_INFO"
log_warn    "$PAYLOAD_WARN"
log_error   "$PAYLOAD_ERROR"
log_success "$PAYLOAD_SUCCESS"
PROBE

run_probe logger-streams \
  PAYLOAD_INFO="$PAYLOAD_INFO" PAYLOAD_WARN="$PAYLOAD_WARN" \
  PAYLOAD_ERROR="$PAYLOAD_ERROR" PAYLOAD_SUCCESS="$PAYLOAD_SUCCESS"

assert_equal "the_four_loggers_all_run_without_error" "0" "$PROBE_STATUS" \
  "output was:" "$PROBE_BOTH"

assert_on_stream "log_info_writes_to_stdout_and_only_stdout" "$PAYLOAD_INFO" "stdout"
assert_on_stream "log_success_writes_to_stdout_and_only_stdout" "$PAYLOAD_SUCCESS" "stdout"
assert_on_stream "log_warn_writes_to_stderr_and_only_stderr" "$PAYLOAD_WARN" "stderr" \
  "a warning on stdout is a warning that vanishes into a command substitution"
assert_on_stream "log_error_writes_to_stderr_and_only_stderr" "$PAYLOAD_ERROR" "stderr"

# ===========================================================================
# 4. I7 — THE ROOT FINDER, BY MARKER AND NEVER BY A COUNTED ../../..
# ===========================================================================
# Two trees, because `.git` takes two shapes and this repository is checked out
# in both: a DIRECTORY in a normal clone, a FILE in a submodule and in a
# worktree. The worktree this test runs in has `.git` as a FILE.
MARKER_FILE_ROOT="${SCRATCH}/marker-as-file"
MARKER_DIRECTORY_ROOT="${SCRATCH}/marker-as-directory"
NO_MARKER_ROOT="${SCRATCH}/no-marker"
DEEP_SUFFIX="one/two/three/four/five"

mkdir -p "${MARKER_FILE_ROOT}/${DEEP_SUFFIX}"
printf 'gitdir: /nowhere/that/matters\n' > "${MARKER_FILE_ROOT}/.git"
mkdir -p "${MARKER_DIRECTORY_ROOT}/${DEEP_SUFFIX}" "${MARKER_DIRECTORY_ROOT}/.git"
mkdir -p "${NO_MARKER_ROOT}/${DEEP_SUFFIX}"

# The expected answers. The probe enters its start directory with `cd -P`, so
# $PWD there is the PHYSICAL path and these must be read the same way: `mktemp
# -d` answers under /var on a mac, /var is a symlink to /private/var, and
# comparing a resolved path against an unresolved one would fail for a reason
# this file says nothing about.
MARKER_FILE_ROOT_RESOLVED="$(cd "$MARKER_FILE_ROOT" && pwd -P)"
MARKER_DIRECTORY_ROOT_RESOLVED="$(cd "$MARKER_DIRECTORY_ROOT" && pwd -P)"

# The not-found case is only a real stimulus while nothing above the scratch
# tree carries a marker. Under a `/tmp` that was itself inside a checkout, the
# finder would correctly answer with that checkout and the check would report a
# defect that is not there.
marker_above=""
scan_directory="$NO_MARKER_ROOT"
while [[ "$scan_directory" != "/" ]]; do
  if [[ -e "${scan_directory}/.git" ]]; then
    marker_above="${marker_above:+${marker_above}
}${scan_directory}/.git"
  fi
  scan_directory="$(dirname "$scan_directory")"
done
if [[ -z "$marker_above" ]]; then
  pass_check "counter_stimulus_the_no_marker_tree_really_has_no_marker_above_it"
else
  fail_check "counter_stimulus_the_no_marker_tree_really_has_no_marker_above_it" \
    "these markers sit above the scratch tree, so the not-found case is not a stimulus:" \
    "$marker_above" \
    "the finder would answer correctly and the check below would report a defect that is not there"
fi

write_probe root-finder-found <<'PROBE'
set -Eeuo pipefail
unset PROJECT_ROOT REPO_ROOT
source "$STANDARD_SH"
cd -P "$PROBE_START"
find_repository_root
PROBE

run_probe root-finder-found PROBE_START="${MARKER_FILE_ROOT}/${DEEP_SUFFIX}"
assert_equal "the_root_finder_walks_up_to_a_marker_FILE_from_a_deep_subdirectory" \
  "$MARKER_FILE_ROOT_RESOLVED" "$PROBE_STDOUT" \
  "5 levels down, and the answer must be the root — a counted ../../.. is right for exactly" \
  "one caller and wrong for the next one somebody adds" \
  "a submodule and a worktree both carry .git as a FILE, and this repository is both" \
  "the run exited ${PROBE_STATUS}; stderr held:" "${PROBE_STDERR:-<nothing>}"

run_probe root-finder-found PROBE_START="${MARKER_DIRECTORY_ROOT}/${DEEP_SUFFIX}"
assert_equal "the_root_finder_walks_up_to_a_marker_DIRECTORY_from_a_deep_subdirectory" \
  "$MARKER_DIRECTORY_ROOT_RESOLVED" "$PROBE_STDOUT" \
  ".git is a DIRECTORY in a normal clone, and a reader written for the worktree shape alone" \
  "would answer nothing here" \
  "the run exited ${PROBE_STATUS}; stderr held:" "${PROBE_STDERR:-<nothing>}"

# The failure case, in the exact caller shape iotea's source.sh:17-18 uses:
# assign, then read `$?`. `set +e` around the assignment because C1 puts errexit
# on, and the point is to READ the status rather than to die of it.
#
# The probe computes the VERDICT itself and prints one token. That is not
# decoration: written as 3 assertions in this file — status non-zero, empty
# answer, non-empty message — all 3 passed on the very first run, on a probe
# that had died at its `source` line and printed nothing at all. A negative
# assertion over an empty string is true of every broken run there is. A single
# POSITIVE token that only a real run can emit cannot pass that way, and the
# token names the half that broke when it is not `refused`.
write_probe root-finder-missing <<'PROBE'
set -Eeuo pipefail
unset PROJECT_ROOT REPO_ROOT
source "$STANDARD_SH"
cd -P "$PROBE_START"
set +e
WORKSPACE_ROOT=$(find_repository_root 2>"$MESSAGE_FILE")
finder_status=$?
set -e
message="$(<"$MESSAGE_FILE")"
verdict="refused"
if [[ "$finder_status" -eq 0 ]]; then verdict="returned-zero"; fi
if [[ ${#WORKSPACE_ROOT} -ne 0 ]]; then verdict="${verdict}+printed-a-path"; fi
if [[ ${#message} -eq 0 ]]; then verdict="${verdict}+said-nothing"; fi
printf 'not-found-verdict=%s\n' "$verdict"
printf 'not-found-detail status=%s answer=[%s] message=[%s]\n' \
  "$finder_status" "$WORKSPACE_ROOT" "$message"
PROBE

run_probe root-finder-missing \
  PROBE_START="${NO_MARKER_ROOT}/${DEEP_SUFFIX}" MESSAGE_FILE="${SCRATCH}/finder-message"
assert_contains "the_root_finder_refuses_when_no_marker_is_found" \
  "$PROBE_STDOUT" "not-found-verdict=refused" \
  "3 halves in 1 token: a non-zero status, an EMPTY answer, and a message on stderr" \
  "a finder that returns 0 having found nothing makes every \`if [ \$? -ne 0 ]\` guard dead;" \
  "one that prints an unverified path makes every path built from it wrong in silence;" \
  "one that refuses without a message leaves the operator a number and no next step" \
  "output was:" "$PROBE_BOTH"

# ===========================================================================
# 5. ONE HOME — AND BOTH HALVES OF IT
# ===========================================================================
# Half A reads the FILES. It is the only half that can see a duplicate whose
# body is byte-identical to the standard's, which is exactly the copy a future
# change would re-add: somebody moves a logger back "so this file stands alone".
for symbol in "${STANDARD_SYMBOLS[@]}"; do
  assert_equal "the_standard_defines_${symbol}_exactly_once" \
    "1" "$(definition_count "$STANDARD_SH" "$symbol")" \
    "${STANDARD_RELATIVE} is the ONE home of ${symbol}" \
    "\`unreadable\` here means the file is not there yet"
done

second_homes=""
for candidate in "${SECOND_HOME_CANDIDATES[@]}"; do
  candidate_path="${REPO_ROOT}/${candidate}"
  if [[ ! -r "$candidate_path" ]]; then
    second_homes="${second_homes:+${second_homes}
}${candidate}: NOT READABLE — this list is stale"
    continue
  fi
  for symbol in "${STANDARD_SYMBOLS[@]}"; do
    count="$(definition_count "$candidate_path" "$symbol")"
    if [[ "$count" != "0" ]]; then
      second_homes="${second_homes:+${second_homes}
}${candidate}: ${count} definition(s) of ${symbol}"
    fi
  done
done
if [[ -z "$second_homes" ]]; then
  pass_check "no_second_home_defines_a_symbol_the_standard_owns"
else
  fail_check "no_second_home_defines_a_symbol_the_standard_owns" \
    "these files define a symbol whose 1 home is ${STANDARD_RELATIVE}:" \
    "$second_homes" \
    "_ctl/lib.sh must SOURCE the standard and delete its own copies, not keep them beside it" \
    "2 copies of a logger is how the 4 repositories drifted in the first place"
fi

# Half B reads the SHELL. It is the only half that can see a copy whose body
# DIFFERS — the drift this feature exists to end — and it is what says the
# definition a caller of _ctl/lib.sh really gets is the standard's.
write_probe declare-from-standard <<'PROBE'
set -Eeuo pipefail
unset PROJECT_ROOT REPO_ROOT
source "$STANDARD_SH"
declare -f $SYMBOL_LIST
PROBE

write_probe declare-from-lib <<'PROBE'
set -Eeuo pipefail
unset REPO_ROOT
PROJECT_ROOT="$REPOSITORY_ROOT_PATH"
export PROJECT_ROOT
source "$LIB_SH"
declare -f $SYMBOL_LIST
PROBE

run_probe declare-from-standard SYMBOL_LIST="$SYMBOL_LIST_TEXT"
standard_bodies="$PROBE_STDOUT"
standard_bodies_status="$PROBE_STATUS"
standard_bodies_stderr="$PROBE_STDERR"

run_probe declare-from-lib \
  SYMBOL_LIST="$SYMBOL_LIST_TEXT" REPOSITORY_ROOT_PATH="$REPO_ROOT"
lib_bodies="$PROBE_STDOUT"
lib_bodies_status="$PROBE_STATUS"
lib_bodies_stderr="$PROBE_STDERR"

assert_equal "sourcing_the_standard_defines_all_five_bodies" "0" "$standard_bodies_status" \
  "declare -f exits non-zero when it is asked for a name that is not defined," \
  "so this status is the whole five-symbol claim in one number" \
  "stderr was:" "${standard_bodies_stderr:-<nothing>}"

# The equality and the LIVENESS of both sides are 1 check. Compared alone, two
# empty answers are equal, and 2 probes that both died at their source line
# would report that the drift this feature exists to end has been closed.
if [[ -z "$standard_bodies" ]]; then
  fail_check "lib_sh_hands_its_callers_the_standards_definitions" \
    "the standard side printed no body at all, so there is nothing to compare against" \
    "it exited ${standard_bodies_status}; stderr was:" "${standard_bodies_stderr:-<nothing>}" \
    "2 empty answers compare EQUAL, and that would report this rule as satisfied"
elif [[ "$lib_bodies_status" -ne 0 || -z "$lib_bodies" ]]; then
  fail_check "lib_sh_hands_its_callers_the_standards_definitions" \
    "sourcing ${LIB_RELATIVE} left one of the five names undefined" \
    "it exited ${lib_bodies_status}; stderr was:" "${lib_bodies_stderr:-<nothing>}" \
    "it printed:" "${lib_bodies:-<nothing>}"
elif [[ "$lib_bodies" != "$standard_bodies" ]]; then
  fail_check "lib_sh_hands_its_callers_the_standards_definitions" \
    "after ${LIB_RELATIVE} loads, these five names must hold the bodies ${STANDARD_RELATIVE} defines" \
    "the standard defines:" "$standard_bodies" \
    "the library hands over:" "$lib_bodies" \
    "a body that DIFFERS is the drift this feature exists to end, and the file half above" \
    "is blind to it whenever a re-added copy happens to be byte-identical"
else
  pass_check "lib_sh_hands_its_callers_the_standards_definitions"
fi

# ===========================================================================
# 6. THE 8 CONSUMERS OF _ctl/lib.sh STILL LOAD
# ===========================================================================
# GREEN today, and here to go red on the change that deletes lib.sh's copies.
# Under `set -Eeuo pipefail` a deleted logger surfaces as
# `line N: log_info: command not found` and status 127, so the status alone is
# most of the claim; the needle is what names the symbol that went missing.
write_probe consumer-load <<'PROBE'
exec bash "$CONSUMER_PATH" ${CONSUMER_ARGV}
PROBE

for probe in "${CONSUMER_PROBES[@]}"; do
  consumer="${probe%%|*}"
  rest="${probe#*|}"
  consumer_argv="${rest%%|*}"
  want_status="${rest##*|}"
  consumer_path="${REPO_ROOT}/${consumer}"

  if [[ ! -r "$consumer_path" ]]; then
    fail_check "every_lib_consumer_still_loads__${consumer//[^A-Za-z0-9]/_}" \
      "named by CONSUMER_PROBES in this file and absent from the tree:" "$consumer" \
      "the list is stale — a consumer that left must leave this table in the same change"
    continue
  fi

  run_probe consumer-load \
    CONSUMER_PATH="$consumer_path" CONSUMER_ARGV="$consumer_argv" \
    GH_TOKEN="" GITHUB_TOKEN=""

  check_name="every_lib_consumer_still_loads__${consumer//[^A-Za-z0-9]/_}"
  if [[ "$PROBE_STATUS" != "$want_status" ]]; then
    fail_check "$check_name" \
      "want: exit ${want_status} from \`bash ${consumer} ${consumer_argv}\`" \
      "got:  ${PROBE_STATUS}" \
      "this argv reaches a line of the script's own and stops there, so the status is a" \
      "statement about LOADING _ctl/lib.sh and not about the verb's work" \
      "output was:" "$PROBE_BOTH"
  elif grep -qF -- "command not found" <<< "$PROBE_BOTH"; then
    fail_check "$check_name" \
      "the exit status is right and the run reports a name it could not call:" \
      "$PROBE_BOTH" \
      "deleting a logger from _ctl/lib.sh without sourcing the standard looks exactly like this"
  else
    pass_check "$check_name"
  fi
done

test_summary "$TEST_NAME"
