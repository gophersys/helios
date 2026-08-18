#!/usr/bin/env bash
#
# _ctl/tests/embedded-entrypoint.test.sh — the mode dispatch of the embedded
# image, and what the pod path must keep saying.
#
# Static means static: this file runs 1 shell script with a stub PATH and reads
# files. It starts no container, it calls no daemon and it reaches no network,
# so it runs identically on a laptop and on a CI runner — and it runs in the
# PULL REQUEST gate.
#
# ============================================================================
# WHY THIS FILE EXISTS
# ============================================================================
#
# `zephyr` and `zephyr-devbox` are 1 image now, and 1 image cannot carry 2
# users. `embedded` therefore ships `USER root` — the pod half binds sshd and
# manages host keys — and embedded/embedded-entrypoint.sh is what picks the
# identity back, keyed on GOPHERSYS_EMBEDDED_MODE. That is a CONTRACT CHANGE:
# before the fold the Dockerfile said `USER dev` and `docker run zephyr id`
# answered `dev` because the kernel said so. Now a shell script decides it.
#
# NOTHING ELSE IN THIS REPOSITORY EXERCISES THAT DECISION. `.ci/smoke.sh` runs
# the image with `--user dev` and an argv of its own, which BYPASSES the
# dispatch on both axes at once: it names the euid it wants, and its argv
# reaches the exec either way. images.yaml says so beside the embedded entry.
# So the dispatch is covered here, on the host, or it is covered nowhere.
#
# ============================================================================
# WHAT IS EXECUTED HERE, AND WHAT IS ONLY READ — SAY WHICH, ALWAYS
# ============================================================================
#
# The DEFAULT arm is EXECUTED. It runs `id -u` and then execs, and it touches
# no path, so a stub PATH is the whole harness it needs. Every check in
# sections 2 to 4 runs the real file and reads what really happened.
#
# The DEVBOX arm is READ AS TEXT, and that is a limit and not a choice. Its
# statements write to ABSOLUTE paths that are baked into the file as plain
# assignments — /etc/ssh/hostkeys, /home/dev/.ssh, /run/devbox-degraded,
# /var/log/code-server.log — and 3 of those writes are SHELL REDIRECTIONS,
# which no PATH stub can intercept. On this host /run does not exist and
# /home/dev is not writable, so the arm dies at its first redirection; as root
# in CI it would not die, it would write into the runner. Running it hermetically
# needs those 4 constants to read the environment first
# (`HOSTKEY_DIR="${HOSTKEY_DIR:-/etc/ssh/hostkeys}"` and its 3 siblings), and
# that is a change to a file this test does not own — recorded as the seam, not
# improvised here.
#
# A text check is weaker and it is not nothing: it fails when somebody deletes
# the marker write, drops the `|| rc=$?` that keeps the supervisor alive, or
# moves the sshd exec inside the code-server branch. Each one below says which
# it is in its own name — `_states_` for a text check, everything else is run.
#
# ============================================================================
# THE STUBS
# ============================================================================
#
# _ctl/tests/stubs/entrypoint/ holds them, and they split in 2:
#
#   MODELS      `id` (the euid the case chooses), `runuser` (records, then
#               execs, setting HOME/USER/LOGNAME the way the real one does) and
#               `embedded-probe-command` (the CMD stand-in that reports its
#               argv, its identity and a chosen exit status).
#   TRIPWIRES   `mkdir`, `chmod`, `chown`, `ssh-keygen`. The default arm must
#               never call one. Each records its argv and returns 0, so a wrong
#               branch is a NAMED line in the log rather than a generic non-zero
#               status — and so that a run as root cannot write host keys into
#               the machine it is testing on.
#
# Usage: bash _ctl/tests/embedded-entrypoint.test.sh
#
set -Eeuo pipefail
IFS=$'\n\t'

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
PROJECT_ROOT="$REPO_ROOT"

# The logging lives in _ctl/lib.sh, 1 time only — the same source line every
# other script in this repository uses.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../lib.sh
source "$REPO_ROOT/_ctl/lib.sh"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=harness.sh
source "$TESTS_DIR/harness.sh"

TEST_NAME="embedded-entrypoint.test.sh"

# The subject, and the stub directory, as literals. A test that discovers the
# path it checks agrees with any path, a wrong one included.
ENTRYPOINT_RELATIVE="embedded/embedded-entrypoint.sh"
ENTRYPOINT="$REPO_ROOT/$ENTRYPOINT_RELATIVE"
STUB_DIR="$TESTS_DIR/stubs/entrypoint"
PROBE_COMMAND="embedded-probe-command"

# The mode variable and its 1 magic value, spelled out. The Dockerfile, the
# entrypoint and the infrastructure pod all have to agree on both, and a test
# that read either out of the file it checks would agree with a typo.
MODE_VARIABLE="GOPHERSYS_EMBEDDED_MODE"
POD_MODE="devbox"

