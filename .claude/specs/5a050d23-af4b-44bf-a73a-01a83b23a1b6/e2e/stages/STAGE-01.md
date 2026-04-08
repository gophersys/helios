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

# Stage 1: Foundation

**Status:** Pending
**Dependencies:** None
**Estimated Tests:** 0 (infrastructure only)

---

## Objective

Build the Playwright infrastructure layer that all E2E tests depend on: page objects, API helpers, Bitbucket/CoreCloud/MTIB helper libraries, test data factories, and the global setup/teardown lifecycle.

---

## Deliverables

### 1.1 Playwright Configuration

**File:** `apps/frontend/app/e2e.config.ts` (separate from existing `playwright.config.ts`)

```typescript
// Separate config for full E2E suite (vs existing unit-level E2E)
export default defineConfig({
  testDir: './e2e/stories',
  fullyParallel: false,        // Sequential — tests are cumulative
  workers: 1,                   // Single worker — shared state
  retries: 0,                   // No retries — real hardware is stateful
  timeout: 600_000,             // 10 min per test (real builds take time)
  expect: { timeout: 30_000 },  // 30s for assertions (API polling)
  use: {
    baseURL: 'http://localhost:4200',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  globalSetup: './e2e/global-setup.ts',
  globalTeardown: './e2e/global-teardown.ts',
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
```

### 1.2 Global Setup

**File:** `apps/frontend/app/e2e/global-setup.ts`

