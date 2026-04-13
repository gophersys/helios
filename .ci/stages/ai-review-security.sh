#!/usr/bin/env bash
# AI review — security vulnerability scan (OWASP-oriented).
# Gate: BLOCKING on critical (actual injection vectors, auth bypass).
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"
source "$(dirname "$0")/../lib/ai-review.sh"

log_stage "ai-review-security — OWASP vulnerability scan"

if ! ai_review_available; then
  log_stage_end
  exit 0
fi

# Scope to code files only — check stat first
DIFF_STAT=$(git diff --stat "${NX_BASE}"...HEAD -- '*.py' '*.ts' '*.svelte' '*.js' \
  ':!**/node_modules/**' ':!**/.nx/**' ':!**/dist/**' \
  2>/dev/null || true)

if [[ -z "$DIFF_STAT" ]]; then
  log_ok "No code files changed"
  log_stage_end
  exit 0
fi

# Write diff to temp file and truncate
DIFF_FILE=$(mktemp /tmp/ai-review-diff-XXXXXX.txt)
(git diff "${NX_BASE}"...HEAD -- '*.py' '*.ts' '*.svelte' '*.js' \
  ':!**/node_modules/**' ':!**/.nx/**' ':!**/dist/**' \
  2>/dev/null | head -c 80000 > "$DIFF_FILE") || true
DIFF=$(cat "$DIFF_FILE")
rm -f "$DIFF_FILE"

PROMPT=$(cat <<PROMPT_EOF
You are a security reviewer for a monorepo called Concord (Python Flask backend + SvelteKit frontend). Review the diff below for OWASP Top 10 and common security vulnerabilities.

## What to Look For

### Critical (blocks merge)
- SQL injection: raw SQL queries, string interpolation in queries (Prisma ORM is safe, but check for raw queries)
- Command injection: subprocess calls with shell=True, unsanitized user input in os.system/popen
- Auth bypass: new API endpoints missing @require_permissions decorator
- Path traversal: user-controlled file paths without sanitization
- Hardcoded secrets: API keys, passwords, tokens in source code (not .env.example defaults)
- Insecure deserialization: pickle.loads, yaml.load without SafeLoader

### High
- XSS: unsanitized user input rendered in Svelte templates (check {@html ...} usage)
- Missing input validation: new from_json() methods without type/length checks
- Insecure file handling: zip extraction without path validation, arbitrary file writes
- CORS misconfiguration: wildcard origins in production code

### Medium
- Information disclosure: stack traces, debug info, verbose error messages in responses
- Missing rate limiting on sensitive endpoints (auth, file upload)
- Weak cryptographic choices (MD5, SHA1 for security purposes)

### Low
- Missing CSRF protection on state-changing endpoints
- Overly permissive file permissions
- Missing security headers

## Instructions

Respond with ONLY valid JSON (no markdown, no explanation):
{
  "verdict": "pass" or "fail",
  "severity": "critical" or "high" or "medium" or "low" or "info",
  "summary": "one sentence summary",
  "findings": [
    {
      "file": "path/to/file",
      "line": 42,
      "severity": "critical",
      "message": "Description of the vulnerability and how to fix it"
    }
  ]
}

Set verdict to "fail" if any finding is high or critical. Set verdict to "pass" otherwise.
Set the top-level severity to the highest severity among all findings.
If no issues found, return verdict "pass" with severity "info" and empty findings.

## Diff

${DIFF}
PROMPT_EOF
)

log_info "Running AI security review..."
RESULT=$(ai_review_run "$PROMPT" 3)

ai_review_parse_verdict "$RESULT"
ai_review_save_report "security" "$RESULT"
ai_review_log_result "security"

if ! ai_review_gate "critical"; then
  log_err "BLOCKED: Critical security vulnerability detected"
  log_stage_end
  exit 1
fi

log_stage_end
