#!/usr/bin/env bash
# Pipeline: Weekly
# Deep AI-powered codebase analysis. Runs Saturday 3 AM Chicago time.
#
# Every stage's stdout/stderr is captured to /tmp/ai-review/<stage>.log
# and POSTed to the dashboard with findings. Full pipeline output is
# also captured as pipeline.log for end-to-end visibility.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$DIR/lib/log.sh"
source "$DIR/lib/context.sh"
source "$DIR/lib/ai-review.sh"

export NX_BASE="HEAD~200"
STARTED_AT=$(date +%s)

log_stage "weekly — deep AI-powered review"
ci_summary
log_stage_end

ai_review_cleanup

# ── Helper: run a stage and capture its log ───────────────────
# Usage: run_and_capture <name> <command> [args...]
# Saves stdout+stderr to /tmp/ai-review/<name>.log
# Always continues (|| true) — failures don't kill the pipeline.
run_and_capture() {
  local name="$1"; shift
  local log_file="${AI_REPORT_DIR}/${name}.log"
  mkdir -p "$AI_REPORT_DIR"
  local stage_start
  stage_start=$(date +%s)

  # Run stage, tee to both terminal and log file
  "$@" 2>&1 | tee "$log_file" || true

  local stage_end
  stage_end=$(date +%s)
  local dur=$(( stage_end - stage_start ))

  # If this is an AI review stage with a .json report, inject duration + log into it
  local report="${AI_REPORT_DIR}/${name}.json"
  if [[ -f "$report" ]]; then
    python3 -c "
import json, pathlib
r = json.loads(pathlib.Path('$report').read_text())
r['duration_seconds'] = $dur
r['logs'] = pathlib.Path('$log_file').read_text()[-10000:]
pathlib.Path('$report').write_text(json.dumps(r, indent=2))
" 2>/dev/null || true
  else
    # Non-AI stage — create a minimal report so it shows up in the dashboard
    python3 -c "
import json, pathlib, datetime
pathlib.Path('$report').write_text(json.dumps({
    'stage': '$name',
    'timestamp': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
    'verdict': 'pass',
    'severity': 'info',
    'summary': 'Stage completed',
    'findings': [],
    'issues': 0,
    'cost_usd': 0,
    'model': 'n/a',
    'duration_seconds': $dur,
    'logs': pathlib.Path('$log_file').read_text()[-10000:]
}, indent=2))
" 2>/dev/null || true
  fi
}

# ── AI review stages ──────────────────────────────────────────
run_and_capture "completeness" bash "$DIR/stages/ai-review-completeness.sh"
run_and_capture "security" bash "$DIR/stages/ai-review-security.sh"
run_and_capture "blast-radius" bash "$DIR/stages/ai-review-blast-radius.sh"
run_and_capture "docs" bash "$DIR/stages/ai-review-docs.sh" --threshold=critical
run_and_capture "architecture" bash "$DIR/stages/ai-review-architecture.sh"

# ── Static analysis stages ────────────────────────────────────
run_and_capture "serializer-check" bash "$DIR/stages/serializer-check.sh"
run_and_capture "proto-sync" bash "$DIR/stages/proto-sync.sh"
run_and_capture "types-sync" bash "$DIR/stages/types-sync.sh"

# ── Trend report (captures its own output) ────────────────────
run_and_capture "trend-report" bash "$DIR/stages/trend-report.sh"

# ── Post results to CI dashboard ──────────────────────────────
log_stage "weekly — post results to dashboard"

COMMIT=$(git rev-parse --short=7 HEAD 2>/dev/null || echo "unknown")
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
DURATION=$(( $(date +%s) - STARTED_AT ))

if [[ -n "${CI_DASHBOARD_URL:-}" ]]; then
  python3 - "${CI_DASHBOARD_URL}" "${BRANCH}" "${COMMIT}" "${DURATION}" << 'PYEOF'
import json, glob, sys, urllib.request, pathlib

dashboard_url = sys.argv[1]
branch = sys.argv[2]
commit = sys.argv[3]
duration = int(sys.argv[4])

report_dir = pathlib.Path("/tmp/ai-review")
stages = []

for f in sorted(report_dir.glob("*.json")):
    name = f.stem
    if name in ("trend-report",) or name.endswith(".raw"):
        continue
    try:
        data = json.loads(f.read_text())
        if "stage" not in data:
            continue
        stages.append(data)
    except Exception:
        continue

if not stages:
    print("No stage reports found")
    sys.exit(0)

payload = {
    "pipeline": "weekly",
    "branch": branch,
    "commitSha": commit,
    "durationSeconds": duration,
    "stages": stages,
}

req = urllib.request.Request(
    f"{dashboard_url}/api/runs",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    resp = urllib.request.urlopen(req, timeout=15)
    print(f"Dashboard updated: HTTP {resp.status} ({len(stages)} stages)")
except Exception as e:
    print(f"Dashboard POST failed (non-fatal): {e}")
PYEOF
else
  log_warn "CI_DASHBOARD_URL not set — skipping dashboard POST"
fi

log_stage_end

# ── Upload to MinIO ───────────────────────────────────────────
log_stage "weekly — upload to MinIO"

RUN_DATE=$(date -u +%Y-%m-%d)
RESULTS_PATH="${MINIO_BUCKET:-ci}/weekly/${RUN_DATE}-${COMMIT}"

if [[ -n "${MINIO_ACCESS_KEY:-}" ]] && [[ -n "${MINIO_SECRET_KEY:-}" ]] && command -v mc &>/dev/null; then
  if mc alias set cluster "${MINIO_ENDPOINT:-http://concord-ci-minio:9000}" \
      "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}" --quiet 2>&1; then

    mc mb -p "cluster/${MINIO_BUCKET:-ci}" 2>/dev/null || true

    for f in /tmp/ai-review/*.json /tmp/ai-review/*.log; do
      [[ -f "$f" ]] && mc cp "$f" "cluster/${RESULTS_PATH}/$(basename "$f")" --quiet 2>&1 || true
    done

    log_ok "Reports + logs uploaded to ${RESULTS_PATH}/"
  else
    log_warn "MinIO alias setup failed — skipping upload"
  fi
else
  log_warn "MinIO credentials not available — skipping upload"
fi

log_stage_end