# The 2 knobs the code-server refusal must name. Literals for the same reason:
# the refusal is the only thing that tells an operator which of them to set, and
# a refusal naming 1 of the 2 sends half of them to the wrong secret.
HASHED_PASSWORD_KNOB="DEVBOX_CODE_SERVER_HASHED_PASSWORD"
AUTH_KNOB="DEVBOX_CODE_SERVER_AUTH=none-behind-proxy"

# The machine-readable state a probe or an operator finds after a degraded boot.
DEGRADED_MARKER="/run/devbox-degraded"

# The first path the pod arm touches. A literal, so that "it entered the pod
# preparation" is asserted against the directory the contract names and not
# against whatever the file happens to say today.
HOSTKEY_DIR="/etc/ssh/hostkeys"

# The log prefix. It is the string an operator greps a pod's logs for and the
# string every runbook and every `kubectl logs | grep` in another repository
# would carry, so it is a NAME with consumers and not decoration. It was
# `[devbox-entrypoint]` while the file was zephyr-devbox's, and the fold renamed
# it — a rename nothing held, which is how the old name would have survived in
# half the tree.
LOG_PREFIX="[embedded-entrypoint]"

# The refusal that is NOT a degraded() call. The empty-argv refusal writes the
# marker itself, GUARDED, because it is the 1 refusal a non-root caller reaches
# and /run is not writable there — see the checks in section 5b.
REFUSAL_MARKER_TEXT="no command to exec in toolchain mode"

# The documented exit status of that refusal. README.md and
# .claude/rules/00-identity.md both spell it beside the step tables, so it is a
# contract and not an implementation detail.
EMPTY_ARGV_EXIT=2

STUB_LOG="$(mktemp)"
ENTRYPOINT_OUTPUT=""
ENTRYPOINT_STATUS=0

function cleanup() {
  rm -f "$STUB_LOG"
}
trap cleanup EXIT

# run_entrypoint <uid> <mode or the empty string> [argv...]
#
# The environment is built from NOTHING (`env -i`), so the suite's own variables
# cannot reach the subject and decide a branch for it. PATH names the stub
# directory first and then the 2 system directories the exec'd command may need.
#
# THE STATUS IS READ ON ITS OWN LINE. `|| true` would discard it before `$?` ran
# and every case below would read 0, which is the reading this whole suite
# exists to prevent.
function run_entrypoint() {
  local uid="$1" mode="$2"
  shift 2
  local -a environment
  environment=(
    "PATH=${STUB_DIR}:/usr/bin:/bin"
    "STUB_ENTRYPOINT_LOG=${STUB_LOG}"
    "STUB_ID_UID=${uid}"
    "STUB_STAT_UID=0"
  )
  if [[ -n "$mode" ]]; then
    environment=("${environment[@]}" "${MODE_VARIABLE}=${mode}")
  fi
  : > "$STUB_LOG"
  ENTRYPOINT_STATUS=0
  ENTRYPOINT_OUTPUT="$(env -i "${environment[@]}" bash "$ENTRYPOINT" "$@" 2>&1)" \
    || ENTRYPOINT_STATUS=$?
}

# stub_log — what the stubs recorded during the last run, or a legible stand-in.
function stub_log() {
  if [[ -s "$STUB_LOG" ]]; then
    cat "$STUB_LOG"
  else
    printf '<no stub was called>'
  fi
}

# line_of <fixed string> — the line NUMBER of the first line of the entrypoint
# holding that string, or the empty string.
#
# COMPUTED, never written here as a number. A hardcoded line number is a test
# that goes red when somebody adds a sentence to a comment, which teaches the
# reader to edit the number instead of reading the failure.
#
# THE STATUS IS READ, AND IT HAS TO BE. grep exits 1 when it matches nothing,
# this file runs under `set -Eeuo pipefail`, and "matched nothing" is the exact
# answer the ORDER check below needs — a section marker that is GONE. The plain
# pipeline killed this file mid-run the first time that was break-tested: 27
# PASS lines, no FAIL line, and NO summary. That is the silent-death shape
# version-coverage.test.sh was hardened against on the same day, reproduced here
# in the file that hunts it. Status 1 is an answer; anything above it is a real
# error and still ends the run.
function line_of() {
  local status=0 hits=""
  hits="$(grep -nF -- "$1" "$ENTRYPOINT")" || status=$?
  [[ "$status" -le 1 ]] || return "$status"
  [[ -z "$hits" ]] && return 0
  printf '%s\n' "$hits" | head -1 | cut -d: -f1
}

