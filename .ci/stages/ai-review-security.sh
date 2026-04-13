#!/usr/bin/env bash
# Stage: ai-review-security
# Gate:  BLOCKING on critical severity.
#
# OWASP-oriented security scan of changed Python, TypeScript, and Svelte
# files. Catches injection vectors, auth bypass, hardcoded secrets, and
# unsafe deserialization that static analysis tools (bandit) may miss.
#
# Scoped paths: *.py, *.ts, *.svelte, *.js (excludes node_modules, dist, .nx)
set -euo pipefail

source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"
source "$(dirname "$0")/../lib/ai-review.sh"

STAGE="security"

log_stage "ai-review-security — OWASP vulnerability scan"

if ! ai_review_available; then
  log_stage_end
  exit 0
fi

# ── Collect scoped diff ────────────────────────────────────────
DIFF=""
if ! ai_review_get_diff DIFF \
    '*.py' '*.ts' '*.svelte' '*.js' \
    ':!**/node_modules/**' ':!**/.nx/**' ':!**/dist/**'; then
  log_ok "No code files changed"
  log_stage_end
  exit 0
fi

# ── Build prompt ───────────────────────────────────────────────
read -r -d '' PROMPT << 'PROMPT_HEREDOC' || true
You are a security reviewer for Concord (Python Flask backend + SvelteKit frontend).

## Checklist

Critical (blocks merge):
- SQL injection (raw queries, string interpolation — Prisma ORM is safe)
- Command injection (subprocess shell=True, os.system with user input)
- Auth bypass (new endpoints missing @require_permissions decorator)
- Path traversal (user-controlled file paths without sanitization)
- Hardcoded secrets in source (not .env.example placeholders)
- Insecure deserialization (pickle.loads, yaml.load without SafeLoader)

High:
- XSS ({@html ...} with unsanitized input in Svelte)
- Missing input validation in from_json() methods
- Insecure zip extraction without path validation
- CORS wildcard in production code

Medium: info disclosure, missing rate limiting, weak crypto.
Low: missing CSRF, permissive file perms, missing headers.

## Response Format

Respond with ONLY valid JSON — no markdown fences, no prose:
{"verdict":"pass"|"fail","severity":"critical"|"high"|"medium"|"low"|"info","summary":"<one line>","findings":[{"file":"<path>","line":<n>,"severity":"<level>","message":"<vulnerability and fix>"}]}

verdict=fail if any finding is high or critical. Top-level severity = highest finding.
PROMPT_HEREDOC

PROMPT="${PROMPT}

## Diff

${DIFF}"

# ── Run, parse, report, gate ──────────────────────────────────
log_info "Running AI security review..."
RESULT=$(ai_review_run "$PROMPT" 3)

ai_review_parse "$RESULT"
ai_review_save_report "$STAGE" "$RESULT"
ai_review_log_result "$STAGE"

if ! ai_review_gate "critical"; then
  log_err "BLOCKED: critical security vulnerability"
  log_stage_end
  exit 1
fi

log_stage_end
