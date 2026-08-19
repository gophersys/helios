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
trap 'rm -rf "$work"' EXIT

invocation_log="${work}/claude-invocations.log"
stderr_file="${work}/stderr.txt"

# --- the stubs ----------------------------------------------------------------------------------
# `claude` records what it was asked to do and answers only --version. Any other invocation is a
# started session: it is recorded, it is refused, and the case that provoked it reads the record.
stub_directory="${work}/bin"
mkdir -p "$stub_directory"
cat >"${stub_directory}/claude" <<'STUB_CLAUDE'
#!/usr/bin/env bash
# Stub `claude` for assert-peer-messaging-available_test.sh. It appends its arguments to
# STUB_CLAUDE_INVOCATION_LOG, prints STUB_CLAUDE_VERSION for --version and refuses everything else.
set -Eeuo pipefail
printf '%s\n' "$*" >>"${STUB_CLAUDE_INVOCATION_LOG}"
if [[ "${1:-}" == '--version' ]]; then
  printf '%s\n' "${STUB_CLAUDE_VERSION}"
  exit "${STUB_CLAUDE_VERSION_STATUS:-0}"
fi
printf 'stub claude: refused — this is a session start, not a version read: %s\n' "$*" >&2
exit 97
STUB_CLAUDE
chmod +x "${stub_directory}/claude"

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
export STUB_CLAUDE_VERSION='2.1.212 (Claude Code)'
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
# session is attempted. This case is the only one that reaches the high band, and it must still end
# with an empty session record.
export STUB_CLAUDE_VERSION='2.1.224 (Claude Code)'
unset "${credential_variable}"
run_subject
expect_case "hard failure: high band without ${credential_variable} -> exit 1, named" \
  1 "$credential_variable" 'UNEXERCISED'
expect_no_session "high band without a credential: no session started"
export STUB_CLAUDE_VERSION='2.1.212 (Claude Code)'

if [[ $fails -ne 0 ]]; then
  printf '\nassert-peer-messaging-available_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi
printf '\nassert-peer-messaging-available_test: all assertions passed (%d band rows, %d receipt rows)\n' \
  "$band_rows" "$receipt_rows"
