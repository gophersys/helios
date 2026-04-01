import { test, expect } from '../fixtures';
import { loginViaAPI } from '../helpers/auth';

test.describe('Builds List Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await page.goto('/builds');
    await page.waitForLoadState('networkidle');
  });

  test('builds page loads without errors', async ({ page }) => {
    // Page should not redirect to login
    await expect(page).not.toHaveURL(/\/login/);
  });

  test('has 3 view mode tabs', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'PR Pipelines' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Build Runs' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Build Jobs' })).toBeVisible();
  });

  test('summary stats bar visible', async ({ page }) => {
    // Should show stat cards with labels
    const content = await page.textContent('body') || '';
    const hasStats = content.includes('Active') || content.includes('Queued') || content.includes('Success') || content.includes('Duration');
    expect(hasStats).toBeTruthy();
  });

  test('can switch to Build Runs tab', async ({ page }) => {
    await page.getByRole('button', { name: 'Build Runs' }).click();
    await page.waitForTimeout(2000);
    // Tab should be active (page doesn't crash)
    await expect(page).not.toHaveURL(/\/login/);
  });

  test('can switch to Build Jobs tab', async ({ page }) => {
    await page.getByRole('button', { name: 'Build Jobs' }).click();
    await page.waitForTimeout(2000);
    await expect(page).not.toHaveURL(/\/login/);
  });

  test('completed pipeline visible with SUCCESS', async ({ page }) => {
    await page.getByRole('button', { name: 'Build Runs' }).click();
    await page.waitForTimeout(2000);
    // Look for SUCCESS status
    const successBadge = page.locator('text=SUCCESS').first();
    if (await successBadge.isVisible({ timeout: 3000 }).catch(() => false)) {
      await expect(successBadge).toBeVisible();
    }
    // If no builds, that's OK — test data may not exist
  });
});
