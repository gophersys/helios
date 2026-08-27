#!/usr/bin/env bash
#
# _supervisor.sh — shared library for the supervisor slash-commands.
#
# Every transition command sources this. It centralizes the determinism primitives so the
# transition logic lives ONCE (one concept, one home):
#   - resolve the project root + the FSM file
#   - read current_state and the legal transition row for a named transition
#   - evaluate a GIT predicate guard against the real working tree (unforgeable by prose)
#   - validate an artifact payload against its JSON Schema
#   - write the artifact to its CANONICAL git path
#   - advance state/fsm.json's current_state
#   - append an audit/log.ndjson record
#   - print the parseable commit trailer grammar `fsm: A -> B / transition / artifact / guard`
#
# These commands NEVER git-commit: the orchestrator (the human/parent loop) reviews and commits.
# The command stages the artifact change in the working tree and prints the commit trailer the
# committer must use; hooks/gate-commit.sh re-derives the trailer and blocks any commit whose
# trailer is not the legal transition (defense in depth — the command computes it, the hook
# proves it).
#
# bash 3.2 safe (macOS); jq required (it is baked into the devcontainer base image).
#
# shellcheck shell=bash

set -Eeuo pipefail

# ── resolution ────────────────────────────────────────────────────────────────────────────

sv_project_dir() {
  if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then printf '%s' "$CLAUDE_PROJECT_DIR"; return; fi
  git rev-parse --show-toplevel 2>/dev/null || pwd
}

sv_fsm_path() { printf '%s/.claude/state/fsm.json' "$(sv_project_dir)"; }
sv_schema_path() { printf '%s/.claude/schemas/%s.schema.json' "$(sv_project_dir)" "$1"; }
sv_audit_path() { printf '%s/audit/log.ndjson' "$(sv_project_dir)"; }

sv_require_jq() {
  command -v jq >/dev/null 2>&1 || sv_die "jq is required (it is baked into the devcontainer base image)."
}

sv_die() { printf 'supervisor: %s\n' "$*" >&2; exit 2; }

# ── FSM reads ─────────────────────────────────────────────────────────────────────────────

sv_current_state() { jq -r '.current_state' "$(sv_fsm_path)"; }

# sv_transition_row <transition-name> — the JSON object for one transition, or empty.
sv_transition_row() {
  jq -c --arg t "$1" '.transitions[] | select(.transition == $t)' "$(sv_fsm_path)"
}

# sv_state_terminal <state> — "true"/"false".
sv_state_terminal() {
  jq -r --arg s "$1" '(.states[] | select(.name==$s) | .terminal) // false' "$(sv_fsm_path)"
}

# sv_assert_legal <transition-name> — current_state must be in the transition's `from`,
# else abort. This is the FSM legality wall: the agent may run ONLY a transition whose
# `from` contains the current state.
sv_assert_legal() {
  local t="$1" row cur
  row="$(sv_transition_row "$t")"
  [[ -n "$row" ]] || sv_die "unknown transition '$t' (not in state/fsm.json)."
  cur="$(sv_current_state)"
  local ok
  ok="$(printf '%s' "$row" | jq -r --arg s "$cur" '([.from[]] | index($s)) != null')"
  [[ "$ok" == "true" ]] || {
    local froms
    froms="$(printf '%s' "$row" | jq -r '.from | join(", ")')"
    sv_die "illegal transition: current_state is '$cur' but '$t' is legal only from {$froms}. Run /state-show to see the one legal transition."
  }
}

# ── git predicate guards (UNFORGEABLE — read the real tree, never prose) ────────────────────
#
# A guard is one of four predicates over a TRACKED git path, evaluated against the working
# tree's index/HEAD. The path is resolved relative to the project root. We read git, not the
# filesystem, so an untracked scratch file cannot satisfy a guard — only a committed/staged
# artifact can. This is what makes the guard impossible to talk past with prose.

# sv_git_tracked <relpath> — 0 if the path is in the git index NOW, 1 otherwise. `git ls-files`
# reflects the index after `git add` (staged-new is listed) and after `git rm` (removed is not),
# so it is the single unambiguous "present in git" predicate — no diff --cached, which would
# also list a staged DELETION and wrongly count a just-removed path as present.
sv_git_tracked() {
  local rel="$1" root; root="$(sv_project_dir)"
  git -C "$root" ls-files --error-unmatch -- "$rel" >/dev/null 2>&1
}

# sv_git_any_under <reldir> — 0 if any file is in the index under the directory.
sv_git_any_under() {
  local rel="$1" root n; root="$(sv_project_dir)"
  rel="${rel%/}"
  n="$(
    git -C "$root" ls-files -- "$rel/" 2>/dev/null | sed '/^$/d' | sort -u | wc -l
  )"
  [[ "${n//[[:space:]]/}" -gt 0 ]]
}

