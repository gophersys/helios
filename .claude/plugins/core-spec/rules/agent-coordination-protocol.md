# Agent Coordination Protocol

When agent teammates work in parallel, they need structured communication patterns to avoid deadlocks, share discoveries, and resolve data dependencies.

## Message Patterns

Teammates communicate via `SendMessage`. Use these patterns:

### 1. Discovery (broadcast to lead)

When a teammate discovers something that affects other stages:

```
SendMessage({
  to: "lead",
  summary: "Stage 7 found API endpoint changed",
  message: "Discovery: The fixture creation endpoint returns 'stationId' not 'station_id'. Stage 3 and Stage 13 specs reference the wrong field name. Updating MEMORY.md."
})
```

### 2. Data Ready (to specific teammate)

When a teammate creates something another teammate needs:

```
SendMessage({
  to: "stage-3-products",
  summary: "Stage 1 foundation helpers ready",
  message: "The page objects and API helpers are committed to worktree e2e-foundation. Key files: e2e/pages/base.page.ts, e2e/helpers/api-extended.ts. You can reference these patterns."
})
```

### 3. Need Data (to specific teammate)

When a teammate needs something from another:

```
SendMessage({
  to: "stage-1-foundation",
  summary: "Stage 5 needs Bitbucket helper types",
  message: "I need the TypeScript interfaces for Bitbucket API responses. Are they in your helpers/bitbucket.ts? If so, can you share the interface names?"
})
```

### 4. Blocker Report (to lead)

When a teammate is stuck:

```
SendMessage({
  to: "lead",
  summary: "Stage 10 blocked on missing Prisma model",
  message: "Cannot proceed: ManufacturingSession model doesn't exist in schema.prisma yet. This is part of my implementation scope but I need to know if Stage 7 is modifying the schema too — don't want conflicts."
})
```

## Dependency Resolution

### When Teammate A Needs Something From Teammate B

```
1. A sends need_data message to B
2. B acknowledges and prioritizes the dependency
3. B sends data_ready when done
4. A resumes work

TIMEOUT: If B doesn't respond in 15 minutes:
  → A logs the dependency in MEMORY.md
  → A marks that specific task as BLOCKED
  → A continues with other tasks in its stage
  → A does NOT halt entirely for one dependency
```

### When Multiple Teammates Need the Same Resource

```
1. First teammate to claim it in STATUS.md owns it
2. Other teammates wait or work on different tasks
3. Owner notifies others via SendMessage when done
4. Use stage-prefixed sections in shared files to avoid overwrites
```

## Shared File Protocol

STATUS.md and MEMORY.md are shared by all teammates. Prevent corruption:

### STATUS.md Updates

```
1. Read current STATUS.md
2. Find YOUR stage's row
3. Update ONLY your row (don't touch other stages)
4. Write the file
5. If write fails (another agent wrote simultaneously), re-read and retry
```

### MEMORY.md Updates

```
1. ALWAYS append, never overwrite
2. Prefix your section with stage number:
   ## Stage 7: <discovery>
3. Use descriptive headers so other teammates can scan
```

### Heartbeat Files (Separate Per Agent)

To avoid shared-file contention for heartbeats, each agent writes its own file:

```
<spec-path>/heartbeats/stage-<N>.txt

Content:
STAGE: 7
STATUS: working
CURRENT_TASK: Writing fixture design CRUD tests
TESTS_WRITTEN: 5
TESTS_PASSING: 4
LAST_UPDATE: 2026-04-09T02:30:00Z
```

The cron watchdog reads these independently — no contention.

## Anti-Patterns

| Don't | Do Instead |
|-------|------------|
| Broadcast to all teammates for every update | Message lead only; lead relays if needed |
| Wait indefinitely for another teammate | 15-minute timeout, then BLOCKED |
| Overwrite STATUS.md entirely | Update only your stage's row |
| Send structured JSON messages | Use plain text messages (Agent SDK limitation) |
| Assume teammates see your console output | Your text output is NOT visible — use SendMessage |
