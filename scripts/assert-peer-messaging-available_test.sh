#!/usr/bin/env bash
#
# scripts/assert-peer-messaging-available_test.sh — behaviour test for
# scripts/assert-peer-messaging-available.sh, the in-container preflight that proves a
# `claude -p` session of THIS pinned version can reach the cross-session messaging socket.
#
# The preflight exists so a missing socket fails the harness-conformance job HERE, with a named
# cause, instead of surfacing much later as "no message received". A preflight that cannot fail is
# the same defect one layer up, so this test drives the subject over the cases that separate a real
# check from a check-shaped one:
#
#   1. THE BAND SPLIT. The messaging socket appears at claude 2.1.224. Below it the capability does
#      not exist, so the preflight prints UNEXERCISED and starts NO session; from it the preflight
#      proves the socket. The split compares the 3 components as NUMBERS. `2.1.9` and `2.1.30` both
#      sort above `2.1.224` as strings while both are below the flip, and `2.10.0` is above the flip
#      while its last component is below 224 — the 3 rows that kill a comparison which is not
#      numeric per component. An unparseable version is a FAILURE, never a band guess.
#   2. THE RECEIPT VERDICT. The high band judges the text a SessionStart hook wrote. Every way that
#      text can lie — absent, truncated, an unset socket variable, a path that is not
#      /tmp/cc-socks/<pid>.sock, is_socket=no — is a distinct verdict. An implementation that reads
#      the receipt and always says ok dies on rows 2 to 8 of that table.
#   3. NO SESSION IN THE LOW BAND, AND NONE ON ANY FAILURE. The stub `claude` records every
#      invocation it receives and refuses anything but `--version`. Each case asserts the recorded
#      set, so a subject that starts a `-p` turn where it must not is caught by the record, not by
#      trust. NOTHING in this file starts a real session: `claude` here is always the stub.
#   4. THE PROBE BODY, DRIVEN BY THE STUB. The high band is the half of the subject a live low-band
#      run can never reach, so a case opts the stub into a session mode and the stub plays claude:
#      it reads the --settings file the subject wrote, binds a REAL AF_UNIX socket at
#      /tmp/cc-socks/<pid>.sock, exports CLAUDE_CODE_MESSAGING_SOCKET to the SessionStart hook only
#      — the way claude does — and runs that hook. The 3 shapes are the success path (verdict ok,
#      exit 0, and the work directory REMOVED, because a preflight that leaks a temp directory on
#      the path it takes 99% of the time leaks it in every job), a turn whose hook never fired, and
#      a turn the deadline killed (stub `timeout`, exit 124). The stub records the settings path, so
#      "the work directory was removed" is read from the path the subject really used.
#
# It drives the subject against stub `claude` and `uname` binaries on PATH, in the style of
# assert-no-skipped-tests_test.sh, so no harness, no credential and no network take part. The pure
# functions are called by sourcing the subject in a subshell, which the subject's main-guard makes
# safe. Run it directly:
#   bash scripts/assert-peer-messaging-available_test.sh
# It exits non-zero when any assertion mismatches. shellcheck-clean at -S style.
set -Eeuo pipefail
IFS=$'\n\t'

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
subject="${here}/assert-peer-messaging-available.sh"

# The credential a `claude -p` turn needs in the harness-conformance job. The name is the one the
# job already carries (.github/workflows/harness-conformance.yml) and the one
# assert-harness-conformance-preconditions.sh already requires.
credential_variable='CLAUDEADAPTER_LIVE_TOKEN'

if [[ ! -f "$subject" ]]; then
  printf 'assert-peer-messaging-available_test: FAILED — the subject does not exist: %s\n' \
    "$subject" >&2
  printf '  This suite is red by absence. It goes green when that script exists and satisfies\n' >&2
  printf '  the contract in this file: peer_messaging_band, peer_messaging_receipt_verdict,\n' >&2
  printf '  peer_messaging_kill_switch_names, and the whole-script cases below.\n' >&2
  exit 1
fi

