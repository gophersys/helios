#!/usr/bin/env bash
#
# session-start.sh — SessionStart hook (ADR-0018 Layer 2).
#
# Injects, into the agent's context at session start:
#   - the neutral library design rules (libs/.claude/rules/*.md)
#   - any active frozen contract being implemented (docs/architecture/contracts/*.md,
#     or a path named in $EDEN_ACTIVE_CONTRACT)
#   - the standing instruction that these are frozen rules, not suggestions
#
# Emits the text via hookSpecificOutput.additionalContext. Always exits 0 — a context
# injector must never block a session.
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_lib.sh"

pg_read_input

PROJECT_DIR="$(pg_project_dir)"

# The plugin lives at libs/plugins/project-go; the rules are at libs/.claude/rules.
# CLAUDE_PLUGIN_ROOT points at the plugin dir; walk up to the libs submodule root.
LIBS_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"   # hooks/ -> project-go/ -> plugins/ -> libs/
RULES_DIR="$LIBS_ROOT/.claude/rules"

# --- assemble the injected text ---
out=""
out+=$'# Eden Go library authoring — active rules (project-go plugin, ADR-0018)\n\n'
out+=$'You are implementing against frozen library contracts. The rules below are '
out+=$'mechanically enforced (golangci-lint + hnslint via the PostToolUse hook and the '
out+=$'git gate); deviations are rejected, not negotiated. Treat them as constraints on '
out+=$'every Go edit you make in this repository.\n\n'

if [[ -d "$RULES_DIR" ]]; then
  for rf in "$RULES_DIR"/*.md; do
    [[ -f "$rf" ]] || continue
    out+="---"$'\n'
    out+="$(cat "$rf")"
    out+=$'\n\n'
  done
else
  out+=$'(rules directory not found at '"$RULES_DIR"$' — the gate still enforces them.)\n\n'
fi

# --- any active frozen contract being implemented ---
CONTRACT=""
if [[ -n "${EDEN_ACTIVE_CONTRACT:-}" && -f "${EDEN_ACTIVE_CONTRACT}" ]]; then
  CONTRACT="$EDEN_ACTIVE_CONTRACT"
fi
if [[ -n "$CONTRACT" ]]; then
  out+=$'---\n# Active frozen contract being implemented\n\n'
  out+=$'Source: '"$CONTRACT"$'\n\n'
  out+="$(cat "$CONTRACT")"
  out+=$'\n'
else
  CONTRACTS_DIR="$PROJECT_DIR/docs/architecture/contracts"
  if [[ -d "$CONTRACTS_DIR" ]]; then
    out+=$'---\n# Library contracts available in this repo\n\n'
    out+=$'Frozen contracts live in docs/architecture/contracts/. When implementing one, '
    out+=$'read its file first and treat it as immutable:\n'
    for cf in "$CONTRACTS_DIR"/*.md; do
      [[ -f "$cf" ]] || continue
      out+="  - ${cf#"$PROJECT_DIR"/}"$'\n'
    done
  fi
fi

# --- ADR-0020 phase-aware guidance (read-only probe; turns static rules into "you are here") ---
# If an active lib is detected (the active contract's lib, or a libs/go/<lib> with dirty Go),
# probe which SDLC phase it is at and tell the agent the NEXT gate to run. Pure read-only; the
# probe only ever runs `go build`/fast `go test`, never mutates, and the hook still exits 0.
ACTIVE_LIBS="$(pg_touched_libs 2>/dev/null || true)"
if [[ -n "$ACTIVE_LIBS" ]]; then
  out+=$'\n---\n# ADR-0020 pipeline — you are here\n\n'
  out+=$'Implement each library in four phases (architecture → implementation → testing → qa); '
  out+=$'each phase has a mechanical gate `bash ./ctl.sh phase-gate <phase>` that MUST pass '
  out+=$'before the next. You may NOT declare a library done before `phase-gate qa` is GREEN '
  out+=$'(the Stop hook enforces this). Detected active library(ies):\n\n'
  while IFS= read -r lib; do
    [[ -n "$lib" ]] || continue
    phase="$(pg_phase_probe "$lib" 2>/dev/null || printf 'unknown')"
    case "$phase" in
      architecture)   nextgate='phase-gate architecture (freeze the contract, compile the skeleton, record .apibaseline)';;
      implementation) nextgate='phase-gate implementation (write fake + conformance RED first, then bodies GREEN — TDD)';;
      testing)        nextgate='phase-gate testing (wire the 8 dimensions: property/leak/lifecycle/load/integration/vuln/sast/secretscan/bench-guard/cover-floor)';;
      qa)             nextgate='phase-gate qa (maintainability + mutate + no-shortcuts + evidence) — then it is done';;
      *)              nextgate='phase-gate all (run the full sequence)';;
    esac
    out+="  - libs/go/${lib}: at phase **${phase}** → next gate: \`bash ./ctl.sh ${nextgate}\`"$'\n'
  done <<< "$ACTIVE_LIBS"
fi

pg_emit_context "SessionStart" "$out"
exit 0
