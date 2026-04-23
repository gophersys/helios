#!/usr/bin/env bash
# Stage: ai-fix
# Gate:  N/A — runs after AI review failures to auto-remediate.
#
# Flow:
#   1. Reads failed findings from /tmp/ai-review/*.json
#   2. Runs Claude with write tools (Edit, Write, Read, Grep, Glob — NO Bash)
#   3. Commits fixes to the CURRENT branch (same as the PR)
#   4. Pushes so CI re-triggers and the next run should pass
#   5. Saves a detailed fix report to /tmp/ai-review/fix.json
#
# Safety: Claude cannot execute shell commands (Bash not in allowedTools).
# The commit message identifies it as an automated fix for traceability.
set -euo pipefail

source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"
source "$(dirname "$0")/../lib/ai-review.sh"

STAGE="fix"

log_stage "ai-fix — auto-remediation of AI review findings"

if ! ai_review_available; then
  log_stage_end
  exit 0
fi

# ── Collect failed findings ────────────────────────────────────
FINDINGS_DIR="/tmp/ai-review"
if [[ ! -d "$FINDINGS_DIR" ]]; then
  log_skip "No AI review reports found"
  log_stage_end
  exit 0
fi

FAILED_COUNT=0
FINDINGS_TEXT=""
FAILED_STAGES=""