# entrypoint_lines <grep argument...> — the same rule for every other reader of
# the file: 0 matches is DATA, and a real grep error still ends the run.
function entrypoint_lines() {
  local status=0 hits=""
  hits="$(grep "$@" "$ENTRYPOINT")" || status=$?
  [[ "$status" -le 1 ]] || return "$status"
  printf '%s' "$hits"
}

# function_body <name> — the lines BETWEEN `function <name>() {` and the `}`
# that closes it in column 1.
#
# A file-wide grep is the wrong reader for a rule about what a FUNCTION does. It
# passes when the string it wants lives anywhere at all, and "anywhere" includes
# the caller that was supposed to stop needing it — which is precisely how a
# `degraded()` reduced to a bare log would keep a marker check green. This
# reader answers about the body and nothing else.
#
# The `[[ -r ]]` guard is not decoration: awk on a file it cannot open exits 2
# and, under `set -Eeuo pipefail`, ends the RUN with no summary. That shape has
# already been shipped twice in this directory.
function function_body() {
  [[ -r "$ENTRYPOINT" ]] || return 0
  awk -v name="$1" '
    $0 ~ "^function[[:space:]]+" name "\\(\\)[[:space:]]*\\{" { inside = 1; next }
    inside && /^\}/ { inside = 0; next }
    inside { print }
  ' "$ENTRYPOINT"
}

printf '=== RUN  %s\n' "$TEST_NAME"

# -------- 1. the subject and its harness are really there --------
# Every check below runs or reads 1 of these. A missing one would make the whole
# file assert about nothing, in green, which is the failure test_summary catches
# only when NO check ran at all.
# NOT `missing`. _ctl/lib.sh, which this file sources, holds an ARRAY of that
# name, and shellcheck follows the source directive — SC2178 on a name a caller
# cannot see is exactly the collision the directive exists to surface.
missing_harness=""
[[ -f "$ENTRYPOINT" ]] || missing_harness="${missing_harness:+${missing_harness}
}${ENTRYPOINT_RELATIVE}"
for stub in id runuser "$PROBE_COMMAND" mkdir chmod chown ssh-keygen stat; do
  [[ -x "$STUB_DIR/$stub" ]] || missing_harness="${missing_harness:+${missing_harness}
}stubs/entrypoint/${stub} (absent, or not executable)"
done
if [[ -n "$missing_harness" ]]; then
  fail_check "the_subject_and_its_stubs_exist" \
    "these are named by this test and absent from the tree:" \
    "$missing_harness"
else
  pass_check "the_subject_and_its_stubs_exist"
fi

# -------- 2. the default arm: it EXECS the argv, as dev, at euid 0 --------
# The image ships USER root, so this is the arm every `docker run embedded`
# takes. What it has to reproduce is what `USER dev` in the old Dockerfile did:
# the command runs, and it runs as dev.
run_entrypoint 0 "" "$PROBE_COMMAND" --flag "an argument"

assert_equal "an_unset_mode_execs_the_argv" \
  "0" "$ENTRYPOINT_STATUS" \
  "with ${MODE_VARIABLE} unset the entrypoint must exec the command it was handed" \
  "it printed:" "${ENTRYPOINT_OUTPUT:-<nothing>}" \
  "the stubs recorded:" "$(stub_log)"

assert_contains "the_argv_reaches_the_command_whole" \
  "$ENTRYPOINT_OUTPUT" "probe-argv: --flag an argument" \
  "docker hands the entrypoint the CMD or the caller's argv, and every word of it has to arrive" \
  "the stubs recorded:" "$(stub_log)"

# The identity, read from the command's own environment rather than from the
# entrypoint's source. `runuser -u dev --` is what sets these 3, deliberately
# WITHOUT --preserve-environment: that flag would keep HOME=/root, and the
# toolchain's caches and oh-my-zsh live in /home/dev.
assert_contains "the_default_arm_runs_the_command_as_dev" \
  "$ENTRYPOINT_OUTPUT" "probe-user: dev" \
  "the old zephyr image said USER dev in its Dockerfile; this arm is what replaces that line" \
  "the stubs recorded:" "$(stub_log)"

assert_contains "the_default_arm_hands_the_command_devs_home" \
  "$ENTRYPOINT_OUTPUT" "probe-home: /home/dev" \
  "HOME=/root would send every cache and every oh-my-zsh read to the wrong tree"

assert_contains "at_euid_0_the_default_arm_drops_through_runuser" \
  "$(stub_log)" "runuser -u dev -- ${PROBE_COMMAND}" \
  "at euid 0 the process is root and something has to drop it; runuser is that something"

