import { test, expect } from './fixtures';
import { loginViaAPI } from './helpers/auth';

test.describe('Sidebar Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('shows all primary nav items', async ({ page }) => {
    for (const label of ['Dashboard', 'Products', 'Builds', 'Validation', 'Fixtures', 'Manufacturing']) {
      await expect(page.locator('nav').getByText(label, { exact: true })).toBeVisible();
    }
  });

  test('clicking Products navigates to /products', async ({ page }) => {
    await page.locator('nav').getByText('Products', { exact: true }).click();
    await page.waitForURL('/products');
    await expect(page.getByRole('heading', { name: 'Products' })).toBeVisible();
  });

  test('clicking Builds navigates to /builds', async ({ page }) => {
    await page.locator('nav').getByText('Builds', { exact: true }).click();
    await page.waitForURL('/builds');
  });

  test('clicking Validation navigates to /validation', async ({ page }) => {
    await page.locator('nav').getByText('Validation', { exact: true }).click();
    await page.waitForURL('/validation');
  });

  test('clicking Fixtures navigates to /fixtures', async ({ page }) => {
    await page.locator('nav').getByText('Fixtures', { exact: true }).click();
    await page.waitForURL('/fixtures');
  });

  test('clicking Manufacturing navigates to /manufacturing', async ({ page }) => {
    await page.locator('nav').getByText('Manufacturing', { exact: true }).click();
    await page.waitForURL('/manufacturing');
  });

  test('System section is expandable', async ({ page }) => {
    const systemBtn = page.locator('button').filter({ hasText: 'System' });
    await expect(systemBtn).toBeVisible();
    await systemBtn.click();
    await page.waitForTimeout(300);
  });

  test('Admin section is expandable', async ({ page }) => {
    const adminBtn = page.locator('button').filter({ hasText: 'Admin' });
    await expect(adminBtn).toBeVisible();
    await adminBtn.click();
    await page.waitForTimeout(300);
  });

  test('Settings link exists', async ({ page }) => {
    // Settings may be at the bottom of the sidebar — scroll into view
    const settingsLink = page.getByText('Settings', { exact: true });
    await settingsLink.scrollIntoViewIfNeeded();
    await expect(settingsLink).toBeVisible();
  });

  test('user info shown at bottom', async ({ page }) => {
    await expect(page.getByText('Dev Admin')).toBeVisible();
  });
});
