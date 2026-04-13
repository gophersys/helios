#!/usr/bin/env bash
# AI review — cross-project blast radius analysis.
# Gate: INFORMATIONAL (never blocks, reports affected projects).
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"
source "$(dirname "$0")/../lib/ai-review.sh"

log_stage "ai-review-blast-radius — cross-project impact analysis"

if ! ai_review_available; then
  log_stage_end
  exit 0
fi

# Get affected projects from Nx
AFFECTED=$(npx nx show projects --affected --base="${NX_BASE}" 2>/dev/null || echo "")
CHANGED_FILES=$(git diff --name-only "${NX_BASE}"...HEAD 2>/dev/null || true)

if [[ -z "$CHANGED_FILES" ]]; then
  log_ok "No files changed"
  log_stage_end
  exit 0
fi

PROMPT=$(cat <<PROMPT_EOF
You are analyzing the blast radius of a code change in a monorepo called Concord.

## Nx Project Dependency Map

Key dependency chains (downstream <- upstream):
- http-api <- database (Prisma), protocols, corekinect (libs/python)
- build-service <- corekinect, protocols
- git-poller <- corekinect, protocols
- mtib-server <- protocols, corekinect
- manufacturing-alpha <- protocols, corekinect
- app (SvelteKit frontend) <- http-api API contract (manual type sync)
- docs (MkDocs) <- independent but should reflect API/feature changes

Shared globals that invalidate ALL project caches:
- prisma/schema.prisma
- libs/python/**
- libs/protocols/**

## Changed Files

${CHANGED_FILES}

## Nx Affected Projects

${AFFECTED:-"(nx affected could not be determined)"}

## Instructions

Analyze which projects are affected and why. Identify any indirect impacts that Nx might miss (e.g., frontend type sync, documentation staleness).

Respond with ONLY valid JSON:
{
  "verdict": "pass",
  "severity": "info",
  "summary": "N projects directly affected, M indirectly impacted",
  "findings": [
    {
      "file": "project-name-or-area",
      "severity": "info",
      "message": "Description of impact and what to verify"
    }
  ]
}

Always return verdict "pass" — this is an informational report, never blocking.
PROMPT_EOF
)

log_info "Running AI blast radius analysis..."
RESULT=$(ai_review_run "$PROMPT" 2)

ai_review_parse_verdict "$RESULT"
ai_review_save_report "blast-radius" "$RESULT"
ai_review_log_result "blast-radius"

# Never blocks — always exit 0
log_stage_end
exit 0
