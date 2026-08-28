import { test, expect } from './fixtures';
import { loginViaAPI } from './helpers/auth';

test.describe('Builds Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await page.goto('/builds');
    await page.waitForLoadState('networkidle');
  });

  test('page loads with builds heading', async ({ page }) => {
    await expect(page.getByText('Builds').first()).toBeVisible();
  });

  test('shows PR Pipelines tab', async ({ page }) => {
    await expect(page.locator('button').filter({ hasText: 'PR Pipelines' })).toBeVisible();
  });

  test('shows Build Runs tab', async ({ page }) => {
    await expect(page.locator('button').filter({ hasText: 'Build Runs' })).toBeVisible();
  });

  test('can switch between tabs', async ({ page }) => {
    await page.locator('button').filter({ hasText: 'Build Runs' }).click();
    await page.waitForTimeout(300);
    await page.locator('button').filter({ hasText: 'PR Pipelines' }).click();
    await page.waitForTimeout(300);
  });

  test('filter bar is visible', async ({ page }) => {
    // Filter bar container should be visible
    const filterBar = page.locator('.rounded-lg.border.bg-surface-1');
    await expect(filterBar.first()).toBeVisible();
  });

  test('empty state when no data', async ({ page }) => {
    // With an empty DB, should show some form of empty state or empty list
    // (either EmptyState component or just an empty list container)
    const hasEmptyState = await page.getByText(/no.*pipeline|no.*build|no.*result/i).isVisible().catch(() => false);
    const hasListContainer = await page.locator('.rounded-xl.border').isVisible().catch(() => false);
    expect(hasEmptyState || hasListContainer).toBe(true);
  });

  test('direct URL /builds loads correctly', async ({ page }) => {
    await page.goto('/builds');
    await page.waitForLoadState('networkidle');
    // Should not show an error page
    await expect(page.getByText('Something went wrong')).not.toBeVisible();
  });
});

test.describe('Build Run Detail', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
  });

  test('navigating to nonexistent run shows error', async ({ page }) => {
    await page.goto('/builds/runs/nonexistent-id');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    // Should show error or "not found" - not crash
    const hasError = await page.getByText(/not found|error|failed/i).isVisible().catch(() => false);
    const noContent = await page.locator('h2').count() === 0;
    expect(hasError || noContent).toBe(true);
  });
});
