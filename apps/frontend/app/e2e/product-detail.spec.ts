/**
 * E2E tests for the Product Detail page with 6-tab layout.
 * Verifies navigation, tab switching, component rendering, and data display.
 *
 * Requires: backend on :9001 (AUTH_ENABLED=false), frontend on :4200
 */
import { test, expect, type Page } from '@playwright/test';

// Auth helper: set a fake token so the frontend calls /v2/auth/me
// With AUTH_ENABLED=false, the backend accepts any token and returns admin user
async function authenticateAs(page: Page) {
  await page.goto('/login');
  await page.evaluate(() => {
    localStorage.setItem('concord-token', 'e2e-test-token');
  });
}

test.describe('Product Detail — 6 Tab Layout', () => {
  let productId: string;
  let productName: string;

  test.beforeAll(async ({ browser }) => {
    // Fetch a real product from the backend to use in tests
    const context = await browser.newContext();
    const page = await context.newPage();
    const res = await page.request.get('http://localhost:9001/v2/products');
    const body = await res.json();
    const products = body.data?.data || [];
    if (products.length > 0) {
      productId = products[0].id;
      productName = products[0].name;
    }
    await context.close();
  });

  test.beforeEach(async ({ page }) => {
    await authenticateAs(page);
  });

  test('catalog page loads and shows products', async ({ page }) => {
    await page.goto('/catalog');
    await page.waitForLoadState('networkidle');

    // Should see the page title
    await expect(page.locator('text=Product Catalog').first()).toBeVisible({ timeout: 10000 });
  });

  test('clicking a product opens detail view with tabs', async ({ page }) => {
    await page.goto('/catalog');
    await page.waitForLoadState('networkidle');

    // Wait for products to load, then click the first one
    const productCard = page.locator(`text=${productName}`).first();
    await expect(productCard).toBeVisible({ timeout: 10000 });
    await productCard.click();

    // Should see the product name in the detail view
    await expect(page.locator('h2').filter({ hasText: productName })).toBeVisible({ timeout: 5000 });

    // Should see all 6 tabs
    await expect(page.getByRole('tab', { name: 'Overview' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Stages' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Pipelines' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Runs' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Firmware' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Settings' })).toBeVisible();
  });

  test('Overview tab is the default active tab', async ({ page }) => {
    await page.goto('/catalog');
    await page.waitForLoadState('networkidle');

    const productCard = page.locator(`text=${productName}`).first();
    await expect(productCard).toBeVisible({ timeout: 10000 });
    await productCard.click();

    // Overview tab should be active by default
    const overviewTab = page.getByRole('tab', { name: 'Overview' });
    await expect(overviewTab).toHaveAttribute('aria-selected', 'true', { timeout: 5000 });
  });

  test('can switch between all tabs', async ({ page }) => {
    await page.goto('/catalog');
    await page.waitForLoadState('networkidle');

    const productCard = page.locator(`text=${productName}`).first();
    await expect(productCard).toBeVisible({ timeout: 10000 });
    await productCard.click();
    await page.waitForLoadState('networkidle');

    // Switch to Stages tab
    await page.getByRole('tab', { name: 'Stages' }).click();
    await expect(page.getByRole('tab', { name: 'Stages' })).toHaveAttribute('aria-selected', 'true');

    // Switch to Pipelines tab
    await page.getByRole('tab', { name: 'Pipelines' }).click();
    await expect(page.getByRole('tab', { name: 'Pipelines' })).toHaveAttribute('aria-selected', 'true');

    // Switch to Runs tab
    await page.getByRole('tab', { name: 'Runs' }).click();
    await expect(page.getByRole('tab', { name: 'Runs' })).toHaveAttribute('aria-selected', 'true');

    // Switch to Firmware tab
    await page.getByRole('tab', { name: 'Firmware' }).click();
    await expect(page.getByRole('tab', { name: 'Firmware' })).toHaveAttribute('aria-selected', 'true');

    // Switch to Settings tab
    await page.getByRole('tab', { name: 'Settings' }).click();
    await expect(page.getByRole('tab', { name: 'Settings' })).toHaveAttribute('aria-selected', 'true');
  });

  test('Stages tab shows stage configuration or initialize button', async ({ page }) => {
    await page.goto('/catalog');
    await page.waitForLoadState('networkidle');

    const productCard = page.locator(`text=${productName}`).first();
    await expect(productCard).toBeVisible({ timeout: 10000 });
    await productCard.click();

    await page.getByRole('tab', { name: 'Stages' }).click();
    await page.waitForLoadState('networkidle');

    // Should see either stage cards or the initialize button
    const hasStages = await page.locator('text=Stage 1').isVisible().catch(() => false);
    const hasInitialize = await page.locator('text=Initialize All 5 Stages').isVisible().catch(() => false);

    expect(hasStages || hasInitialize).toBe(true);
  });

  test('Settings tab shows product info and danger zone', async ({ page }) => {
    await page.goto('/catalog');
    await page.waitForLoadState('networkidle');

    const productCard = page.locator(`text=${productName}`).first();
    await expect(productCard).toBeVisible({ timeout: 10000 });
    await productCard.click();

    await page.getByRole('tab', { name: 'Settings' }).click();
    await page.waitForLoadState('networkidle');

    // Should show the product name in settings
    await expect(page.locator('text=General').first()).toBeVisible({ timeout: 5000 });

    // Should have a danger zone
    await expect(page.locator('text=Danger Zone').first()).toBeVisible();
  });
});
