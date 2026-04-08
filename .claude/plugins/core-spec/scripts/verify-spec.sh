#!/bin/bash
# Verify spec structure is correct
# Usage: verify-spec.sh <session-id> <spec-name>

set -euo pipefail

SPEC_BASE=".claude/specs/specs"
SESSION_ID="${1:-}"
SPEC_NAME="${2:-}"

# Auto-detect session ID if not provided
if [ -z "$SESSION_ID" ]; then
    CWD_SLUG=$(pwd | sed 's|/|-|g')
    SESSION_DIR="$HOME/.claude/projects/$CWD_SLUG"
    SESSION_ID=$(ls -t "$SESSION_DIR"/*.jsonl 2>/dev/null | head -1 | xargs -I{} basename {} .jsonl 2>/dev/null || echo "")
    if [ -z "$SESSION_ID" ]; then
        echo "ERROR: Could not auto-detect session ID"
        echo "Usage: $0 <session-id> <spec-name>"
        exit 1
    fi
fi

# Auto-detect spec name from .active if not provided
if [ -z "$SPEC_NAME" ]; then
    ACTIVE_FILE="$SPEC_BASE/$SESSION_ID/.active"
    if [ -f "$ACTIVE_FILE" ]; then
        SPEC_NAME=$(cat "$ACTIVE_FILE")
    else
        echo "ERROR: No .active file found and no spec-name provided"
        echo "Usage: $0 <session-id> <spec-name>"
        exit 1
    fi
fi

SPEC_DIR="$SPEC_BASE/$SESSION_ID/$SPEC_NAME"

echo "Verifying spec at: $SPEC_DIR"
echo "========================================"

# Required files
REQUIRED=(
    "SPEC.md"
    "PLAN.md"
    "STATUS.md"
    "MEMORY.md"
    "ENVIRONMENT.md"
)

MISSING=0
for file in "${REQUIRED[@]}"; do
    if [ -f "$SPEC_DIR/$file" ]; then
        SIZE=$(wc -c < "$SPEC_DIR/$file")
        echo "✅ $file ($SIZE bytes)"
    else
        echo "❌ $file MISSING"
        MISSING=$((MISSING + 1))
    fi
done

# Check .active file
ACTIVE_FILE="$SPEC_BASE/$SESSION_ID/.active"
if [ -f "$ACTIVE_FILE" ]; then
    ACTIVE_CONTENT=$(cat "$ACTIVE_FILE")
    if [ "$ACTIVE_CONTENT" = "$SPEC_NAME" ]; then
        echo "✅ .active points to '$SPEC_NAME'"
    else
        echo "⚠️  .active points to '$ACTIVE_CONTENT' (expected '$SPEC_NAME')"
    fi
else
    echo "❌ .active MISSING"
    MISSING=$((MISSING + 1))
fi

# Check stages directory
STAGES_DIR="$SPEC_DIR/stages"
if [ -d "$STAGES_DIR" ]; then
    STAGE_COUNT=$(ls -1 "$STAGES_DIR"/STAGE-*.md 2>/dev/null | wc -l)
    if [ "$STAGE_COUNT" -ge 8 ]; then
        echo "✅ stages/ ($STAGE_COUNT stage files)"
    else
        echo "⚠️  stages/ (only $STAGE_COUNT files, need at least 8 for Tier 3)"
    fi
else
    echo "❌ stages/ MISSING"
    MISSING=$((MISSING + 1))
fi

echo "========================================"
if [ "$MISSING" -eq 0 ]; then
    echo "✅ SPEC STRUCTURE VALID"
    exit 0
else
    echo "❌ SPEC STRUCTURE INVALID ($MISSING missing)"
    exit 1
fi