fails=0
work="$(mktemp -d "${TMPDIR:-/tmp}/assert-peer-messaging-available_test.XXXXXX")"

invocation_log="${work}/claude-invocations.log"
stderr_file="${work}/stderr.txt"
# What the stub saw when it played a session: the --settings path it was handed, and every socket it
# bound. The first is how a case reads the subject's own work directory; the second is what to
# remove, since a bound AF_UNIX socket outlives the process that bound it.
settings_record="${work}/settings-path.txt"
socket_record="${work}/bound-sockets.txt"
: >"$settings_record"
: >"$socket_record"

# This trap owns the paths it removes: both are set above and both are global. A trap that reads a
# variable local to a function runs after that function returned, when the name is gone.
remove_test_artefacts() {
  local socket
  while IFS= read -r socket; do
    [[ -n "$socket" ]] || continue
    rm -f "$socket"
  done <"$socket_record"
  rm -rf "$work"
}
trap remove_test_artefacts EXIT

# --- the stubs ----------------------------------------------------------------------------------
# `claude` records what it was asked to do and answers only --version. Any other invocation is a
# started session: it is recorded, and unless the case opted in with STUB_CLAUDE_SESSION_MODE it is
# refused, so "no session started" stays a recorded fact everywhere else in this file.
stub_directory="${work}/bin"
mkdir -p "$stub_directory"
cat >"${stub_directory}/claude" <<'STUB_CLAUDE'
#!/usr/bin/env bash
# Stub `claude` for assert-peer-messaging-available_test.sh. It appends its arguments to
# STUB_CLAUDE_INVOCATION_LOG, prints STUB_CLAUDE_VERSION for --version, and plays a session only
# when STUB_CLAUDE_SESSION_MODE asks for one.
set -Eeuo pipefail
printf '%s\n' "$*" >>"${STUB_CLAUDE_INVOCATION_LOG}"
if [[ "${1:-}" == '--version' ]]; then
  printf '%s\n' "${STUB_CLAUDE_VERSION}"
  exit "${STUB_CLAUDE_VERSION_STATUS:-0}"
fi

if [[ "${STUB_CLAUDE_SESSION_MODE:-refuse}" == 'refuse' ]]; then
  printf 'stub claude: refused — this is a session start, not a version read: %s\n' "$*" >&2
  exit 97
fi

