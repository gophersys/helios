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

# Stage 6: Build Pipeline

**Status:** Pending
**Dependencies:** Stages 4, 5
**Estimated Tests:** ~35

---

## Preconditions

- Product created with all 5 stages configured (from Stages 3-4)
- Bitbucket branch + PR created (from Stage 5)
- Git poller running and monitoring concord-main

---

## Test Files

### `e2e/stories/builds/auto-trigger.spec.ts` (~8 tests)

```
test('git-poller detects PR within 120s of creation')
test('BuildRun created with correct product, branch, commitSha')
test('BuildRun has expected number of BuildJobs (matches build matrix)')
test('BuildRun triggerType is "pr_push"')
test('BuildRun captures PR metadata (prNumber, prTitle, prAuthor, sourceBranch)')
test('builds page shows new build run')
test('build run appears in product detail Builds tab')
test('PR pipeline page shows build run for the PR')
```

### `e2e/stories/builds/monitoring.spec.ts` (~10 tests)

```
test('build run detail page loads with correct metadata')
test('build jobs listed with matrix labels')
test('job status transitions: QUEUED → CLONING visible in UI')
test('job status transitions: CLONING → BUILDING visible in UI')
test('build log streams in real-time (poll or WebSocket)')
test('build progress indicator updates during build')
test('all jobs reach SUCCESS or FAILED within timeout (20 min)')
test('BuildRun status updates to SUCCESS when all jobs pass')
test('build duration recorded correctly')
test('builds page filter by status:SUCCESS shows completed builds')
```

### `e2e/stories/builds/artifacts.spec.ts` (~7 tests)

```
test('completed build has artifacts listed')
test('artifacts include .hex files per target')
test('artifacts include .cfw files per target')
test('artifacts include build.json manifest')
test('artifact download returns valid file (check Content-Disposition)')
test('build run artifacts download returns zip')
test('artifact sizes are non-zero')
```

### `e2e/stories/builds/caching.spec.ts` (~5 tests)

```
test('create second PR from same commit as first PR')
test('wait for git-poller to detect second PR')
test('second BuildRun created with new build jobs')
test('build jobs show CACHED status (same fingerprint as first build)')
test('cached jobs have reusedFromId pointing to original SUCCESS jobs')
```

### `e2e/stories/builds/pr-pipeline.spec.ts` (~5 tests)

```
test('PR pipeline page shows all build runs for the PR')
test('pipeline shows stage badges for each run')
test('pipeline shows build matrix with job statuses')
test('pipeline links to individual build run details')
test('pipeline shows PR metadata (title, author, branch)')
```

### `e2e/stories/builds/failure.spec.ts` (~4 tests)

```
test('build with invalid recipe fails with FAILED status')
test('failed BuildJob shows errorMessage in UI')
test('failed BuildRun status is BUILD_FAILED')
test('failed build does NOT create validation queue entries')
```

### `e2e/stories/builds/settings.spec.ts` (~3 tests)

```
test('/builds/settings page loads')
test('settings shows configured CI repositories')
test('build stage definitions visible')
```

---

## Timing Considerations

- **Git-poller detection:** Up to 120s (60s poll interval + processing)
- **Build execution:** 5-20 min per firmware target (real compilation)
- **Total stage duration:** 30-45 min (mostly waiting for builds)

Tests use `waitForBuildComplete()` with generous timeouts.

---

## Gate Criteria

- [ ] Builds triggered automatically by git-poller
- [ ] Build status transitions visible in UI
- [ ] Build artifacts downloadable and valid
- [ ] Build caching works (CACHED status for duplicate fingerprint)
- [ ] PR pipeline view shows correct build matrix
- [ ] All 35 tests pass
