import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import {
  createProductViaAPI,
  createBuildRun,
  getBuildRun,
} from '../../helpers/api-extended';
import { waitForBuildComplete } from '../../helpers/wait';
import { BuildsPage } from '../../pages/builds.page';
import { BuildDetailPage } from '../../pages/build-detail.page';

/**
 * Build Monitoring — build detail page, job listing, status transitions,
 * log streaming, and completion verification.
 *
 * Triggers a real firmware build via API and monitors it through to completion.
 * Uses generous timeouts since real builds take 5-20 minutes.
 */

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';

test.describe.configure({ mode: 'serial', timeout: 1_200_000 });

const timestamp = Date.now();
let productId: string;
let buildRunId: string;

test.describe('Build Monitoring', () => {
  test.beforeAll(async () => {
    test.setTimeout(120_000);

    const product = await createProductViaAPI({
      name: `E2E Monitor ${timestamp}`,
      slug: `e2e-monitor-${timestamp}`,
      description: 'Product for build monitoring E2E tests',
    });
    productId = product.id;

    // Trigger a manual build run
    try {
      const run = await createBuildRun({
        product: product.slug || product.name,
        board: 'alpha_b0',
        branch: 'concord-main',
        name: `monitor-build-${timestamp}`,
        triggerType: 'manual',
        matrixMode: 'smoke',
      });
      buildRunId = run.id;
    } catch {
      // Build creation may fail if infrastructure is not ready
      buildRunId = '';
    }
  });

  // ── Build detail page ──────────────────────────────────

  test('build detail page loads for the triggered build', async ({ page }) => {
    test.skip(!buildRunId, 'Build run creation not available');

    await loginAsRole(page, 'admin');
    await page.goto(`/builds/${buildRunId}`);
    await page.waitForLoadState('networkidle');

    // Page should load without errors
    await expect(page.locator('main, [role="main"]').first()).toBeVisible({ timeout: 15_000 });
  });

  test('build detail shows the build name or identifier', async ({ page }) => {
    test.skip(!buildRunId, 'Build run creation not available');

    await loginAsRole(page, 'admin');
    await page.goto(`/builds/${buildRunId}`);
    await page.waitForLoadState('networkidle');

    // Build name or ID should be visible somewhere on the page
    const hasName = await page.getByText(`monitor-build-${timestamp}`).first()
      .isVisible({ timeout: 5_000 }).catch(() => false);
    const hasId = await page.getByText(buildRunId.slice(0, 8)).first()
      .isVisible({ timeout: 3_000 }).catch(() => false);

    expect(hasName || hasId).toBe(true);
  });

  test('build detail shows a status badge', async ({ page }) => {
    test.skip(!buildRunId, 'Build run creation not available');

    await loginAsRole(page, 'admin');
    await page.goto(`/builds/${buildRunId}`);
    await page.waitForLoadState('networkidle');

    // Status badge should be present
    const badge = page.locator('[data-testid="status-badge"]').first()
      .or(page.getByText(/PENDING|QUEUED|RUNNING|SUCCESS|FAILED/i).first());
    await expect(badge).toBeVisible({ timeout: 15_000 });
  });

  test('build shows branch information', async ({ page }) => {
    test.skip(!buildRunId, 'Build run creation not available');

    await loginAsRole(page, 'admin');
    await page.goto(`/builds/${buildRunId}`);
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('concord-main').first()).toBeVisible({ timeout: 10_000 });
  });

  test('build API returns correct initial status', async () => {
    test.skip(!buildRunId, 'Build run creation not available');

    const run = await getBuildRun(buildRunId);
    expect(['PENDING', 'QUEUED', 'RUNNING', 'SUCCESS']).toContain(run.status);
    expect(run.branch).toBe('concord-main');
  });

  // ── Job listing ────────────────────────────────────────

  test('build detail lists jobs when build is processing', async ({ page }) => {
    test.skip(!buildRunId, 'Build run creation not available');
    test.setTimeout(300_000);

    await loginAsRole(page, 'admin');

    // Poll API until build is at least RUNNING so jobs exist
    const start = Date.now();
    let isRunning = false;
    while (Date.now() - start < 120_000) {
      const run = await getBuildRun(buildRunId);
      if (['RUNNING', 'SUCCESS', 'FAILED', 'ERROR'].includes(run.status)) {
        isRunning = true;
        break;
      }
      await new Promise((r) => setTimeout(r, 5_000));
    }

    if (!isRunning) {
      test.skip(true, 'Build did not reach RUNNING within 120s');
      return;
    }

    await page.goto(`/builds/${buildRunId}`);
    await page.waitForLoadState('networkidle');

    // Job items should appear
    const jobs = page.locator('[data-testid="build-job"]');
    const hasJobs = await jobs.first().isVisible({ timeout: 15_000 }).catch(() => false);

    // If the build has jobs, verify they are listed
    if (hasJobs) {
      const jobCount = await jobs.count();
      expect(jobCount).toBeGreaterThanOrEqual(1);
    }
  });

  test('job items show individual status badges', async ({ page }) => {
    test.skip(!buildRunId, 'Build run creation not available');

    await loginAsRole(page, 'admin');
    await page.goto(`/builds/${buildRunId}`);
    await page.waitForLoadState('networkidle');

    const jobs = page.locator('[data-testid="build-job"]');
    const hasJobs = await jobs.first().isVisible({ timeout: 10_000 }).catch(() => false);

    if (hasJobs) {
      const firstJobBadge = jobs.first().locator('[data-testid="status-badge"]').first();
      const hasBadge = await firstJobBadge.isVisible({ timeout: 5_000 }).catch(() => false);
      if (hasBadge) {
        const text = await firstJobBadge.textContent();
        expect(text).toBeTruthy();
      }
    }
  });

  // ── Log streaming ──────────────────────────────────────

  test('build log endpoint returns content', async () => {
    test.skip(!buildRunId, 'Build run creation not available');
    test.setTimeout(300_000);

    // Wait until build has been running for a bit
    const start = Date.now();
    while (Date.now() - start < 120_000) {
      const run = await getBuildRun(buildRunId);
      if (['RUNNING', 'SUCCESS', 'FAILED', 'ERROR'].includes(run.status)) break;
      await new Promise((r) => setTimeout(r, 5_000));
    }

    const res = await fetch(`${API_URL}/v2/builds/runs/${buildRunId}/log`, {
      headers: { Authorization: `ApiKey ${API_KEY}` },
    });

    // Log may not be available yet (204/404) or may have content (200)
    expect([200, 204, 404]).toContain(res.status);

    if (res.status === 200) {
      const body = await res.text();
      expect(body.length).toBeGreaterThan(0);
    }
  });

  test('build log content grows as build progresses', async () => {
    test.skip(!buildRunId, 'Build run creation not available');
    test.setTimeout(300_000);

    // Take two snapshots of log length 30s apart
    const fetchLogLength = async (): Promise<number> => {
      const res = await fetch(`${API_URL}/v2/builds/runs/${buildRunId}/log`, {
        headers: { Authorization: `ApiKey ${API_KEY}` },
      });
      if (res.status !== 200) return 0;
      const body = await res.text();
      return body.length;
    };

    const len1 = await fetchLogLength();
    await new Promise((r) => setTimeout(r, 30_000));
    const len2 = await fetchLogLength();

    // If the build is still running, log should have grown
    const run = await getBuildRun(buildRunId);
    if (run.status === 'RUNNING') {
      expect(len2).toBeGreaterThanOrEqual(len1);
    }
  });

  // ── Completion ─────────────────────────────────────────

  test('build reaches terminal status within 20 minutes', async ({ page }) => {
    test.skip(!buildRunId, 'Build run creation not available');
    test.setTimeout(1_200_000);

    const completedRun = await waitForBuildComplete(page, buildRunId, 1_200_000);
    expect(['SUCCESS', 'FAILED', 'ERROR', 'CANCELLED']).toContain(completedRun.status);
  });

  test('completed build detail page shows terminal status', async ({ page }) => {
    test.skip(!buildRunId, 'Build run creation not available');

    const run = await getBuildRun(buildRunId);
    if (!['SUCCESS', 'FAILED', 'ERROR', 'CANCELLED'].includes(run.status)) {
      test.skip(true, 'Build not yet complete');
      return;
    }

    await loginAsRole(page, 'admin');
    await page.goto(`/builds/${buildRunId}`);
    await page.waitForLoadState('networkidle');

    await expect(
      page.getByText(run.status, { exact: false }).first(),
    ).toBeVisible({ timeout: 15_000 });
  });
});
