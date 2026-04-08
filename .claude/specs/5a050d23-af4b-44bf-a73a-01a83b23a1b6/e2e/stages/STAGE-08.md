<!-- AGENT RECOVERY PROTOCOL
If you are reading this after context compaction:
1. You are working on this specific stage
2. Read STATUS.md to find your progress within this stage
3. Read MEMORY.md for all decisions and gotchas
4. Read ORCHESTRATOR.md if you need the overall system or recovery steps
5. Continue from where STATUS.md says you left off
6. UPDATE STATUS.md after every significant action
7. Commit your work with descriptive messages (NO AI attribution)
8. When this stage is COMPLETE:
   a. Run the Post-Stage Reconciliation Protocol (see ORCHESTRATOR.md)
   b. Write a ## Reconciliation section at the bottom of THIS file
   c. Do a Global Coherence Check against SPEC.md
   d. Update any downstream stage files if your work changed assumptions
   e. Update STATUS.md and MEMORY.md
   f. THEN exit
-->

# Stage 8: Validation Queue

**Status:** Pending
**Dependencies:** Stages 6, 7
**Estimated Tests:** ~25

---

## Preconditions

- Product with stages configured (from Stages 3-4)
- Builds completed with artifacts (from Stage 6)
- Fixture created and AVAILABLE with assigned node (from Stage 7)

---

## Test Files

### `e2e/stories/validation/queue-creation.spec.ts` (~8 tests)

```
test('completed build auto-creates ValidationQueueEntries (one per enabled stage)')
test('queue entries have correct buildRunId and stage number')
test('queue entries start with status QUEUED')
test('queue entries have default priority of 50')
test('queue page shows pending entries')
test('queue stats show correct counts (queued, assigned, running, completed)')
test('manual queue entry creation via API works')
test('queue entry captures reason field (e.g., "PR #42")')
```

### `e2e/stories/validation/queue-assignment.spec.ts` (~8 tests)

```
test('when no fixture available, entries remain QUEUED')
test('when fixture becomes AVAILABLE, highest-priority entry gets ASSIGNED')
test('assigned entry has fixtureId set')
test('assigned fixture status changes to LOCKED')
test('assigned entry transitions to RUNNING when K8s job starts')
test('running entry has sessionId set')
test('session created with correct product, fixture, buildRun references')
test('after session completes, fixture returns to AVAILABLE and next entry assigned')
```

### `e2e/stories/validation/queue-priority.spec.ts` (~4 tests)

```
test('higher priority entries are assigned before lower priority')
test('same priority entries are assigned in requestedAt order (FIFO)')
test('promote action increases entry priority')
test('cancel action sets entry to CANCELLED (releases any locked fixture)')
```

### `e2e/stories/validation/queue-ui.spec.ts` (~5 tests)

```
test('queue page lists all entries with status badges')
test('queue page shows fixture assignment column')
test('cancel button on queue entry works')
test('promote button on queue entry works')
test('queue page auto-refreshes to show status changes')
```

---

## Key Timing

- **Scheduler poll interval:** 10s
- **Fixture assignment:** Nearly immediate once fixture is AVAILABLE
- **K8s job creation:** 5-30s (pod scheduling)

Tests use `waitForQueueAssignment()` with 60s timeout.

---

## Gate Criteria

- [ ] Queue entries auto-created from completed builds
- [ ] Fixture assignment happens automatically when fixture available
- [ ] Priority ordering respected
- [ ] Cancel and promote operations work
- [ ] Queue UI shows correct real-time status
- [ ] All 25 tests pass
