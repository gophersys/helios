#!/usr/bin/env bash
# .ci/lib/bitbucket.sh — Bitbucket REST API helpers for CI.
#
# Provides:
#   bb_available          Check if Bitbucket credentials are set
#   bb_post_pr_comment    Post a comment on a PR
#   bb_render_findings    Render AI review findings as markdown
#
# Required env vars (all optional — functions skip gracefully):
#   BITBUCKET_EMAIL        Email for Basic auth
#   BITBUCKET_API_TOKEN    API token for Basic auth
#   BITBUCKET_PR_ID        PR number (set by Bitbucket Pipelines automatically)
#   BITBUCKET_WORKSPACE    Workspace slug (default: corekinect)
#   BITBUCKET_REPO_SLUG    Repository slug (default: concord)

_BB_API="https://api.bitbucket.org/2.0"
_BB_WORKSPACE="${BITBUCKET_WORKSPACE:-corekinect}"
_BB_REPO="${BITBUCKET_REPO_SLUG:-concord}"

# ── bb_available ───────────────────────────────────────────────
# Returns 0 if credentials and PR context are present.
bb_available() {
  [[ -n "${BITBUCKET_EMAIL:-}" ]] && \
  [[ -n "${BITBUCKET_API_TOKEN:-}" ]] && \
  [[ -n "${BITBUCKET_PR_ID:-}" ]]
}

# ── bb_post_pr_comment ─────────────────────────────────────────
# Usage: bb_post_pr_comment "markdown content"
# Posts a comment to the current PR. Silently skips if credentials missing.
bb_post_pr_comment() {
  local content="$1"

  if ! bb_available; then
    return 0
  fi

  local url="${_BB_API}/repositories/${_BB_WORKSPACE}/${_BB_REPO}/pullrequests/${BITBUCKET_PR_ID}/comments"

  # Build JSON payload via Python (safe escaping)
  local payload
  payload=$(python3 -c "import json,sys; print(json.dumps({'content':{'raw':sys.stdin.read()}}))" <<< "$content")

  local http_code
  http_code=$(curl -s -o /dev/null -w '%{http_code}' \
    -u "${BITBUCKET_EMAIL}:${BITBUCKET_API_TOKEN}" \
    -H "Content-Type: application/json" \
    -X POST \
    -d "$payload" \
    "$url" 2>/dev/null)

  if [[ "$http_code" == "201" ]]; then
    log_ok "PR comment posted (PR #${BITBUCKET_PR_ID})"
  else
    log_warn "PR comment failed (HTTP $http_code)"
  fi
}

# ── bb_render_findings ─────────────────────────────────────────
# Usage: bb_render_findings stage_name report_json_path
# Outputs formatted markdown to stdout.
bb_render_findings() {
  local stage="$1"
  local report_path="$2"

  python3 - "$stage" "$report_path" << 'PYEOF'
import json, sys

stage = sys.argv[1]
try:
    report = json.load(open(sys.argv[2]))
except Exception:
    print(f"## AI Review: {stage}\n\n*Report unavailable*")
    sys.exit(0)

v = report.get("verdict", "unknown")
sev = report.get("severity", "info")
summary = report.get("summary", "No summary")
findings = report.get("findings", [])
cost = report.get("cost_usd", 0)
model = report.get("model", "unknown")

icon = {"pass": ":white_check_mark:", "fail": ":x:", "error": ":warning:"}.get(v, ":grey_question:")

lines = [
    f"## {icon} AI Review: {stage}",
    f"**Verdict:** {v} | **Severity:** {sev} | **Cost:** ${cost:.4f} | **Model:** {model}",
    "",
    summary,
    "",
]

if findings:
    lines.append("| Severity | File | Finding |")
    lines.append("|----------|------|---------|")
    for f in findings[:15]:  # Cap at 15 to avoid huge comments
        file_str = f"`{f.get('file', '-')}`"
        sev_str = f.get("severity", "-")
        msg = f.get("message", "-").replace("\n", " ")[:200]
        lines.append(f"| {sev_str} | {file_str} | {msg} |")
    if len(findings) > 15:
        lines.append(f"\n*...and {len(findings) - 15} more findings*")

print("\n".join(lines))
PYEOF
}

# ── bb_post_ai_review ──────────────────────────────────────────
# Usage: bb_post_ai_review stage_name
# Convenience: renders findings and posts as PR comment.
bb_post_ai_review() {
  local stage="$1"
  local report_path="/tmp/ai-review/${stage}.json"

  if ! bb_available; then
    return 0
  fi

  if [[ ! -f "$report_path" ]]; then
    return 0
  fi

  local markdown
  markdown=$(bb_render_findings "$stage" "$report_path")
  bb_post_pr_comment "$markdown"
}
