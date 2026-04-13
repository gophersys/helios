#!/usr/bin/env bash
# AI review — schema/type propagation completeness check.
# Gate: BLOCKING on critical (schema changed but downstream types not updated).
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"
source "$(dirname "$0")/../lib/ai-review.sh"

log_stage "ai-review-completeness — schema/type propagation check"

if ! ai_review_available; then
  log_stage_end
  exit 0
fi

# Scope the diff to propagation chain files only — use --stat first to check if anything changed
DIFF_STAT=$(git diff --stat "${NX_BASE}"...HEAD -- \
  prisma/schema.prisma \
  libs/python/database/ \
  apps/backend/http-api/src/api/v2/ \
  apps/frontend/app/src/lib/types/ \
  libs/protocols/ \
  2>/dev/null || true)

if [[ -z "$DIFF_STAT" ]]; then
  log_ok "No propagation chain files changed"
  log_stage_end
  exit 0
fi

# Write diff to temp file (can be very large) and truncate
DIFF_FILE=$(mktemp /tmp/ai-review-diff-XXXXXX.txt)
(git diff "${NX_BASE}"...HEAD -- \
  prisma/schema.prisma \
  libs/python/database/ \
  apps/backend/http-api/src/api/v2/ \
  apps/frontend/app/src/lib/types/ \
  libs/protocols/ \
  2>/dev/null | tr -d '\0' | head -c 80000 > "$DIFF_FILE") || true

DIFF=$(cat "$DIFF_FILE")
rm -f "$DIFF_FILE"

PROMPT=$(cat <<PROMPT_EOF
You are a code reviewer for a monorepo called Concord. Your job is to check whether schema and type changes are fully propagated through the codebase.

## Propagation Chain Rules

When prisma/schema.prisma changes, ALL of these must also be updated:
1. Backend serializers: apps/backend/http-api/src/api/v2/<domain>/<entity>.py — the _serialize_*() functions
2. Contract test shapes: apps/backend/http-api/tests/contracts/ — shape dicts matching serializer output
3. OpenAPI spec: apps/backend/http-api/src/api/v2/docs.py — component schemas
4. Frontend types: apps/frontend/app/src/lib/types/models.ts — TypeScript interfaces

When libs/protocols/**/*.proto changes:
1. Generated stubs must be updated (libs/protocols/mtib/mtib_pb2.py etc.)

## Instructions

Examine the diff below. For each file in the propagation chain that was modified:
- Check if all downstream files in the chain were ALSO modified in this diff
- A missing downstream update is a "finding"

Respond with ONLY valid JSON (no markdown, no explanation):
{
  "verdict": "pass" or "fail",
  "severity": "critical" or "high" or "medium" or "low" or "info",
  "summary": "one sentence summary",
  "findings": [
    {
      "file": "path/to/file/that/should/have/changed",
      "severity": "critical",
      "message": "Specific description of what's missing and how to fix it"
    }
  ]
}

Severity guide:
- critical: A schema model/field was added/removed/renamed but frontend types or serializers were NOT updated
- high: Proto file changed but generated stubs not regenerated
- medium: OpenAPI spec not updated to match serializer changes
- low: Minor inconsistency that won't break at runtime
- info: Observation, no action needed

If all propagation chains are complete, return verdict "pass" with severity "info".

## Diff

${DIFF}
PROMPT_EOF
)

log_info "Running AI completeness review..."
RESULT=$(ai_review_run "$PROMPT" 2)

ai_review_parse_verdict "$RESULT"
ai_review_save_report "completeness" "$RESULT"
ai_review_log_result "completeness"

if ! ai_review_gate "critical"; then
  log_err "BLOCKED: Incomplete propagation chain detected"
  log_stage_end
  exit 1
fi

log_stage_end
