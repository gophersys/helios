#!/usr/bin/env bash
#
# _ctl/tests/embedded-entrypoint.test.sh — the hermetic spec of the embedded
# image's dev-drop entrypoint.
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
# `embedded` ships `USER root`. embedded/embedded-entrypoint.sh is what puts the
# identity back: it execs the argv docker hands it AS `dev`, so
# `docker run embedded id` answers `dev` the way the pre-fold Dockerfile's
# `USER dev` line did. A kernel fact became a shell script, and this file is
# what holds the shell script to it.
#
# NOTHING ELSE IN THIS REPOSITORY PROVES BOTH ARMS OF THAT. `.ci/smoke.sh` runs
# the image with `--user dev`, which reaches the NON-root arm only — the euid-0
# arm, the one every plain `docker run` takes, is exercised here or nowhere.
# images.yaml says so beside the embedded entry.
#
# ============================================================================
# WHAT THIS FILE USED TO BE, AND WHY IT SHRANK
# ============================================================================
#
# It was 39 checks over a 2-armed MODE DISPATCH: `GOPHERSYS_EMBEDDED_MODE=devbox`
# entered a pod path that generated SSH host keys, installed authorized_keys,
# linked /dev/mcu-slot-N, started code-server on :8443 and exec'd sshd. That path
# is DELETED — Mateo, 2026-08-19: "yes strip and delete and clean up anything
# devbox we don't need any of it anymore"; the record is "The devbox mode is
# deleted" in .claude/rules/00-identity.md.
#
# So every check about the pod arm, every check about a near-miss mode value not
# entering it, and every TEXT check about a refusal inside it went with the code
# they read. What is left is the behaviour that survives, and it is still
# behaviour a shell script decides rather than the kernel — which is the whole
# reason this file was written.
#
# NOTHING HERE IS A TEXT CHECK ANY MORE. The old file read the pod arm as text
# because its statements wrote to absolute paths no PATH stub could intercept.
# The surviving file touches no path at all, so every check below RUNS the real
# script and reads what really happened.
#
# ============================================================================
# THE STUBS
# ============================================================================
#
# _ctl/tests/stubs/entrypoint/ holds 3, and they are all MODELS:
#
#   id                        the euid the case chooses.
#   runuser                   records, then execs, setting HOME/USER/LOGNAME
#                             the way the real one does.
#   embedded-probe-command    the CMD stand-in that reports its argv, its
#                             identity and a chosen exit status.
#
# The 5 TRIPWIRES — `mkdir`, `chmod`, `chown`, `ssh-keygen`, `stat` — were
# deleted with the pod path. They existed so that a fall-through into the host
# key generation would be a NAMED line in a log; there is no host key generation
# to fall into, and a tripwire over deleted code is a check that cannot fail.
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

# The log prefix. It is the string an operator greps a container's logs for, so
# it is a NAME with consumers and not decoration. It was `[devbox-entrypoint]`
# while the file was zephyr-devbox's, and the fold renamed it — a rename nothing
# held, which is how the old name would have survived in half the tree.
LOG_PREFIX="[embedded-entrypoint]"

# The documented exit status of the empty-argv refusal. README.md and
# .claude/rules/00-identity.md both spell it beside the step table, so it is a
# contract and not an implementation detail.
EMPTY_ARGV_EXIT=2

# The mode variable and its 1 magic value, spelled out as LITERALS — the same
# reason the old file spelled them: a test that read either out of the file it
# checks agrees with a typo. What they are asserted for is INVERTED now. They
# used to name the dispatch this file proved; they now name the dispatch that
# must be GONE, so that a revert, a bad merge or a copy from an old branch
# cannot quietly restore a pod path that nothing in the org sets and that no
# check below would otherwise notice.
DELETED_MODE_VARIABLE="GOPHERSYS_EMBEDDED_MODE"
DELETED_POD_MODE="devbox"

# The other surfaces the pod path owned, each spelled once. Same rule: these are
# what a restored devbox arm would put back, and this is the file that would see
# it first.
DELETED_SURFACES=(
  "/run/devbox-degraded"
  "/etc/ssh/hostkeys"
  "/etc/devbox/authorized_keys"
  "DEVBOX_AUTHORIZED_KEYS"
  "DEVBOX_CODE_SERVER_HASHED_PASSWORD"
  "DEVBOX_CODE_SERVER_AUTH"
  "code-server"
  "sshd"
  "mcu-slot"
)