for report in "$FINDINGS_DIR"/*.json; do
  [[ -f "$report" ]] || continue
  # Skip non-stage reports
  [[ "$(basename "$report")" == "trend-report.json" ]] && continue
  [[ "$(basename "$report")" == "serializer-check.json" ]] && continue
  [[ "$(basename "$report")" == "fix.json" ]] && continue
  [[ "$(basename "$report")" =~ \.raw\.json$ ]] && continue

  _verdict=$(python3 -c "import json; print(json.load(open('$report')).get('verdict','pass'))" 2>/dev/null || echo "pass")
  if [[ "$_verdict" == "fail" ]]; then
    FAILED_COUNT=$((FAILED_COUNT + 1))
    FAILED_STAGES="${FAILED_STAGES} $(basename "$report" .json)"
    FINDINGS_TEXT="${FINDINGS_TEXT}$(cat "$report")
---
"
  fi
done

if [[ "$FAILED_COUNT" -eq 0 ]]; then
  log_skip "No failed findings to fix"
  log_stage_end
  exit 0
fi

log_info "Failed stages:$FAILED_STAGES ($FAILED_COUNT total)"

# ── Build prompt ───────────────────────────────────────────────
read -r -d '' FIX_PROMPT << 'PROMPT_HEREDOC' || true
You are fixing CI review findings in the Concord monorepo.

## Instructions

1. Read each finding carefully — the "file" field tells you WHERE and the
   "message" field tells you WHAT to fix.
2. Use Glob and Grep to locate the relevant files.
3. Use Read to understand the current code.
4. Use Edit to apply targeted fixes. Prefer small, precise edits.
5. Only fix what the findings describe — do not refactor unrelated code.
6. Do NOT add code comments explaining the fix.
7. Do NOT create new files unless a finding explicitly requires it.

After fixing everything, summarize what you changed in one paragraph.
PROMPT_HEREDOC

FIX_PROMPT="${FIX_PROMPT}

## Findings to Fix

${FINDINGS_TEXT}

Working directory: $(pwd)"

# ── Run Claude in write mode ──────────────────────────────────
log_info "Running Claude in write mode (max-turns: 10)..."
FIX_RAW=$(echo "$FIX_PROMPT" | claude -p \
  --output-format json \
  --max-turns 10 \
  --allowedTools "Read,Grep,Glob,Edit,Write" \
  2>/dev/null || true)

# Save raw Claude response for inspection
mkdir -p "$FINDINGS_DIR"
if [[ -n "$FIX_RAW" ]]; then
  printf '%s' "$FIX_RAW" > "${FINDINGS_DIR}/fix.raw.json"

  # Extract Claude's summary of what it did
  FIX_SUMMARY=$(python3 -c "
import json, sys, re
try:
    w = json.loads(sys.stdin.read())
    t = w.get('result', '')
    cost = w.get('total_cost_usd', 0)
    turns = w.get('num_turns', 0)
    print(f'turns={turns} cost=\${cost:.4f}')
    # Print Claude's text summary (strip markdown fences)
    fence = chr(96) * 3
    if isinstance(t, str):
        t = t.strip()
        if t.startswith(fence):
            t = re.sub(r'^[^\n]*\n', '', t, count=1)
            t = re.sub(r'\n[^\n]*$', '', t.rstrip())
    print(t[:500])
except Exception as e:
    print(f'parse error: {e}')
" <<< "$FIX_RAW" 2>/dev/null || echo "(could not parse Claude response)")

  log_info "Claude response:"
  echo "$FIX_SUMMARY" | sed 's/^/  /'
fi

# ── Check for changes ──────────────────────────────────────────
if git diff --quiet && git diff --cached --quiet; then
  log_warn "Claude made no file changes — manual fix required"

  # Save report even on no-change
  python3 -c "
import json, datetime
json.dump({
    'stage': 'fix',
    'timestamp': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
    'action': 'no_changes',
    'failed_stages': '${FAILED_STAGES}'.split(),
    'failed_count': ${FAILED_COUNT},
}, open('${FINDINGS_DIR}/fix.json', 'w'), indent=2)
" 2>/dev/null || true

  log_stage_end
  exit 0
fi

# ── Show what changed ─────────────────────────────────────────
CHANGED_FILES=$(git diff --name-only)
CHANGED_COUNT=$(echo "$CHANGED_FILES" | wc -l)
log_info "Claude modified $CHANGED_COUNT file(s):"
echo "$CHANGED_FILES" | sed 's/^/  /'
echo ""

# Show the actual diff (abbreviated)
log_info "Diff summary:"
git diff --stat | sed 's/^/  /'

# ── Commit to the CURRENT branch ──────────────────────────────
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
log_info "Committing fixes to branch: $CURRENT_BRANCH"

git add -A
git commit -m "fix: auto-remediate AI review findings

Fixes for $FAILED_COUNT failed review(s):$FAILED_STAGES
$CHANGED_COUNT file(s) modified by automated CI fix." 2>/dev/null || {
  log_warn "Commit failed"
  git checkout -- . 2>/dev/null || true
  log_stage_end
  exit 0
}

# ── Push to origin (triggers CI re-run) ───────────────────────
PUSH_SUCCESS=false
if [[ -f /root/.ssh/id_rsa ]]; then
  export GIT_SSH_COMMAND="ssh -i /root/.ssh/id_rsa -o StrictHostKeyChecking=no"
  if git push origin "$CURRENT_BRANCH" 2>/dev/null; then
    PUSH_SUCCESS=true
    log_ok "Fixes pushed to $CURRENT_BRANCH — CI will re-run"
  else
    log_warn "Push failed — fixes committed locally but not pushed"
  fi
else
  log_warn "No SSH key — fixes committed locally on $CURRENT_BRANCH"
fi

# ── Post PR comment ───────────────────────────────────────────
if [[ -n "${BITBUCKET_PR_ID:-}" ]] && [[ "$PUSH_SUCCESS" == "true" ]]; then
  source "$(dirname "$0")/../lib/bitbucket.sh"

  # Build detailed comment with file list
  FILE_LIST=$(echo "$CHANGED_FILES" | sed 's/^/- `/' | sed 's/$/`/')
  bb_post_pr_comment "## :wrench: Automated Fix Committed

Claude Code applied fixes for **$FAILED_COUNT** failed AI review(s) and pushed to \`$CURRENT_BRANCH\`. CI will re-run automatically.

**Failed stages:**$FAILED_STAGES
**Files changed:**
${FILE_LIST}

Review the latest commit to verify the fixes."
fi

# ── Save fix report ───────────────────────────────────────────
python3 -c "
import json, datetime
json.dump({
    'stage': 'fix',
    'timestamp': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
    'action': 'committed_and_pushed' if '$PUSH_SUCCESS' == 'true' else 'committed_locally',
    'branch': '${CURRENT_BRANCH}',
    'failed_stages': '${FAILED_STAGES}'.split(),
    'failed_count': ${FAILED_COUNT},
    'files_changed': ${CHANGED_COUNT},
    'pushed': '$PUSH_SUCCESS' == 'true',
}, open('${FINDINGS_DIR}/fix.json', 'w'), indent=2)
" 2>/dev/null || true

log_stage_end
