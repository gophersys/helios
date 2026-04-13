#!/usr/bin/env bash
# .ci/lib/ai-review.sh — shared functions for AI-powered review stages.
#
# All AI review stages source this file for:
#   - Availability check (token + CLI present)
#   - Running Claude Code in non-interactive mode
#   - Parsing JSON verdicts
#   - Gate logic (block vs warn vs pass)
#   - Report saving for MinIO upload

# ── Severity levels (ordered) ──────────────────────────────────
# critical > high > medium > low > info
_SEVERITY_CRITICAL=5
_SEVERITY_HIGH=4
_SEVERITY_MEDIUM=3
_SEVERITY_LOW=2
_SEVERITY_INFO=1

_severity_to_int() {
  case "${1:-info}" in
    critical) echo $_SEVERITY_CRITICAL ;;
    high)     echo $_SEVERITY_HIGH ;;
    medium)   echo $_SEVERITY_MEDIUM ;;
    low)      echo $_SEVERITY_LOW ;;
    info)     echo $_SEVERITY_INFO ;;
    *)        echo $_SEVERITY_INFO ;;
  esac
}

# ── Check if AI review is available ────────────────────────────
# Returns 0 if Claude CLI is available and authenticated, 1 otherwise.
# In CI: requires CLAUDE_CODE_OAUTH_TOKEN env var.
# Locally: uses existing interactive OAuth session (~/.claude/.credentials.json).
# When returning 1, logs a skip message — stages should exit 0.
ai_review_available() {
  if ! command -v claude &>/dev/null; then
    log_skip "claude CLI not installed — skipping AI review"
    return 1
  fi

  # Check for any valid auth: OAuth token env var OR credentials file
  if [[ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]] && [[ ! -f "${HOME}/.claude/.credentials.json" ]]; then
    log_skip "No Claude auth found (set CLAUDE_CODE_OAUTH_TOKEN or run 'claude' to login) — skipping AI review"
    return 1
  fi

  return 0
}

# ── Run Claude Code in non-interactive mode ────────────────────
# Usage: ai_review_run "prompt text" max_turns [model]
# Writes raw JSON output to stdout. Returns Claude's exit code.
ai_review_run() {
  local prompt="$1"
  local max_turns="${2:-2}"
  local model="${3:-}"

  local -a cmd=(
    claude -p
    --output-format json
    --allowedTools "Read,Grep,Glob"
    --max-turns "$max_turns"
  )

  if [[ -n "$model" ]]; then
    cmd+=(--model "$model")
  fi

  # Pass prompt via stdin to avoid shell escaping issues with large diffs
  echo "$prompt" | "${cmd[@]}" 2>/dev/null
}