# sv_eval_predicate <predicate> <path> — 0 if satisfied, 1 otherwise. The four predicates:
#   present     — the path is a tracked/staged file
#   absent      — the path is NOT tracked/staged
#   any-under   — at least one tracked/staged file exists under the directory
#   none-under  — no tracked/staged file exists under the directory
sv_eval_predicate() {
  local pred="$1" path="$2"
  case "$pred" in
    present)    sv_git_tracked "$path" ;;
    absent)     ! sv_git_tracked "$path" ;;
    any-under)  sv_git_any_under "$path" ;;
    none-under) ! sv_git_any_under "$path" ;;
    *) sv_die "unknown git predicate '$pred' in fsm.json" ;;
  esac
}

# sv_assert_guard <transition-name> — evaluate the transition's guard; abort with the
# documented reason if unsatisfied. Prints nothing on success.
sv_assert_guard() {
  local t="$1" row pred path id desc
  row="$(sv_transition_row "$t")"
  pred="$(printf '%s' "$row" | jq -r '.guard.git_predicate')"
  path="$(printf '%s' "$row" | jq -r '.guard.path')"
  id="$(printf '%s' "$row" | jq -r '.guard.id')"
  desc="$(printf '%s' "$row" | jq -r '.guard.description')"
  if ! sv_eval_predicate "$pred" "$path"; then
    sv_die "guard '$id' FAILED: $desc (git predicate: $pred '$path'). This guard reads git, not prose — produce the artifact and stage/commit it first."
  fi
}

