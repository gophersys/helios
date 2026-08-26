#!/usr/bin/env bash
#
# scripts/assert-peer-messaging-available.sh — the harness-conformance job (ADR-0021) proves that a
# `claude -p` session of the INSTALLED pinned version can reach the same-host cross-session
# messaging socket, or it stops here with a named cause.
#
# The reason it runs here and not later: the socket is how one session reaches another, so a session
# that cannot reach it fails at the far end of a suite as "no message received", which names no
# cause and reads like flakiness. This preflight turns that into one red step that says what is
# missing.
#
# THE BAND. Same-host cross-session messaging landed in claude 2.1.224
# (code.claude.com/docs/en/cross-session-messaging.md). Below that release the capability does not
# exist, so there is nothing to prove: the preflight prints UNEXERCISED, starts NO session and exits
# 0. From 2.1.224 it starts ONE `claude -p` turn whose SessionStart hook writes a receipt, and it
# judges that receipt. The band is read from the INSTALLED binary — the one that will run the turn —
# and never from the pin, and the 3 components are compared as NUMBERS: as text, 2.1.30 sorts above
# 2.1.224 while it is below the flip, and 2.10.0 sorts below it while it is above.
#
# NOTHING HERE IS A SKIP. An absent claude, a version no band can be read from, any of the 4 kill
# switches, a foreign operating system and — above the flip — an absent CLAUDEADAPTER_LIVE_TOKEN are
# each a FAILURE that names itself. Every failure of one run is collected and reported together.
#
# The pure functions are sourceable: the main guard at the foot keeps a `source` inert, so the band
# table and the receipt table are testable without a session, a credential or a network.
set -Eeuo pipefail
IFS=$'\n\t'

# The release that landed same-host cross-session messaging. Below it there is no socket to prove.
PEER_MESSAGING_MINIMUM_VERSION='2.1.224'

# The socket claude opens for a session: /tmp/cc-socks/<pid>.sock, execution-proven on 2.1.234. A
# receipt naming any other shape is not the capability the messaging program depends on.
PEER_MESSAGING_SOCKET_PATTERN='^/tmp/cc-socks/[0-9]+\.sock$'

# The credential a `claude -p` turn needs. The name is the one the job already carries and the one
# assert-harness-conformance-preconditions.sh already requires.
PEER_MESSAGING_CREDENTIAL='CLAUDEADAPTER_LIVE_TOKEN'

# The operating system this preflight can conclude anything on. Messaging itself is macOS+Linux, but
# the job runs in the base container: another answer from `uname -s` means the check is not running
# where the job runs, and a check that ran somewhere else proves nothing about the job's own session.
PEER_MESSAGING_OPERATING_SYSTEM='Linux'

# The probe's scratch directory. It is script-scope, and not a `local` in the function that makes
# it, because the EXIT trap runs at top level after that function has returned: a `local` is gone by
# then, `set -u` turns the cleanup into "work: unbound variable", and the SUCCESS path — the only
# path that returns instead of exiting inside the function — ends 1 with the directory left behind.
PEER_MESSAGING_WORK=''

# peer_messaging_kill_switch_names — the environment variables that disable cross-session messaging
# entirely, one per line. Each one makes the socket absent for a reason that is configuration and
# not a defect, so all 4 are read and the one that is set is named. The list is execution-proven
# (2.1.234) and it is the whole list: a name missing from it is an unchecked way to turn the feature
# off under a green preflight.
peer_messaging_kill_switch_names() {
  printf '%s\n' \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC \
    DISABLE_TELEMETRY \
    DO_NOT_TRACK \
    DISABLE_GROWTHBOOK
}

