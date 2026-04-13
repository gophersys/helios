#!/usr/bin/env bash
# Pipeline: Weekly
# Deep AI-powered codebase analysis. Runs Saturday 3 AM Chicago time.
#
# Completeness + security stages are BLOCKING.
# Docs review is BLOCKING at critical threshold.
# Blast-radius is always informational.
#
# Each stage's stdout/stderr is captured to /tmp/ai-review/<stage>.log
# for inclusion in the dashboard. Reports uploaded to MinIO.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$DIR/lib/log.sh"
source "$DIR/lib/context.sh"
source "$DIR/lib/ai-review.sh"

# Full codebase scope — not just affected files
export NX_BASE="HEAD~200"
STARTED_AT=$(date +%s)

log_stage "weekly — deep AI-powered review"
ci_summary
log_stage_end

ai_review_cleanup

# ── Run stages with log capture ───────────────────────────────
# Each stage's output is tee'd to /tmp/ai-review/<stage>.log

ai_review_capture_stage "completeness" bash "$DIR/stages/ai-review-completeness.sh" || true
ai_review_capture_stage "security" bash "$DIR/stages/ai-review-security.sh" || true
ai_review_capture_stage "blast-radius" bash "$DIR/stages/ai-review-blast-radius.sh" || true
ai_review_capture_stage "docs" bash "$DIR/stages/ai-review-docs.sh" --threshold=critical || true
ai_review_capture_stage "architecture" bash "$DIR/stages/ai-review-architecture.sh" || true
ai_review_capture_stage "serializer-check" bash "$DIR/stages/serializer-check.sh" || true

# ── Trend report (no log capture needed) ──────────────────────
bash "$DIR/stages/trend-report.sh" || true

# ── Post results to CI dashboard ──────────────────────────────
log_stage "weekly — post results to dashboard"

COMMIT=$(git rev-parse --short=7 HEAD 2>/dev/null || echo "unknown")
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
RUN_DATE=$(date -u +%Y-%m-%d)
DURATION=$(( $(date +%s) - STARTED_AT ))

if [[ -n "${CI_DASHBOARD_URL:-}" ]]; then
  python3 - "${CI_DASHBOARD_URL}" "${BRANCH}" "${COMMIT}" "${DURATION}" << 'PYEOF'
import json, glob, sys, urllib.request, pathlib

dashboard_url = sys.argv[1]
branch = sys.argv[2]
commit = sys.argv[3]
duration = int(sys.argv[4])

# Collect stage reports with logs
stages = []
report_dir = pathlib.Path("/tmp/ai-review")

for f in sorted(report_dir.glob("*.json")):
    name = f.stem
    if name in ("trend-report", "serializer-check", "fix") or name.endswith(".raw"):
        continue
    try:
        data = json.loads(f.read_text())
        if "stage" not in data or "verdict" not in data:
            continue
    except Exception:
        continue

    # Attach logs if captured
    log_file = report_dir / f"{name}.log"
    logs = log_file.read_text() if log_file.exists() else ""

    data["logs"] = logs[-10000:]  # Cap at 10KB per stage
    data["duration_seconds"] = data.get("duration_seconds", 0)
    stages.append(data)

if not stages:
    print("No stage reports found — skipping dashboard POST")
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
    print(f"Dashboard updated: HTTP {resp.status}")
except Exception as e:
    print(f"Dashboard POST failed (non-fatal): {e}")
PYEOF
else
  log_warn "CI_DASHBOARD_URL not set — skipping dashboard POST"
fi

log_stage_end

# ── Upload to MinIO ───────────────────────────────────────────
log_stage "weekly — upload to MinIO"

RESULTS_PATH="${MINIO_BUCKET:-devops}/weekly/${RUN_DATE}-${COMMIT}"

if [[ -n "${MINIO_ACCESS_KEY:-}" ]] && [[ -n "${MINIO_SECRET_KEY:-}" ]] && command -v mc &>/dev/null; then
  if mc alias set cluster "${MINIO_ENDPOINT:-http://concord-ci-minio:9000}" \
      "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}" --quiet 2>&1; then

    mc mb -p "cluster/${MINIO_BUCKET:-devops}" 2>/dev/null || true

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