# ── schema validation ───────────────────────────────────────────────────────────────────────
#
# sv_validate_schema <schema-name> <payload-json> — validate a JSON payload against the named
# schema using ajv if present, else a jq structural fallback over `required`. Aborts on failure.
sv_validate_schema() {
  local schema="$1" payload="$2" schema_file
  schema_file="$(sv_schema_path "$schema")"
  [[ -f "$schema_file" ]] || sv_die "schema '$schema' not found at $schema_file"
  printf '%s' "$payload" | jq -e . >/dev/null 2>&1 || sv_die "payload for '$schema' is not valid JSON."

  if command -v ajv >/dev/null 2>&1; then
    local tmp; tmp="$(mktemp)"; printf '%s' "$payload" >"$tmp"
    if ! ajv validate -s "$schema_file" -d "$tmp" --strict=false >/dev/null 2>&1; then
      local err; err="$(ajv validate -s "$schema_file" -d "$tmp" --strict=false 2>&1 || true)"
      rm -f "$tmp"; sv_die "schema '$schema' validation failed:"$'\n'"$err"
    fi
    rm -f "$tmp"; return 0
  fi

  # Fallback: enforce top-level required keys (the load-bearing structural check). We read the
  # schema's `required` array and the payload's keys, then report any required key the payload
  # lacks. (jq `has` needs the key bound to a variable, not the iteration dot.)
  local missing
  missing="$(jq -rn \
    --slurpfile s "$schema_file" \
    --argjson p "$payload" '
      ($s[0].required // []) as $req
      | [ $req[] as $k | select(($p | has($k)) | not) | $k ] | join(", ")
    ')"
  [[ -z "$missing" ]] || sv_die "schema '$schema' validation failed: missing required field(s): $missing"
}

# ── artifact write ───────────────────────────────────────────────────────────────────────────
#
# sv_write_markdown_artifact <relpath> <frontmatter-json> <body> — write a markdown artifact
# whose YAML-ish front matter is the validated JSON payload (as a fenced json block for fidelity)
# plus a human body. Idempotent overwrite. Creates parent dirs.
sv_write_markdown_artifact() {
  local rel="$1" payload="$2" body="$3" root abs dir
  root="$(sv_project_dir)"; abs="$root/$rel"; dir="$(dirname "$abs")"
  mkdir -p "$dir"
  {
    printf '<!-- supervisor:artifact schema=%s -->\n' "$(basename "$dir")"
    printf '```json\n'
    printf '%s\n' "$payload" | jq -S .
    printf '```\n\n'
    printf '%s\n' "$body"
  } >"$abs"
  # Stage the artifact so a transition guard (which inspects the index) is satisfiable within ONE
  # supervisor turn. The orchestrator still commits (the agent only stages — 20-git-protocol.md).
  git -C "$root" add -- "$rel" 2>/dev/null || true
}

# sv_write_json_marker <relpath> <payload> — write a small JSON marker file (e.g. .ratified,
# the product/open/<id> markers). Creates parent dirs.
sv_write_json_marker() {
  local rel="$1" payload="$2" root abs dir
  root="$(sv_project_dir)"; abs="$root/$rel"; dir="$(dirname "$abs")"
  mkdir -p "$dir"
  printf '%s\n' "$payload" | jq -S . >"$abs"
  # Stage the marker (see sv_write_markdown_artifact) so a transition guard sees it in one turn.
  git -C "$root" add -- "$rel" 2>/dev/null || true
}

# sv_write_text_artifact <relpath> <body> — write a PLAIN text/markdown artifact whose ENTIRE file
# body is <body> (no front-matter, no fenced-json header). The setup wizard renders the
# init/product/questionnaire/* and init/product/answers/* files by taking the WHOLE file body as the
# question / answer text (setupWizard.ts parseQuestions/parseAnswers), so these artifacts must carry
# only that text — the supervisor:artifact comment a markdown artifact prepends would leak into the
# rendered question. Creates parent dirs and stages (git add) like the other writers, so a transition
# guard that inspects the index is satisfiable within one supervisor turn.
sv_write_text_artifact() {
  local rel="$1" body="$2" root abs dir
  root="$(sv_project_dir)"; abs="$root/$rel"; dir="$(dirname "$abs")"
  mkdir -p "$dir"
  printf '%s\n' "$body" >"$abs"
  # Stage the artifact (see sv_write_markdown_artifact) so a transition guard sees it in one turn.
  git -C "$root" add -- "$rel" 2>/dev/null || true
}

# ── state advance ────────────────────────────────────────────────────────────────────────────
#
# sv_advance_state <to-state> — rewrite state/fsm.json's current_state. The ONLY writer of
# current_state. Validates the target is a declared state.
sv_advance_state() {
  local to="$1" fsm tmp known
  fsm="$(sv_fsm_path)"
  known="$(jq -r --arg s "$to" '([.states[].name] | index($s)) != null' "$fsm")"
  [[ "$known" == "true" ]] || sv_die "cannot advance to unknown state '$to'."
  tmp="$(mktemp)"
  jq --arg s "$to" '.current_state = $s' "$fsm" >"$tmp"
  mv "$tmp" "$fsm"
}

# sv_resolve_target <transition-name> — print the destination state. If the transition has a
# static `to`, print it. If it has `to_when`, evaluate each branch's git predicate IN ORDER and
# print the first match's `to` (so the destination itself is git-derived — unforgeable).
sv_resolve_target() {
  local t="$1" row to n i pred path
  row="$(sv_transition_row "$t")"
  to="$(printf '%s' "$row" | jq -r '.to // empty')"
  if [[ -n "$to" ]]; then printf '%s' "$to"; return; fi
  n="$(printf '%s' "$row" | jq -r '.to_when | length')"
  i=0
  while [[ "$i" -lt "$n" ]]; do
    pred="$(printf '%s' "$row" | jq -r --argjson i "$i" '.to_when[$i].git_predicate')"
    path="$(printf '%s' "$row" | jq -r --argjson i "$i" '.to_when[$i].path')"
    if sv_eval_predicate "$pred" "$path"; then
      printf '%s' "$(printf '%s' "$row" | jq -r --argjson i "$i" '.to_when[$i].to')"
      return
    fi
    i=$((i + 1))
  done
  sv_die "no to_when branch matched for transition '$t' (fsm.json is incoherent)."
}

# ── audit + trailer ──────────────────────────────────────────────────────────────────────────

# sv_append_audit <transition> <from> <to> <artifact> <guard> [by] [detail]
sv_append_audit() {
  local t="$1" from="$2" to="$3" artifact="$4" guard="$5" by="${6:-supervisor}" detail="${7:-}"
  local audit dir entry
  audit="$(sv_audit_path)"; dir="$(dirname "$audit")"; mkdir -p "$dir"
  entry="$(jq -nc \
    --arg at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg transition "$t" --arg from "$from" --arg to "$to" \
    --arg artifact "$artifact" --arg guard "$guard" --arg by "$by" --arg detail "$detail" \
    '{at:$at, transition:$transition, from:$from, to:$to, artifact:$artifact, guard:$guard, by:$by, detail:$detail}')"
  printf '%s\n' "$entry" >>"$audit"
}

# sv_print_trailer <from> <to> <transition> <artifact> <guard> — print the canonical, parseable
# commit-trailer grammar the committer (orchestrator) must put on the commit, and that
# gate-commit.sh re-derives and verifies. Grammar: `fsm: A -> B / transition / artifact / guard`.
sv_print_trailer() {
  printf 'fsm: %s -> %s / %s / %s / %s\n' "$1" "$2" "$3" "$4" "$5"
}

# sv_run_transition <transition> <artifact-relpath-for-trailer> <payload-for-audit-detail>
# Common tail: assert legality + guard already done by the command; this resolves the target,
# advances state, appends audit, and prints the trailer. Returns the resolved target via stdout
# of nothing — it prints the human-facing trailer block.
sv_finish_transition() {
  local t="$1" artifact="$2" by="${3:-supervisor}" detail="${4:-}"
  local from to guard
  from="$(sv_current_state)"
  guard="$(sv_transition_row "$t" | jq -r '.guard.id')"
  to="$(sv_resolve_target "$t")"
  sv_advance_state "$to"
  sv_append_audit "$t" "$from" "$to" "$artifact" "$guard" "$by" "$detail"
  printf '\n--- transition recorded (NOT committed — the orchestrator reviews + commits) ---\n'
  printf 'state advanced: %s -> %s\n' "$from" "$to"
  printf 'commit with this trailer (gate-commit.sh enforces it):\n\n  '
  sv_print_trailer "$from" "$to" "$t" "$artifact" "$guard"
}