# peer_messaging_band <the text `claude --version` printed> — print `low` or `high` and exit 0, or
# name the cause on stderr and exit 1. A version it cannot read is never a band guess: guessing low
# would silently unexercise the check, and guessing high would start a turn that cannot work.
peer_messaging_band() {
  local reported="${1:-}"
  local version_pattern='^[[:space:]]*([0-9]+)\.([0-9]+)\.([0-9]+)([^0-9].*)?$'

  if [[ ! "$reported" =~ $version_pattern ]]; then
    printf "assert-peer-messaging-available: FAILED — no <major>.<minor>.<patch> version in what claude reported: '%s'\n" \
      "$reported" >&2
    return 1
  fi

  local -a installed=("${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}")
  local -a flip
  IFS='.' read -r -a flip <<<"$PEER_MESSAGING_MINIMUM_VERSION"

  local index
  for index in 0 1 2; do
    # 10# reads a component like 08 as decimal; without it bash refuses it as an octal literal.
    if ((10#${installed[index]} > 10#${flip[index]})); then
      printf 'high\n'
      return 0
    fi
    if ((10#${installed[index]} < 10#${flip[index]})); then
      printf 'low\n'
      return 0
    fi
  done
  printf 'high\n'
}

# peer_messaging_receipt_verdict <the text the SessionStart hook wrote> — print ONE verdict token
# and exit 0 for `ok` only.
#
# Every way the receipt can lie is a different verdict, because each one is a different defect: no
# receipt at all means the hook never ran, an unset socket means messaging is off in a version that
# has it, a half-written receipt means the hook died mid-write, a path outside /tmp/cc-socks/<pid>
# means the runtime moved and this preflight is reading the wrong thing, and is_socket=no means the
# name exists while the socket does not.
peer_messaging_receipt_verdict() {
  local receipt="${1:-}"
  local line socket='' socket_named='no' is_socket=''

  while IFS= read -r line; do
    case "$line" in
      messaging_socket=*)
        socket="${line#messaging_socket=}"
        socket_named='yes'
        ;;
      is_socket=*) is_socket="${line#is_socket=}" ;;
    esac
  done <<<"$receipt"

  if [[ -z "${receipt//[[:space:]]/}" ]]; then
    printf 'receipt-empty\n'
    return 1
  fi
  if [[ "$socket_named" == 'no' || -z "$socket" ]]; then
    printf 'socket-unset\n'
    return 1
  fi
  if [[ -z "$is_socket" ]]; then
    printf 'receipt-incomplete\n'
    return 1
  fi
  if [[ ! "$socket" =~ $PEER_MESSAGING_SOCKET_PATTERN ]]; then
    printf 'socket-path-unexpected\n'
    return 1
  fi
  if [[ "$is_socket" != 'yes' ]]; then
    printf 'socket-not-a-socket\n'
    return 1
  fi
  printf 'ok\n'
}

# peer_messaging_report_failures <cause...> — name every cause of this run together and stop.
peer_messaging_report_failures() {
  printf 'assert-peer-messaging-available: FAILED\n' >&2
  printf '  - %s\n' "$@" >&2
  exit 1
}

# peer_messaging_probe <the version claude reported> — the high band. Start ONE `claude -p` turn
# whose SessionStart hook writes a receipt, then judge the receipt. The turn is the only way to read
# the socket: claude exports CLAUDE_CODE_MESSAGING_SOCKET to its hooks and never to the shell that
# started it.
peer_messaging_probe() {
  local reported="$1"

  if [[ -z "${!PEER_MESSAGING_CREDENTIAL:-}" ]]; then
    peer_messaging_report_failures \
      "${PEER_MESSAGING_CREDENTIAL} is unset or empty — claude ${reported} cannot start the turn that proves the socket, and an unproven socket is what this preflight exists to refuse"
  fi
  if ! command -v timeout >/dev/null 2>&1; then
    peer_messaging_report_failures \
      "timeout is not installed — an unbounded 'claude -p' turn would hang this job instead of failing it"
  fi

  local receipt hook settings
  PEER_MESSAGING_WORK="$(mktemp -d "${TMPDIR:-/tmp}/assert-peer-messaging-available.XXXXXX")"
  trap 'rm -rf "$PEER_MESSAGING_WORK"' EXIT
  receipt="${PEER_MESSAGING_WORK}/receipt.txt"
  hook="${PEER_MESSAGING_WORK}/write-receipt.sh"
  settings="${PEER_MESSAGING_WORK}/settings.json"

  cat >"$hook" <<HOOK
#!/usr/bin/env bash
# Written by assert-peer-messaging-available.sh. claude runs it at SessionStart, after it exports
# the messaging variables, which is the only point where they can be read.
set -Eeuo pipefail
socket="\${CLAUDE_CODE_MESSAGING_SOCKET:-}"
if [[ -n "\$socket" && -S "\$socket" ]]; then
  is_socket=yes
else
  is_socket=no
fi
printf 'messaging_socket=%s\nis_socket=%s\n' "\$socket" "\$is_socket" >'${receipt}'
HOOK
  chmod +x "$hook"

  cat >"$settings" <<SETTINGS
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          { "type": "command", "command": "${hook}" }
        ]
      }
    ]
  }
}
SETTINGS

  # -k 30: TERM alone bounds nothing against a process that traps it, and this one starts a network
  # turn. KILL follows 30s later, so the step is bounded whatever claude does with the signal. 124
  # is the TERM timeout and 137 the KILL, and both arrive below as a named non-zero turn status.
  local turn_output='' turn_status=0
  # INJECT the credential this preflight just validated. It checked ${PEER_MESSAGING_CREDENTIAL}
  # (CLAUDEADAPTER_LIVE_TOKEN) was non-empty and then invoked claude without passing it, so the turn
  # ran unauthenticated: the check proved the token EXISTS and proved nothing about whether it WORKS.
  # CLAUDE_CODE_OAUTH_TOKEN is the name the CLI actually reads — the same constant claudeadapter
  # injects (claudeadapter.go:13). ANTHROPIC_API_KEY is scrubbed for the same reason the adapter
  # scrubs it: an inherited key would authenticate the turn by a DIFFERENT path, and the preflight
  # would pass while the credential it is supposed to prove was never exercised.
  turn_output="$(ANTHROPIC_API_KEY='' CLAUDE_CODE_OAUTH_TOKEN="${!PEER_MESSAGING_CREDENTIAL}" \
    timeout -k 30 120 claude -p 'Reply with the single word: ready.' --settings "$settings" 2>&1)" ||
    turn_status=$?

  local receipt_text=''
  if [[ -f "$receipt" ]]; then
    receipt_text="$(cat -- "$receipt")"
  fi

  local verdict='' verdict_status=0
  verdict="$(peer_messaging_receipt_verdict "$receipt_text")" || verdict_status=$?

  printf "claude -p -> exit %d   receipt verdict: %s\n" "$turn_status" "$verdict"
  if [[ $verdict_status -ne 0 ]]; then
    peer_messaging_report_failures \
      "the SessionStart receipt is not the socket this job needs: ${verdict}" \
      "receipt: $(printf '%s' "$receipt_text" | tr '\n' ' ')" \
      "'claude -p' exited ${turn_status}: ${turn_output}"
  fi
  if [[ $turn_status -ne 0 ]]; then
    peer_messaging_report_failures \
      "the receipt is ok but 'claude -p' exited ${turn_status}: ${turn_output}"
  fi

  printf 'assert-peer-messaging-available: OK — claude %s reached the messaging socket (%s)\n' \
    "$reported" "$(printf '%s' "$receipt_text" | tr '\n' ' ')"
}

