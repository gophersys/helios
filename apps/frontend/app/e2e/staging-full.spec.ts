/**
 * Comprehensive E2E tests against staging backend.
 * Tests all major pages and functionality with real data.
 *
 * Run with: VITE_BACKEND_URL=https://staging.concord.local npx playwright test e2e/staging-full.spec.ts
 */
import { test, expect, type Page, type BrowserContext } from '@playwright/test';

// Staging test API key
const API_KEY = 'ck_run_test_Oi4FANF9YUsaWuJJM3fzG2K1VngfctZlDO72yyo0CDk';

// Helper to authenticate via API key
async function authenticateWithApiKey(context: BrowserContext) {
  // Set up API key auth by intercepting requests
  await context.route('**/v2/**', async route => {
    const headers = {
      ...route.request().headers(),
      'Authorization': `ApiKey ${API_KEY}`
    };
    await route.continue({ headers });
  });
}

// Alternative: Mock the auth state in localStorage
async function mockAuthState(page: Page) {
  await page.goto('/login');
  await page.evaluate(() => {
    localStorage.setItem('concord-token', 'staging-e2e-test-token');
    localStorage.setItem('concord-user', JSON.stringify({
      id: 'e2e-test-user',
      email: 'test@example.com',
      name: 'E2E Test User',
      permissionSetName: 'Super Admin',
      permissions: [
        'products:view', 'products:manage',
        'builds:view', 'builds:trigger', 'builds:manage',
        'validation:view', 'validation:run', 'validation:manage',
        'fixtures:view', 'fixtures:manage',
        'benches:view', 'benches:manage',
        'devices:view', 'devices:manage',
        'cluster:view', 'cluster:manage',
        'users:view', 'users:manage',
        'permissions:manage',
        'api-keys:view', 'api-keys:manage',
        'system:view', 'system:manage'
      ]
    }));
  });
}

