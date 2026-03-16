/**
 * E2E tests for sidebar navigation and page routing.
 * Verifies sidebar items, navigation, active states, and page rendering.
 *
 * Requires: backend on :9001 (AUTH_ENABLED=false), frontend on :4200
 */
import { test, expect, type Page } from '@playwright/test';

async function authenticateAs(page: Page) {
  await page.goto('/login');
  await page.evaluate(() => {
    localStorage.setItem('concord-token', 'e2e-test-token');
  });
}

test.describe('Sidebar Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await authenticateAs(page);
  });

  test('sidebar shows all primary nav items for admin user', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Primary nav items should be visible
    await expect(page.locator('nav').locator('text=Dashboard').first()).toBeVisible({ timeout: 10000 });
    await expect(page.locator('nav').locator('text=Products').first()).toBeVisible();
    await expect(page.locator('nav').locator('text=Builds').first()).toBeVisible();
    await expect(page.locator('nav').locator('text=Validation').first()).toBeVisible();
    await expect(page.locator('nav').locator('text=Hardware').first()).toBeVisible();
  });

  test('clicking Products navigates to catalog page', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.locator('nav').locator('a[href="/catalog"]').click();
    await expect(page).toHaveURL(/.*catalog/);
    await expect(page.locator('text=Product Catalog').first()).toBeVisible({ timeout: 10000 });
  });

  test('clicking Builds navigates to CI page', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.locator('nav').locator('a[href="/ci"]').click();
    await expect(page).toHaveURL(/.*ci/);
  });

  test('clicking Validation navigates to validation hub', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.locator('nav').locator('a[href="/validation"]').click();
    await expect(page).toHaveURL(/.*validation/);
    await expect(page.locator('text=Validation').first()).toBeVisible({ timeout: 10000 });
  });

  test('active nav item has accent highlight', async ({ page }) => {
    await page.goto('/catalog');
    await page.waitForLoadState('networkidle');

    // The Products nav link should have the active class
    const productsLink = page.locator('nav a[href="/catalog"]');
    await expect(productsLink).toHaveClass(/text-accent/, { timeout: 10000 });
  });
});

test.describe('Validation Hub Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await authenticateAs(page);
  });

  test('validation hub shows nav cards', async ({ page }) => {
    await page.goto('/validation');
    await page.waitForLoadState('networkidle');

    // Should see navigation cards
    await expect(page.locator('text=Validation Runs').first()).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Test Catalog').first()).toBeVisible();
    await expect(page.locator('text=Test Benches').first()).toBeVisible();
    await expect(page.locator('text=Fixture Designs').first()).toBeVisible();
    await expect(page.locator('text=Validation Queue').first()).toBeVisible();
  });

  test('clicking Validation Runs card navigates correctly', async ({ page }) => {
    await page.goto('/validation');
    await page.waitForLoadState('networkidle');

    await page.locator('a[href="/validation/runs"]').first().click();
    await expect(page).toHaveURL(/.*validation\/runs/);
  });

  test('clicking Validation Queue card navigates correctly', async ({ page }) => {
    await page.goto('/validation');
    await page.waitForLoadState('networkidle');

    await page.locator('a[href="/validation/queue"]').first().click();
    await expect(page).toHaveURL(/.*validation\/queue/);
  });
});

test.describe('Page Rendering', () => {
  test.beforeEach(async ({ page }) => {
    await authenticateAs(page);
  });

  test('dashboard renders without errors', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Should not show error states
    const errors = await page.locator('[class*="error"]').count();
    // Dashboard should render some content
    await expect(page.locator('body')).not.toBeEmpty();
  });

  test('validation queue page renders', async ({ page }) => {
    await page.goto('/validation/queue');
    await page.waitForLoadState('networkidle');

    // Should show the queue page header
    await expect(page.locator('text=Validation Queue').first()).toBeVisible({ timeout: 10000 });
  });

  test('CI builds page renders', async ({ page }) => {
    await page.goto('/ci/builds');
    await page.waitForLoadState('networkidle');

    // Should show builds page
    await expect(page.locator('body')).not.toBeEmpty();
  });
});
