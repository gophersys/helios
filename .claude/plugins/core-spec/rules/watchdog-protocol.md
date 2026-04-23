# Watchdog Protocol — Cron-Driven Health Monitoring

The 15-minute cron job is both an orchestrator (state machine) AND a watchdog (health monitor). This rule defines the watchdog responsibilities.

## Watchdog Checks (Every Cron Fire)

On every cron fire, AFTER reading STATUS.md and before executing the state machine:

### Check 1: Heartbeat Freshness

```bash
# Read heartbeat files for all IN_PROGRESS stages
for f in <spec-path>/heartbeats/stage-*.txt; do
  STAGE=$(grep "^STAGE:" "$f" | cut -d' ' -f2)
  LAST=$(grep "^LAST_UPDATE:" "$f" | cut -d' ' -f2)
  AGE_MIN=$(( ($(date +%s) - $(date -d "$LAST" +%s)) / 60 ))

  if [ $AGE_MIN -gt 45 ]; then
    echo "WARNING: Stage $STAGE heartbeat stale ($AGE_MIN min)"
  fi
  if [ $AGE_MIN -gt 90 ]; then
    echo "CRITICAL: Stage $STAGE likely stalled ($AGE_MIN min)"
  fi
done
```

### Check 2: STATUS.md Staleness

```
For each IN_PROGRESS stage in STATUS.md:
  Read "Last Update" column
  Calculate minutes since last update
  
  > 45 min: WARNING — send Discord notification
  > 90 min: RE-LAUNCH — increment attempt count, re-launch agent
  > 180 min (3h): BLOCKED — mark stage BLOCKED, notify, continue
```

### Check 3: Blocked Stage Count

```
Count stages with Status = BLOCKED in STATUS.md

  0-2 BLOCKED: Normal — continue execution
  3-4 BLOCKED: WARNING — send Discord alert, continue cautiously
  > 50% BLOCKED: EMERGENCY STOP — halt launches, send critical Discord notification
```

### Check 4: Team Health

```
Read ~/.claude/teams/<team-name>/config.json
Check if all expected teammates are listed
If a teammate is missing (crashed without cleanup):
  → Log in MEMORY.md
  → Re-launch if attempts < 3
```

## Escalation Ladder

| Minutes Stale | Action |
|:------------:|--------|
| 0-30 | Normal — agent is working |
| 30-45 | Monitor — check on next cron fire |
| 45-60 | Warning — Discord: "Stage N may be stalling" |
| 60-90 | Alert — Discord: "Stage N stalled, re-launching" → re-launch |
| 90-180 | Critical — Discord: "Stage N failed after re-launch" → try once more |
| 180+ | Blocked — Discord: "Stage N BLOCKED" → mark blocked, skip |

## Discord Notification Templates

```bash
# Warning (45+ min stale)
"⚠️ Stage {N} ({name}) heartbeat stale ({age} min). Monitoring."

# Re-launch (90+ min)
"🔄 Stage {N} ({name}) stalled — re-launching (attempt {n}/3)"

# Blocked (180+ min or 3 failed re-launches)
"🚫 Stage {N} ({name}) BLOCKED after {attempts} attempts. Skipping. Error: {last_error}"

# Emergency stop (>50% blocked)
"🔴 EMERGENCY: {blocked_count}/{total_count} stages blocked. Halting further launches. Manual intervention needed."

# Health report (every 4th cron fire = hourly)
"📊 Health: {running}/{total} stages running, {complete} complete, {blocked} blocked. ETA: {estimate}"
```

## Heartbeat File Format

Each agent writes to `<spec-path>/heartbeats/stage-<N>.txt`:

```
STAGE: 7
STATUS: working | testing | blocked | completing
CURRENT_TASK: Writing fixture CRUD E2E tests
TESTS_WRITTEN: 12
TESTS_PASSING: 10
TESTS_FAILING: 2
ERRORS: TypeError in api helper line 45
LAST_UPDATE: 2026-04-09T02:30:00Z
ATTEMPT: 1
```

Agents MUST update this file every 10 minutes. The cron watchdog reads these independently of STATUS.md (which may have write contention with multiple agents).

## Emergency Stop Behavior

When >50% of stages are BLOCKED:

```
1. Send CRITICAL Discord notification
2. Do NOT launch any new agents or waves
3. Log full status to MEMORY.md
4. Update STATUS.md State → BLOCKED
5. Wait for human intervention
6. When human resumes, re-read STATUS.md and continue from current state
```

The system should NEVER silently die. Even in emergency stop, it notifies and documents.
