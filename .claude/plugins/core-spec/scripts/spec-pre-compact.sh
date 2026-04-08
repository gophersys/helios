#!/usr/bin/env bash
# spec-pre-compact.sh — PreCompact hook for spec system
# Saves current spec state before context compaction
set -uo pipefail

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""')

[ -z "$SESSION_ID" ] && exit 0

CODECTL_DIR=".claude/specs"
SPECS_DIR="$CODECTL_DIR/specs/$SESSION_ID"
ACTIVE_FILE="$SPECS_DIR/.active"

# Check for active spec
[ ! -f "$ACTIVE_FILE" ] && exit 0

SPEC_NAME=$(cat "$ACTIVE_FILE" | tr -d '\n')
[ -z "$SPEC_NAME" ] && exit 0

SPEC_DIR="$SPECS_DIR/$SPEC_NAME"
[ ! -d "$SPEC_DIR" ] && exit 0

# Create a compaction checkpoint in spec memory
MEMORY_FILE="$SPEC_DIR/MEMORY.md"
if [ -f "$MEMORY_FILE" ]; then
  # Append compaction note if not already there recently
  COMPACT_NOTE="## Compaction $(date +%Y-%m-%d-%H%M)"
  if ! grep -q "^## Compaction $(date +%Y-%m-%d)" "$MEMORY_FILE" 2>/dev/null; then
    cat >> "$MEMORY_FILE" << EOF

$COMPACT_NOTE

Context compacted at $(date -Iseconds).
Resume from STATUS.md current stage state.

EOF
  fi
fi

# Output reminder to Claude
echo ""
echo "⚠️  PRE-COMPACT: Update MEMORY.md and STATUS.md NOW at:"
echo "    $SPEC_DIR/"
echo ""

exit 0
