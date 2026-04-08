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

**Status:** COMPLETE
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

- [x] concord-main synced with main in both repos
- [x] Feature branches created and verified in Bitbucket
- [x] PRs created with correct source/target
- [x] PRs can be declined and branches deleted
- [x] All cleanup operations leave repos in clean state
- [x] All 15 tests pass

---

## Reconciliation

### Files Created
- `apps/frontend/app/e2e/helpers/bitbucket.ts` — Bitbucket Cloud REST API helpers (branches, PRs, cleanup)
- `apps/frontend/app/e2e/stories/bitbucket/01-sync.spec.ts` — 5 tests for concord-main sync
- `apps/frontend/app/e2e/stories/bitbucket/02-branch-pr.spec.ts` — 10 tests for branch/PR lifecycle
- `apps/frontend/app/e2e/global-teardown.ts` — Stub (required by e2e.config.ts from Stage 1)

### Key Implementation Decisions
- **Rate limit handling**: Bitbucket Cloud enforces aggressive rate limits. All API calls use exponential backoff with up to 8 retries (max ~12 min wait). Tests need 300s timeout.
- **Empty PR workaround**: Bitbucket rejects PRs with no changes. Tests create a file commit via the source API (`/src` endpoint) before opening PRs.
- **Content-Type fix**: The decline/delete endpoints reject `Content-Type: application/json` when no body is sent. `bbFetch` now only sets Content-Type when a body is present.
- **File ordering**: Tests prefixed with `01-`/`02-` to ensure sync runs before branch-pr (sync creates `concord-main` which branch-pr depends on).
- **Cleanup scope**: `cleanupE2EPRs` declines PRs matching "E2E", "[Test]", or from `e2e/*` branches to handle debris from any test suite.

### Run Command
```bash
npx playwright test --config=playwright.config.ts --timeout=300000 e2e/stories/bitbucket/
```

### Test Results
All 15 tests passing (3.7 min total due to rate limit backoff).
