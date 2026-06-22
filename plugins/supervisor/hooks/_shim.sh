#!/usr/bin/env bash
#
# _shim.sh — shared resolver for the supervisor plugin-level hook shims.
#
# When the plugin is INSTALLED (vs. the agent running directly off a rendered template), the four
# lifecycle events fire from ${CLAUDE_PLUGIN_ROOT}/hooks/*.sh. Those shims delegate to the rendered
# template's .claude/hooks/<name>.sh in the project working dir, passing stdin through unchanged, so
# the determinism logic lives in ONE place (the template) and is not duplicated in the plugin.
#
# If the project has no rendered template (no .claude/hooks/<name>.sh), the shim is a no-op that
# exits 0 — the plugin must never break a non-supervisor project that merely has it installed.
#
# shellcheck shell=bash

# sv_shim_delegate <hook-basename> — run the project's .claude/hooks/<basename>, forwarding stdin.
sv_shim_delegate() {
  local name="$1" project target input
  input="$(cat)"   # consume the hook payload once
  if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
    project="$CLAUDE_PROJECT_DIR"
  else
    # derive the project from the payload cwd, else the git toplevel.
    project=""
    if command -v jq >/dev/null 2>&1; then
      project="$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null || true)"
    fi
    [[ -n "$project" ]] || project="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
  fi
  target="$project/.claude/hooks/$name"
  if [[ -f "$target" ]]; then
    printf '%s' "$input" | CLAUDE_PROJECT_DIR="$project" bash "$target"
    exit $?
  fi
  exit 0   # not a supervisor project — no-op
}
