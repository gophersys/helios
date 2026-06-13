#!/usr/bin/env bash
#
# project-go/hooks/_lib.sh — shared helpers for the Eden project-go plugin hooks.
# Sourced by session-start.sh, post-edit-lint.sh, pre-git-gate.sh.
#
# macOS ships bash 3.2; these hooks avoid bash-4-only builtins.
#
# shellcheck shell=bash

# Read the hook's stdin payload once into $HOOK_INPUT (Claude Code feeds a JSON object).
pg_read_input() {
  HOOK_INPUT="$(cat)"
  export HOOK_INPUT
}

# pg_json <jq-filter> [default] — extract a field from $HOOK_INPUT; prints default if jq
# is absent or the value is null/empty. Never fails the hook on a parse miss.
pg_json() {
  local filter="$1" default="${2:-}"
  if command -v jq >/dev/null 2>&1 && [[ -n "${HOOK_INPUT:-}" ]]; then
    local v
    v="$(printf '%s' "$HOOK_INPUT" | jq -r "$filter // empty" 2>/dev/null)"
    [[ -n "$v" ]] && { printf '%s' "$v"; return 0; }
  fi
  printf '%s' "$default"
}

# pg_project_dir — the project root. Prefer $CLAUDE_PROJECT_DIR (set by Claude Code),
# else the payload cwd, else `git rev-parse`.
pg_project_dir() {
  if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then printf '%s' "$CLAUDE_PROJECT_DIR"; return; fi
  local cwd; cwd="$(pg_json '.cwd')"
  if [[ -n "$cwd" ]]; then printf '%s' "$cwd"; return; fi
  git rev-parse --show-toplevel 2>/dev/null || pwd
}

# pg_have <cmd> — resolve a tool on PATH or in $(go env GOPATH)/bin (pinned Go tools).
# Prints the path and returns 0; returns 1 if missing.
pg_have() {
  local cmd="$1" p
  if p="$(command -v "$cmd" 2>/dev/null)"; then printf '%s' "$p"; return 0; fi
  if command -v go >/dev/null 2>&1; then
    p="$(go env GOPATH 2>/dev/null)/bin/$cmd"
    [[ -x "$p" ]] && { printf '%s' "$p"; return 0; }
  fi
  return 1
}

# pg_module_dir <abs-file> — nearest ancestor dir containing go.mod, or empty.
pg_module_dir() {
  local dir; dir="$(dirname "$1")"
  while [[ -n "$dir" && "$dir" != "/" ]]; do
    [[ -f "$dir/go.mod" ]] && { printf '%s' "$dir"; return 0; }
    dir="$(dirname "$dir")"
  done
}

# pg_emit_context <text> — return model-visible context to the agent via the documented
# hookSpecificOutput.additionalContext channel, valid for SessionStart and PostToolUse.
# $1 = the event name, $2 = the context text.
pg_emit_context() {
  local event="$1" text="$2"
  if command -v jq >/dev/null 2>&1; then
    jq -n --arg ev "$event" --arg ctx "$text" \
      '{hookSpecificOutput: {hookEventName: $ev, additionalContext: $ctx}}'
  else
    # Minimal hand-rolled JSON fallback (text is escaped conservatively).
    local esc
    esc="$(printf '%s' "$text" | sed 's/\\/\\\\/g; s/"/\\"/g' | awk '{printf "%s\\n", $0}')"
    printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"%s"}}' "$event" "$esc"
  fi
}

# ── ADR-0020 phase-aware helpers (shared by session-start.sh + stop-phase-check.sh) ───────────

# pg_repo_root — the MONOREPO root. The plugin lives in the libs submodule, so prefer the git
# superproject working tree (the monorepo), else the project dir, else the submodule toplevel.
pg_repo_root() {
  local pd sp
  pd="$(pg_project_dir)"
  sp="$(git -C "$pd" rev-parse --show-superproject-working-tree 2>/dev/null || true)"
  if [[ -n "$sp" ]]; then printf '%s' "$sp"; return; fi
  git -C "$pd" rev-parse --show-toplevel 2>/dev/null || printf '%s' "$pd"
}

# pg_touched_libs — the unique set of libs/go/<lib> slugs touched by the agent's edits this
# turn. The libs/ tree is a git SUBMODULE, so the dirty Go files appear in the submodule's own
# status as `go/<lib>/...`, not in the superproject as `libs/go/<lib>/...`. We therefore read
# BOTH: the superproject (paths prefixed `libs/go/`) and the libs submodule (paths `go/`).
# Source order also includes the active contract's lib ($EDEN_ACTIVE_CONTRACT basename).
pg_touched_libs() {
  local root libs_root; root="$(pg_repo_root)"; libs_root="$root/libs"
  {
    # superproject dirty Go files: libs/go/<lib>/...
    git -C "$root" status --porcelain 2>/dev/null \
      | awk '{print $NF}' \
      | sed -nE 's#^libs/go/([^/]+)/.*\.go$#\1#p'
    # libs-submodule dirty Go files: go/<lib>/...
    if [[ -d "$libs_root/go" ]]; then
      git -C "$libs_root" status --porcelain 2>/dev/null \
        | awk '{print $NF}' \
        | sed -nE 's#^go/([^/]+)/.*\.go$#\1#p'
    fi
    # the active contract's lib, if set
    if [[ -n "${EDEN_ACTIVE_CONTRACT:-}" ]]; then
      basename "${EDEN_ACTIVE_CONTRACT%.md}"
    fi
  } | sort -u | sed '/^$/d'
}

# pg_phase_probe <lib> — read-only detection of the CURRENT SDLC phase of a lib by probing which
# gates pass, cheapest-first. Prints one of: architecture | implementation | testing | qa | done.
# NEVER mutates state; bounded by `go build` only (no test runs) so it is fast and side-effect free.
pg_phase_probe() {
  local lib="$1" root lib_dir
  root="$(pg_repo_root)"; lib_dir="$root/libs/go/$lib"
  [[ -d "$lib_dir" ]] || { printf 'unknown'; return; }
  # architecture: does the skeleton compile and is the apibaseline recorded?
  if ! ( cd "$lib_dir" && go build ./... >/dev/null 2>&1 ); then
    printf 'architecture'; return
  fi
  if [[ ! -f "$lib_dir/.apibaseline" ]]; then
    printf 'architecture'; return
  fi
  # implementation: does the unit + fake conformance suite pass (no race, fast)?
  if ! ( cd "$lib_dir" && go test ./... -count=1 >/dev/null 2>&1 ); then
    printf 'implementation'; return
  fi
  # testing: is a benchbaseline recorded (the testing phase produces it)?
  if [[ ! -d "$lib_dir/.benchbaseline" ]]; then
    printf 'testing'; return
  fi
  printf 'qa'
}
