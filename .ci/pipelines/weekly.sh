#!/usr/bin/env bash
# Pipeline: Weekly
# Deep AI-powered analysis. Runs Saturday night.
# All AI reviews run with full codebase scope.
# Completeness + security are BLOCKING. Docs review is BLOCKING (--threshold=critical).
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$DIR/lib/log.sh"
source "$DIR/lib/context.sh"

# Full codebase review — not just affected files
export NX_BASE="HEAD~200"

log_stage "weekly — deep AI-powered review"
ci_summary

# ── AI review stages (blocking) ──────────────────────────────
bash "$DIR/stages/ai-review-completeness.sh"
bash "$DIR/stages/ai-review-security.sh"

# ── AI review stages (informational) ─────────────────────────
bash "$DIR/stages/ai-review-blast-radius.sh" || true

# ── AI docs review (blocking at critical threshold) ──────────
bash "$DIR/stages/ai-review-docs.sh" --threshold=critical

log_stage_end

# ── Upload consolidated report to MinIO ──────────────────────
log_stage "weekly — upload reports"
COMMIT=$(git rev-parse --short=7 HEAD 2>/dev/null || echo "unknown")
RUN_DATE=$(date -u +%Y-%m-%d)

if [[ -n "${MINIO_ACCESS_KEY:-}" ]] && [[ -n "${MINIO_SECRET_KEY:-}" ]] && command -v mc &>/dev/null; then
  RESULTS_PATH="${MINIO_BUCKET:-devops}/weekly/${RUN_DATE}-${COMMIT}"

  if mc alias set cluster "${MINIO_ENDPOINT:-http://concord-minio.staging.svc:9000}" "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}" --quiet 2>&1; then
    mc mb -p "cluster/${MINIO_BUCKET:-devops}" 2>/dev/null || true

    # Upload individual stage reports
    for report in /tmp/ai-review/*.json; do
      if [[ -f "$report" ]]; then
        mc cp "$report" "cluster/${RESULTS_PATH}/$(basename "$report")" --quiet 2>&1 || log_warn "Failed to upload $(basename "$report")"
      fi
    done

    # Create and upload summary
    python3 -c "
import json, glob, os

reports = {}
for f in glob.glob('/tmp/ai-review/*.json'):
    name = os.path.splitext(os.path.basename(f))[0]
    try:
        with open(f) as fh:
            reports[name] = json.load(fh)
    except Exception:
        reports[name] = {'error': 'failed to parse'}

summary = {
    'date': '${RUN_DATE}',
    'commit': '${COMMIT}',
    'branch': '$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)',
    'stages': list(reports.keys()),
    'reports': reports
}

with open('/tmp/ai-review/summary.json', 'w') as f:
    json.dump(summary, f, indent=2)
" 2>/dev/null || true

    if [[ -f /tmp/ai-review/summary.json ]]; then
      mc cp /tmp/ai-review/summary.json "cluster/${RESULTS_PATH}/summary.json" --quiet 2>&1 || log_warn "Failed to upload summary"
    fi

    log_ok "Reports uploaded to ${RESULTS_PATH}/"
  else
    log_warn "MinIO alias setup failed — skipping upload"
  fi
else
  log_warn "MinIO credentials not available — skipping upload"
fi

log_stage_end
