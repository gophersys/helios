#!/usr/bin/env bash
#
# gate-commit.sh — PreToolUse hook on Bash, the COMMIT-TRAILER wall.
#
# The supervisor commands never commit (the orchestrator reviews + commits). But IF a `git commit`
# is ever attempted inside the harness, this hook proves its `fsm:` trailer is the LEGAL transition
# for the real git state, and that the committed artifact validates against its schema. It denies
# any commit whose trailer is missing, malformed, names an unknown transition, is not legal from a
# state the FSM could have been in, fails its git guard, or whose artifact fails its JSON Schema.
#
# Trailer grammar (one line, emitted by every command): `fsm: A -> B / transition / artifact / guard`.
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
[[ "$TOOL" == "Bash" ]] || exit 0
CMD="$(sv_json '.tool_input.command')"
case "$CMD" in *git*commit*) ;; *) exit 0 ;; esac   # only gate commits

PROJECT_DIR="$(sv_project_dir)"
FSM="$(sv_fsm)"
command -v jq >/dev/null 2>&1 || exit 0   # cannot verify without jq — degrade open (the command already computed it)
[[ -f "$FSM" ]] || exit 0

# Extract the commit message: prefer an inline -m "..."; else the message-file -F; else abort
# with a request to use the trailer (we cannot read an editor session here).
extract_message() {
  local c="$1"
  # -m "msg" or -m 'msg' (first occurrence; trailer is single-line so one -m carries it)
  local m
  m="$(printf '%s' "$c" | sed -nE "s/.*-m[[:space:]]+\"([^\"]*)\".*/\1/p")"
  [[ -n "$m" ]] && { printf '%s' "$m"; return; }
  m="$(printf '%s' "$c" | sed -nE "s/.*-m[[:space:]]+'([^']*)'.*/\1/p")"
  [[ -n "$m" ]] && { printf '%s' "$m"; return; }
}
MSG="$(extract_message "$CMD")"

# Find the fsm: trailer line.
TRAILER="$(printf '%s\n' "$MSG" | grep -E '^fsm:[[:space:]]' | tail -1 || true)"
if [[ -z "$TRAILER" ]]; then
  sv_deny "Supervisor commit blocked: the commit message has no \`fsm:\` trailer. Every supervisor commit MUST carry exactly one line of the grammar \`fsm: A -> B / transition / artifact / guard\` (printed by the slash-command you just ran). Re-run the transition command and copy its trailer onto the commit."
fi

