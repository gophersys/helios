#!/usr/bin/env bash
# FUOTA overnight build monitor — checks build status and reports to Discord
set -euo pipefail

DISCORD_WEBHOOK="https://discord.com/api/webhooks/1478806971934179490/itB9fJ2tuhvy74ivLusiiipHJS5PyEYwY1571fO9JhigBMuAZ_OFZ7Hhmgpb5zUzADXp"
STATE_FILE="/tmp/fuota_monitor_state"

# Query build status — all non-cancelled builds since 00:40
get_build_status() {
    kubectl exec -n staging concord-postgres-7fcc584fcc-vx67x -- bash -c "PGPASSWORD=concord-staging psql -U concord -d concord -t -A -c \"
        SELECT b.status, b.\\\"versionString\\\", b.\\\"configFlags\\\"::text
        FROM build_jobs b
        WHERE b.\\\"createdAt\\\" > '2026-03-20 00:40:00'
        AND b.status != 'CANCELLED'
        ORDER BY b.\\\"createdAt\\\" ASC;
    \"" 2>/dev/null
}

check_all_success() {
    local status_output
    status_output=$(get_build_status)
    local total=0 success=0 building=0 queued=0 failed=0
    local details=""

    while IFS='|' read -r status version config; do
        [[ -z "$status" ]] && continue
        total=$((total + 1))
        # Extract matrixLabel from configFlags JSON
        local label
        label=$(echo "$config" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('matrixLabel','?'))" 2>/dev/null || echo "?")
        local icon="?"
        case "$status" in
            SUCCESS) success=$((success + 1)); icon="+" ;;
            BUILDING|CLONING) building=$((building + 1)); icon="~" ;;
            QUEUED) queued=$((queued + 1)); icon="." ;;
            FAILED|BUILD_FAILED) failed=$((failed + 1)); icon="X" ;;
        esac
        details="${details}[$icon] $label v${version:-?} ($status)\\n"
    done <<< "$status_output"

    echo "$total|$success|$building|$queued|$failed|$details"
}

discord_notify() {
    curl -s -H "Content-Type: application/json" \
        -d "{\"content\": \"$1\"}" \
        "$DISCORD_WEBHOOK" >/dev/null 2>&1 || true
}

check_pipeline() {
    kubectl exec -n staging concord-postgres-7fcc584fcc-vx67x -- bash -c "PGPASSWORD=concord-staging psql -U concord -d concord -t -A -c \"
        SELECT id, status
        FROM pipeline_runs
        WHERE \\\"createdAt\\\" > '2026-03-20 01:00:00'
        ORDER BY \\\"createdAt\\\" DESC
        LIMIT 1;
    \"" 2>/dev/null
}

# Main
RESULT=$(check_all_success)
IFS='|' read -r TOTAL SUCCESS BUILDING QUEUED FAILED DETAILS <<< "$RESULT"

PREV_STATE=""
[[ -f "$STATE_FILE" ]] && PREV_STATE=$(cat "$STATE_FILE")
CURR_STATE="${SUCCESS}/${TOTAL}/f${FAILED}"

if [[ "$CURR_STATE" != "$PREV_STATE" ]]; then
    echo "$CURR_STATE" > "$STATE_FILE"

    if [[ "$FAILED" -gt 0 ]]; then
        discord_notify "**Build FAILURE** -- $FAILED/$TOTAL failed\\n\`\`\`\\n${DETAILS}\`\`\`"
    elif [[ "$SUCCESS" -eq "$TOTAL" && "$TOTAL" -ge 6 ]]; then
        discord_notify "**All $TOTAL builds SUCCESS** -- Ready for pipeline creation\\n\`\`\`\\n${DETAILS}\`\`\`"
    else
        discord_notify "**Builds:** $SUCCESS/$TOTAL done, $BUILDING building, $QUEUED queued\\n\`\`\`\\n${DETAILS}\`\`\`"
    fi
fi

# Output machine-readable status
if [[ "$SUCCESS" -ge 6 && "$TOTAL" -ge 6 && "$FAILED" -eq 0 ]]; then
    PIPELINE=$(check_pipeline)
    if [[ -n "$PIPELINE" ]]; then
        echo "PIPELINE_READY|$(echo "$PIPELINE" | cut -d'|' -f1)|$(echo "$PIPELINE" | cut -d'|' -f2)"
    else
        echo "ALL_BUILDS_DONE"
    fi
elif [[ "$FAILED" -gt 0 ]]; then
    echo "BUILD_FAILED|$FAILED/$TOTAL"
else
    echo "IN_PROGRESS|$SUCCESS/$TOTAL"
fi
