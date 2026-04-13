#!/usr/bin/env bash
# Stage: ai-review-completeness
# Gate:  BLOCKING on critical severity.
#
# Checks whether schema and type changes are fully propagated through the
# codebase. The Concord propagation chain has 5 manual steps — this stage
# catches when a developer changes the schema but forgets to update the
# serializers, contract tests, OpenAPI spec, or frontend TypeScript types.
#
# Scoped paths: prisma/, libs/python/database/, apps/backend/http-api/src/api/v2/,
#               apps/frontend/app/src/lib/types/, libs/protocols/
set -euo pipefail

source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"
source "$(dirname "$0")/../lib/ai-review.sh"

STAGE="completeness"

log_stage "ai-review-completeness — schema/type propagation check"

if ! ai_review_available; then
  log_stage_end
  exit 0
fi

# ── Collect scoped diff ────────────────────────────────────────
DIFF=""
if ! ai_review_get_diff DIFF \
    prisma/schema.prisma \
    libs/python/database/ \
    apps/backend/http-api/src/api/v2/ \
    apps/frontend/app/src/lib/types/ \
    libs/protocols/; then
  log_ok "No propagation-chain files changed"
  log_stage_end
  exit 0
fi

# ── Build prompt ───────────────────────────────────────────────
read -r -d '' PROMPT << 'PROMPT_HEREDOC' || true
You are reviewing a Concord monorepo PR for propagation-chain completeness.

## Propagation Chain

When prisma/schema.prisma changes, ALL of these must also be updated:
1. Serializers in apps/backend/http-api/src/api/v2/<domain>/<entity>.py
2. Contract-test shapes in apps/backend/http-api/tests/contracts/
3. OpenAPI spec in apps/backend/http-api/src/api/v2/docs.py
4. Frontend types in apps/frontend/app/src/lib/types/models.ts

When libs/protocols/**/*.proto changes:
1. Generated stubs (libs/protocols/mtib/mtib_pb2*.py) must be regenerated.

## Task

Examine the diff. For every file in the chain that was modified, check
whether all downstream files were ALSO modified. A missing downstream
update is a finding.

## Response Format

Respond with ONLY valid JSON — no markdown fences, no prose:
{"verdict":"pass"|"fail","severity":"critical"|"high"|"medium"|"low"|"info","summary":"<one line>","findings":[{"file":"<path>","severity":"<level>","message":"<what is missing and how to fix>"}]}

Severity: critical = schema field added/removed but types or serializers missing.
high = proto changed but stubs not regenerated. medium = OpenAPI not updated.
low = minor. info = all complete.
PROMPT_HEREDOC

PROMPT="${PROMPT}

## Diff

${DIFF}"

# ── Run, parse, report, gate ──────────────────────────────────
log_info "Running AI completeness review..."
RESULT=$(ai_review_run "$PROMPT" 2)

ai_review_parse "$RESULT"
ai_review_save_report "$STAGE" "$RESULT"
ai_review_log_result "$STAGE"

if ! ai_review_gate "critical"; then
  log_err "BLOCKED: incomplete propagation chain"
  log_stage_end
  exit 1
fi

log_stage_end
