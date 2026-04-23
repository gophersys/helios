#!/usr/bin/env bash
# spec-post-compact.sh — PostCompact hook for spec system
# Re-reads active spec after context compaction to restore state
set -uo pipefail

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""')

[ -z "$SESSION_ID" ] && exit 0

CODECTL_DIR=".claude/specs"
SPECS_DIR="$CODECTL_DIR/specs/$SESSION_ID"
ACTIVE_FILE="$SPECS_DIR/.active"

# No active spec? Nothing to restore
[ ! -f "$ACTIVE_FILE" ] && exit 0

SPEC_NAME=$(cat "$ACTIVE_FILE" | tr -d '\n')
SPEC_DIR="$SPECS_DIR/$SPEC_NAME"

# Spec directory doesn't exist? Nothing to restore
[ ! -d "$SPEC_DIR" ] && exit 0

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  CONTEXT COMPACTED — SPEC RECOVERY REQUIRED                    ║"
echo "╠════════════════════════════════════════════════════════════════╣"
echo "  Session: $SESSION_ID"
echo "  Spec: $SPEC_NAME"
echo "  Path: $SPEC_DIR"
echo ""
echo "  MANDATORY: Read these files NOW to restore context:"
echo ""
echo "    1. $SPEC_DIR/STATUS.md"
echo "       → Current stage, progress, what you were doing"
echo ""
echo "    2. $SPEC_DIR/MEMORY.md"
echo "       → Decisions made, errors encountered, learnings"
echo ""
echo "    3. $SPEC_DIR/PLAN.md"
echo "       → Stage dependencies and roadmap"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

exit 0
