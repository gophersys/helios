#!/usr/bin/env bash
# Stage: ai-review-docs
# Gate:  INFORMATIONAL by default. Pass --threshold=critical to make it
#        blocking (used by the weekly pipeline).
#
# Detects documentation staleness: code changed in a feature area but the
# corresponding docs/ section was not updated.
set -euo pipefail

source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"
source "$(dirname "$0")/../lib/ai-review.sh"

STAGE="docs"
THRESHOLD=""

# ── Parse args ─────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --threshold=*) THRESHOLD="${1#*=}"; shift ;;
    --threshold)   THRESHOLD="${2:-}"; shift 2 ;;
    *)             shift ;;
  esac
done

log_stage "ai-review-docs — documentation staleness check"

if ! ai_review_available; then
  log_stage_end
  exit 0
fi

# ── Collect inputs ─────────────────────────────────────────────
CHANGED_CODE=$(git diff --name-only "${NX_BASE}"...HEAD -- \
  'apps/' 'libs/' 'prisma/' 'deploy/' 'infrastructure/' \
  ':!docs/' ':!**/*.md' 2>/dev/null || true)

CHANGED_DOCS=$(git diff --name-only "${NX_BASE}"...HEAD -- \
  'docs/' 'mkdocs.yml' 2>/dev/null || true)

if [[ -z "$CHANGED_CODE" ]] && [[ -z "$CHANGED_DOCS" ]]; then
  log_ok "No code or doc files changed"
  log_stage_end
  exit 0
fi

# ── Build prompt ───────────────────────────────────────────────
read -r -d '' PROMPT << 'PROMPT_HEREDOC' || true
You are checking documentation freshness for the Concord monorepo.

## Doc Structure (docs/ — feature-first)

products/       hardware, repos, build matrix, stage config
builds/         triggering, config, CI, monitoring, artifacts
validation/     queue, execution, results, real-time, stages
manufacturing/  config, fixtures, sessions, POST, results
fixtures/       designs, instances, slots, MTIB deployment
administration/ setup, users, permissions, API keys, ops
reference/      Python SDK, REST API, corectl, error codes
platform/       architecture, build system, validation system

## Rules

- Architecture docs: reviewed every 90 days.
- Reference docs: reviewed every 60 days.
- Code in a feature area changed → corresponding docs section should be checked.
- Every doc page needs min_role frontmatter and a mkdocs.yml nav entry.

## Response Format

Respond with ONLY valid JSON — no markdown fences, no prose:
{"verdict":"pass"|"fail","severity":"critical"|"high"|"medium"|"low"|"info","summary":"<one line>","findings":[{"file":"<docs/path>","severity":"<level>","message":"<what changed and why this doc needs review>"}]}

critical = API endpoint added/removed but reference docs untouched.
high = feature workflow changed but how-to guide not updated.
medium = code area changed but docs section not touched.
low/info = minor or up-to-date.
PROMPT_HEREDOC

PROMPT="${PROMPT}

## Code Changes

${CHANGED_CODE:-"(none)"}

## Documentation Changes

${CHANGED_DOCS:-"(none)"}"

# ── Run, parse, report, gate ──────────────────────────────────
log_info "Running AI docs staleness review..."
RESULT=$(ai_review_run "$PROMPT" 3)

ai_review_parse "$RESULT"
ai_review_save_report "$STAGE" "$RESULT"
ai_review_log_result "$STAGE"

if [[ -n "$THRESHOLD" ]]; then
  if ! ai_review_gate "$THRESHOLD"; then
    log_err "BLOCKED: documentation staleness exceeds $THRESHOLD threshold"
    log_stage_end
    exit 1
  fi
fi

log_stage_end
exit 0