# A session. Find the settings file the subject wrote and record it: its directory IS the subject's
# work directory, which is how a case can ask whether that directory was removed afterwards.
settings=''
while [[ $# -gt 0 ]]; do
  if [[ "$1" == '--settings' ]]; then
    settings="${2:-}"
    break
  fi
  shift
done
if [[ -z "$settings" || ! -f "$settings" ]]; then
  printf 'stub claude: the invocation carries no readable --settings file\n' >&2
  exit 96
fi
printf '%s\n' "$settings" >"${STUB_CLAUDE_SETTINGS_RECORD}"

hook="$(grep -o '"command"[[:space:]]*:[[:space:]]*"[^"]*"' "$settings" | tail -1 |
  sed 's/.*"\(.*\)"$/\1/')"
if [[ -z "$hook" || ! -x "$hook" ]]; then
  printf 'stub claude: the settings name no runnable SessionStart hook: %s\n' "$settings" >&2
  exit 95
fi

if [[ "${STUB_CLAUDE_SESSION_MODE}" == 'session-without-receipt' ]]; then
  # The turn runs and the SessionStart hook never fires. No receipt is written, which is exactly
  # the shape the preflight exists to catch.
  printf 'ready\n'
  exit 0
fi

# session-with-socket: bind a REAL AF_UNIX socket at the shape claude uses, then run the hook with
# the messaging variables in ITS environment and in nothing else — the reason the preflight needs a
# hook at all.
socket_directory='/tmp/cc-socks'
mkdir -p "$socket_directory"
socket="${socket_directory}/$$.sock"
rm -f "$socket"
python3 -c '
import socket as socket_module
import sys

server = socket_module.socket(socket_module.AF_UNIX, socket_module.SOCK_STREAM)
server.bind(sys.argv[1])
' "$socket"
printf '%s\n' "$socket" >>"${STUB_CLAUDE_SOCKET_RECORD}"
CLAUDE_CODE_MESSAGING_SOCKET="$socket" CLAUDE_CODE_MESSAGING_TOKEN='test-only-not-a-token' "$hook"
printf 'ready\n'
STUB_CLAUDE
chmod +x "${stub_directory}/claude"

# `timeout` runs what it is given, unless STUB_TIMEOUT_STATUS asks it to answer like GNU timeout
# after it killed the command (exit 124). It skips timeout's own options and its duration, so it
# survives the day the subject grows a `-k 30`.
cat >"${stub_directory}/timeout" <<'STUB_TIMEOUT'
#!/usr/bin/env bash
# Stub `timeout` for assert-peer-messaging-available_test.sh.
set -Eeuo pipefail
if [[ -n "${STUB_TIMEOUT_STATUS:-}" ]]; then
  printf 'stub timeout: the command was killed at the deadline\n' >&2
  exit "${STUB_TIMEOUT_STATUS}"
fi
while [[ $# -gt 0 ]]; do
  case "$1" in
    -k | --kill-after | -s | --signal) shift 2 ;;
    -*) shift ;;
    *) break ;;
  esac
done
shift
exec "$@"
STUB_TIMEOUT
chmod +x "${stub_directory}/timeout"

# `uname` answers with STUB_UNAME_S so the OS check is reachable from a test.
cat >"${stub_directory}/uname" <<'STUB_UNAME'
#!/usr/bin/env bash
# Stub `uname` for assert-peer-messaging-available_test.sh.
set -Eeuo pipefail
printf '%s\n' "${STUB_UNAME_S:-Linux}"
STUB_UNAME
chmod +x "${stub_directory}/uname"

# The same directory without `claude`, for the not-installed case.
stub_directory_without_claude="${work}/bin-without-claude"
mkdir -p "$stub_directory_without_claude"
cp "${stub_directory}/uname" "${stub_directory_without_claude}/uname"

original_path="$PATH"
PATH="${stub_directory}:${original_path}"
export PATH
export STUB_CLAUDE_INVOCATION_LOG="$invocation_log"
export STUB_CLAUDE_SETTINGS_RECORD="$settings_record"
export STUB_CLAUDE_SOCKET_RECORD="$socket_record"
export STUB_CLAUDE_VERSION='2.1.212 (Claude Code)'
export STUB_CLAUDE_SESSION_MODE='refuse'
export STUB_UNAME_S='Linux'

# A PATH that still resolves a real claude would test the host, not the subject.
resolved_claude="$(command -v claude)"
if [[ "$resolved_claude" != "${stub_directory}/claude" ]]; then
  printf 'assert-peer-messaging-available_test: FAILED — the stub claude is not first on PATH (got %s).\n' \
    "$resolved_claude" >&2
  exit 1
fi

# --- the harness --------------------------------------------------------------------------------
run_status=0
run_output=''
run_stderr=''

# run_subject — run the whole script (it takes no arguments), capture stdout+stderr together, and
# start every case from an empty invocation record.
run_subject() {
  : >"$invocation_log"
  : >"$settings_record"
  run_output="$( ( bash "$subject" ) 2>&1 )" && run_status=0 || run_status=$?
}

# run_function <function name> [arguments...] — source the subject in a subshell and call one pure
# function. stdout and stderr are captured apart, so a case can assert that a refusal printed no
# verdict at all on stdout.
run_function() {
  : >"$invocation_log"
  run_output="$(
    bash -c '
      set -Eeuo pipefail
      source "$1" || exit 90
      shift
      "$@"
    ' _ "$subject" "$@" 2>"$stderr_file"
  )" && run_status=0 || run_status=$?
  run_stderr="$(cat "$stderr_file")"
}