# ── Parse verdict from Claude's JSON output ────────────────────
# Usage: ai_review_parse_verdict "$json_output"
# Sets global variables: AI_VERDICT, AI_SEVERITY, AI_SUMMARY, AI_ISSUES_COUNT, AI_COST
ai_review_parse_verdict() {
  local json_output="$1"
  local parse_file
  parse_file=$(mktemp /tmp/ai-review-parse-XXXXXX.json)

  # Write to temp file to avoid shell escaping issues
  python3 -c "
import json, sys

try:
    wrapper = json.loads(sys.stdin.read())
    result_text = wrapper.get('result', '{}')

    # Strip markdown code block wrappers if present
    import re
    fence = chr(96) * 3
    if isinstance(result_text, str):
        result_text = result_text.strip()
        if result_text.startswith(fence):
            result_text = re.sub(r'^[^\n]*\n', '', result_text, count=1)
            result_text = re.sub(r'\n[^\n]*$', '', result_text.rstrip())

    try:
        result = json.loads(result_text)
    except (json.JSONDecodeError, TypeError):
        result = {'verdict': 'pass', 'severity': 'info', 'summary': str(result_text)[:200], 'findings': []}

    out = {
        'verdict': result.get('verdict', 'pass'),
        'severity': result.get('severity', 'info'),
        'summary': result.get('summary', 'No summary provided'),
        'issues_count': len(result.get('findings', [])),
        'cost': str(wrapper.get('cost_usd', 'unknown'))
    }
    json.dump(out, open('${parse_file}', 'w'))
except Exception as e:
    json.dump({
        'verdict': 'error',
        'severity': 'info',
        'summary': f'Failed to parse AI response: {e}',
        'issues_count': 0,
        'cost': 'unknown'
    }, open('${parse_file}', 'w'))
" <<< "$json_output"

  # Read parsed values from temp file (safe from shell escaping)
  AI_VERDICT=$(python3 -c "import json; print(json.load(open('${parse_file}'))['verdict'])" 2>/dev/null || echo "error")
  AI_SEVERITY=$(python3 -c "import json; print(json.load(open('${parse_file}'))['severity'])" 2>/dev/null || echo "info")
  AI_SUMMARY=$(python3 -c "import json; print(json.load(open('${parse_file}'))['summary'])" 2>/dev/null || echo "Parse error")
  AI_ISSUES_COUNT=$(python3 -c "import json; print(json.load(open('${parse_file}'))['issues_count'])" 2>/dev/null || echo "0")
  AI_COST=$(python3 -c "import json; print(json.load(open('${parse_file}'))['cost'])" 2>/dev/null || echo "unknown")

  rm -f "$parse_file"
}

# ── Gate: decide if the review should block ────────────────────
# Usage: ai_review_gate "threshold"
# Compares AI_SEVERITY against threshold. Returns 0 (pass) or 1 (block).
# Example: ai_review_gate "critical" — only blocks if severity is critical.
ai_review_gate() {
  local threshold="${1:-critical}"
  local threshold_int
  threshold_int=$(_severity_to_int "$threshold")
  local severity_int
  severity_int=$(_severity_to_int "$AI_SEVERITY")

  if [[ "$AI_VERDICT" == "fail" ]] && [[ $severity_int -ge $threshold_int ]]; then
    return 1
  fi

  return 0
}

# ── Save report JSON for later upload ──────────────────────────
# Usage: ai_review_save_report "stage-name" "$json_output"
ai_review_save_report() {
  local stage="$1"
  local json_output="$2"
  local report_dir="/tmp/ai-review"

  mkdir -p "$report_dir"
  echo "$json_output" > "${report_dir}/${stage}.json"
}

# ── Log the review result with appropriate color ───────────────
ai_review_log_result() {
  local stage="$1"

  case "$AI_VERDICT" in
    pass)
      log_ok "${stage}: passed (${AI_SEVERITY}) — ${AI_SUMMARY}"
      ;;
    fail)
      if [[ "$AI_SEVERITY" == "critical" ]] || [[ "$AI_SEVERITY" == "high" ]]; then
        log_err "${stage}: ${AI_SEVERITY} — ${AI_SUMMARY} (${AI_ISSUES_COUNT} issue(s))"
      else
        log_warn "${stage}: ${AI_SEVERITY} — ${AI_SUMMARY} (${AI_ISSUES_COUNT} issue(s))"
      fi
      ;;
    error)
      log_warn "${stage}: review error — ${AI_SUMMARY}"
      ;;
    *)
      log_info "${stage}: ${AI_VERDICT} — ${AI_SUMMARY}"
      ;;
  esac

  log_info "${stage}: cost=\$${AI_COST}"
}

# ── Truncate diff to stay within token limits ──────────────────
# Usage: truncate_diff "$diff_text" max_chars
# Outputs truncated text with a warning appended if truncated.
ai_review_truncate_diff() {
  local diff="$1"
  local max_chars="${2:-80000}"
  local len=${#diff}

  if [[ $len -gt $max_chars ]]; then
    echo "${diff:0:$max_chars}"
    echo ""
    echo "[TRUNCATED: diff was ${len} chars, showing first ${max_chars}. Review may be incomplete.]"
  else
    echo "$diff"
  fi
}
