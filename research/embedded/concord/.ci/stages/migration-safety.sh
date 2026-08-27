#!/usr/bin/env bash
# Database migration safety check.
# Gate: ADVISORY — warns about potentially dangerous migration patterns.
# Checks Prisma schema changes for operations that could cause data loss
# or long locks on production tables.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

log_stage "migration-safety — Prisma schema change analysis"

SCHEMA="prisma/schema.prisma"

if [[ ! -f "$SCHEMA" ]]; then
  log_warn "No Prisma schema found at $SCHEMA"
  log_stage_end
  exit 0
fi

# Get schema diff against base branch
DIFF=$(git diff "${NX_BASE:-origin/main}"...HEAD -- "$SCHEMA" 2>/dev/null || true)

if [[ -z "$DIFF" ]]; then
  log_ok "No schema changes detected"
  log_stage_end
  exit 0
fi

log_info "Schema changes detected — checking for dangerous patterns..."

WARNINGS=0

# Check for dropped models (data loss)
DROPPED_MODELS=$(echo "$DIFF" | grep "^-model " | sed 's/^-model //' | awk '{print $1}')
if [[ -n "$DROPPED_MODELS" ]]; then
  log_warn "DROPPED MODEL(S) — potential data loss:"
  echo "$DROPPED_MODELS" | while read -r m; do echo "  - $m"; done
  ((WARNINGS++)) || true
fi

# Check for dropped fields (data loss)
DROPPED_FIELDS=$(echo "$DIFF" | grep "^-  " | grep -v "^-  //" | grep -v "^-  @@" | head -20)
if [[ -n "$DROPPED_FIELDS" ]]; then
  log_warn "DROPPED FIELD(S) — potential data loss:"
  echo "$DROPPED_FIELDS" | head -10
  ((WARNINGS++)) || true
fi

# Check for type changes (potential data truncation)
TYPE_CHANGES=$(echo "$DIFF" | grep -E "^[-+]  \w+\s+(String|Int|Float|Boolean|DateTime|Json|Bytes)" | head -20)
if [[ -n "$TYPE_CHANGES" ]]; then
  log_info "Field type changes detected — verify data compatibility:"
  echo "$TYPE_CHANGES" | head -10
fi

# Check for removed @@unique or @@index (performance impact)
DROPPED_INDEXES=$(echo "$DIFF" | grep "^-  @@\(unique\|index\)" | head -10)
if [[ -n "$DROPPED_INDEXES" ]]; then
  log_warn "DROPPED INDEX/UNIQUE constraint(s) — verify query performance:"
  echo "$DROPPED_INDEXES"
  ((WARNINGS++)) || true
fi

# Check for new required fields without defaults (migration will fail on existing data)
NEW_REQUIRED=$(echo "$DIFF" | grep "^+  " | grep -v "?" | grep -v "@default" | grep -v "//" | grep -v "@@" | grep -v "^+  }" | head -10)
if [[ -n "$NEW_REQUIRED" ]]; then
  log_warn "New REQUIRED field(s) without @default — migration will fail if table has data:"
  echo "$NEW_REQUIRED" | head -5
  ((WARNINGS++)) || true
fi

if [[ "$WARNINGS" -gt 0 ]]; then
  log_warn "$WARNINGS potential migration issue(s) — review before deploying"
else
  log_ok "Schema changes look safe"
fi

# Advisory — never fails the pipeline
log_stage_end
