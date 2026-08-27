import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';

/**
 * Route guard tests.
 *
 * Two categories:
 * 1. Unauthenticated: root layout redirects to /login
 * 2. Insufficient permissions: page-level onMount redirects to / (dashboard)
 *
 * Routes and their required permissions:
 *   /products       → products:view
 *   /builds         → builds:view
 *   /validation     → validation:view
 *   /fixtures       → fixtures:view
 *   /kubernetes     → system:view
 *   /users          → users:view
 *   /manufacturing  → manufacturing:view (all roles have this)
 */

test.describe('Route guards — unauthenticated', () => {
  test('unauthenticated user redirected from /products to /login', async ({ page }) => {
    await page.goto('/products');
    await expect(page).toHaveURL('/login');
  });

  test('unauthenticated user redirected from /builds to /login', async ({ page }) => {
    await page.goto('/builds');
    await expect(page).toHaveURL('/login');
  });
});

test.describe('Route guards — Operator (restricted role)', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsRole(page, 'operator');
  });

  test('Operator navigating to /products gets redirected to dashboard', async ({ page }) => {
    await page.goto('/products');
    await page.waitForLoadState('networkidle');
    // Page-level guard redirects to / (dashboard)
    await expect(page).toHaveURL('/');
  });

  test('Operator navigating to /builds gets redirected to dashboard', async ({ page }) => {
    await page.goto('/builds');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL('/');
  });

  test('Operator navigating to /validation gets redirected to dashboard', async ({ page }) => {
    await page.goto('/validation');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL('/');
  });

  test('Operator navigating to /fixtures gets redirected to dashboard', async ({ page }) => {
    await page.goto('/fixtures');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL('/');
  });

  test('Operator navigating to /users gets redirected to dashboard', async ({ page }) => {
    await page.goto('/users');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL('/');
  });
});

test.describe('Route guards — Developer (no system/users access)', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsRole(page, 'developer');
  });

  test('Developer navigating to /users gets redirected to dashboard', async ({ page }) => {
    await page.goto('/users');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL('/');
  });

  test('Developer navigating to /kubernetes gets redirected to dashboard', async ({ page }) => {
    await page.goto('/kubernetes');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL('/');
  });
});

test.describe('Route guards — all roles can access /manufacturing', () => {
  for (const role of ['admin', 'maintainer', 'developer', 'operator'] as const) {
    test(`${role} can access /manufacturing`, async ({ page }) => {
      await loginAsRole(page, role);
      await page.goto('/manufacturing');
      await page.waitForLoadState('networkidle');
      // Should stay on manufacturing, not get redirected
      await expect(page).toHaveURL('/manufacturing');
    });
  }
});
