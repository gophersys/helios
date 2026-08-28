#!/usr/bin/env bash
#
# _hooklib.sh — shared helpers for the supervisor template hooks (session-start, gate-tool,
# gate-commit, stop-gate). Mirrors project-go/hooks/_lib.sh mechanics: read the hook stdin once,
# extract fields with jq (graceful default), resolve the project dir, and emit the documented
# hookSpecificOutput channels. bash 3.2 safe; jq-optional but expected (baked into the base image).
#
# shellcheck shell=bash

sv_read_input() { HOOK_INPUT="$(cat)"; export HOOK_INPUT; }

# sv_json <jq-filter> [default]
sv_json() {
  local filter="$1" default="${2:-}"
  if command -v jq >/dev/null 2>&1 && [[ -n "${HOOK_INPUT:-}" ]]; then
    local v
    v="$(printf '%s' "$HOOK_INPUT" | jq -r "$filter // empty" 2>/dev/null)"
    [[ -n "$v" ]] && { printf '%s' "$v"; return 0; }
  fi
  printf '%s' "$default"
}

sv_project_dir() {
  if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then printf '%s' "$CLAUDE_PROJECT_DIR"; return; fi
  local cwd; cwd="$(sv_json '.cwd')"
  if [[ -n "$cwd" ]]; then printf '%s' "$cwd"; return; fi
  git rev-parse --show-toplevel 2>/dev/null || pwd
}

sv_fsm() { printf '%s/.claude/state/fsm.json' "$(sv_project_dir)"; }

# sv_current_state — current_state from the FSM, or "unknown".
sv_current_state() {
  local f; f="$(sv_fsm)"
  [[ -f "$f" ]] || { printf 'unknown'; return; }
  jq -r '.current_state // "unknown"' "$f" 2>/dev/null || printf 'unknown'
}

# sv_emit_context <event> <text> — additionalContext channel (SessionStart / PostToolUse).
sv_emit_context() {
  local event="$1" text="$2"
  if command -v jq >/dev/null 2>&1; then
    jq -n --arg ev "$event" --arg ctx "$text" \
      '{hookSpecificOutput: {hookEventName: $ev, additionalContext: $ctx}}'
  else
    local esc
    esc="$(printf '%s' "$text" | sed 's/\\/\\\\/g; s/"/\\"/g' | awk '{printf "%s\\n", $0}')"
    printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"%s"}}' "$event" "$esc"
  fi
}

# sv_deny <reason> — emit a PreToolUse deny decision and exit 0 (Claude Code honors the JSON
# decision regardless of exit code; we ALSO exit 2 so a harness that reads exit codes blocks too).
sv_deny() {
  local reason="$1"
  if command -v jq >/dev/null 2>&1; then
    jq -n --arg r "$reason" \
      '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $r}}'
  else
    local esc
    esc="$(printf '%s' "$reason" | sed 's/\\/\\\\/g; s/"/\\"/g' | awk '{printf "%s\\n", $0}')"
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}' "$esc"
  fi
  exit 2
}

# sv_block_stop <reason> — emit a Stop block decision.
sv_block_stop() {
  local reason="$1"
  if command -v jq >/dev/null 2>&1; then
    jq -n --arg r "$reason" '{decision: "block", reason: $r}'
  else
    local esc
    esc="$(printf '%s' "$reason" | sed 's/\\/\\\\/g; s/"/\\"/g' | awk '{printf "%s\\n", $0}')"
    printf '{"decision":"block","reason":"%s"}' "$esc"
  fi
  exit 0
}

# sv_tree_dirty — 0 if the working tree has any uncommitted change (the supervisor must leave a
# clean tree between transitions; git is the only memory). 1 if clean.
sv_tree_dirty() {
  local root; root="$(sv_project_dir)"
  [[ -n "$(git -C "$root" status --porcelain 2>/dev/null)" ]]
}

# sv_open_forks — count of files in the git index under init/decisions/open/. `git ls-files`
# reflects the index (staged-new listed, staged-deletion not), the single unambiguous predicate.
sv_open_forks() {
  local root; root="$(sv_project_dir)"
  git -C "$root" ls-files -- 'init/decisions/open/' 2>/dev/null | sed '/^$/d' | sort -u | wc -l | tr -d '[:space:]'
}