Responsibilities:
- Verify dev docker-compose stack is running (http-api on :9001, postgres on :5433, minio on :8675)
- If not running: `nx start platform` (or error — don't auto-start, user should have started it)
- Wipe database: `npx prisma migrate reset --force` (destructive! fresh start every time)
- Re-run migrations: `npx prisma migrate deploy`
- Run platform seed ONLY (roles, permission sets, dev users — NOT product data)
- Wait for API health check (`GET /v2/docs` returns 200)
- Verify external connectivity:
  - Bitbucket API: `GET https://api.bitbucket.org/2.0/` (any response = OK)
  - CoreCloud: TLS handshake to auth.office.corekinect.cloud:2013
  - K8s: `kubectl cluster-info` (needed for MTIB deployment only)
  - MTIB node: `kubectl get node verdin-imx8mm-15005665` (Ready?)
- Store base URLs and credentials in environment

**CRITICAL:** Dev is docker-compose for ALL backend services. The ONLY K8s interaction is MTIB server deployment on edge nodes (done in Stage 7, not here).

### 1.3 Global Teardown

**File:** `apps/frontend/app/e2e/global-teardown.ts`

Responsibilities:
- Clean up Bitbucket branches/PRs created during tests
- Clean up CoreCloud device state
- Clean up MinIO test artifacts
- Verify database is clean (only system defaults remain)
- Stop docker-compose test stack (optional — may leave running for debugging)

### 1.4 Page Object Base Class

**File:** `apps/frontend/app/e2e/pages/base.page.ts`

```typescript
export abstract class BasePage {
  constructor(protected page: Page) {}

  // Common navigation
  async goto(): Promise<void>;
  async waitForLoad(): Promise<void>;

  // Common assertions
  async expectVisible(): Promise<void>;
  async expectPageTitle(title: string): Promise<void>;

  // Sidebar interaction
  async sidebar(): Promise<SidebarComponent>;
}
```

### 1.5 Page Objects

| Page Object | File | Key Methods |
|-------------|------|-------------|
| `LoginPage` | `pages/login.page.ts` | `loginAsRole(role)`, `loginWithCredentials(email, pass)`, `expectRoleButtons()` |
| `DashboardPage` | `pages/dashboard.page.ts` | `expectFixtureCards(count)`, `toggleMode(mode)`, `getFixtureCard(name)` |
| `SidebarComponent` | `pages/sidebar.component.ts` | `expectItems(items[])`, `navigateTo(item)`, `expectHidden(items[])`, `viewAsRole(role)` |
| `ProductsPage` | `pages/products.page.ts` | `expectProductList(count)`, `searchProduct(name)`, `openCreateWizard()`, `deleteProduct(name)` |
| `ProductDetailPage` | `pages/product-detail.page.ts` | `switchTab(tab)`, `expectTab(tab)`, `editField(field, value)`, `saveEdits()` |
| `ProductWizardComponent` | `pages/product-wizard.component.ts` | `selectBranch(name)`, `selectBoard(family)`, `configureRevision(config)`, `confirm()` |
| `StageConfigWizard` | `pages/stage-config-wizard.component.ts` | `selectRevision(rev)`, `setWatchBranch(br)`, `setTriggerTypes(types[])`, `editRecipe(yaml)`, `save()` |
| `BuildsPage` | `pages/builds.page.ts` | `expectBuildList(count)`, `filterByStatus(s)`, `filterByStage(s)`, `openBuild(id)` |
| `BuildDetailPage` | `pages/build-detail.page.ts` | `expectStatus(s)`, `expectJobs(count)`, `downloadArtifacts()`, `getJobStatus(label)` |
| `ValidationPage` | `pages/validation.page.ts` | `expectRunList(count)`, `filterByStatus(s)`, `filterByStage(s)`, `openRun(id)` |
| `ValidationRunPage` | `pages/validation-run.page.ts` | `expectStatus(s)`, `expectTestCount(n)`, `waitForCompletion(timeout)`, `getTestResult(name)` |
| `QueuePage` | `pages/queue.page.ts` | `expectEntries(count)`, `expectStatus(id, s)`, `cancelEntry(id)`, `promoteEntry(id)` |
| `FixturesPage` | `pages/fixtures.page.ts` | `switchTab(tab)`, `createDesign(config)`, `createFixture(config)`, `deleteFixture(name)` |
| `FixtureDetailComponent` | `pages/fixture-detail.component.ts` | `expectSlots(count)`, `assignNode(slotIdx, nodeId)`, `expectStatus(s)` |
| `ManufacturingPage` | `pages/manufacturing.page.ts` | `expectRunList(count)`, `triggerSession(config)` |
| `UsersPage` | `pages/users.page.ts` | `switchTab(tab)`, `createUser(config)`, `editUser(email, changes)`, `deactivateUser(email)` |
| `PermissionSetsTab` | `pages/permission-sets.component.ts` | `createSet(config)`, `editSet(name, changes)`, `deleteSet(name)` |

### 1.6 API Helpers (Extended)

**File:** `apps/frontend/app/e2e/helpers/api.ts` (extend existing)

New helpers needed:
```typescript
// Bitbucket
async function syncConcordMain(workspace: string, repo: string): Promise<void>;
async function createBranch(workspace: string, repo: string, name: string, from: string): Promise<void>;
async function deleteBranch(workspace: string, repo: string, name: string): Promise<void>;
async function createPR(workspace: string, repo: string, source: string, target: string, title: string): Promise<number>;
async function declinePR(workspace: string, repo: string, prId: number): Promise<void>;
async function listPRs(workspace: string, repo: string): Promise<PR[]>;

// CoreCloud
async function cleanupCorecloudDevice(deviceId: string): Promise<void>;

// MTIB
async function checkMtibHealth(host: string, port: number): Promise<boolean>;

// Products (extend existing)
async function createProductViaAPI(config: ProductConfig): Promise<Product>;
async function configureStage(productId: string, stage: number, config: StageConfig): Promise<void>;

// Fixtures
async function createFixtureDesign(config: DesignConfig): Promise<FixtureDesign>;
async function createFixture(config: FixtureConfig): Promise<Fixture>;
async function assignNodeToSlot(fixtureId: string, slotId: string, nodeId: string): Promise<void>;
async function createNode(config: NodeConfig): Promise<Node>;

// Users
async function createUserViaAPI(config: UserConfig): Promise<User>;
async function deleteUserViaAPI(userId: string): Promise<void>;

// Queue
async function getQueueEntries(filters?: QueueFilters): Promise<QueueEntry[]>;
async function waitForQueueStatus(entryId: string, status: string, timeout: number): Promise<void>;

// Sessions
async function waitForSessionComplete(sessionId: string, timeout: number): Promise<Session>;

// Cleanup
async function resetDatabase(): Promise<void>;
async function cleanupBitbucketBranches(prefix: string): Promise<void>;
async function cleanupMinioArtifacts(prefix: string): Promise<void>;
```

### 1.7 Test Data Factories

**File:** `apps/frontend/app/e2e/helpers/factories.ts`

```typescript
// Generates consistent test data with unique names (timestamp-suffixed)
export function productConfig(overrides?: Partial<ProductConfig>): ProductConfig;
export function fixtureDesignConfig(boardRevisionId: string, overrides?: Partial<DesignConfig>): DesignConfig;
export function fixtureConfig(productId: string, type: 'MANUFACTURING' | 'VALIDATION', overrides?: Partial<FixtureConfig>): FixtureConfig;
export function nodeConfig(type: 'MANUFACTURING' | 'VALIDATION', overrides?: Partial<NodeConfig>): NodeConfig;
export function userConfig(role: Role, overrides?: Partial<UserConfig>): UserConfig;
```

### 1.8 Auth Helpers (Extended)

**File:** `apps/frontend/app/e2e/helpers/auth.ts` (extend existing)

```typescript
// Login as specific dev role (uses dev-login endpoint, no seed needed)
async function loginAsRole(page: Page, role: 'admin' | 'maintainer' | 'developer' | 'operator'): Promise<void>;

// Login via UI role button (tests the actual UI flow)
async function loginAsRoleViaUI(page: Page, role: 'admin' | 'maintainer' | 'developer' | 'operator'): Promise<void>;
```

### 1.9 WebSocket Helpers

**File:** `apps/frontend/app/e2e/helpers/websocket.ts`

```typescript
// Subscribe to validation run events and collect them
async function subscribeToRun(page: Page, runId: string): Promise<RunEventCollector>;

interface RunEventCollector {
  testStarts: TestStartEvent[];
  testResults: TestResultEvent[];
  runFinished: RunFinishEvent | null;
  waitForTestResult(testName: string, timeout: number): Promise<TestResultEvent>;
  waitForRunFinish(timeout: number): Promise<RunFinishEvent>;
  dispose(): void;
}
```

### 1.10 Wait Helpers

**File:** `apps/frontend/app/e2e/helpers/wait.ts`

```typescript
// Poll API until condition met (for async operations like builds, validation)
async function waitFor<T>(
  fetchFn: () => Promise<T>,
  condition: (result: T) => boolean,
  options: { timeout: number; interval: number; message: string }
): Promise<T>;

// Specific waiters
async function waitForBuildComplete(page: Page, buildRunId: string, timeout?: number): Promise<BuildRun>;
async function waitForValidationComplete(page: Page, sessionId: string, timeout?: number): Promise<Session>;
async function waitForQueueAssignment(page: Page, entryId: string, timeout?: number): Promise<QueueEntry>;
async function waitForGitPollerDetection(page: Page, productId: string, branch: string, timeout?: number): Promise<BuildRun>;
```

---

## Gate Criteria

- [ ] Playwright config loads without error
- [ ] Global setup starts docker-compose stack and verifies API health
- [ ] All page objects compile (TypeScript check)
- [ ] API helpers can create/delete a product via API
- [ ] Bitbucket helpers can list branches in alpha_fw
- [ ] Auth helpers can login as each of the 4 roles
- [ ] Factory functions generate valid, unique test data
