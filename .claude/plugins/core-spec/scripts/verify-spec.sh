#!/bin/bash
# Verify spec structure, content, and cross-file consistency
# Usage: verify-spec.sh [session-id] [spec-name]
# Called by UserPromptSubmit hook and manually

set -uo pipefail

# Try multiple spec base paths (plugin uses different layout than projects)
SPEC_BASE=""
for candidate in ".claude/specs/specs" ".claude/specs"; do
    if [ -d "$candidate" ]; then
        SPEC_BASE="$candidate"
        break
    fi
done

if [ -z "$SPEC_BASE" ]; then
    # No spec directory at all — that's fine, not every session uses specs
    exit 0
fi

SESSION_ID="${1:-}"
SPEC_NAME="${2:-}"

# Auto-detect session ID if not provided
if [ -z "$SESSION_ID" ]; then
    CWD_SLUG=$(pwd | sed 's|/|-|g')
    SESSION_DIR="$HOME/.claude/projects/$CWD_SLUG"
    SESSION_ID=$(ls -t "$SESSION_DIR"/*.jsonl 2>/dev/null | head -1 | xargs -I{} basename {} .jsonl 2>/dev/null || echo "")
    if [ -z "$SESSION_ID" ]; then
        exit 0  # No session — nothing to verify
    fi
fi

# Check if session has a spec directory
if [ ! -d "$SPEC_BASE/$SESSION_ID" ]; then
    exit 0  # No spec for this session — normal
fi

# Auto-detect spec name from .active if not provided
if [ -z "$SPEC_NAME" ]; then
    ACTIVE_FILE="$SPEC_BASE/$SESSION_ID/.active"
    if [ -f "$ACTIVE_FILE" ]; then
        SPEC_NAME=$(cat "$ACTIVE_FILE" | tr -d '\n')
    else
        exit 0  # No active spec — normal
    fi
fi

SPEC_DIR="$SPEC_BASE/$SESSION_ID/$SPEC_NAME"

if [ ! -d "$SPEC_DIR" ]; then
    exit 0  # Spec directory doesn't exist — normal
fi

# ── Existence Checks ──────────────────────────────────────

REQUIRED=("SPEC.md" "PLAN.md" "STATUS.md" "MEMORY.md")
MISSING=0
EMPTY=0

for file in "${REQUIRED[@]}"; do
    if [ ! -f "$SPEC_DIR/$file" ]; then
        MISSING=$((MISSING + 1))
    elif [ ! -s "$SPEC_DIR/$file" ]; then
        EMPTY=$((EMPTY + 1))
    fi
done

# ── Content Validation ────────────────────────────────────

WARNINGS=""

# STATUS.md format check: must have **State:** field
if [ -f "$SPEC_DIR/STATUS.md" ] && [ -s "$SPEC_DIR/STATUS.md" ]; then
    if ! grep -q '^\*\*State:' "$SPEC_DIR/STATUS.md" 2>/dev/null; then
        if ! grep -q '^\*\*Stage:' "$SPEC_DIR/STATUS.md" 2>/dev/null; then
            WARNINGS="${WARNINGS}\n⚠️  STATUS.md missing **State:** or **Stage:** field"
        fi
    fi
fi

# PLAN.md stage count check
if [ -f "$SPEC_DIR/PLAN.md" ] && [ -d "$SPEC_DIR/stages" ]; then
    PLAN_STAGES=$(grep -c '^\| [0-9]' "$SPEC_DIR/PLAN.md" 2>/dev/null || echo "0")
    FILE_STAGES=$(ls -1 "$SPEC_DIR/stages"/STAGE-*.md 2>/dev/null | wc -l)
    if [ "$PLAN_STAGES" -gt 0 ] && [ "$FILE_STAGES" -gt 0 ]; then
        if [ "$PLAN_STAGES" -ne "$FILE_STAGES" ]; then
            WARNINGS="${WARNINGS}\n⚠️  PLAN.md lists $PLAN_STAGES stages but stages/ has $FILE_STAGES files"
        fi
    fi
fi

# MEMORY.md should have at least one decision or section
if [ -f "$SPEC_DIR/MEMORY.md" ] && [ -s "$SPEC_DIR/MEMORY.md" ]; then
    LINES=$(wc -l < "$SPEC_DIR/MEMORY.md")
    if [ "$LINES" -lt 5 ]; then
        WARNINGS="${WARNINGS}\n⚠️  MEMORY.md has only $LINES lines (seems empty)"
    fi
fi

# ── Output ────────────────────────────────────────────────

# Only print output if there are problems (silent on success for hook usage)
if [ "$MISSING" -gt 0 ] || [ "$EMPTY" -gt 0 ] || [ -n "$WARNINGS" ]; then
    echo ""
    echo "📋 Spec check: $SPEC_DIR"
    if [ "$MISSING" -gt 0 ]; then
        echo "❌ $MISSING required files MISSING"
    fi
    if [ "$EMPTY" -gt 0 ]; then
        echo "⚠️  $EMPTY required files are EMPTY"
    fi
    if [ -n "$WARNINGS" ]; then
        echo -e "$WARNINGS"
    fi
    echo ""
fi

exit 0  # Always exit 0 — this is advisory, not blocking
