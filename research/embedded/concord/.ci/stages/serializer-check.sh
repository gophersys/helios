#!/usr/bin/env bash
# Stage: serializer-check
# Gate:  ADVISORY — reports serializer/schema mismatches.
#
# Compares _serialize_*() function output keys against OpenAPI schema
# properties defined in docs.py. Catches fields that exist in the
# schema but aren't emitted by serializers (data loss risk).
set -euo pipefail

source "$(dirname "$0")/../lib/log.sh"

log_stage "serializer-check — serializer/schema field coverage"

TOOL="$(dirname "$0")/../tools/check-serializers.py"

if [[ ! -f "$TOOL" ]]; then
  log_err "check-serializers.py not found at $TOOL"
  log_stage_end
  exit 1
fi

OUTPUT=$(python3 "$TOOL" --json 2>&1)
EXIT=$?

# Parse summary
SERIALIZERS=$(echo "$OUTPUT" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('serializers_found',0))" 2>/dev/null || echo "?")
SCHEMAS=$(echo "$OUTPUT" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('schemas_found',0))" 2>/dev/null || echo "?")
FINDINGS=$(echo "$OUTPUT" | python3 -c "import json,sys; print(len(json.loads(sys.stdin.read()).get('findings',[])))" 2>/dev/null || echo "?")

log_info "Serializers: $SERIALIZERS | Schemas: $SCHEMAS | Findings: $FINDINGS"

# Save report
mkdir -p /tmp/ai-review
echo "$OUTPUT" > /tmp/ai-review/serializer-check.json

if [[ $EXIT -ne 0 ]]; then
  log_warn "Serializer completeness issues found ($FINDINGS finding(s))"
  # Show top findings
  echo "$OUTPUT" | python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
for f in data.get('findings', [])[:5]:
    print(f'  [{f[\"severity\"]}] {f[\"message\"][:120]}')
" 2>/dev/null || true
else
  log_ok "Serializers match OpenAPI schemas"
fi

log_stage_end
# Advisory — don't fail the pipeline
exit 0