STUB_LOG="$(mktemp)"
ENTRYPOINT_OUTPUT=""
ENTRYPOINT_STATUS=0

function cleanup() {
  rm -f "$STUB_LOG"
}
trap cleanup EXIT

# run_entrypoint <uid> [argv...]
#
# The environment is built from NOTHING (`env -i`), so the suite's own variables
# cannot reach the subject and decide a branch for it. PATH names the stub
# directory first and then the 2 system directories the exec'd command may need.
#
# THE STATUS IS READ ON ITS OWN LINE. `|| true` would discard it before `$?` ran
# and every case below would read 0, which is the reading this whole suite
# exists to prevent.
function run_entrypoint() {
  local uid="$1"
  shift
  : > "$STUB_LOG"
  ENTRYPOINT_STATUS=0
  ENTRYPOINT_OUTPUT="$(env -i \
    "PATH=${STUB_DIR}:/usr/bin:/bin" \
    "STUB_ENTRYPOINT_LOG=${STUB_LOG}" \
    "STUB_ID_UID=${uid}" \
    bash "$ENTRYPOINT" "$@" 2>&1)" \
    || ENTRYPOINT_STATUS=$?
}

# run_entrypoint_with_mode <uid> <mode value> [argv...] — the same run with the
# deleted mode variable SET. Nothing may read it, so every assertion about these
# runs is that they behave exactly like the runs above.
function run_entrypoint_with_mode() {
  local uid="$1" mode="$2"
  shift 2
  : > "$STUB_LOG"
  ENTRYPOINT_STATUS=0
  ENTRYPOINT_OUTPUT="$(env -i \
    "PATH=${STUB_DIR}:/usr/bin:/bin" \
    "STUB_ENTRYPOINT_LOG=${STUB_LOG}" \
    "STUB_ID_UID=${uid}" \
    "${DELETED_MODE_VARIABLE}=${mode}" \
    bash "$ENTRYPOINT" "$@" 2>&1)" \
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

# entrypoint_lines <grep argument...> — 0 matches is DATA, and a real grep error
# still ends the run. grep exits 1 when it matches nothing, this file runs under
# `set -Eeuo pipefail`, and "matched nothing" is an ANSWER here rather than a
# failure. The plain pipeline killed the old version of this file mid-run the
# first time that was break-tested: PASS lines, no FAIL line, and NO summary.
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
for stub in id runuser "$PROBE_COMMAND"; do
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

# The 5 tripwire stubs are DELETED, and their absence is asserted rather than
# assumed. A stub left on disk after the code it guarded went is residue that
# reads like coverage: a later author finds `ssh-keygen` in this directory and
# concludes something here still generates host keys.
stale_stubs=""
for stale in mkdir chmod chown ssh-keygen stat; do
  [[ ! -e "$STUB_DIR/$stale" ]] || stale_stubs="${stale_stubs:+${stale_stubs}
}stubs/entrypoint/${stale}"
done
if [[ -z "$stale_stubs" ]]; then
  pass_check "the_pod_paths_tripwire_stubs_are_gone"
else
  fail_check "the_pod_paths_tripwire_stubs_are_gone" \
    "these stubs modelled commands only the deleted pod path called:" \
    "$stale_stubs" \
    "a stub with no caller is scaffolding that reads like coverage"
fi

# -------- 2. euid 0: it EXECS the argv, as dev --------
# The image ships USER root, so this is the arm every `docker run embedded`
# takes. What it has to reproduce is what `USER dev` in the old Dockerfile did:
# the command runs, and it runs as dev.
run_entrypoint 0 "$PROBE_COMMAND" --flag "an argument"

assert_equal "at_euid_0_the_entrypoint_execs_the_argv" \
  "0" "$ENTRYPOINT_STATUS" \
  "the entrypoint must exec the command it was handed" \
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
assert_contains "the_command_runs_as_dev" \
  "$ENTRYPOINT_OUTPUT" "probe-user: dev" \
  "the old zephyr image said USER dev in its Dockerfile; this script is what replaces that line" \
  "the stubs recorded:" "$(stub_log)"

assert_contains "the_command_gets_devs_home" \
  "$ENTRYPOINT_OUTPUT" "probe-home: /home/dev" \
  "HOME=/root would send every cache and every oh-my-zsh read to the wrong tree"

assert_contains "at_euid_0_the_drop_goes_through_runuser" \
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
run_entrypoint 0 "$PROBE_COMMAND"
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

