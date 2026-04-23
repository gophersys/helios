---
min_role: DEVELOPER
---
# Validation Queue

You have a firmware build that needs testing, but every fixture is occupied. Or you have three builds waiting and need the critical one to run first. The validation queue handles scheduling: it holds pending validation requests, orders them by priority, and assigns them to fixtures as they become available.

## Queue entries

A queue entry represents a single validation request for a specific build run and stage. Each entry carries four fields:

| Field | Type | Description |
|-------|------|-------------|
| `buildRunId` | string | The build run to validate |
| `stage` | integer | Validation stage number (1-5) |
| `priority` | integer | Higher values run first. Default is 50 for build-triggered entries; manual entries default to 0 unless specified |
| `reason` | string | Free-text note explaining why this was queued (optional) |

Entries start with status **QUEUED** immediately after creation. The scheduler picks them up on its next pass.

### Creating entries

Entries are created automatically when a build completes -- the build service pushes one entry per configured stage. You can also create entries manually via the API:

```bash
curl -X POST https://concord.local/v2/validation/queue \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "buildRunId": "<build-run-id>",
    "stage": 4,
    "priority": 50,
    "reason": "Re-run after fixture cable replacement"
  }'
```

## Priority and ordering

The scheduler processes entries in **priority-descending** order. A priority-90 entry runs before a priority-10 entry regardless of when each was created.

When two entries share the same priority, the scheduler falls back to FIFO -- the entry with the earlier `requestedAt` timestamp goes first.

### Promoting an entry

If a queued entry needs to jump the line, promote it. The promote action bumps its priority above its current value:

```bash
curl -X POST https://concord.local/v2/validation/queue/<entry-id>/promote \
  -H "Authorization: Bearer <token>"
```

In the UI, the **Promote** button on any queued entry does the same thing.

### Cancelling an entry

Cancel removes an entry from the queue. The entry stays in the database with status **CANCELLED** and a `completedAt` timestamp, but the scheduler ignores it. Use this when you realize a build is bad or the stage is no longer relevant.

## Assignment

The scheduler runs periodically and matches queued entries to available fixtures. The logic:

1. Find all entries with status QUEUED, ordered by priority then `requestedAt`
2. For each entry, find a fixture that matches the entry's product and has status AVAILABLE
3. If a fixture is found, set the entry to **ASSIGNED** and the fixture to **LOCKED**
4. Trigger a K8s Job to execute the validation session
5. When the Job starts, the entry transitions to **RUNNING** and gets a `sessionId`

If no fixture matches -- because all are locked, offline, or wired for a different product -- the entry stays QUEUED until the next scheduler pass.

## Entry lifecycle

```
QUEUED → ASSIGNED → RUNNING → COMPLETED
                             → FAILED
                             → CANCELLED
```

An entry can be cancelled from any pre-RUNNING state. Once RUNNING, the session drives the final outcome: if all tests pass, the entry moves to COMPLETED; if any test fails or the session errors out, it moves to FAILED.

## Queue stats

The stats endpoint returns aggregate counts across all entries:

| Counter | Meaning |
|---------|---------|
| `queued` | Entries waiting for a fixture |
| `running` | Active validation sessions |
| `completed` | Sessions that passed |
| `failed` | Sessions that failed or errored |
| `cancelled` | Manually cancelled entries |
| `total` | Sum of all the above |

## Queue page

Navigate to **Validation > Queue** in the sidebar. The page shows a table of all queue entries with columns for status, stage, priority, reason, and bench (fixture) assignment. Unassigned entries show `---` in the bench column. Each row has a status badge (QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED).

The table auto-refreshes every 10 seconds, so new entries and status changes appear without a manual reload.

Admins see **Cancel** and **Promote** buttons on each queued entry row.

## Filtering

Filter entries by status using the API:

```bash
curl https://concord.local/v2/validation/queue?status=QUEUED \
  -H "Authorization: Bearer <token>"
```

Returns only entries matching the specified status.

---

See also: [Running validation](running-validation.md) for triggering runs directly, [Results](results.md) for interpreting session outcomes, [Run detail](run-detail.md) for the session view once a queue entry starts executing.