report_fail() {
  local name="$1"
  shift
  printf '  FAIL  %s\n' "$name" >&2
  local problem
  for problem in "$@"; do
    printf '          %s\n' "$problem" >&2
  done
  fails=$((fails + 1))
}

# expect_case <name> <want status> <text that must appear> <text that must not appear|empty>
expect_case() {
  local name="$1" want_status="$2" want_present="$3" want_absent="$4"
  local problems=()
  if [[ $run_status -ne $want_status ]]; then
    problems+=("exit status got=${run_status} want=${want_status}")
  fi
  if [[ -n "$want_present" && "$run_output" != *"$want_present"* ]]; then
    problems+=("output does not contain: ${want_present}")
  fi
  if [[ -n "$want_absent" && "$run_output" == *"$want_absent"* ]]; then
    problems+=("output must not contain: ${want_absent}")
  fi
  if [[ ${#problems[@]} -ne 0 ]]; then
    problems+=('--- subject output ---' "$run_output" '----------------------')
    report_fail "$name" "${problems[@]}"
    return 0
  fi
  printf '  ok    %s\n' "$name"
}

# recorded_invocations — the arguments of each stub-claude call, one per line.
recorded_invocations() {
  [[ -f "$invocation_log" ]] || return 0
  cat -- "$invocation_log"
}

# count_probe_work_directories — how many of the subject's own work directories exist right now. The
# subject creates them with mktemp -d "${TMPDIR:-/tmp}/assert-peer-messaging-available.XXXXXX"; this
# test's own directory carries a _test infix, so it is not counted.
count_probe_work_directories() {
  local directory count=0
  for directory in "${TMPDIR:-/tmp}"/assert-peer-messaging-available.*; do
    [[ -d "$directory" ]] || continue
    count=$((count + 1))
  done
  printf '%d\n' "$count"
}

# expect_session_started <case name> — the record holds exactly 1 session, and the stub served it.
# Without this, a subject that printed OK while starting no turn at all would pass the probe cases.
expect_session_started() {
  local name="$1" line sessions=0
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    if [[ "$line" != '--version' ]]; then
      sessions=$((sessions + 1))
    fi
  done < <(recorded_invocations)
  if [[ $sessions -ne 1 ]]; then
    report_fail "$name" "the record holds ${sessions} session(s), want 1" \
      "record: $(recorded_invocations | tr '\n' '|')" \
      'the probe proves the socket with ONE claude -p turn, and the stub is the only claude here'
    return 0
  fi
  printf '  ok    %s\n' "$name"
}

# expect_work_directory_removed <case name> — the subject removed the work directory it wrote its
# hook and its settings into. The path comes from the stub, so this reads the directory the subject
# really used and never a guess.
expect_work_directory_removed() {
  local name="$1" settings_path='' probe_work=''
  settings_path="$(cat -- "$settings_record")"
  if [[ -z "$settings_path" ]]; then
    report_fail "$name" 'the stub recorded no --settings path, so no work directory was observed' \
      'the case proves nothing about cleanup — the turn never reached the stub'
    return 0
  fi
  probe_work="${settings_path%/*}"
  if [[ -d "$probe_work" ]]; then
    report_fail "$name" "the work directory is still there: ${probe_work}" \
      "it holds: $(find "$probe_work" -mindepth 1 -maxdepth 1 | tr '\n' ' ')" \
      'the EXIT trap must remove it on EVERY path, and a trap that reads a variable local to a function reads nothing once that function returned'
    return 0
  fi
  printf '  ok    %s\n' "$name"
}

# expect_no_session <case name> — the record may hold --version reads and nothing else.
expect_no_session() {
  local name="$1" line problems=()
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    if [[ "$line" != '--version' ]]; then
      problems+=("stub claude was asked to run: ${line}")
    fi
  done < <(recorded_invocations)
  if [[ ${#problems[@]} -ne 0 ]]; then
    problems+=('the preflight must start NO session here')
    report_fail "$name" "${problems[@]}"
    return 0
  fi
  printf '  ok    %s\n' "$name"
}

# --- test 1 — the band split is a version comparison, never a string comparison -------------------
printf '\n-- test 1: band split --\n'
band_rows=0
while IFS='|' read -r want raw; do
  [[ -n "$want" ]] || continue
  [[ "${want:0:1}" != '#' ]] || continue
  band_rows=$((band_rows + 1))
  run_function peer_messaging_band "$raw"
  if [[ "$want" == 'fail' ]]; then
    problems=()
    if [[ $run_status -eq 0 ]]; then
      problems+=('exit status got=0 want=non-zero on an unparseable version')
    fi
    if [[ "$run_output" == *low* || "$run_output" == *high* ]]; then
      problems+=("stdout named a band on an unparseable version: ${run_output}")
    fi
    if [[ -z "$run_stderr" ]]; then
      problems+=('the refusal named no cause on stderr')
    fi
    if [[ -n "$raw" && "$run_stderr" != *"$raw"* ]]; then
      problems+=("the refusal does not quote what it read: ${run_stderr}")
    fi
    if [[ ${#problems[@]} -ne 0 ]]; then
      report_fail "band: '${raw}' -> refuse" "${problems[@]}"
    else
      printf "  ok    band: '%s' -> refuse (%s)\n" "$raw" "${run_stderr%%$'\n'*}"
    fi
    continue
  fi
  if [[ $run_status -ne 0 || "$run_output" != "$want" ]]; then
    report_fail "band: '${raw}' -> ${want}" \
      "stdout got='${run_output}' want='${want}'" \
      "exit status got=${run_status} want=0" \
      "stderr: ${run_stderr}"
  else
    printf "  ok    band: '%s' -> %s\n" "$raw" "$want"
  fi
done <<'BAND_ROWS'
low|2.1.212 (Claude Code)
low|2.1.223 (Claude Code)
high|2.1.224 (Claude Code)
high|2.1.225 (Claude Code)
high|2.2.0 (Claude Code)
high|3.0.0 (Claude Code)
high|2.1.224
# The 3 rows that kill a comparison which is not numeric per component. As strings, 2.1.9 and
# 2.1.30 both sort ABOVE 2.1.224 (measured with bash [[ < ]] in C.UTF-8, the container locale), so
# a string comparison reads both high while both are below the flip. 2.10.0 is above the flip and
# its last component (0) is below 224, so a comparison of the patch alone reads it low.
low|2.1.9 (Claude Code)
low|2.1.30 (Claude Code)
high|2.10.0 (Claude Code)
# An unparseable version is never a band guess.
fail|
fail|unknown
fail|2.1 (Claude Code)
fail|Claude Code
BAND_ROWS

if [[ $band_rows -lt 14 ]]; then
  printf 'assert-peer-messaging-available_test: FAILED — the band table read %d rows; it holds 14.\n' \
    "$band_rows" >&2
  exit 1
fi
expect_no_session 'band: the pure function starts no session'

# --- test 2 — the receipt verdict names every way the receipt can lie -----------------------------
printf '\n-- test 2: receipt verdicts --\n'
# One receipt for each row, written as a file so the text carries real newlines.
receipt_ok="${work}/receipt-ok.txt"
printf 'messaging_socket=/tmp/cc-socks/4711.sock\nis_socket=yes\n' >"$receipt_ok"
receipt_empty="${work}/receipt-empty.txt"
: >"$receipt_empty"
receipt_socket_empty="${work}/receipt-socket-empty.txt"
printf 'messaging_socket=\nis_socket=no\n' >"$receipt_socket_empty"
receipt_socket_absent="${work}/receipt-socket-absent.txt"
printf 'is_socket=yes\n' >"$receipt_socket_absent"
receipt_incomplete="${work}/receipt-incomplete.txt"
printf 'messaging_socket=/tmp/cc-socks/4711.sock\n' >"$receipt_incomplete"
receipt_not_a_socket="${work}/receipt-not-a-socket.txt"
printf 'messaging_socket=/tmp/cc-socks/4711.sock\nis_socket=no\n' >"$receipt_not_a_socket"
receipt_wrong_directory="${work}/receipt-wrong-directory.txt"
printf 'messaging_socket=/tmp/claude/4711.sock\nis_socket=yes\n' >"$receipt_wrong_directory"
receipt_wrong_name="${work}/receipt-wrong-name.txt"
printf 'messaging_socket=/tmp/cc-socks/session.sock\nis_socket=yes\n' >"$receipt_wrong_name"

receipt_rows=0
while IFS='|' read -r want_verdict want_status receipt_path; do
  [[ -n "$want_verdict" ]] || continue
  [[ "${want_verdict:0:1}" != '#' ]] || continue
  receipt_rows=$((receipt_rows + 1))
  run_function peer_messaging_receipt_verdict "$(cat -- "$receipt_path")"
  problems=()
  [[ "$run_output" == "$want_verdict" ]] ||
    problems+=("verdict got='${run_output}' want='${want_verdict}'")
  [[ $run_status -eq $want_status ]] ||
    problems+=("exit status got=${run_status} want=${want_status}")
  if [[ ${#problems[@]} -ne 0 ]]; then
    problems+=("receipt: ${receipt_path##*/}" "stderr: ${run_stderr}")
    report_fail "receipt: ${receipt_path##*/} -> ${want_verdict}" "${problems[@]}"
  else
    printf '  ok    receipt: %-30s -> %s (exit %d)\n' "${receipt_path##*/}" "$want_verdict" "$run_status"
  fi
done <<RECEIPT_ROWS
ok|0|${receipt_ok}
receipt-empty|1|${receipt_empty}
socket-unset|1|${receipt_socket_empty}
socket-unset|1|${receipt_socket_absent}
receipt-incomplete|1|${receipt_incomplete}
socket-not-a-socket|1|${receipt_not_a_socket}
socket-path-unexpected|1|${receipt_wrong_directory}
socket-path-unexpected|1|${receipt_wrong_name}
RECEIPT_ROWS

if [[ $receipt_rows -lt 8 ]]; then
  printf 'assert-peer-messaging-available_test: FAILED — the receipt table read %d rows; it holds 8.\n' \
    "$receipt_rows" >&2
  exit 1
fi
expect_no_session 'receipt: the pure function starts no session'

# --- test 3 — the whole script: the low band, and every named hard failure ------------------------
printf '\n-- test 3: the script --\n'

# The low band prints UNEXERCISED, exits 0 and starts NO session. The credential is absent here on
# purpose: below the flip the preflight needs none, and a subject that demands one everywhere fails
# this case.
unset CLAUDE_CODE_MESSAGING_SOCKET
unset "${credential_variable}"
export STUB_CLAUDE_VERSION='2.1.212 (Claude Code)'
run_subject
expect_case 'low band: 2.1.212 -> exit 0 and UNEXERCISED' 0 'UNEXERCISED' 'FAILED'
expect_case 'low band: the verdict names the version it read' 0 '2.1.212' ''
expect_no_session 'low band: no session started'
if [[ "$(recorded_invocations)" != '--version' ]]; then
  report_fail 'low band: exactly one --version read' \
    "the record holds: $(recorded_invocations | tr '\n' ' ')" \
    'the low band reads the version once and does nothing else'
else
  printf '  ok    low band: exactly one --version read\n'
fi

# The low band must not inherit a socket from the environment: a set CLAUDE_CODE_MESSAGING_SOCKET
# below the flip is a lie about a capability that does not exist in this version.
export CLAUDE_CODE_MESSAGING_SOCKET='/tmp/cc-socks/4711.sock'
run_subject
expect_case 'low band: an inherited CLAUDE_CODE_MESSAGING_SOCKET -> exit 1, named' \
  1 'CLAUDE_CODE_MESSAGING_SOCKET' 'UNEXERCISED'
expect_no_session 'low band with an inherited socket: no session started'
unset CLAUDE_CODE_MESSAGING_SOCKET

# Hard failure 1 — claude is not installed at all.
saved_path="$PATH"
PATH="${stub_directory_without_claude}:/usr/bin:/bin:/usr/sbin:/sbin"
export PATH
if command -v claude >/dev/null 2>&1; then
  report_fail 'hard failure: claude absent' \
    "this PATH still resolves a claude: $(command -v claude)" \
    'the case cannot fail here, so it proves nothing — run it where claude is not installed'
else
  run_subject
  expect_case 'hard failure: claude not installed -> exit 1, named' 1 'not installed' 'UNEXERCISED'
  expect_case 'hard failure: claude not installed -> the cause names the binary' 1 'claude' ''
fi
PATH="$saved_path"
export PATH

# Hard failure 2 — the installed claude answers something no band can be read from.
export STUB_CLAUDE_VERSION='banana-3 (Claude Code)'
run_subject
expect_case 'hard failure: unparseable version -> exit 1, quotes what it read' \
  1 'banana-3' 'UNEXERCISED'
expect_no_session 'unparseable version: no session started'
export STUB_CLAUDE_VERSION='2.1.212 (Claude Code)'

# Hard failure 3 — a kill switch is set. The list is the subject's own; it must hold exactly 4
# names, and each one must really be read, not merely declared.
run_function peer_messaging_kill_switch_names
kill_switches=()
while IFS= read -r kill_switch; do
  [[ -n "$kill_switch" ]] || continue
  kill_switches+=("$kill_switch")
done <<<"$run_output"
if [[ $run_status -ne 0 ]]; then
  report_fail 'kill switches: the subject declares its list' \
    "peer_messaging_kill_switch_names exited ${run_status}" "stderr: ${run_stderr}"
elif [[ ${#kill_switches[@]} -ne 4 ]]; then
  report_fail 'kill switches: the list holds exactly 4 names' \
    "got ${#kill_switches[@]}: ${run_output}" \
    'the preflight checks 4 kill switches; a shorter list is an unchecked way to disable messaging'
else
  printf '  ok    kill switches: the list holds exactly 4 names (%s)\n' "$(printf '%s ' "${kill_switches[@]}")"
  for kill_switch in "${kill_switches[@]}"; do
    if [[ ! $kill_switch =~ ^[A-Z][A-Z0-9_]*$ ]]; then
      report_fail "kill switches: '${kill_switch}' is not an environment variable name" \
        'the list names environment variables, one per line'
      continue
    fi
    export "${kill_switch}=1"
    run_subject
    expect_case "hard failure: ${kill_switch} set -> exit 1, named" 1 "$kill_switch" 'UNEXERCISED'
    expect_no_session "kill switch ${kill_switch}: no session started"
    unset "${kill_switch}"
  done
fi

# Hard failure 4 — the preflight is an in-container check. Another OS cannot prove anything about
# the socket the job needs, so it is a failure and never a quiet pass.
export STUB_UNAME_S='Darwin'
run_subject
expect_case 'hard failure: unsupported OS -> exit 1, names the OS it read' 1 'Darwin' 'UNEXERCISED'
expect_no_session 'unsupported OS: no session started'
export STUB_UNAME_S='Linux'

# Hard failure 5 — in the high band the credential is required, and its absence is named BEFORE any
# session is attempted: the run must end with an empty session record even though it reached the
# probe.
export STUB_CLAUDE_VERSION='2.1.224 (Claude Code)'
unset "${credential_variable}"
run_subject
expect_case "hard failure: high band without ${credential_variable} -> exit 1, named" \
  1 "$credential_variable" 'UNEXERCISED'
expect_no_session "high band without a credential: no session started"
export STUB_CLAUDE_VERSION='2.1.212 (Claude Code)'

# --- test 3b — the probe body, played by the stub -------------------------------------------------
# Everything above stops before the turn. These 3 cases drive the turn itself, which is the half of
# the subject a live low-band run can never reach: the stub binds a real AF_UNIX socket and runs the
# subject's own SessionStart hook against it. `claude` is still the stub, and it is the only claude
# on PATH.
printf '\n-- test 3b: the probe --\n'

# ADR-0020 FAIL-NOT-SKIP: the socket the hook reads must be a real one, and python3 is what binds it
# here. An absent python3 is a failure of this environment, named, never a skipped case.
if ! command -v python3 >/dev/null 2>&1; then
  printf 'assert-peer-messaging-available_test: FAILED — python3 is required to bind the AF_UNIX socket the probe cases read; this host has none.\n' >&2
  printf '  Run it in the base devcontainer, which carries python3:\n' >&2
  printf '    bash .devcontainer/base/ctl.sh exec -- bash scripts/assert-peer-messaging-available_test.sh\n' >&2
  exit 1
fi

export STUB_CLAUDE_VERSION='2.1.224 (Claude Code)'
export "${credential_variable}=test-only-not-a-credential"

# Probe case 1 — the success path. The hook reads a real socket, the verdict is ok, the run exits 0,
# and the work directory the subject wrote its hook into is GONE afterwards. The cleanup assertion
# belongs here and not on a failure path: an EXIT trap that reads a variable local to a function
# still works while that function is on the stack (every failure path exits from inside it) and
# breaks exactly once the function has returned — which is the success path, the path every green
# job takes.
export STUB_CLAUDE_SESSION_MODE='session-with-socket'
work_directories_before="$(count_probe_work_directories)"
run_subject
expect_case 'probe: a real socket in the hook -> exit 0 and OK' \
  0 'assert-peer-messaging-available: OK — claude 2.1.224' 'FAILED'
expect_case 'probe: the receipt names the socket and its shape' 0 'is_socket=yes' ''
expect_case 'probe: the run reports the turn and the verdict' 0 'receipt verdict: ok' ''
expect_session_started 'probe: exactly one claude -p turn, served by the stub'
expect_work_directory_removed 'probe: the work directory is removed on the success path'
work_directories_after="$(count_probe_work_directories)"
if [[ "$work_directories_after" -ne "$work_directories_before" ]]; then
  report_fail 'probe: no work directory leaks' \
    "before=${work_directories_before} after=${work_directories_after} in ${TMPDIR:-/tmp}" \
    'each green run of this preflight would leave one directory behind in the job container'
else
  printf '  ok    probe: no work directory leaks (%s before, %s after)\n' \
    "$work_directories_before" "$work_directories_after"
fi

# Probe case 2 — the turn runs and the SessionStart hook never fires. No receipt is the shape that
# would otherwise surface much later as "no message received", so it is named here.
export STUB_CLAUDE_SESSION_MODE='session-without-receipt'
run_subject
expect_case 'probe: no receipt written -> exit 1, names the verdict' \
  1 'receipt-empty' 'OK — claude'
expect_case 'probe: the failure is the named kind' 1 'assert-peer-messaging-available: FAILED' ''
expect_session_started 'probe: the turn did run before the verdict'
expect_work_directory_removed 'probe: the work directory is removed after a failed verdict'

# Probe case 3 — the deadline killed the turn. GNU timeout answers 124, and the preflight must name
# that instead of reading the missing receipt as some other defect.
export STUB_CLAUDE_SESSION_MODE='session-with-socket'
export STUB_TIMEOUT_STATUS='124'
run_subject
expect_case 'probe: timeout kills the turn -> exit 1, names exit 124' 1 '124' 'OK — claude'
expect_case 'probe: a killed turn is a named failure' 1 'assert-peer-messaging-available: FAILED' ''
expect_no_session 'probe: the bound held — the turn never reached claude'
unset STUB_TIMEOUT_STATUS

export STUB_CLAUDE_SESSION_MODE='refuse'
export STUB_CLAUDE_VERSION='2.1.212 (Claude Code)'
unset "${credential_variable}"

if [[ $fails -ne 0 ]]; then
  printf '\nassert-peer-messaging-available_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi
printf '\nassert-peer-messaging-available_test: all assertions passed (%d band rows, %d receipt rows)\n' \
  "$band_rows" "$receipt_rows"