# -------- 3. a NON-ROOT euid --------
# This is the arm .ci/smoke.sh reaches: it runs this image with
# `docker run --user dev`. runuser is present in the image and UNPRIVILEGED
# there — the real binary refuses with "may not be used by non-root users" — so
# a script that always ran it would turn the repository's own smoke invocation
# into an error.
run_entrypoint 1000 "$PROBE_COMMAND" --flag

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

# -------- 4. an EMPTY argv is refused, at both euids --------
# `exec` with no command and no redirection is a NO-OP in bash: control falls to
# the next statement. With the pod path deleted the next statement is the end of
# the file, so an unguarded empty argv would hand the caller a container that
# started nothing and exited 0 — a silence, which is worse than the old
# fall-through because there is no log line at all to read afterwards.
#
# The image declares CMD, so reaching this needs a caller that replaced it with
# nothing. EXACTLY 2, and not merely non-zero: the status is the documented
# contract and both step tables spell it.
for empty_argv_uid in 0 1000; do
  run_entrypoint "$empty_argv_uid"

  assert_equal "an_empty_argv_at_euid_${empty_argv_uid}_is_refused" \
    "$EMPTY_ARGV_EXIT" "$ENTRYPOINT_STATUS" \
    "an exec with no argv is a no-op, and a script that then simply ends reports success" \
    "it printed:" "${ENTRYPOINT_OUTPUT:-<nothing>}" \
    "the stubs recorded:" "$(stub_log)"

  assert_contains "an_empty_argv_at_euid_${empty_argv_uid}_names_its_cause" \
    "$ENTRYPOINT_OUTPUT" "no command to exec" \
    "an exit code with no line above it leaves the caller to guess which of 2 things broke"

  assert_contains "an_empty_argv_at_euid_${empty_argv_uid}_logs_through_the_images_prefix" \
    "$ENTRYPOINT_OUTPUT" "$LOG_PREFIX" \
    "this is the string an operator greps for, and the refusal is the 1 line this script ever writes"

  assert_not_contains "an_empty_argv_at_euid_${empty_argv_uid}_runs_no_command" \
    "$(stub_log)" "$PROBE_COMMAND" \
    "a refusal that also ran something is not a refusal" \
    "it printed:" "${ENTRYPOINT_OUTPUT:-<nothing>}"
done

# -------- 5. the deleted mode variable is INERT --------
# The pod path is gone, so GOPHERSYS_EMBEDDED_MODE decides nothing. This section
# is the guard against a revert putting it back: it sets the variable to the
# value that used to open the pod path and asserts the run is byte-identical to
# the run without it.
#
# THIS IS THE CHECK THAT WOULD FAIL FIRST if the dispatch came back, and it is
# the reason the literals above are spelled here rather than read out of the
# subject. A test that read the mode name out of the file would find nothing to
# read and agree with any file.
for restored_uid in 0 1000; do
  run_entrypoint_with_mode "$restored_uid" "$DELETED_POD_MODE" "$PROBE_COMMAND"

  assert_equal "mode_${DELETED_POD_MODE}_at_euid_${restored_uid}_still_execs_the_argv" \
    "0" "$ENTRYPOINT_STATUS" \
    "${DELETED_MODE_VARIABLE} names a dispatch that is deleted; setting it may change nothing" \
    "it printed:" "${ENTRYPOINT_OUTPUT:-<nothing>}" \
    "the stubs recorded:" "$(stub_log)"

  # The COMMAND ran. That is the whole property: the old pod arm never exec'd
  # the argv at all — it ended at `exec /usr/sbin/sshd -D -e` — so a run that
  # reaches this stub is a run that did not take a pod path.
  assert_contains "mode_${DELETED_POD_MODE}_at_euid_${restored_uid}_reaches_the_command" \
    "$(stub_log)" "$PROBE_COMMAND" \
    "a restored pod arm would exec sshd and never reach the command this caller named" \
    "it printed:" "${ENTRYPOINT_OUTPUT:-<nothing>}"
done

# The euid-0 arm carries the extra half, and it is asserted only there: at a
# non-zero euid the process is ALREADY dev, so the entrypoint execs plainly and
# sets no identity — `probe-user` is legitimately unset in that run, and
# asserting `dev` there would be a test written against the stub rather than
# against the contract.
run_entrypoint_with_mode 0 "$DELETED_POD_MODE" "$PROBE_COMMAND"
assert_contains "mode_${DELETED_POD_MODE}_at_euid_0_still_drops_to_dev" \
  "$ENTRYPOINT_OUTPUT" "probe-user: dev" \
  "the identity this script exists to set must not depend on a variable that decides nothing"

