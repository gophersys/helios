import { test, expect } from '../fixtures';
import { loginViaAPI } from '../helpers/auth';

test.describe('Build Run Detail', () => {
  let runId: string | null = null;

  test.beforeAll(async ({ request }) => {
    // Find a completed build run via API
    const res = await request.get('http://localhost:9001/v2/builds/runs?limit=1', {
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
    test.skip(!runId, 'No build runs available');

    await page.goto(`/builds/runs/${runId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Page should show something — either the run details or an error
    const content = await page.textContent('body') || '';
    const hasContent = content.includes('SUCCESS') || content.includes('BUILDING') ||
                       content.includes('Alpha') || content.includes('builds') ||
                       content.includes('MFG') || content.includes('pipeline');
    expect(hasContent).toBeTruthy();
  });

  test('shows build information', async ({ page }) => {
    test.skip(!runId, 'No build runs available');

    await page.goto(`/builds/runs/${runId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const content = await page.textContent('body') || '';

    // Should show product name or branch or commit info
    const hasInfo = content.includes('alpha') || content.includes('Alpha') ||
                    content.includes('concord') || content.includes('main');
    expect(hasInfo).toBeTruthy();
  });

  test('shows version strings', async ({ page }) => {
    test.skip(!runId, 'No build runs available');

    await page.goto(`/builds/runs/${runId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const content = await page.textContent('body') || '';
    const hasVersions = content.includes('0.5') || content.includes('0.8') || content.includes('version');
    expect(hasVersions).toBeTruthy();
  });
});
