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
for stub in id runuser "$PROBE_COMMAND" mkdir chmod chown ssh-keygen; do
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
# chmod are the first 2 statements of the pod preparation and ssh-keygen is the
# third, so all 3 absent is "the preparation was not entered".
run_entrypoint 0 "" "$PROBE_COMMAND"
touched_etc_ssh=""
for tripwire in mkdir chmod chown ssh-keygen; do
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
  assert_status_nonzero "an_empty_argv_at_euid_${empty_argv_uid}_is_refused" \
    "$ENTRYPOINT_STATUS" \
    "an exec with no argv is a no-op, and the next statement is the pod preparation" \
    "it printed:" "${ENTRYPOINT_OUTPUT:-<nothing>}" \
    "the stubs recorded:" "$(stub_log)"

  assert_not_contains "an_empty_argv_at_euid_${empty_argv_uid}_does_not_reach_the_pod_preparation" \
    "$(stub_log)" "ssh-keygen" \
    "falling through here would start an sshd for a caller who asked for a command" \
    "it printed:" "${ENTRYPOINT_OUTPUT:-<nothing>}"
done

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

# shellcheck disable=SC2016
# The single quotes are the point: the needle is the LITERAL source text of the
# redirection, and a `${DEGRADED_MARKER}` this file expanded would search the
# entrypoint for a path instead of for the write that uses it.
marker_write="$(grep -cF -- '>>"${DEGRADED_MARKER}"' <<< "$entrypoint_code")" || marker_write=0
assert_equal "degraded_appends_to_the_marker_rather_than_only_logging" \
  "1" "$marker_write" \
  "the marker write is what makes a degraded boot MACHINE-READABLE" \
  "a degraded() that only logged would leave the state invisible to everything but a human"

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

# The pod arm's ORDER, as the order the sections appear in the file. It is a
# structural proxy and it says so: what it holds is that host keys come before
# authorized_keys, that the mcu links come before code-server, and that the sshd
# exec is below all of them. Moving the sshd exec above code-server would start
# the listener and never reach the browser IDE, and no reader of a running pod
# would see why.
order_ok=1
order_evidence=""
previous=0
for marker in \
  "# -------- host keys --------" \
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
  pass_check "the_pod_arm_states_its_5_steps_in_order"
else
  fail_check "the_pod_arm_states_its_5_steps_in_order" \
    "the pod preparation must read host keys -> authorized_keys -> mcu symlinks -> code-server -> sshd" \
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
