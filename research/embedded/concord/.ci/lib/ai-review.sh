#!/usr/bin/env bash
# .ci/lib/ai-review.sh — shared functions for AI-powered CI review stages.
#
# Provides:
#   ai_review_available     Check if Claude CLI + auth are present
#   ai_review_get_diff      Safely capture a scoped git diff to a temp file
#   ai_review_run           Run Claude Code in non-interactive print mode
#   ai_review_parse         Parse Claude's JSON output into shell variables
#   ai_review_gate          Decide pass/block based on severity threshold
#   ai_review_save_report   Save a standardized report for MinIO upload
#   ai_review_log_result    Print colored result to terminal
#
# Required: source log.sh and context.sh BEFORE sourcing this file.
# Security: tokens are never logged. All Claude calls redirect stderr.

# ── Constants ──────────────────────────────────────────────────
readonly AI_REPORT_DIR="/tmp/ai-review"
readonly AI_MAX_DIFF_CHARS=80000

# Severity rank: higher = more severe
readonly _SEV_CRITICAL=5 _SEV_HIGH=4 _SEV_MEDIUM=3 _SEV_LOW=2 _SEV_INFO=1

_sev_rank() {
  case "${1:-info}" in
    critical) echo "$_SEV_CRITICAL" ;;
    high)     echo "$_SEV_HIGH" ;;
    medium)   echo "$_SEV_MEDIUM" ;;
    low)      echo "$_SEV_LOW" ;;
    *)        echo "$_SEV_INFO" ;;
  esac
}

# ── ai_review_available ───────────────────────────────────────
# Returns 0 if Claude Code can run, 1 otherwise (with log_skip).
# Checks: CLI on PATH + (CLAUDE_CODE_OAUTH_TOKEN OR credentials file).
ai_review_available() {
  if ! command -v claude &>/dev/null; then
    log_skip "claude CLI not installed — AI review skipped"
    return 1
  fi
  if [[ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]] && [[ ! -f "${HOME}/.claude/.credentials.json" ]]; then
    log_skip "no Claude auth — AI review skipped"
    return 1
  fi
  return 0
}

# ── ai_review_get_diff ────────────────────────────────────────
# Usage: ai_review_get_diff output_var [pathspec ...]
# Captures `git diff $NX_BASE...HEAD -- <pathspecs>` into a variable,
# strips null bytes, truncates to AI_MAX_DIFF_CHARS. Returns 1 if empty.
ai_review_get_diff() {
  local -n _out_var="$1"; shift

  # Validate NX_BASE is a resolvable git ref
  if ! git rev-parse --verify "${NX_BASE}^{commit}" &>/dev/null 2>&1; then
    log_warn "NX_BASE ($NX_BASE) is not a valid commit — using HEAD~10"
    NX_BASE="HEAD~10"
  fi

  local diff_file
  diff_file=$(mktemp /tmp/ai-diff-XXXXXX.txt)

  # Subshell absorbs SIGPIPE from head closing the pipe early
  (git diff "${NX_BASE}"...HEAD -- "$@" 2>/dev/null \
    | tr -d '\0' \
    | head -c "$AI_MAX_DIFF_CHARS" > "$diff_file") || true

  if [[ ! -s "$diff_file" ]]; then
    rm -f "$diff_file"
    return 1
  fi

  # Warn if diff was truncated
  local actual_size
  actual_size=$(wc -c < "$diff_file")
  if [[ "$actual_size" -ge "$AI_MAX_DIFF_CHARS" ]]; then
    log_warn "diff truncated to ${AI_MAX_DIFF_CHARS} chars — review may be incomplete"
  fi

  _out_var=$(cat "$diff_file")
  rm -f "$diff_file"
  return 0
}

# ── ai_review_run ─────────────────────────────────────────────
# Usage: ai_review_run prompt max_turns [model]
# Runs `claude -p` with the given prompt. Writes raw JSON to stdout.
# stderr is suppressed to prevent token leakage in logs.
ai_review_run() {
  local prompt="$1"
  local max_turns="${2:-2}"
  local model="${3:-}"
  local -a cmd=(claude -p --output-format json --max-turns "$max_turns")

  cmd+=(--allowedTools "Read,Grep,Glob")
  [[ -n "$model" ]] && cmd+=(--model "$model")

  echo "$prompt" | "${cmd[@]}" 2>/dev/null
}