# The command's status is the CONTAINER's status. The entrypoint is PID 1, so a
# status it swallowed is a container that exited 0 while the tool inside it
# failed — a green CI step over a failed build, and the shape `|| true` produces
# everywhere else this repository refuses it.
#
# WHAT THIS PAIR DOES NOT PROVE: that the exec is an EXEC. A `runuser ... "$@"`
# with no `exec` returns the same status from the same script, so the status
# cannot tell a replaced process from a waited-for child — measured by
# break-test on 2026-08-18, where dropping the `exec` keyword left both checks
# green. What that costs is signal delivery and PID 1 semantics, and proving it
# needs the process tree rather than the exit code. Stated, not claimed.
run_entrypoint 0 "" "$PROBE_COMMAND"
assert_equal "the_command_status_is_the_containers_status" \
  "0" "$ENTRYPOINT_STATUS" \
  "a status of 0 here only says the command ran; the next check is the one that binds them"

STUB_PROBE_STATUS_CASE=0
ENTRYPOINT_STATUS=0
ENTRYPOINT_OUTPUT="$(env -i \
  "PATH=${STUB_DIR}:/usr/bin:/bin" \
  "STUB_ENTRYPOINT_LOG=${STUB_LOG}" \
  "STUB_ID_UID=0" \
  "STUB_PROBE_STATUS=42" \
  bash "$ENTRYPOINT" "$PROBE_COMMAND" 2>&1)" || STUB_PROBE_STATUS_CASE=$?
assert_equal "a_failing_commands_exit_status_is_the_entrypoints" \
  "42" "$STUB_PROBE_STATUS_CASE" \
  "an entrypoint that ended 0 over a failed command is a container that lies about its own run" \
  "it printed:" "${ENTRYPOINT_OUTPUT:-<nothing>}"

# -------- 3. the default arm at a NON-ROOT euid --------
# This is risk 1 of the fold, and it is not hypothetical: .ci/smoke.sh runs this
# image with `docker run --user dev`. runuser is present in the image and
# UNPRIVILEGED there — the real binary refuses with "may not be used by non-root
# users" — so an arm that always ran it would turn the repository's own smoke
# invocation into an error.
run_entrypoint 1000 "" "$PROBE_COMMAND" --flag

assert_equal "a_non_root_caller_still_runs_the_command" \
  "0" "$ENTRYPOINT_STATUS" \
  "docker run --user dev is what .ci/smoke.sh does, and it must not become an error" \
  "it printed:" "${ENTRYPOINT_OUTPUT:-<nothing>}" \
  "the stubs recorded:" "$(stub_log)"

assert_not_contains "a_non_root_caller_never_reaches_runuser" \
  "$(stub_log)" "runuser" \
  "runuser at a non-zero euid refuses, naming the caller — the euid test is what avoids it" \
  "it printed:" "${ENTRYPOINT_OUTPUT:-<nothing>}"

assert_contains "a_non_root_caller_execs_the_argv_plainly" \
  "$ENTRYPOINT_OUTPUT" "probe-argv: --flag" \
  "the command still has to run; only the way it is reached changes"

# -------- 4. the default arm is the SAFE-BY-ABSENCE one --------
# An entrypoint that fell through to the pod preparation whenever an env was
# missing would start an sshd for every `docker run`. `devbox` is the only value
# that opts in, and everything else — a near miss, a different case, a trailing
# space — is the toolchain.
for wrong_mode in "DEVBOX" "devbox " "dev" "toolchain"; do
  run_entrypoint 0 "$wrong_mode" "$PROBE_COMMAND"
  mode_label="$(printf '%s' "$wrong_mode" | tr -c 'A-Za-z0-9' '_')"
  assert_not_contains "mode_${mode_label}_is_not_the_pod_mode" \
    "$(stub_log)" "ssh-keygen" \
    "only the literal '${POD_MODE}' reaches the pod preparation; this ran '${wrong_mode}'" \
    "it printed:" "${ENTRYPOINT_OUTPUT:-<nothing>}"
done

# The whole of /etc/ssh, stated as the log this arm may not hold. mkdir and
# chmod are the first 2 statements of the pod preparation, ssh-keygen is the
# third, and stat + chown belong to the mounted-volume ownership step below
# them — so all 5 absent is "the preparation was not entered", read at 5
# different depths of it rather than at 1.
run_entrypoint 0 "" "$PROBE_COMMAND"
touched_etc_ssh=""
for tripwire in mkdir chmod chown ssh-keygen stat; do
  if grep -q "^${tripwire} " "$STUB_LOG"; then
    touched_etc_ssh="${touched_etc_ssh:+${touched_etc_ssh}
}${tripwire}"
  fi
done
if [[ -z "$touched_etc_ssh" ]]; then
  pass_check "an_unset_mode_never_touches_etc_ssh"
else
  fail_check "an_unset_mode_never_touches_etc_ssh" \
    "with ${MODE_VARIABLE} unset the entrypoint called these pod-preparation commands:" \
    "$touched_etc_ssh" \
    "the whole log was:" "$(stub_log)" \
    "host keys, volume ownership and sshd belong to the pod, and the pod opts IN"

fi

