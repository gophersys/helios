#!/usr/bin/env bash
#
# open-decision.sh — FSM transition `open-decision`:
#   {product_decomposed|decisions_open|decisions_ruled} -> decisions_open.
# Records ONE unruled fork under init/decisions/open/<id>.md. Guard: the product is decomposed
# (at least one work item under init/product/). Validates the decision schema, writes the
# artifact, advances state, audits, prints the trailer. Does NOT commit.
#
# Usage: open-decision.sh '<decision-json>'
#
# shellcheck shell=bash
# shellcheck source=_supervisor.sh
# shellcheck disable=SC1091
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_supervisor.sh"
sv_require_jq

PAYLOAD="${*:-}"
[[ -n "$PAYLOAD" ]] || sv_die "open-decision requires a JSON decision payload."

TRANSITION="open-decision"

sv_assert_legal    "$TRANSITION"
sv_assert_guard    "$TRANSITION"
sv_validate_schema "decision" "$PAYLOAD"

id="$(printf '%s' "$PAYLOAD" | jq -r '.id')"
ARTIFACT="init/decisions/open/${id}.md"

body="$(printf '%s' "$PAYLOAD" | jq -r '
  "# Open decision — \(.question)\n\n" +
  (if (.context // "") != "" then "## Context\n\n\(.context)\n\n" else "" end) +
  "## Options\n\n" +
  ([.options[] | "- **\(.name)** — \(.tradeoffs)"] | join("\n")) +
  (if (.affects // []) | length > 0
   then "\n\n## Affects\n\n" + ([.affects[] | "- " + .] | join("\n"))
   else "" end) + "\n"
')"

sv_write_markdown_artifact "$ARTIFACT" "$PAYLOAD" "$body"

printf 'opened decision (UNRULED fork): %s  (id: %s)\n' "$ARTIFACT" "$id"
sv_finish_transition "$TRANSITION" "$ARTIFACT" "supervisor" "$id"
