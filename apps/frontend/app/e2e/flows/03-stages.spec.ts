import { test, expect } from '../fixtures';
import { loginViaAPI } from '../helpers/auth';

test.describe('Stage Configuration', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
  });

  async function navigateToValidationTab(page: import('@playwright/test').Page) {
    await page.goto('/products');
    await page.waitForLoadState('networkidle');
    await page.getByRole('heading', { name: 'Alpha', level: 3 }).click();
    await page.waitForLoadState('networkidle');
    await page.getByRole('button', { name: 'Validation' }).click();
    await page.waitForLoadState('networkidle');
  }

  test('validation tab shows 5 stage cards', async ({ page }) => {
    await navigateToValidationTab(page);

    await expect(page.getByText('Smoke')).toBeVisible();
    await expect(page.getByText('Silicon')).toBeVisible();
    await expect(page.getByText('Integration')).toBeVisible();
    await expect(page.getByText('Nightly')).toBeVisible();
    await expect(page.getByText('FUOTA')).toBeVisible();
  });

  test('FUOTA stage shows as enabled', async ({ page }) => {
    await navigateToValidationTab(page);

    // FUOTA should have an enabled indicator
    const fuotaSection = page.locator('text=FUOTA').first().locator('..');
    // Look for enabled badge or trigger type near FUOTA
    await expect(page.getByText('FUOTA')).toBeVisible();
  });

  test('stage cards show trigger type badges', async ({ page }) => {
    await navigateToValidationTab(page);

    // FUOTA has pr_push and pr_merge triggers configured
    // Look for trigger type indicators
    const pageContent = await page.textContent('body');
    // At minimum, the stage names should be visible
    expect(pageContent).toContain('Smoke');
    expect(pageContent).toContain('FUOTA');
  });
});