# An empty argv in the default arm would `exec` nothing and FALL THROUGH to the
# pod preparation — the silent wrong branch the dispatch exists to prevent. The
# image declares CMD, so reaching this needs a caller that replaced it with
# nothing, and the answer is a refusal that says so.
#
# BOTH EUID ARMS, AND THE NON-ROOT ONE IS THE ONE THAT MATTERS. `exec` with no
# command and no redirection is a NO-OP in bash: control falls to the next
# statement. At euid 0 the arm reads `exec runuser -u dev -- "$@"`, so an empty
# argv still execs runuser and the fall-through cannot happen there; at a
# non-zero euid it reads `exec "$@"`, and THAT is where an unguarded empty argv
# walks into the host-key generation. Measured by break-test: with the guard
# deleted, the euid-0 case stayed green and only this one went red.
for empty_argv_uid in 0 1000; do
  run_entrypoint "$empty_argv_uid" ""
  # EXACTLY 2, and not merely non-zero. The status is the documented contract —
  # both step tables spell it — and it is also what proves the marker write is
  # GUARDED: an unguarded `printf >>/run/devbox-degraded` on a host where /run
  # is absent or unwritable dies under `set -e` and the caller reads 1, so a
  # NAMED refusal would arrive as an unexplained failure. Measured by
  # break-test: removing the `if !` turns this into 1 on this host.
  assert_equal "an_empty_argv_at_euid_${empty_argv_uid}_is_refused" \
    "$EMPTY_ARGV_EXIT" "$ENTRYPOINT_STATUS" \
    "an exec with no argv is a no-op, and the next statement is the pod preparation" \
    "it printed:" "${ENTRYPOINT_OUTPUT:-<nothing>}" \
    "the stubs recorded:" "$(stub_log)"

  assert_not_contains "an_empty_argv_at_euid_${empty_argv_uid}_does_not_reach_the_pod_preparation" \
    "$(stub_log)" "ssh-keygen" \
    "falling through here would start an sshd for a caller who asked for a command" \
    "it printed:" "${ENTRYPOINT_OUTPUT:-<nothing>}"
done

# -------- 4b. the POSITIVE case: devbox mode ENTERS the pod arm --------
#
# THE WHOLE FILE WAS NEGATIVE UNTIL THIS SECTION, and that was a hole big enough
# to drive both production pods through. Every check above asserts that some
# value is NOT the pod mode; not one asserted that the pod mode IS. Measured by
# the verifier on 2026-08-18: change the dispatch's literal "devbox" to
# "devboxx" and all 31 checks stayed green, `ctl.sh test` stayed green, and
# `ctl.sh validate` stayed green — while both live devboxes would have come up
# as toolchain containers that exec `zsh`, exit, and report Completed. No sshd,
# no code-server, no host keys, and nothing anywhere in this repository saying
# so.
#
# A dispatch is 2-armed and a suite that only ever exercises 1 arm has tested a
# branch, not a dispatch.
#
# HOW FAR THIS RUNS, exactly. The pod arm reaches its first SHELL REDIRECTION
# and dies there — /run/devbox-degraded on a host where /run does not exist
# (this mac) or is not writable (a Linux container as `dev`). That is the
# absolute-path seam recorded at the top of this file and deferred. So the
# assertions are about the steps that DID run, read from the stub log, and the
# status is deliberately not asserted: it is a fact about the seam, not about
# the dispatch, and pinning it would turn this red on the day the seam lands.
#
# WHAT IT COSTS ON A ROOT HOST: where /run IS writable the arm gets 1 line
# further and appends 1 line to /run/devbox-degraded before dying. No image of
# this repository runs its suite as root — every one of them runs as `dev` —
# and DEVBOX_AUTHORIZED_KEYS is deliberately left unset here so the run takes
# the degraded branch rather than the branch that WRITES /home/dev/.ssh/
# authorized_keys, which on a Linux host would be a real user's real file.
run_entrypoint 0 "$POD_MODE" "$PROBE_COMMAND"

assert_contains "the_pod_mode_enters_the_pod_preparation" \
  "$(stub_log)" "mkdir -p ${HOSTKEY_DIR}" \
  "GOPHERSYS_EMBEDDED_MODE=${POD_MODE} is the ONLY value that may reach this, and it must" \
  "it printed:" "${ENTRYPOINT_OUTPUT:-<nothing>}"

assert_contains "the_pod_mode_generates_the_persistent_host_keys" \
  "$(stub_log)" "ssh-keygen" \
  "the box keeps its SSH identity across pod restarts because this step runs" \
  "the stubs recorded:" "$(stub_log)"

assert_contains "the_pod_mode_logs_through_the_images_own_prefix" \
  "$ENTRYPOINT_OUTPUT" "${LOG_PREFIX} generating ed25519 host key" \
  "the prefix and the step together: this is the line an operator greps for in a pod that" \
  "came up, and it is the proof this run reached the pod arm rather than merely not exec-ing"

