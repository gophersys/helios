#!/usr/bin/env bash
#
# propose-work-item.sh — FSM transition `propose-work-item`:
#   {charter_ratified|product_decomposed} -> product_decomposed.
# Decomposes the ratified product into ONE work item per invocation. Guard: the charter is
# ratified (init/charter/.ratified tracked in git). Validates the work-item schema, writes
# init/product/<id>.md, advances state, audits, prints the trailer. Does NOT commit.
#
# Usage: propose-work-item.sh '<work-item-json>'
#
# shellcheck shell=bash
# shellcheck source=_supervisor.sh
# shellcheck disable=SC1091
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_supervisor.sh"
sv_require_jq

PAYLOAD="${*:-}"
[[ -n "$PAYLOAD" ]] || sv_die "propose-work-item requires a JSON work-item payload."

TRANSITION="propose-work-item"

sv_assert_legal    "$TRANSITION"
sv_assert_guard    "$TRANSITION"
sv_validate_schema "work-item" "$PAYLOAD"

id="$(printf '%s' "$PAYLOAD" | jq -r '.id')"
ARTIFACT="init/product/${id}.md"

body="$(printf '%s' "$PAYLOAD" | jq -r '
  "# Work item — \(.title)\n\n## Summary\n\n\(.summary)\n\n## Acceptance criteria\n\n" +
  ([.acceptance[] | "- " + .] | join("\n")) +
  (if (.depends_on // []) | length > 0
   then "\n\n## Depends on\n\n" + ([.depends_on[] | "- " + .] | join("\n"))
   else "" end) + "\n"
')"

sv_write_markdown_artifact "$ARTIFACT" "$PAYLOAD" "$body"

printf 'wrote work item: %s  (id: %s)\n' "$ARTIFACT" "$id"
sv_finish_transition "$TRANSITION" "$ARTIFACT" "supervisor" "$id"
