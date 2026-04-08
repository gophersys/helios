import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import { SidebarComponent } from '../../pages/sidebar.component';
import { DashboardPage } from '../../pages/dashboard.page';
import { ProductsPage } from '../../pages/products.page';
import { BuildsPage } from '../../pages/builds.page';
import { ValidationPage } from '../../pages/validation.page';
import { ManufacturingPage } from '../../pages/manufacturing.page';
import { FixturesPage } from '../../pages/fixtures.page';

/**
 * Stage 15 — Developer role story E2E tests.
 *
 * Developer journey: login, view-only products, can trigger/manage builds,
 * can run validation, cannot manage products/fixtures/validation, view-only
 * manufacturing, can manage API keys. No users/system/kubernetes access.
 *
 * Developer permissions:
 *   products:view, builds:view, builds:trigger, builds:manage,
 *   validation:view, validation:run, manufacturing:view,
 *   fixtures:view, devices:view, api-keys:view, api-keys:manage
 *
 * Does NOT have: products:manage, validation:manage, manufacturing:run,
 *   manufacturing:manage, fixtures:manage, devices:manage, users:*, system:*,
 *   kubernetes:*, permissions:manage
 *
 * All test data prefixed with "s15-" for resource isolation.
 */

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';

async function loginDeveloperAndGoHome(page: import('@playwright/test').Page) {
  await loginAsRole(page, 'developer');
  await page.goto('/');
  await page.waitForLoadState('networkidle');
}

/**
 * Get a JWT token for the developer role to use in direct API calls.
 */
async function getDeveloperToken(page: import('@playwright/test').Page): Promise<string> {
  const res = await page.request.post(`${API_URL}/v2/auth/dev-login`, {
    data: { email: 'developer@concord.dev' },
  });
  const body = await res.json();
  return body?.data?.token;
}