main() {
  local failures=()

  local operating_system
  operating_system="$(uname -s)"
  if [[ "$operating_system" != "$PEER_MESSAGING_OPERATING_SYSTEM" ]]; then
    failures+=("'uname -s' reported '${operating_system}' and this preflight concludes on ${PEER_MESSAGING_OPERATING_SYSTEM} only — the job runs in the base container, so a check that ran elsewhere proves nothing about the session the job will start")
  fi

  local kill_switch
  while IFS= read -r kill_switch; do
    if [[ -n "${!kill_switch:-}" ]]; then
      failures+=("kill switch ${kill_switch} is set ('${!kill_switch}') — it disables cross-session messaging entirely, so the socket would be absent by configuration")
    fi
  done < <(peer_messaging_kill_switch_names)

  if ! command -v claude >/dev/null 2>&1; then
    failures+=("claude is not installed — the job installs the pinned harnesses before this step, so an absent binary means that install did not happen")
    peer_messaging_report_failures "${failures[@]}"
  fi

  local reported
  if ! reported="$(claude --version 2>&1)"; then
    failures+=("'claude --version' failed: ${reported}")
    peer_messaging_report_failures "${failures[@]}"
  fi
  printf 'claude --version -> %s   (messaging lands at %s)\n' "$reported" "$PEER_MESSAGING_MINIMUM_VERSION"

  local band=''
  if ! band="$(peer_messaging_band "$reported")"; then
    failures+=("claude reported a version no band can be read from: '${reported}'")
  fi

  if [[ ${#failures[@]} -gt 0 ]]; then
    peer_messaging_report_failures "${failures[@]}"
  fi

  if [[ "$band" == 'low' ]]; then
    # A socket variable below the flip describes a capability this claude does not have. Something
    # upstream set it, and taking it at face value is how a preflight goes green on nothing.
    if [[ -n "${CLAUDE_CODE_MESSAGING_SOCKET:-}" ]]; then
      peer_messaging_report_failures \
        "CLAUDE_CODE_MESSAGING_SOCKET is set ('${CLAUDE_CODE_MESSAGING_SOCKET}') while claude ${reported} is below ${PEER_MESSAGING_MINIMUM_VERSION} — that version has no cross-session messaging, so the variable names a capability that does not exist"
    fi
    printf 'assert-peer-messaging-available: UNEXERCISED — claude %s is below %s. No session was started and no socket was proven.\n' \
      "$reported" "$PEER_MESSAGING_MINIMUM_VERSION"
    return 0
  fi

  peer_messaging_probe "$reported"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
