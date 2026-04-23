#!/usr/bin/env bash
# spec-stop.sh — Stop hook for spec system
# Updates spec state when session stops
set -uo pipefail

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""')
TOKENS_IN=$(echo "$INPUT" | jq -r '.input_tokens_used // 0')
TOKENS_OUT=$(echo "$INPUT" | jq -r '.output_tokens_used // 0')
COST=$(echo "$INPUT" | jq -r '.total_cost // 0')

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

# Update STATUS.md with session end marker
STATUS_FILE="$SPEC_DIR/STATUS.md"
if [ -f "$STATUS_FILE" ]; then
  echo "" >> "$STATUS_FILE"
  echo "---" >> "$STATUS_FILE"
  echo "**Session Ended:** $(date -Iseconds)" >> "$STATUS_FILE"
  echo "**Tokens Used:** $((TOKENS_IN + TOKENS_OUT))" >> "$STATUS_FILE"
  echo "**Cost:** \$${COST:-0}" >> "$STATUS_FILE"
fi

exit 0