# -------- 6. the pod path is gone from the FILE, surface by surface --------
# Section 5 proves the BEHAVIOUR. This proves the text, because a half-restored
# pod path — a constant back, its branch not yet — would satisfy section 5 and
# be the seed of the next revert. Comments are read too, and deliberately: the
# file's own header records the deletion, so what these needles must not find is
# a comment that still DOCUMENTS a live pod path.
#
# The needles are checked against the CODE and the header separately for exactly
# that reason: the header sentence "the /run/devbox-degraded marker went with the
# pod" is a record and must be allowed, while a `DEGRADED_MARKER=` assignment is
# a restoration. So the code check reads code, and there is no whole-file check.
entrypoint_code="$(entrypoint_lines -vE '^[[:space:]]*#')"

restored=""
for surface in "$DELETED_MODE_VARIABLE" "${DELETED_SURFACES[@]}"; do
  if printf '%s' "$entrypoint_code" | grep -qF -- "$surface"; then
    restored="${restored:+${restored}
}${surface}"
  fi
done
if [[ -z "$restored" ]]; then
  pass_check "no_devbox_surface_survives_in_the_entrypoints_code"
else
  fail_check "no_devbox_surface_survives_in_the_entrypoints_code" \
    "these belong to the deleted pod path and are back in the CODE of ${ENTRYPOINT_RELATIVE}:" \
    "$restored" \
    "the pod half was deleted on Mateo's order of 2026-08-19 and has no consumer anywhere in" \
    "the org — see 'The devbox mode is deleted' in .claude/rules/00-identity.md"
fi

# The whole file, as lines of code, is SMALL — and that is the property the
# deletion bought. A bound rather than an equality: a bound goes red when the pod
# path comes back and stays green when somebody adds a comment or an argument.
# The number is generous on purpose. It is not a style rule; it is the shape of
# "this script execs a command and does nothing else", and the pod path was 150
# lines of the 240 this file used to hold.
code_line_count=0
code_line_count="$(entrypoint_lines -cvE '^[[:space:]]*(#|$)')" || code_line_count=0
if [[ "$code_line_count" -le 20 ]]; then
  pass_check "the_entrypoint_is_still_only_a_dev_drop"
else
  fail_check "the_entrypoint_is_still_only_a_dev_drop" \
    "${ENTRYPOINT_RELATIVE} holds ${code_line_count} lines of code, and the bound is 20" \
    "this script execs the argv as dev and refuses an empty one; anything that needs more" \
    "lines than that is a second job, and the last one to live here was a pod"
fi

# -------- 7. the image and the entrypoint still agree --------
# Every check in this file is about a script nothing runs, unless the image
# names it as PID 1.
dockerfile_text="$(cat "$REPO_ROOT/embedded/Dockerfile")"

assert_contains "the_Dockerfile_entrypoints_this_file" \
  "$dockerfile_text" \
  'ENTRYPOINT ["/usr/local/bin/embedded-entrypoint.sh"]' \
  "every check in this file is about a script nothing runs, unless the image names it as PID 1"

# The Dockerfile's OWN devbox surfaces, held the same way. The image is where
# the pod half actually cost 1.5 GB: openssh-server, the sshd drop-in, the
# code-server .deb and its seeded extension set, and the 2 EXPOSE lines. Read as
# INSTRUCTIONS and not as prose — the file's header records the deletion in
# words, and that record must stay legal.
dockerfile_instructions="$(grep -vE '^[[:space:]]*#' "$REPO_ROOT/embedded/Dockerfile" || true)"
restored_image=""
for surface in "openssh-server" "sshd_config" "/etc/ssh/hostkeys" "/etc/devbox" \
               "code-server" "CODE_SERVER" "EXPOSE"; do
  if printf '%s' "$dockerfile_instructions" | grep -qF -- "$surface"; then
    restored_image="${restored_image:+${restored_image}
}${surface}"
  fi
done
if [[ -z "$restored_image" ]]; then
  pass_check "no_devbox_surface_survives_in_the_Dockerfiles_instructions"
else
  fail_check "no_devbox_surface_survives_in_the_Dockerfiles_instructions" \
    "these belong to the deleted pod half and are back in the INSTRUCTIONS of embedded/Dockerfile:" \
    "$restored_image" \
    "the image listens on nothing and installs no ssh server; that is what the deletion bought"
fi

test_summary "$TEST_NAME"
