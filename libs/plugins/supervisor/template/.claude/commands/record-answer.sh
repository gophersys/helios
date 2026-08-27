#!/usr/bin/env bash
#
# record-answer.sh — FSM transition `record-answer`: init -> init (a self-loop in the early
# product-inquiry phase). Records the human's answer to ONE questionnaire question: writes
# init/product/answers/<question>.md whose body is the answer text (the wizard renders the file
# body verbatim and joins it to the question by the shared slug). Guard: a questionnaire exists
# (any file under init/product/questionnaire/). Advances state (self-loop), audits, prints the
# trailer. Does NOT commit.
#
# Usage: record-answer.sh '{"question":"<NN-slug>","answer":"..."}'
#
# shellcheck shell=bash
# shellcheck source=_supervisor.sh
# shellcheck disable=SC1091
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_supervisor.sh"
sv_require_jq

PAYLOAD="${*:-}"
[[ -n "$PAYLOAD" ]] || sv_die "record-answer requires a JSON answer payload."

TRANSITION="record-answer"

sv_assert_legal    "$TRANSITION"
sv_assert_guard    "$TRANSITION"
sv_validate_schema "answer" "$PAYLOAD"

# question is the question slug being answered; answer is the recorded text. Accept `text` /
# `response` as aliases for `answer` (a model commonly emits either); a blank answer is a HARD
# error so the wizard never renders "null" as the recorded answer.
question="$(printf '%s' "$PAYLOAD" | jq -r '.question // empty')"
[[ -n "$question" ]] || sv_die "record-answer payload has no question slug."
answer="$(printf '%s' "$PAYLOAD" | jq -r '.answer // .text // .response // empty')"
[[ -n "$answer" ]] || sv_die "record-answer payload for '$question' has no answer/text."
ARTIFACT="init/product/answers/${question}.md"

sv_write_text_artifact "$ARTIFACT" "$answer"

printf 'recorded answer: %s  (question: %s)\n' "$ARTIFACT" "$question"
sv_finish_transition "$TRANSITION" "$ARTIFACT" "supervisor" "$question"