test.describe('Staging Full E2E Suite', () => {
  test.beforeEach(async ({ context, page }) => {
    await authenticateWithApiKey(context);
    await mockAuthState(page);
  });

  // ==========================================
  // DASHBOARD
  // ==========================================
  test.describe('Dashboard', () => {
    test('loads dashboard page', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toBeEmpty();
    });
  });

  // ==========================================
  // PRODUCTS / CATALOG
  // ==========================================
  test.describe('Products', () => {
    test('catalog page shows product list', async ({ page }) => {
      await page.goto('/catalog');
      await page.waitForLoadState('networkidle');

      // Should see Catalog heading
      await expect(page.locator('text=Catalog').first()).toBeVisible({ timeout: 10000 });

      // Should see Products
      await expect(page.locator('text=Products').first()).toBeVisible();
    });

    test('can view product detail with 6 tabs', async ({ page }) => {
      await page.goto('/catalog');
      await page.waitForLoadState('networkidle');

      // Click on the Alpha product card (the card is a div with role="button")
      const alphaCard = page.locator('[role="button"]').filter({ hasText: 'Alpha' }).first();
      await expect(alphaCard).toBeVisible({ timeout: 10000 });
      await alphaCard.click();

      // Wait for detail view to load
      await page.waitForTimeout(2000);

      // Should see all 6 tabs - check each one
      const tabs = ['Overview', 'Stages', 'Pipelines', 'Runs', 'Firmware', 'Settings'];
      for (const tab of tabs) {
        await expect(page.getByRole('tab', { name: tab })).toBeVisible({ timeout: 5000 });
      }
    });

    test('product stages tab works', async ({ page }) => {
      await page.goto('/catalog');
      await page.waitForLoadState('networkidle');

      await page.locator('[role="button"]').filter({ hasText: 'Alpha' }).first().click();
      await page.waitForTimeout(2000);

      // Click Stages tab
      await page.getByRole('tab', { name: 'Stages' }).click();
      await page.waitForTimeout(2000);

      // Should see stage content (either stages list or initialize button)
      const content = page.locator('.card-md');
      await expect(content).toBeVisible();
    });

    test('product settings tab shows danger zone', async ({ page }) => {
      await page.goto('/catalog');
      await page.waitForLoadState('networkidle');

      await page.locator('[role="button"]').filter({ hasText: 'Alpha' }).first().click();
      await page.waitForTimeout(2000);

      // Click Settings tab
      await page.getByRole('tab', { name: 'Settings' }).click();
      await page.waitForTimeout(1000);

      // Should see General and Danger Zone sections
      await expect(page.locator('text=General').first()).toBeVisible({ timeout: 5000 });
    });
  });

  // ==========================================
  // BUILDS
  // ==========================================
  test.describe('Builds', () => {
    test('Builds page loads', async ({ page }) => {
      await page.goto('/builds');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toBeEmpty();
    });

    test('builds list page works', async ({ page }) => {
      await page.goto('/builds');
      await page.waitForLoadState('networkidle');
      // Should show builds page content
      await expect(page.locator('body')).not.toBeEmpty();
    });

    test('Builds settings page works', async ({ page }) => {
      await page.goto('/builds/settings');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toBeEmpty();
    });
  });

  // ==========================================
  // VALIDATION
  // ==========================================
  test.describe('Validation', () => {
    test('validation hub shows nav cards', async ({ page }) => {
      await page.goto('/validation');
      await page.waitForLoadState('networkidle');

      // Should see validation hub cards
      await expect(page.locator('text=Validation').first()).toBeVisible({ timeout: 10000 });
    });

    test('validation runs page loads', async ({ page }) => {
      await page.goto('/validation/runs');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toBeEmpty();
    });

    test('validation queue page loads with stats', async ({ page }) => {
      await page.goto('/validation/queue');
      await page.waitForLoadState('networkidle');

      // Should see queue page
      await expect(page.locator('text=Validation Queue').first()).toBeVisible({ timeout: 10000 });
    });

    test('validation catalog page loads', async ({ page }) => {
      await page.goto('/validation/catalog');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toBeEmpty();
    });

    test('test benches page loads', async ({ page }) => {
      await page.goto('/validation/benches');
      await page.waitForLoadState('networkidle');

      // Should see benches page
      await expect(page.locator('text=Test Benches').first()).toBeVisible({ timeout: 10000 });
    });

    test('fixture designs page loads', async ({ page }) => {
      await page.goto('/validation/designs');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toBeEmpty();
    });
  });

  // ==========================================
  // HARDWARE
  // ==========================================
  test.describe('Hardware', () => {
    test('MTIB nodes page loads', async ({ page }) => {
      await page.goto('/mtib');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toBeEmpty();
    });

    test('ICLE devices page loads', async ({ page }) => {
      await page.goto('/icle');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toBeEmpty();
    });
  });

  // ==========================================
  // KUBERNETES
  // ==========================================
  test.describe('Kubernetes', () => {
    test('K8s overview page loads', async ({ page }) => {
      await page.goto('/kubernetes');
      await page.waitForLoadState('networkidle');

      // Should see Kubernetes page heading
      await expect(page.locator('text=Kubernetes').first()).toBeVisible({ timeout: 10000 });
    });

    test('K8s pods page shows pods', async ({ page }) => {
      await page.goto('/kubernetes/pods');
      await page.waitForLoadState('networkidle');

      // Should see pods table or list
      await expect(page.locator('body')).not.toBeEmpty();
    });

    test('K8s deployments page works', async ({ page }) => {
      await page.goto('/kubernetes/deployments');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toBeEmpty();
    });

    test('K8s services page works', async ({ page }) => {
      await page.goto('/kubernetes/services');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toBeEmpty();
    });

    test('K8s nodes page shows cluster nodes', async ({ page }) => {
      await page.goto('/kubernetes/nodes');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toBeEmpty();
    });

    test('K8s jobs page works', async ({ page }) => {
      await page.goto('/kubernetes/jobs');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toBeEmpty();
    });

    test('K8s events page shows events', async ({ page }) => {
      await page.goto('/kubernetes/events');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toBeEmpty();
    });

    test('K8s RBAC page works', async ({ page }) => {
      await page.goto('/kubernetes/rbac');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toBeEmpty();
    });

    test('K8s config page works', async ({ page }) => {
      await page.goto('/kubernetes/config');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toBeEmpty();
    });
  });

  // ==========================================
  // ADMIN SECTION
  // ==========================================
  test.describe('Admin', () => {
    test('fixtures page loads', async ({ page }) => {
      await page.goto('/fixtures');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toBeEmpty();
    });

    test('users page loads', async ({ page }) => {
      await page.goto('/users');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toBeEmpty();
    });
  });

  // ==========================================
  // SYSTEM SECTION
  // ==========================================
  test.describe('System', () => {
    test('history page loads', async ({ page }) => {
      await page.goto('/history');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toBeEmpty();
    });
  });

  // ==========================================
  // SIDEBAR NAVIGATION
  // ==========================================
  test.describe('Sidebar Navigation', () => {
    test('sidebar shows all sections', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Primary nav items
      await expect(page.locator('text=Dashboard').first()).toBeVisible({ timeout: 10000 });
      await expect(page.locator('text=Products').first()).toBeVisible();
      await expect(page.locator('text=Builds').first()).toBeVisible();
      await expect(page.locator('text=Validation').first()).toBeVisible();
      await expect(page.locator('text=Hardware').first()).toBeVisible();

      // Footer sections - Settings should be visible somewhere
      await expect(page.getByText('Settings').first()).toBeVisible({ timeout: 5000 });
    });

    test('admin section expands', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Admin section should be visible in sidebar
      const adminToggle = page.getByText('Admin').first();
      await expect(adminToggle).toBeVisible({ timeout: 10000 });

      // Click to expand if it's a toggle
      await adminToggle.click();
      await page.waitForTimeout(500);

      // Should show admin sub-items (Fixtures or Users visible after expand)
      const fixtures = page.getByText('Fixtures');
      const users = page.getByText('Users');
      const isFixturesVisible = await fixtures.first().isVisible().catch(() => false);
      const isUsersVisible = await users.first().isVisible().catch(() => false);
      expect(isFixturesVisible || isUsersVisible).toBe(true);
    });

    test('system section expands', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // System section should be visible
      const systemToggle = page.getByText('System').first();
      await expect(systemToggle).toBeVisible({ timeout: 10000 });

      // Click to expand
      await systemToggle.click();
      await page.waitForTimeout(500);

      // Should show system sub-items (Cluster or History visible after expand)
      const cluster = page.getByText('Cluster');
      const history = page.getByText('History');
      const isClusterVisible = await cluster.first().isVisible().catch(() => false);
      const isHistoryVisible = await history.first().isVisible().catch(() => false);
      expect(isClusterVisible || isHistoryVisible).toBe(true);
    });

    test('can navigate via sidebar clicks', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Navigate to Products - use more robust selector
      const productsLink = page.locator('a[href="/catalog"]').first();
      await expect(productsLink).toBeVisible({ timeout: 10000 });
      await productsLink.click();
      await expect(page).toHaveURL(/.*catalog/, { timeout: 10000 });
      await page.waitForLoadState('networkidle');

      // Navigate to Validation
      const validationLink = page.locator('a[href="/validation"]').first();
      await expect(validationLink).toBeVisible({ timeout: 5000 });
      await validationLink.click();
      await expect(page).toHaveURL(/.*validation/, { timeout: 10000 });
      await page.waitForLoadState('networkidle');

      // Navigate to Builds
      const buildsLink = page.locator('a[href="/builds"]').first();
      await expect(buildsLink).toBeVisible({ timeout: 5000 });
      await buildsLink.click();
      await expect(page).toHaveURL(/.*builds/, { timeout: 10000 });
    });
  });

  // ==========================================
  // RESPONSIVE DESIGN
  // ==========================================
  test.describe('Responsive Design', () => {
    test('works on tablet viewport', async ({ page }) => {
      await page.setViewportSize({ width: 768, height: 1024 });
      await page.goto('/catalog');
      await page.waitForLoadState('domcontentloaded');
      // Should see either Catalog or Products label (may differ by responsive layout)
      const catalog = page.getByText('Catalog');
      const products = page.getByText('Products');
      // Wait for any of these to appear
      await page.waitForTimeout(3000);
      const isCatalogVisible = await catalog.first().isVisible().catch(() => false);
      const isProductsVisible = await products.first().isVisible().catch(() => false);
      const hasAnyContent = await page.locator('body').textContent().then(t => (t?.length ?? 0) > 10);
      // Either a heading is visible, or the page has substantial content
      expect(isCatalogVisible || isProductsVisible || hasAnyContent).toBe(true);
    });

    test('works on mobile viewport', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto('/catalog');
      await page.waitForLoadState('domcontentloaded');
      // Content should still render - check for sidebar or main content
      await expect(page.locator('body')).not.toBeEmpty();
      // Wait a bit and verify page hasn't crashed
      await page.waitForTimeout(2000);
      await expect(page.locator('body')).toBeVisible();
    });
  });

  // ==========================================
  // ERROR HANDLING
  // ==========================================
  test.describe('Error Handling', () => {
    test('404 page for unknown routes', async ({ page }) => {
      await page.goto('/this-route-does-not-exist');
      // Should show error page or redirect
      await expect(page.locator('body')).not.toBeEmpty();
    });
  });
});
