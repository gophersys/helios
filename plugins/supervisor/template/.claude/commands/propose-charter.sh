#!/usr/bin/env bash
#
# propose-charter.sh — FSM transition `propose-charter`: {init|charter_drafted} -> charter_drafted.
# Validates the JSON payload against the charter schema, checks the FSM guard (charter not yet
# ratified) against git, writes the canonical artifact init/charter/charter.md, advances state,
# appends audit, and prints the commit trailer. Does NOT commit.
#
# Usage: propose-charter.sh '<charter-json>'
#
# shellcheck shell=bash
# shellcheck source=_supervisor.sh
# shellcheck disable=SC1091
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_supervisor.sh"
sv_require_jq

PAYLOAD="${*:-}"
[[ -n "$PAYLOAD" ]] || sv_die "propose-charter requires a JSON charter payload as the argument."

TRANSITION="propose-charter"
ARTIFACT="init/charter/charter.md"

sv_assert_legal   "$TRANSITION"
sv_assert_guard   "$TRANSITION"
sv_validate_schema "charter" "$PAYLOAD"

title="$(printf '%s' "$PAYLOAD" | jq -r '.title')"
body="$(printf '%s' "$PAYLOAD" | jq -r '
  "# Charter — \(.title)\n\n## Problem\n\n\(.problem)\n\n## Outcomes\n\n" +
  ([.outcomes[] | "- " + .] | join("\n")) +
  "\n\n## Non-goals\n\n" + ([.non_goals[] | "- " + .] | join("\n")) +
  "\n\n## Constraints\n\n" + ([(.constraints // [])[] | "- " + .] | join("\n")) +
  "\n\n## Stakeholders\n\n" + ([.stakeholders[] | "- " + .] | join("\n")) + "\n"
')"

sv_write_markdown_artifact "$ARTIFACT" "$PAYLOAD" "$body"

printf 'wrote charter artifact: %s  (title: %s)\n' "$ARTIFACT" "$title"
sv_finish_transition "$TRANSITION" "$ARTIFACT" "supervisor" "$title"
