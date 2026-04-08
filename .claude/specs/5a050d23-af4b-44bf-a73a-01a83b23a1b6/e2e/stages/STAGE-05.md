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

# Stage 5: Bitbucket Integration

**Status:** Pending
**Dependencies:** Stage 1
**Estimated Tests:** ~15

---

## Test Files

### `e2e/stories/bitbucket/sync.spec.ts` (~5 tests)

```
test('fetch main branch HEAD SHA from alpha_fw')
test('fetch concord-main branch HEAD SHA from alpha_fw')
test('sync concord-main to match main HEAD (force update if diverged)')
test('sync concord-main for alpha_mfg_fw repo')
test('verify both repos have concord-main at same SHA as main')
```

### `e2e/stories/bitbucket/branch-pr.spec.ts` (~10 tests)

```
test('create feature branch "e2e/test-{timestamp}" from concord-main')
test('verify branch appears in Bitbucket branch list')
test('open PR: e2e/test-{timestamp} → concord-main with title "E2E Test PR"')
test('verify PR appears in open PR list')
test('PR has correct source and target branches')
test('create second branch "e2e/cache-test-{timestamp}" from same commit')
test('open second PR for cache verification')
test('decline/close PR via API')
test('delete feature branches via API')
test('verify branches no longer appear in list')
```

---

## Bitbucket API Helpers

```typescript
const BB_API = 'https://api.bitbucket.org/2.0';
const WORKSPACE = 'corekinect';

// Branch operations
async function getBranchSHA(repo: string, branch: string): Promise<string>;
async function createBranch(repo: string, name: string, fromBranch: string): Promise<void>;
async function deleteBranch(repo: string, name: string): Promise<void>;
async function forceSyncBranch(repo: string, target: string, source: string): Promise<void>;

// PR operations
async function createPR(repo: string, source: string, target: string, title: string): Promise<{ id: number; url: string }>;
async function declinePR(repo: string, prId: number): Promise<void>;
async function listOpenPRs(repo: string, target?: string): Promise<PR[]>;

// Cleanup
async function cleanupE2EBranches(repo: string): Promise<void>;  // Deletes all branches matching "e2e/*"
async function cleanupE2EPRs(repo: string): Promise<void>;       // Declines all PRs with "E2E" in title
```

---

## Gate Criteria

- [ ] concord-main synced with main in both repos
- [ ] Feature branches created and verified in Bitbucket
- [ ] PRs created with correct source/target
- [ ] PRs can be declined and branches deleted
- [ ] All cleanup operations leave repos in clean state
- [ ] All 15 tests pass