# ── ai_review_parse ───────────────────────────────────────────
# Usage: ai_review_parse "$raw_json"
# Sets: AI_VERDICT AI_SEVERITY AI_SUMMARY AI_ISSUES AI_COST AI_MODEL
# Single Python call parses everything (efficient, consistent).
ai_review_parse() {
  local raw="$1"
  local rf pf
  rf=$(mktemp /tmp/ai-raw-XXXXXX.json)
  pf=$(mktemp /tmp/ai-parse-XXXXXX.json)

  printf '%s' "$raw" > "$rf"

  # Single Python call extracts all fields at once
  python3 - "$rf" "$pf" << 'PYEOF'
import json, sys, re, pathlib

raw_path = sys.argv[1]
out_path = sys.argv[2]

try:
    wrapper = json.loads(pathlib.Path(raw_path).read_text())
    result_text = wrapper.get("result", "{}")
    cost = wrapper.get("total_cost_usd", wrapper.get("cost_usd", 0))
    model_usage = wrapper.get("modelUsage", {})
    model = next(iter(model_usage.keys()), "unknown") if model_usage else "unknown"

    # Strip markdown code-block fences
    if isinstance(result_text, str):
        t = result_text.strip()
        fence = chr(96) * 3
        if t.startswith(fence):
            t = re.sub(r"^[^\n]*\n", "", t, count=1)
            t = re.sub(r"\n[^\n]*$", "", t.rstrip())
        result_text = t

    try:
        result = json.loads(result_text)
    except (json.JSONDecodeError, TypeError):
        result = {"verdict": "pass", "severity": "info",
                  "summary": str(result_text)[:200], "findings": []}

    out = {
        "verdict":  result.get("verdict", "pass"),
        "severity": result.get("severity", "info"),
        "summary":  result.get("summary", "No summary"),
        "issues":   len(result.get("findings", [])),
        "findings": result.get("findings", []),
        "cost":     round(float(cost), 4) if cost else 0,
        "model":    model,
    }
except Exception as e:
    out = {"verdict": "error", "severity": "info",
           "summary": f"Parse error: {e}", "issues": 0,
           "findings": [], "cost": 0, "model": "unknown"}

pathlib.Path(out_path).write_text(json.dumps(out))
PYEOF

  rm -f "$rf"

  # Single Python call to read all values (was 6 calls, now 1)
  eval "$(python3 -c "
import json, shlex
d = json.load(open('$pf'))
for k in ('verdict','severity','summary','issues','cost','model'):
    v = str(d.get(k, ''))
    print(f'AI_{k.upper()}={shlex.quote(v)}')
" 2>/dev/null || echo 'AI_VERDICT=error; AI_SEVERITY=info; AI_SUMMARY="parse failed"; AI_ISSUES=0; AI_COST=0; AI_MODEL=unknown')"

  _AI_PARSED_FILE="$pf"
}

# ── ai_review_gate ────────────────────────────────────────────
# Usage: ai_review_gate threshold
# Returns 0 (pass) or 1 (block). Only blocks when verdict=fail AND
# severity >= threshold.
ai_review_gate() {
  local threshold="${1:-critical}"
  if [[ "$AI_VERDICT" == "fail" ]]; then
    local t_rank s_rank
    t_rank=$(_sev_rank "$threshold")
    s_rank=$(_sev_rank "$AI_SEVERITY")
    [[ $s_rank -ge $t_rank ]] && return 1
  fi
  return 0
}

