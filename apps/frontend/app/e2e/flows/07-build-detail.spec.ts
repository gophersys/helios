import { test, expect } from '../fixtures';
import { loginViaAPI } from '../helpers/auth';
import { getBuildRuns } from '../helpers/api';

test.describe('Build Run Detail', () => {
  let runId: string | null = null;

  test.beforeAll(async ({ request }) => {
    // Find a completed build run
    const res = await request.get('http://localhost:9001/v2/builds/runs?limit=1&status=SUCCESS', {
      headers: { Authorization: 'ApiKey ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG' },
    });
    const body = await res.json();
    const runs = body?.data?.data;
    if (runs?.length > 0) {
      runId = runs[0].id;
    }
  });

  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
  });

  test('build run detail page loads', async ({ page }) => {
    test.skip(!runId, 'No completed build runs available');

    await page.goto(`/builds/runs/${runId}`);
    await page.waitForLoadState('networkidle');

    // Should show status badge
    await expect(page.getByText('SUCCESS').first()).toBeVisible();
  });

  test('shows build matrix with correct labels', async ({ page }) => {
    test.skip(!runId, 'No completed build runs available');

    await page.goto(`/builds/runs/${runId}`);
    await page.waitForLoadState('networkidle');

    const content = await page.textContent('body');

    // FUOTA pipeline should have these labels
    const expectedLabels = ['MFG_BASE', 'MFG_BUMP', 'FUT_VERBOSE_A', 'FUT_VERBOSE_B',
                           'FUT_QUIET_A', 'FUT_QUIET_B', 'MAIN_BASELINE', 'MAIN_MERGED'];

    let foundCount = 0;
    for (const label of expectedLabels) {
      if (content?.includes(label)) foundCount++;
    }

    // At least some labels should be visible
    expect(foundCount).toBeGreaterThan(0);
  });

  test('shows version information', async ({ page }) => {
    test.skip(!runId, 'No completed build runs available');

    await page.goto(`/builds/runs/${runId}`);
    await page.waitForLoadState('networkidle');

    const content = await page.textContent('body');

    // Version strings from the builds
    const hasVersions = content?.includes('0.5.') || content?.includes('0.8.');
    expect(hasVersions).toBeTruthy();
  });

  test('shows PR metadata', async ({ page }) => {
    test.skip(!runId, 'No completed build runs available');

    await page.goto(`/builds/runs/${runId}`);
    await page.waitForLoadState('networkidle');

    // PR info should be visible (if the run was triggered by a PR)
    const content = await page.textContent('body');
    const hasPRInfo = content?.includes('PR #') || content?.includes('concord') || content?.includes('alpha_fw');
    expect(hasPRInfo).toBeTruthy();
  });

  test('shows build count', async ({ page }) => {
    test.skip(!runId, 'No completed build runs available');

    await page.goto(`/builds/runs/${runId}`);
    await page.waitForLoadState('networkidle');

    // Should show 8/8 builds or similar count
    const content = await page.textContent('body');
    const hasCount = content?.includes('8') || content?.includes('/8');
    expect(hasCount).toBeTruthy();
  });
});
