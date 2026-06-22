#!/usr/bin/env bash
#
# gate-tool.sh — PreToolUse hook on Bash (the hard-interface wall).
#
# settings.json already denies raw Write/Edit/Bash and allows only the command scripts + a
# read-only git allowlist; this hook is the belt-and-suspenders that gives the agent an inline
# REASON when it reaches outside the hard interface, and catches a compound/obfuscated Bash
# command the allowlist's prefix match might not (e.g. `git status; rm -rf x`). It denies any
# Bash command that is not EXACTLY one of: a supervisor command script, or a read-only git verb.
#
# Deny channel: hookSpecificOutput.permissionDecision=deny (+ exit 2). Allow: exit 0.
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_hooklib.sh
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_hooklib.sh"

sv_read_input

TOOL="$(sv_json '.tool_name')"
[[ "$TOOL" == "Bash" ]] || exit 0   # only gate Bash; other tools are governed by settings.json deny

CMD="$(sv_json '.tool_input.command')"
[[ -n "$CMD" ]] || exit 0

# The whitelist of intent. A command is allowed iff EVERY statement in it (split on ; && || |)
# matches one of these safe forms. Anything else → deny with a reason.
#   - bash ./.claude/commands/<one-of-the-seven>.sh ...
#   - read-only git: git status|ls-files|log|diff|show (NEVER add|commit|push|rm|reset|mv)
_stmt_allowed() {
  local s="$1"
  # trim
  s="$(printf '%s' "$s" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')"
  [[ -z "$s" ]] && return 0   # empty statement (trailing separator) is harmless
  case "$s" in
    bash\ ./.claude/commands/state-show.sh*|\
    bash\ ./.claude/commands/propose-charter.sh*|\
    bash\ ./.claude/commands/ratify-charter.sh*|\
    bash\ ./.claude/commands/propose-questionnaire.sh*|\
    bash\ ./.claude/commands/open-decision.sh*|\
    bash\ ./.claude/commands/rule-decision.sh*|\
    bash\ ./.claude/commands/plan.sh*|\
    bash\ ./.claude/commands/advance.sh*)
      return 0 ;;
    git\ status*|git\ ls-files*|git\ log*|git\ diff*|git\ show*)
      return 0 ;;
    *) return 1 ;;
  esac
}

# Split the command into statements on the shell control operators and check each.
# (A conservative split: any of ; & | newline. We do not try to parse quoting — a quoted
# operator only makes us MORE strict, which is the safe direction for a deny-by-default wall.)
illegal=""
IFS=$'\n'
for stmt in $(printf '%s' "$CMD" | tr ';&|' '\n' | tr '\n' '\n'); do
  if ! _stmt_allowed "$stmt"; then
    illegal="$stmt"
    break
  fi
done
unset IFS

if [[ -n "$illegal" ]]; then
  sv_deny "Supervisor hard-interface violation: you may run ONLY the typed supervisor slash-commands (state-show / propose-charter / ratify-charter / propose-questionnaire / open-decision / rule-decision / plan / advance) and read-only git (status/ls-files/log/diff/show). The statement \`${illegal}\` is outside that interface and is denied. Act through a slash-command — never ad-hoc shell, Write, or Edit. Run \`/state-show\` to see the one legal transition."
fi

exit 0