# ── ai_review_save_report ─────────────────────────────────────
# Usage: ai_review_save_report stage_name raw_json
# Saves TWO files:
#   $AI_REPORT_DIR/<stage>.json       — standardized parsed report
#   $AI_REPORT_DIR/<stage>.raw.json   — full Claude response (for debugging)
#
# Report schema: {stage, timestamp, verdict, severity, summary,
#   findings[], issues, cost_usd, model, branch, commit}
ai_review_save_report() {
  local stage="$1" raw="${2:-}"
  mkdir -p "$AI_REPORT_DIR"

  # Save raw Claude response for debugging / detailed inspection
  if [[ -n "$raw" ]]; then
    printf '%s' "$raw" > "${AI_REPORT_DIR}/${stage}.raw.json"
  fi

  local branch commit
  branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
  commit=$(git rev-parse --short=7 HEAD 2>/dev/null || echo "unknown")

  python3 - "$stage" "${_AI_PARSED_FILE:-/dev/null}" "$AI_REPORT_DIR" "$branch" "$commit" << 'PYEOF'
import json, sys, datetime, pathlib

stage   = sys.argv[1]
pf      = sys.argv[2]
out_dir = sys.argv[3]
branch  = sys.argv[4]
commit  = sys.argv[5]

try:
    parsed = json.load(open(pf))
except Exception:
    parsed = {"verdict": "error", "severity": "info", "summary": "no data",
              "issues": 0, "findings": [], "cost": 0, "model": "unknown"}

report = {
    "stage":     stage,
    "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    "branch":    branch,
    "commit":    commit,
    "verdict":   parsed["verdict"],
    "severity":  parsed["severity"],
    "summary":   parsed["summary"],
    "findings":  parsed.get("findings", []),
    "issues":    parsed["issues"],
    "cost_usd":  parsed["cost"],
    "model":     parsed["model"],
}

pathlib.Path(f"{out_dir}/{stage}.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False)
)
PYEOF

  rm -f "${_AI_PARSED_FILE:-}" 2>/dev/null
  _AI_PARSED_FILE=""
}

# ── ai_review_log_result ──────────────────────────────────────
# Usage: ai_review_log_result stage_name
# Prints verdict summary AND each individual finding with file + severity.
ai_review_log_result() {
  local stage="$1"

  # Verdict line
  case "$AI_VERDICT" in
    pass)  log_ok   "$stage: passed — $AI_SUMMARY" ;;
    fail)
      case "$AI_SEVERITY" in
        critical|high) log_err  "$stage: $AI_SEVERITY — $AI_SUMMARY ($AI_ISSUES issue(s))" ;;
        *)             log_warn "$stage: $AI_SEVERITY — $AI_SUMMARY ($AI_ISSUES issue(s))" ;;
      esac ;;
    error) log_warn "$stage: parse error — $AI_SUMMARY" ;;
    *)     log_info "$stage: $AI_VERDICT — $AI_SUMMARY" ;;
  esac

  # Individual findings (if report file exists)
  local report_file="${AI_REPORT_DIR}/${stage}.json"
  if [[ -f "$report_file" ]] && [[ "$AI_ISSUES" -gt 0 ]]; then
    python3 -c "
import json, sys
r = json.load(open('$report_file'))
for f in r.get('findings', [])[:20]:
    sev = f.get('severity', '?')
    file = f.get('file', '?')
    msg = f.get('message', '?')[:150]
    icon = {'critical': '!!', 'high': '! ', 'medium': '~ ', 'low': '  ', 'info': '  '}.get(sev, '  ')
    print(f'  {icon}[{sev}] {file}')
    print(f'         {msg}')
if len(r.get('findings', [])) > 20:
    print(f'  ... and {len(r[\"findings\"]) - 20} more')
" 2>/dev/null || true
  fi

  log_info "$stage: model=$AI_MODEL cost=\$${AI_COST}"
}

# ── ai_review_cleanup ─────────────────────────────────────────
# Remove stale reports older than 24 hours. Call at start of a run.
ai_review_cleanup() {
  mkdir -p "$AI_REPORT_DIR"
  find "$AI_REPORT_DIR" -type f -mmin +1440 -delete 2>/dev/null || true
}

# ── ai_review_capture_stage ───────────────────────────────────
# Usage: ai_review_capture_stage stage_name command [args...]
# Runs a stage command, captures stdout+stderr to a log file, and
# saves the log alongside the report for dashboard ingestion.
# The log file is at $AI_REPORT_DIR/<stage>.log
ai_review_capture_stage() {
  local stage="$1"; shift
  local log_file="${AI_REPORT_DIR}/${stage}.log"
  mkdir -p "$AI_REPORT_DIR"

  # Run the command, tee output to both terminal and log file
  "$@" 2>&1 | tee "$log_file"
  return "${PIPESTATUS[0]}"
}
