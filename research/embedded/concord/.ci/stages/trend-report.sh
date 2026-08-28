#!/usr/bin/env bash
# Stage: trend-report
# Gate:  N/A — always passes. Aggregates AI review metrics and uploads
#        a trend snapshot to MinIO for historical tracking.
set -euo pipefail

source "$(dirname "$0")/../lib/log.sh"

log_stage "trend-report — historical metrics aggregation"

REPORTS_DIR="/tmp/ai-review"

if [[ ! -d "$REPORTS_DIR" ]] || [[ -z "$(ls -A "$REPORTS_DIR"/*.json 2>/dev/null)" ]]; then
  log_skip "No AI review reports found"
  log_stage_end
  exit 0
fi

TOOL="$(dirname "$0")/../tools/trend-report.py"

python3 "$TOOL" \
  --reports-dir "$REPORTS_DIR" \
  --minio-endpoint "${MINIO_ENDPOINT:-}" \
  --minio-access-key "${MINIO_ACCESS_KEY:-}" \
  --minio-secret-key "${MINIO_SECRET_KEY:-}" \
  --minio-bucket "${MINIO_BUCKET:-devops}" \
  2>&1 | sed 's/^/  /'

if [[ -f "$REPORTS_DIR/trend-report.json" ]]; then
  log_ok "Trend report generated"
else
  log_warn "Trend report generation failed"
fi

log_stage_end