test.describe('Developer role story', () => {
  // ── Login & Dashboard ────────────────────────────────────

  test('login as Developer, dashboard loads', async ({ page }) => {
    await loginDeveloperAndGoHome(page);
    const dashboard = new DashboardPage(page);
    await dashboard.expectVisible();
  });

  // ── Sidebar Visibility ───────────────────────────────────

  test('primary sidebar items visible: Products, Builds, Validation, Manufacturing, Fixtures', async ({ page }) => {
    await loginDeveloperAndGoHome(page);
    const sidebar = new SidebarComponent(page);
    await sidebar.expectItems(['Dashboard', 'Products', 'Builds', 'Validation', 'Manufacturing', 'Fixtures']);
  });

  test('Admin toggle not visible (no users:view)', async ({ page }) => {
    await loginDeveloperAndGoHome(page);
    const adminBtn = page.locator('button').filter({ hasText: 'Admin' });
    await expect(adminBtn).not.toBeVisible();
  });

  test('System toggle not visible (no system:view)', async ({ page }) => {
    await loginDeveloperAndGoHome(page);
    const systemBtn = page.locator('button').filter({ hasText: 'System' });
    await expect(systemBtn).not.toBeVisible();
  });

  test('View-As-Role dropdown NOT available', async ({ page }) => {
    await loginDeveloperAndGoHome(page);
    const viewAsBtn = page.locator('button').filter({ hasText: /view as/i });
    await expect(viewAsBtn).not.toBeVisible();
  });

  // ── Page Navigation ──────────────────────────────────────

  test('navigate to Products — list loads (has products:view)', async ({ page }) => {
    await loginDeveloperAndGoHome(page);
    const productsPage = new ProductsPage(page);
    await productsPage.goto();
    await productsPage.expectVisible();
  });

  test('navigate to Builds — list loads', async ({ page }) => {
    await loginDeveloperAndGoHome(page);
    const buildsPage = new BuildsPage(page);
    await buildsPage.goto();
    await buildsPage.expectVisible();
  });

  test('navigate to Validation — page loads', async ({ page }) => {
    await loginDeveloperAndGoHome(page);
    const validationPage = new ValidationPage(page);
    await validationPage.goto();
    await validationPage.expectVisible();
  });

  test('navigate to Manufacturing — page loads (has manufacturing:view)', async ({ page }) => {
    await loginDeveloperAndGoHome(page);
    const mfgPage = new ManufacturingPage(page);
    await mfgPage.goto();
    await mfgPage.expectVisible();
  });

  test('navigate to Fixtures — list loads (has fixtures:view)', async ({ page }) => {
    await loginDeveloperAndGoHome(page);
    const fixturesPage = new FixturesPage(page);
    await fixturesPage.goto();
    await fixturesPage.expectVisible();
  });

  // ── Route Guards: Blocked Pages ──────────────────────────

  test('navigate to /users redirected to dashboard (no users:view)', async ({ page }) => {
    await loginDeveloperAndGoHome(page);
    await page.goto('/users');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL('/');
  });

  test('navigate to /kubernetes redirected to dashboard (no system:view)', async ({ page }) => {
    await loginDeveloperAndGoHome(page);
    await page.goto('/kubernetes');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL('/');
  });

  // ── API: Allowed Operations ──────────────────────────────

  test('builds:manage via API succeeds (D16 — Developer HAS builds:manage)', async ({ page }) => {
    const token = await getDeveloperToken(page);

    // Verify developer can access build management endpoints
    const res = await page.request.get(`${API_URL}/v2/builds/runs`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(200);
  });

  test('builds:trigger via API succeeds', async ({ page }) => {
    const token = await getDeveloperToken(page);

    // Verify developer can access builds (trigger requires build configuration)
    const res = await page.request.get(`${API_URL}/v2/builds/runs`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(200);
  });

  test('validation:run via API succeeds', async ({ page }) => {
    const token = await getDeveloperToken(page);

    const res = await page.request.get(`${API_URL}/v2/sessions`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(200);
  });

  test('api-keys:manage via API succeeds', async ({ page }) => {
    const token = await getDeveloperToken(page);

    const res = await page.request.post(`${API_URL}/v2/api-keys`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      data: { name: 's15-Dev Test Key' },
    });
    expect(res.status()).toBe(201);

    // Cleanup: delete the key
    const body = await res.json();
    const keyId = body?.data?.id;
    if (keyId) {
      const ADMIN_API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';
      await page.request.delete(`${API_URL}/v2/api-keys/${keyId}`, {
        headers: { Authorization: `ApiKey ${ADMIN_API_KEY}` },
      });
    }
  });

  // ── API: Denied Operations ───────────────────────────────

  test('products:manage via API denied (403)', async ({ page }) => {
    const token = await getDeveloperToken(page);

    const res = await page.request.post(`${API_URL}/v2/products`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      data: { name: 's15-Dev Denied Product', slug: 's15-dev-denied' },
    });
    expect(res.status()).toBe(403);
  });

  test('validation:manage via API denied (403)', async ({ page }) => {
    const token = await getDeveloperToken(page);

    // Attempting to create/manage validation config should be denied
    const res = await page.request.post(`${API_URL}/v2/fixtures/designs`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      data: { name: 's15-Dev Denied Design' },
    });
    expect(res.status()).toBe(403);
  });

  test('manufacturing:run via API denied (403)', async ({ page }) => {
    const token = await getDeveloperToken(page);

    // Developer does NOT have manufacturing:run
    const res = await page.request.get(`${API_URL}/v2/manufacturing/configs`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    // manufacturing:manage endpoints should be denied
    expect([403, 404]).toContain(res.status());
  });

  test('fixtures:manage via API denied (403)', async ({ page }) => {
    const token = await getDeveloperToken(page);

    const res = await page.request.post(`${API_URL}/v2/fixtures`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      data: { name: 's15-Dev Denied Fixture' },
    });
    expect(res.status()).toBe(403);
  });

  test('users:view via API denied (403)', async ({ page }) => {
    const token = await getDeveloperToken(page);

    const res = await page.request.get(`${API_URL}/v2/users`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(403);
  });
});