# The other half, and it is the half that the misspelling break turns red: the
# toolchain exec must NOT have happened. Without this, a dispatch that ran BOTH
# arms would satisfy every assertion above.
assert_not_contains "the_pod_mode_never_execs_the_argv" \
  "$(stub_log)" "$PROBE_COMMAND" \
  "the pod arm ends at the sshd exec; a run that also exec'd the CMD is not a dispatch" \
  "it printed:" "${ENTRYPOINT_OUTPUT:-<nothing>}"

assert_not_contains "the_pod_mode_never_drops_to_dev_through_runuser" \
  "$(stub_log)" "runuser -u dev -- ${PROBE_COMMAND}" \
  "the pod half runs as ROOT: it binds :22, writes /etc/ssh and chowns mountpoints" \
  "it printed:" "${ENTRYPOINT_OUTPUT:-<nothing>}"

# -------- 5. the pod arm, READ AS TEXT --------
# Section 0 of this header says why these are text and what would make them
# executable. Each one names a property whose deletion is a silent defect: the
# code carries on, the pod reports Running, and the thing that is gone is a
# refusal, a marker or a restart.
#
# EVERY CHECK HERE READS CODE, NEVER COMMENTS, and that clause was earned. The
# first version of `the_code_server_supervisor_keeps_a_failing_exit_in_a_condition`
# searched the whole file for `|| rc=$?`, and the entrypoint's own comment
# EXPLAINS that idiom 5 lines above the statement — so deleting the statement
# left the check green on the prose describing it. The break-test is what said
# so, which is the only reason to run one.
entrypoint_code="$(entrypoint_lines -vE '^[[:space:]]*#')"

assert_contains "the_pod_arm_writes_the_degraded_marker_path" \
  "$entrypoint_code" "DEGRADED_MARKER=${DEGRADED_MARKER}" \
  "degraded() is the ERROR path of every missing credential and every failed service" \
  "without the marker a probe and an operator have only the log to read, and a pod that" \
  "reports Running while a declared service is absent is the failure this file had once"

# THIS WAS A HEADCOUNT, AND A HEADCOUNT IS NOT A PROPERTY. It counted the
# `>>"${DEGRADED_MARKER}"` writes in the file and asserted 1, and the moment a
# SECOND refusal correctly grew a marker write the check went red on a
# correctness improvement. Bumping the literal to 2 would have re-armed the same
# trap one number further along: what the file owes is that each refusal writes
# the marker, not that the file holds N writes. So the rule is now per-WRITER,
# and each writer is named.
#
# WRITER 1 — degraded(), the pod path. Read from the FUNCTION BODY and not from
# the file: a `>>"${DEGRADED_MARKER}"` anywhere else satisfies a file-wide grep
# while degraded() itself only logs, which is exactly the state this check
# exists to refuse.
# The single quotes are the point: the needle is the LITERAL source text of the
# redirection, and a `${DEGRADED_MARKER}` this file expanded would search the
# entrypoint for a path instead of for the write that uses it. The disable
# directive sits on the line ABOVE the statement, because shellcheck attaches it
# to the command that FOLLOWS it and a prose line in between detaches it — which
# is how the first version of this hunk failed `ctl.sh validate`.
degraded_body_write=0
# shellcheck disable=SC2016
degraded_body_write="$(grep -cF -- '>>"${DEGRADED_MARKER}"' <<< "$(function_body degraded)")" \
  || degraded_body_write=0
assert_equal "the_degraded_function_body_writes_the_marker" \
  "1" "$degraded_body_write" \
  "the marker write is what makes a degraded boot MACHINE-READABLE" \
  "a degraded() that only logged would leave the state invisible to everything but a human" \
  "the body this test read was:" "$(function_body degraded)"

# WRITER 2 — the empty-argv refusal, the TOOLCHAIN path. It is deliberately not
# a degraded() call, and section 5b below is where that difference is held.
refusal_marker_line=""
refusal_marker_line="$(grep -F "$REFUSAL_MARKER_TEXT" <<< "$entrypoint_code")" \
  || refusal_marker_line=""
# shellcheck disable=SC2016
# A literal needle again, for the reason above it.
assert_contains "the_toolchain_refusal_writes_the_marker_too" \
  "$refusal_marker_line" '>>"${DEGRADED_MARKER}"' \
  "the log line always lands; the marker is the half a probe and an operator can read" \
  "a refusal that only logged would leave the toolchain path with no machine-readable state" \
  "at all, while the pod path has one"

# The refusal itself, as 1 line, and then the 2 knobs inside it. Asserting the
# knob NAMES against the whole file would pass on the header paragraph that
# documents them, which is the trap the clause above records.
refusal_line=""
refusal_line="$(grep -F 'degraded "code-server NOT STARTED' <<< "$entrypoint_code")" \
  || refusal_line=""
