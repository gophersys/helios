#!/usr/bin/env bash
# AI review — documentation staleness detection.
# Gate: INFORMATIONAL on PR, BLOCKING on weekly (pass --threshold critical).
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"
source "$(dirname "$0")/../lib/ai-review.sh"

# Parse optional threshold override (used by weekly pipeline)
THRESHOLD="none"
for arg in "$@"; do
  case "$arg" in
    --threshold=*) THRESHOLD="${arg#*=}" ;;
    --threshold)   shift; THRESHOLD="${1:-none}" ;;
  esac
done

log_stage "ai-review-docs — documentation staleness check"

if ! ai_review_available; then
  log_stage_end
  exit 0
fi

# Get changed code files and changed doc files separately
CHANGED_CODE=$(git diff --name-only "${NX_BASE}"...HEAD -- \
  'apps/' 'libs/' 'prisma/' 'deploy/' 'infrastructure/' \
  ':!docs/' ':!**/*.md' \
  2>/dev/null || true)

CHANGED_DOCS=$(git diff --name-only "${NX_BASE}"...HEAD -- \
  'docs/' 'mkdocs.yml' \
  2>/dev/null || true)

if [[ -z "$CHANGED_CODE" ]] && [[ -z "$CHANGED_DOCS" ]]; then
  log_ok "No code or doc files changed"
  log_stage_end
  exit 0
fi

PROMPT=$(cat <<PROMPT_EOF
You are checking whether documentation is up-to-date with code changes in a monorepo called Concord.

## Documentation Structure

docs/ is organized by product feature area:
- docs/products/ — hardware, repos, build matrix, recipes, stage config
- docs/builds/ — triggering, config, CI, monitoring, artifacts
- docs/validation/ — queue, execution, results, real-time, stages
- docs/manufacturing/ — config, fixtures, sessions, POST, results
- docs/fixtures/ — designs, instances, slots, MTIB deployment
- docs/administration/ — setup, users, permissions, API keys, ops
- docs/reference/ — Python SDK, REST API, corectl, error codes
- docs/platform/ — architecture, build system, validation system

## Rules
- Architecture docs should be reviewed every 90 days (check "Last reviewed:" frontmatter)
- Reference docs should be reviewed every 60 days
- When code in a feature area changes, the corresponding docs section should be checked
- Every doc page must have min_role frontmatter
- Every doc must appear in mkdocs.yml nav

## Code Changes (non-doc files)

${CHANGED_CODE:-"(no code changes)"}

## Documentation Changes

${CHANGED_DOCS:-"(no documentation changes)"}

## Instructions

Check for staleness:
1. Were code files in a feature area changed without corresponding docs updates?
2. Map code paths to doc sections: apps/backend/http-api/src/api/v2/builds/ -> docs/builds/
3. Are there docs that reference APIs or features that may have changed?

Respond with ONLY valid JSON:
{
  "verdict": "pass" or "fail",
  "severity": "critical" or "high" or "medium" or "low" or "info",
  "summary": "one sentence summary",
  "findings": [
    {
      "file": "docs/section/that-needs-update.md",
      "severity": "medium",
      "message": "What changed in code and why this doc needs review"
    }
  ]
}

Severity guide:
- critical: A public API endpoint was added/removed but reference docs not updated
- high: A feature workflow changed but the how-to guide wasn't updated
- medium: Code changed in a feature area but docs section not touched
- low: Minor inconsistency
- info: Docs are up to date

If everything looks consistent, return verdict "pass" with severity "info".
PROMPT_EOF
)

log_info "Running AI docs staleness review..."
RESULT=$(ai_review_run "$PROMPT" 3)

ai_review_parse_verdict "$RESULT"
ai_review_save_report "docs" "$RESULT"
ai_review_log_result "docs"

# Apply gate only if threshold was specified (weekly pipeline)
if [[ "$THRESHOLD" != "none" ]]; then
  if ! ai_review_gate "$THRESHOLD"; then
    log_err "BLOCKED: Documentation staleness exceeds threshold ($THRESHOLD)"
    log_stage_end
    exit 1
  fi
fi

log_stage_end
exit 0