# Parse: fsm: <from> -> <to> / <transition> / <artifact> / <guard>. Portable (no ERE backrefs /
# non-greedy quantifiers — BSD/macOS sed lacks them): drop the `fsm:` prefix, split on `/` into
# exactly four segments, and split the first on `->`. trim() collapses surrounding whitespace.
trim() { local s="$1"; s="${s#"${s%%[![:space:]]*}"}"; s="${s%"${s##*[![:space:]]}"}"; printf '%s' "$s"; }

BODY="$(trim "${TRAILER#fsm:}")"
# The segment delimiter is ' / ' (space-slash-space) — NOT a bare '/', because the artifact
# segment is a path that contains bare slashes (e.g. init/charter/charter.md). Replace the 3-char
# delimiter with a tab sentinel, then field-split on tab into exactly four segments.
SENT="$(printf '%s' "$BODY" | sed 's# / #\t#g')"
OLD_IFS="$IFS"; IFS=$'\t'
read -r SEG_STATES SEG_TRANS SEG_ART SEG_GUARD SEG_EXTRA <<EOF
$SENT
EOF
IFS="$OLD_IFS"
if [[ -z "$SEG_STATES" || -z "$SEG_TRANS" || -z "$SEG_ART" || -z "$SEG_GUARD" || -n "$SEG_EXTRA" ]]; then
  sv_deny "Supervisor commit blocked: the \`fsm:\` trailer is malformed: \`${TRAILER}\`. Required grammar: \`fsm: <from> -> <to> / <transition> / <artifact> / <guard>\` (exactly four ' / '-separated segments; states use underscores, transitions use hyphens)."
fi

# Split the states segment on '->'.
T_FROM="$(trim "${SEG_STATES%%->*}")"
T_TO="$(trim "${SEG_STATES#*->}")"
T_NAME="$(trim "$SEG_TRANS")"
T_ART="$(trim "$SEG_ART")"
T_GUARD="$(trim "$SEG_GUARD")"
if [[ "$SEG_STATES" != *"->"* || -z "$T_FROM" || -z "$T_TO" || -z "$T_NAME" || -z "$T_ART" || -z "$T_GUARD" ]]; then
  sv_deny "Supervisor commit blocked: the \`fsm:\` trailer is malformed: \`${TRAILER}\`. Required grammar: \`fsm: <from> -> <to> / <transition> / <artifact> / <guard>\`."
fi

# 1) The transition must exist in the FSM.
ROW="$(jq -c --arg t "$T_NAME" '.transitions[] | select(.transition==$t)' "$FSM")"
[[ -n "$ROW" ]] || sv_deny "Supervisor commit blocked: trailer names unknown transition '${T_NAME}'. It must be one declared in state/fsm.json."

# 2) `from` must be a legal source for this transition.
legal_from="$(printf '%s' "$ROW" | jq -r --arg s "$T_FROM" '([.from[]] | index($s)) != null')"
[[ "$legal_from" == "true" ]] || sv_deny "Supervisor commit blocked: '${T_NAME}' is not legal from '${T_FROM}' (legal from: $(printf '%s' "$ROW" | jq -rc '.from'))."

# 2b) `to` must be a declared destination of this transition (its static `to`, or one of the
#     `to_when` branches' `to`). This pins the trailer's claimed movement to the FSM table.
declared_to="$(printf '%s' "$ROW" | jq -r --arg s "$T_TO" '
  ([ (.to // empty) ] + [ (.to_when // [])[].to ]) as $tos
  | ($tos | index($s)) != null')"
[[ "$declared_to" == "true" ]] || sv_deny "Supervisor commit blocked: '${T_NAME}' has no declared destination '${T_TO}' (declared: $(printf '%s' "$ROW" | jq -rc '([ (.to // empty) ] + [ (.to_when // [])[].to ])'))."

# 3) `guard` id must match the transition's guard, AND the guard predicate must hold in git NOW.
g_id="$(printf '%s' "$ROW" | jq -r '.guard.id')"
[[ "$T_GUARD" == "$g_id" ]] || sv_deny "Supervisor commit blocked: trailer guard '${T_GUARD}' is not transition '${T_NAME}' guard '${g_id}'."
g_pred="$(printf '%s' "$ROW" | jq -r '.guard.git_predicate')"
g_path="$(printf '%s' "$ROW" | jq -r '.guard.path')"
# evaluate the predicate against git (same `git ls-files` index semantics as the command lib)
_tracked() { git -C "$PROJECT_DIR" ls-files --error-unmatch -- "$1" >/dev/null 2>&1; }
_any_under() {
  local n; n="$( git -C "$PROJECT_DIR" ls-files -- "${1%/}/" 2>/dev/null | sed '/^$/d' | sort -u | wc -l )"
  [[ "${n//[[:space:]]/}" -gt 0 ]]
}
guard_ok=1
case "$g_pred" in
  present)    _tracked "$g_path" || guard_ok=0 ;;
  absent)     _tracked "$g_path" && guard_ok=0 ;;
  any-under)  _any_under "$g_path" || guard_ok=0 ;;
  none-under) _any_under "$g_path" && guard_ok=0 ;;
esac
[[ "$guard_ok" -eq 1 ]] || sv_deny "Supervisor commit blocked: guard '${g_id}' ($g_pred '$g_path') is NOT satisfied in git. The transition's prerequisite is not present — this commit's claimed state movement is unforgeable, and git says it has not happened."

# 4) The committed artifact (if it is a schema-bearing markdown doc) must validate. We read the
#    fenced json front matter from the STAGED blob and check it against the transition's schema.
SCHEMA="$(printf '%s' "$ROW" | jq -r '.schema')"
SCHEMA_FILE="$PROJECT_DIR/.claude/schemas/${SCHEMA}.schema.json"
case "$T_ART" in
  */ | state/fsm.json) : ;;   # directory/marker/state artifacts carry no front-matter doc to validate here
  *.md)
    if [[ -f "$SCHEMA_FILE" ]]; then
      staged="$(git -C "$PROJECT_DIR" show ":${T_ART}" 2>/dev/null || true)"
      if [[ -n "$staged" ]]; then
        payload="$(printf '%s' "$staged" | awk '/^```json$/{f=1;next} /^```$/{f=0} f')"
        if [[ -n "$payload" ]]; then
          if ! printf '%s' "$payload" | jq -e . >/dev/null 2>&1; then
            missing="PARSE"
          else
            missing="$(jq -rn --slurpfile s "$SCHEMA_FILE" --argjson p "$payload" '($s[0].required // []) as $req | [ $req[] as $k | select(($p | has($k)) | not) | $k ] | join(", ")' 2>/dev/null || printf 'PARSE')"
          fi
          if [[ "$missing" == "PARSE" ]]; then
            sv_deny "Supervisor commit blocked: the staged artifact '${T_ART}' front-matter is not valid JSON; it cannot satisfy schema '${SCHEMA}'."
          elif [[ -n "$missing" ]]; then
            sv_deny "Supervisor commit blocked: the staged artifact '${T_ART}' fails schema '${SCHEMA}' — missing required field(s): ${missing}."
          fi
        fi
      fi
    fi
    ;;
esac

exit 0
