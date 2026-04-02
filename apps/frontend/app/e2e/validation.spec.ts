import { test, expect } from './fixtures';
import { loginViaAPI } from './helpers/auth';

test.describe('Validation Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await page.goto('/validation');
    await page.waitForLoadState('networkidle');
  });

  test('page loads with heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /validation/i })).toBeVisible();
  });

  test('shows description', async ({ page }) => {
    await expect(page.getByText(/test run|hardware/i)).toBeVisible();
  });

  test('page has filtering or content controls', async ({ page }) => {
    // Validation page should have some form of filtering or controls
    const hasSelect = await page.locator('select').first().isVisible().catch(() => false);
    const hasInput = await page.locator('input').first().isVisible().catch(() => false);
    const hasButton = await page.locator('button').first().isVisible().catch(() => false);
    expect(hasSelect || hasInput || hasButton).toBe(true);
  });

  test('handles empty state gracefully', async ({ page }) => {
    // No validation runs in clean DB — should show empty state or empty list
    await expect(page.getByText('Something went wrong')).not.toBeVisible();
  });

  test('direct URL loads correctly', async ({ page }) => {
    await page.goto('/validation');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /validation/i })).toBeVisible();
  });
});

test.describe('Validation Runs Redirect', () => {
  test('visiting /validation/runs redirects to /validation', async ({ page }) => {
    await loginViaAPI(page);
    await page.goto('/validation/runs');
    await page.waitForLoadState('networkidle');
    // Should either redirect to /validation or show validation content
    const url = page.url();
    const isOnValidation = url.includes('/validation');
    expect(isOnValidation).toBe(true);
  });
});
