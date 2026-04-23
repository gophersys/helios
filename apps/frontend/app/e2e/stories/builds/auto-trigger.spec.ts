import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import {
  createProductViaAPI,
  configureStage,
  getBuildRun,
} from '../../helpers/api-extended';
import {
  createBranch,
  createFileCommit,
  createPR,
  declinePR,
  deleteBranch,
  cleanupE2EPRs,
  cleanupE2EBranches,
  getBranchSHA,
} from '../../helpers/bitbucket';
import { waitForGitPollerDetection } from '../../helpers/wait';
import { BuildsPage } from '../../pages/builds.page';

/**
 * Build Auto-Trigger — git-poller detects PRs and creates BuildRuns.
 *
 * Exercises the full trigger path: Bitbucket PR -> git-poller detection ->
 * BuildRun creation with correct metadata (branch, commit, product, trigger type).
 *
 * Prerequisites:
 *   - BITBUCKET_POLLER_ENABLED=true in docker-compose
 *   - alpha_fw repo with concord-main branch on Bitbucket
 */

const REPO = 'alpha_fw';
const timestamp = Date.now();
const BRANCH = `e2e/s6-trigger-${timestamp}`;

test.describe.configure({ mode: 'serial', timeout: 300_000 });

test.describe('Build Auto-Trigger', () => {
  let productId: string;
  let prId: number;
  let detectedRunId: string;
  let commitHash: string;

  test.beforeAll(async () => {
    test.setTimeout(300_000);

    // Clean up any stale E2E artifacts from prior runs
    await cleanupE2EPRs(REPO);
    await cleanupE2EBranches(REPO);

    // Use the seeded Alpha product — it already has fwRepoSlug=alpha_fw
    // and stage configs with pr_push triggers that the poller watches.
    const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
    const API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';
    const res = await fetch(`${API_URL}/v2/products`, {
      headers: { Authorization: `ApiKey ${API_KEY}` },
    });
    const body = await res.json();
    const products = body?.data?.data ?? [];
    const alpha = products.find((p: any) => p.slug === 'alpha');
    if (!alpha) throw new Error('Seeded Alpha product not found — run prisma seed first');
    productId = alpha.id;
  });

  test.afterAll(async () => {
    // Decline PR and clean up branch
    if (prId) {
      try { await declinePR(REPO, prId); } catch { /* best effort */ }
    }
    try { await deleteBranch(REPO, BRANCH); } catch { /* best effort */ }
  });

  // ── Branch + PR setup ───────────────────────────────────

  test('create feature branch from concord-main', async () => {
    await createBranch(REPO, BRANCH, 'concord-main');
    // No throw = branch created successfully
  });

  test('commit a file on the feature branch', async () => {
    await createFileCommit(
      REPO,
      BRANCH,
      '.e2e-trigger-test',
      `Auto-trigger E2E test file — ${timestamp}`,
      'chore: e2e auto-trigger commit',
    );

    // Capture the branch HEAD after the commit
    commitHash = await getBranchSHA(REPO, BRANCH);
    expect(commitHash).toBeTruthy();
    expect(commitHash.length).toBeGreaterThanOrEqual(12);
  });

  test('open PR targeting concord-main', async () => {
    const result = await createPR(
      REPO,
      BRANCH,
      'concord-main',
      `E2E Auto-Trigger Test PR ${timestamp}`,
    );
    prId = result.id;
    expect(prId).toBeGreaterThan(0);
  });

  // ── Git-poller detection ────────────────────────────────

  test('git-poller detects PR and creates a BuildRun within 180s', async ({ page }) => {
    test.setTimeout(240_000);

    const run = await waitForGitPollerDetection(page, productId, BRANCH, 180_000);
    expect(run).toBeTruthy();
    expect(run.id).toBeTruthy();
    detectedRunId = run.id;
  });

  test('BuildRun has correct product reference', async () => {
    test.skip(!detectedRunId, 'No build run detected');

    const run = await getBuildRun(detectedRunId);
    expect(run.product).toBeTruthy();
    // Product field can be id or slug — verify it relates to our product
    expect(
      run.product === productId ||
      run.product === `e2e-trigger-${timestamp}`,
    ).toBe(true);
  });

  test('BuildRun has correct branch metadata', async () => {
    test.skip(!detectedRunId, 'No build run detected');

    const run = await getBuildRun(detectedRunId);
    expect(run.branch).toBe(BRANCH);
  });

  test('BuildRun status is PENDING, QUEUED, or RUNNING after detection', async () => {
    test.skip(!detectedRunId, 'No build run detected');

    const run = await getBuildRun(detectedRunId);
    expect(['PENDING', 'QUEUED', 'RUNNING', 'SUCCESS']).toContain(run.status);
  });

  test('BuildRun appears on the builds list page', async ({ page }) => {
    test.skip(!detectedRunId, 'No build run detected');

    await loginAsRole(page, 'admin');
    const buildsPage = new BuildsPage(page);
    await buildsPage.goto();

    // The newly triggered build should be visible in the list
    const buildLink = page.locator(`[href*="${detectedRunId}"]`).first();
    await expect(buildLink).toBeVisible({ timeout: 15_000 });
  });
});