if [[ -n "$refusal_line" ]]; then
  pass_check "the_no_auth_case_refuses_instead_of_starting_code_server"
else
  fail_check "the_no_auth_case_refuses_instead_of_starting_code_server" \
    "no degraded() call for the no-credential case survives in the code of ${ENTRYPOINT_RELATIVE}" \
    "the account code-server runs as holds passwordless sudo, so a reachable unauthenticated" \
    ":8443 is root on the pod for any peer the network lets through — the refusal is the wall"
fi

assert_contains "the_code_server_refusal_names_the_hashed_password_knob" \
  "$refusal_line" "$HASHED_PASSWORD_KNOB" \
  "with neither knob set code-server does NOT start, and the refusal is what names the fix"

assert_contains "the_code_server_refusal_names_the_auth_knob" \
  "$refusal_line" "$AUTH_KNOB" \
  "a refusal naming 1 of the 2 knobs sends half its readers to the wrong answer" \
  "DEVBOX_CODE_SERVER_AUTH=none-behind-proxy is the operator's EXPLICIT statement that an" \
  "authenticating proxy owns :8443 — the old behaviour, opt-in instead of default"

supervisor_guard=0
supervisor_guard="$(grep -cF -- '|| rc=$?' <<< "$entrypoint_code")" || supervisor_guard=0
assert_equal "the_code_server_supervisor_keeps_a_failing_exit_in_a_condition" \
  "1" "$supervisor_guard" \
  "the subshell inherits set -e, under which a non-zero code-server exit would kill the" \
  "restart loop at the exact moment it exists for — measured on the first probe of this file"

# -------- 5b. the toolchain refusal's marker write is GUARDED --------
# The 2 writers are not the same shape, and the difference is load-bearing.
#
# degraded()'s write is BARE. It runs on the pod path only, as root, where /run
# exists and is writable, and a failure there is a defect worth dying on.
#
# The empty-argv refusal is the 1 refusal a NON-ROOT caller reaches —
# `docker run --user dev embedded` with a replaced CMD, and `--user dev` is the
# shape .ci/smoke.sh itself uses. There /run is not writable. An unguarded
# append would then fail, `set -e` would kill the script at that line, and the
# caller would read status 1 with no explanation — a NAMED refusal turned into
# an unexplained death, on the one path a real caller can reach.
#
# So the write is attempted and a failure to write is REPORTED rather than
# fatal. Nothing else in this repository holds that shape, and the check for it
# is 2-sided on purpose: the exit-status assertion in section 4 fails when the
# guard goes away on a host with an unwritable /run, and this text check fails
# EVERYWHERE, including on a root host where the bare write would succeed and
# the behavioural check could not tell the difference.
if [[ -z "$refusal_marker_line" ]]; then
  fail_check "the_toolchain_refusal_guards_its_marker_write" \
    "no line of ${ENTRYPOINT_RELATIVE} carries the refusal text: ${REFUSAL_MARKER_TEXT}" \
    "the writer this rule is about is gone, so its shape cannot be judged"
else
  refusal_marker_trimmed="${refusal_marker_line#"${refusal_marker_line%%[![:space:]]*}"}"
  case "$refusal_marker_trimmed" in
    "if ! "*)
      pass_check "the_toolchain_refusal_guards_its_marker_write"
      ;;
    *)
      fail_check "the_toolchain_refusal_guards_its_marker_write" \
        "the refusal's marker write is not inside a condition; the line reads:" \
        "$refusal_marker_trimmed" \
        "this refusal is reachable as a NON-root caller, where /run is not writable — a bare" \
        "append fails there, set -e kills the script at that line, and the documented exit ${EMPTY_ARGV_EXIT}" \
        "never happens: the caller gets an unexplained 1 instead of a named refusal"
      ;;
  esac
fi

# The log PREFIX. Every line this file emits carries it, so it is the string an
# operator greps a pod's logs for and the string a runbook in another repository
# would hardcode. It was `[devbox-entrypoint]` until the fold renamed the file,
# and nothing held it — a rename that leaves a stale reference is not complete,
# and here the stale reference would have been in every reader's fingers.
# log() is a 1-line definition, so its text IS its body and function_body (which
# reads to a `}` in column 1) correctly returns nothing for it. The definition
# line is the haystack, and it is read rather than the whole file: the header
# paragraph above the dispatch also spells the name, and a check the PROSE could
# satisfy is the trap section 5 opens with.
log_definition=""
log_definition="$(grep -F 'function log()' <<< "$entrypoint_code")" || log_definition=""
assert_contains "the_log_prefix_is_the_images_own_name" \
  "$log_definition" "$LOG_PREFIX" \
  "log() is the 1 producer of every line this entrypoint writes, so this prefix is the" \
  "whole grep contract an operator has against a running pod — it read [devbox-entrypoint]" \
  "until the fold, and a rename that leaves a stale reference is not complete"

