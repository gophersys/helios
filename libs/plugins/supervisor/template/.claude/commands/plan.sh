#!/usr/bin/env bash
#
# plan.sh — FSM transition `plan`: {decisions_ruled|product_decomposed} -> planned. Guard: the
# unforgeable 'no open fork' predicate (none-under init/decisions/open/). Validates the plan
# schema, cross-checks every referenced work-item id exists under init/product/, writes
# init/plan/plan.md, seeds one init/product/open/<package> marker per package (the advance
# transition's work-remaining tokens), advances state, audits, prints the trailer. Does NOT commit.
#
# Usage: plan.sh '<plan-json>'
#
# shellcheck shell=bash
# shellcheck source=_supervisor.sh
# shellcheck disable=SC1091
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_supervisor.sh"
sv_require_jq

PAYLOAD="${*:-}"
[[ -n "$PAYLOAD" ]] || sv_die "plan requires a JSON plan payload."

TRANSITION="plan"
ARTIFACT="init/plan/plan.md"

sv_assert_legal    "$TRANSITION"
sv_assert_guard    "$TRANSITION"
sv_validate_schema "plan" "$PAYLOAD"

root="$(sv_project_dir)"

# Cross-check: every referenced work-item id must have a file under init/product/.
while IFS= read -r wi; do
  [[ -n "$wi" ]] || continue
  [[ -f "$root/init/product/${wi}.md" ]] || sv_die "plan references unknown work item '$wi' (no init/product/${wi}.md). Decompose it first via /propose-questionnaire."
done < <(printf '%s' "$PAYLOAD" | jq -r '[.packages[].work_items[]] | unique[]')

# Write the plan document.
body="$(printf '%s' "$PAYLOAD" | jq -r '
  "# Implementation plan\n\n" +
  ([ .packages | sort_by(.order)[] |
     "## Package `\(.id)` (order \(.order))\n\n" +
     "Work items: " + ([.work_items[] | "`" + . + "`"] | join(", ")) +
     (if .budget then "\n\nBudget: " +
        ((.budget.max_cost_micros // 0)|tostring) + " micros / " +
        ((.budget.max_turns // 0)|tostring) + " turns" else "" end)
   ] | join("\n\n")) + "\n"
')"
sv_write_markdown_artifact "$ARTIFACT" "$PAYLOAD" "$body"

# Seed one work-remaining marker per package. These tracked files ARE the advance guard.
while IFS= read -r pkg; do
  [[ -n "$pkg" ]] || continue
  marker_rel="init/product/open/${pkg}"
  sv_write_json_marker "$marker_rel" "$(printf '%s' "$PAYLOAD" | jq -c --arg id "$pkg" '.packages[] | select(.id==$id)')"
  git -C "$root" add -- "$marker_rel" 2>/dev/null || true
done < <(printf '%s' "$PAYLOAD" | jq -r '.packages[].id')

n="$(printf '%s' "$PAYLOAD" | jq -r '.packages | length')"
printf 'wrote plan: %s  (%s package(s); seeded init/product/open/ markers)\n' "$ARTIFACT" "$n"
sv_finish_transition "$TRANSITION" "$ARTIFACT" "supervisor" "packages=$n"
