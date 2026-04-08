#!/usr/bin/env bash
# spec-session-start.sh — SessionStart hook for spec system
# Checks for active specs in .claude/specs/<session-id>/
set -uo pipefail

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""')
CWD=$(echo "$INPUT" | jq -r '.cwd // ""')

[ -z "$SESSION_ID" ] && exit 0

CODECTL_DIR=".claude/specs"
SPECS_DIR="$CODECTL_DIR/specs/$SESSION_ID"

# Ensure spec directory exists for this session
mkdir -p "$SPECS_DIR"

# Check if there's an active spec
ACTIVE_FILE="$SPECS_DIR/.active"
if [ -f "$ACTIVE_FILE" ]; then
  SPEC_NAME=$(cat "$ACTIVE_FILE" | tr -d '\n')
  SPEC_DIR="$SPECS_DIR/$SPEC_NAME"

  if [ -d "$SPEC_DIR" ] && [ -f "$SPEC_DIR/STATUS.md" ]; then
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║  SPEC-RESUME: Active spec detected                             ║"
    echo "╠════════════════════════════════════════════════════════════════╣"
    echo "  Spec: $SPEC_NAME"
    echo "  Path: $SPEC_DIR"
    echo ""
    echo "  Required reading:"
    echo "    - STATUS.md  → current progress"
    echo "    - MEMORY.md  → context and decisions"
    echo "    - PLAN.md    → stage roadmap"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "READ THESE FILES IMMEDIATELY before proceeding."
  fi
fi

exit 0