# The ORDER, as the order the sections appear in the file. It is a structural
# proxy and it says so: what it holds is that each step is above the step that
# depends on it, and that the sshd exec is below all of them.
#
# ALL 7 MARKERS, and it held 5. The 2 that were missing are the 2 whose position
# carries the most:
#
#   mode dispatch    it is the FIRST section, and everything below it is the pod
#                    path. A dispatch that sank below the host-key generation
#                    would run the pod preparation for every `docker run` and
#                    then decide the mode, which is the safe-by-absence property
#                    inverted while every behavioural check still passed.
#   mounted-volume   its `chmod 0755` on /home/dev has to run BEFORE
#   ownership        authorized_keys is written into /home/dev/.ssh. local-path
#                    PVCs mount 0777, sshd StrictModes then refuses the key file
#                    ("bad ownership or modes for directory /home/dev"), and the
#                    pod comes up REFUSING EVERY LOGIN with a correct key
#                    installed. The file states that itself, in the comment
#                    above the chmod, and nothing held it. Moving that block
#                    below authorized_keys is a 2-line diff that reads as tidying.
#
# The names are the file's own section banners. That is a coupling worth being
# explicit about: renaming a banner turns this red, and the failure names the
# marker it could not find rather than pretending the step is gone.
order_ok=1
order_evidence=""
previous=0
for marker in \
  "# -------- mode dispatch --------" \
  "# -------- host keys --------" \
  "# -------- mounted-volume ownership --------" \
  "# -------- authorized_keys --------" \
  "# -------- mcu slot symlinks --------" \
  "# -------- code-server --------" \
  "# -------- sshd --------"
do
  current="$(line_of "$marker")"
  order_evidence="${order_evidence:+${order_evidence}
}${current:-<absent>}: ${marker}"
  if [[ -z "$current" ]] || [[ "$current" -le "$previous" ]]; then
    order_ok=0
  fi
  previous="${current:-0}"
done
if [[ "$order_ok" -eq 1 ]]; then
  pass_check "the_entrypoint_states_its_7_steps_in_order"
else
  fail_check "the_entrypoint_states_its_7_steps_in_order" \
    "the file must read mode dispatch -> host keys -> mounted-volume ownership ->" \
    "authorized_keys -> mcu symlinks -> code-server -> sshd" \
    "the section markers were found at:" \
    "$order_evidence" \
    "an absent marker is a section that was renamed or deleted, and a marker out of order is a" \
    "step that now runs after something that depended on it"

fi

# sshd is the LAST instruction, and it is outside the code-server branch. That
# is the property that makes code-server SUPPLEMENTARY: a missing credential
# must not take the primary service down.
last_instruction="$(entrypoint_lines -vE '^[[:space:]]*(#|$)' | tail -1)"
assert_equal "sshd_is_the_last_instruction_so_a_degraded_code_server_never_stops_it" \
  "exec /usr/sbin/sshd -D -e" "$last_instruction" \
  "code-server is supplementary and sshd is the primary service" \
  "if the exec moved inside the code-server branch, a pod with no auth knob would run no sshd" \
  "and the pull request that did it would look like a refactor"

# -------- 6. the image and the entrypoint agree about the mode --------
# 2 files spell this variable, and a typo in either is a pod that silently takes
# the toolchain arm: the Dockerfile's own header documents the contract, and the
# entrypoint implements it. The infrastructure pod spells it a third time, in
# another repository, which this gate cannot reach — so it is named in the
# evidence rather than checked.
assert_contains "the_entrypoint_reads_the_mode_variable" \
  "$entrypoint_code" "\${${MODE_VARIABLE}:-}" \
  "the dispatch is keyed on this 1 name, and the pod that sets it lives in gophersys/infrastructure"

# The Dockerfile check reads the WHOLE file, comments included, and that is the
# point of it rather than an oversight: what it holds is that a reader meeting
# this image is TOLD about the 2 modes, and the telling is prose.
assert_contains "the_Dockerfile_documents_the_same_mode_variable" \
  "$(cat "$REPO_ROOT/embedded/Dockerfile")" "$MODE_VARIABLE" \
  "embedded/Dockerfile is where a reader meets this image first, and the 2 modes are its contract"

assert_contains "the_Dockerfile_entrypoints_this_file" \
  "$(cat "$REPO_ROOT/embedded/Dockerfile")" \
  'ENTRYPOINT ["/usr/local/bin/embedded-entrypoint.sh"]' \
  "every check in this file is about a script nothing runs, unless the image names it as PID 1"

test_summary "$TEST_NAME"
