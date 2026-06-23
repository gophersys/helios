#!/usr/bin/env bash
#
# propose-questionnaire.sh — FSM transition `propose-questionnaire`: init -> init (a self-loop
# in the early product-inquiry phase). Generates the product-scoping interview: ONE focused
# question per file under init/product/questionnaire/<NN>-<id>.md (NN is the 2-digit order, id is
# the question slug). The whole set is written in a single invocation. The setup wizard renders
# each file's BODY verbatim as the question, so the body carries only the question text (no
# front-matter) — written via sv_write_text_artifact. Guard: the charter is NOT yet ratified
# (the interview precedes the charter). Advances state (self-loop), audits, prints the trailer.
# Does NOT commit.
#
# Usage: propose-questionnaire.sh '{"questions":[{"id":"<slug>","prompt":"..."}, ...]}'
#
# shellcheck shell=bash
# shellcheck source=_supervisor.sh
# shellcheck disable=SC1091
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_supervisor.sh"
sv_require_jq

PAYLOAD="${*:-}"
[[ -n "$PAYLOAD" ]] || sv_die "propose-questionnaire requires a JSON questionnaire payload."

TRANSITION="propose-questionnaire"
ARTIFACT="init/product/questionnaire/"

sv_assert_legal    "$TRANSITION"
sv_assert_guard    "$TRANSITION"
sv_validate_schema "questionnaire" "$PAYLOAD"

count="$(printf '%s' "$PAYLOAD" | jq -r '.questions | length')"
[[ "$count" -gt 0 ]] || sv_die "questionnaire must contain at least one question."

i=0
while [[ "$i" -lt "$count" ]]; do
  qid="$(printf '%s' "$PAYLOAD" | jq -r --argjson i "$i" '.questions[$i].id')"
  prompt="$(printf '%s' "$PAYLOAD" | jq -r --argjson i "$i" '.questions[$i].prompt')"
  ord="$(printf '%02d' "$((i + 1))")"
  rel="init/product/questionnaire/${ord}-${qid}.md"
  sv_write_text_artifact "$rel" "$prompt"
  printf 'wrote question %s: %s\n' "$ord" "$rel"
  i=$((i + 1))
done

sv_finish_transition "$TRANSITION" "$ARTIFACT" "supervisor" "${count} questions"
