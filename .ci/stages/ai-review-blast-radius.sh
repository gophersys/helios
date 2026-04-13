#!/usr/bin/env bash
# Stage: ai-review-blast-radius
# Gate:  INFORMATIONAL — never blocks.
#
# Cross-project impact analysis. Combines Nx affected output with the
# dependency map to report which projects are directly and indirectly
# affected by the current changeset.
set -euo pipefail

source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"
source "$(dirname "$0")/../lib/ai-review.sh"

STAGE="blast-radius"

log_stage "ai-review-blast-radius — cross-project impact analysis"

if ! ai_review_available; then
  log_stage_end
  exit 0
fi

# ── Collect inputs ─────────────────────────────────────────────
CHANGED_FILES=$(git diff --name-only "${NX_BASE}"...HEAD 2>/dev/null || true)
if [[ -z "$CHANGED_FILES" ]]; then
  log_ok "No files changed"
  log_stage_end
  exit 0
fi

AFFECTED=$(npx nx show projects --affected --base="${NX_BASE}" 2>/dev/null || echo "(could not determine)")

# ── Build prompt ───────────────────────────────────────────────
read -r -d '' PROMPT << 'PROMPT_HEREDOC' || true
You are analyzing the blast radius of a PR in the Concord monorepo.

## Dependency Map

http-api       <- database (Prisma), protocols, corekinect
build-service  <- corekinect, protocols
git-poller     <- corekinect, protocols
mtib-server    <- protocols, corekinect
mfg-alpha      <- protocols, corekinect
app (frontend) <- http-api API contract (manual TypeScript type sync)
docs (MkDocs)  <- should reflect API / feature changes

Shared globals (invalidate ALL caches): prisma/schema.prisma, libs/python/**, libs/protocols/**

## Response Format

Respond with ONLY valid JSON — no markdown fences, no prose:
{"verdict":"pass","severity":"info","summary":"<N direct, M indirect>","findings":[{"file":"<project-or-area>","severity":"info","message":"<impact description>"}]}

Always verdict=pass. This is an informational report.
PROMPT_HEREDOC

PROMPT="${PROMPT}

## Changed Files

${CHANGED_FILES}

## Nx Affected Projects

${AFFECTED}"

# ── Run, parse, report ────────────────────────────────────────
log_info "Running AI blast-radius analysis..."
RESULT=$(ai_review_run "$PROMPT" 2)

ai_review_parse "$RESULT"
ai_review_save_report "$STAGE" "$RESULT"
ai_review_log_result "$STAGE"

log_stage_end
exit 0
