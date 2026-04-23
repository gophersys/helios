import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import { SidebarComponent } from '../../pages/sidebar.component';
import { DashboardPage } from '../../pages/dashboard.page';
import { ProductsPage } from '../../pages/products.page';
import { BuildsPage } from '../../pages/builds.page';
import { ValidationPage } from '../../pages/validation.page';
import { ManufacturingPage } from '../../pages/manufacturing.page';
import { FixturesPage } from '../../pages/fixtures.page';
import { UsersPage } from '../../pages/users.page';

/**
 * Stage 15 — Admin role story E2E tests.
 *
 * Full Admin journey: login, verify all sidebar items, navigate all pages,
 * View-As-Role impersonation, and API-level permission verification.
 *
 * Admin has ALL permissions — every sidebar item visible, every endpoint accessible.
 * All test data prefixed with "s15-" for resource isolation.
 */

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const ADMIN_API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';

async function loginAdminAndGoHome(page: import('@playwright/test').Page) {
  await loginAsRole(page, 'admin');
  await page.goto('/');
  await page.waitForLoadState('networkidle');
}

test.describe('Admin role story', () => {
  // ── Login & Dashboard ────────────────────────────────────

  test('login as Admin, dashboard loads', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const dashboard = new DashboardPage(page);
    await dashboard.expectVisible();
  });

  // ── Sidebar Visibility ───────────────────────────────────

  test('all primary sidebar items visible', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const sidebar = new SidebarComponent(page);
    await sidebar.expectItems(['Dashboard', 'Products', 'Builds', 'Validation', 'Manufacturing', 'Fixtures']);
  });

  test('System toggle reveals Kubernetes', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const sidebar = new SidebarComponent(page);
    await sidebar.expandSection('System');
    await sidebar.expectItems(['Kubernetes']);
  });

  test('Admin toggle reveals Users', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const sidebar = new SidebarComponent(page);
    await sidebar.expandSection('Admin');
    await sidebar.expectItems(['Users']);
  });

  // ── Page Navigation ──────────────────────────────────────

  test('navigate to Products — list loads', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const productsPage = new ProductsPage(page);
    await productsPage.goto();
    await productsPage.expectVisible();
  });

  test('navigate to Builds — list loads', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const buildsPage = new BuildsPage(page);
    await buildsPage.goto();
    await buildsPage.expectVisible();
  });

  test('navigate to Validation — page loads', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const validationPage = new ValidationPage(page);
    await validationPage.goto();
    await validationPage.expectVisible();
  });

  test('navigate to Manufacturing — page loads', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const mfgPage = new ManufacturingPage(page);
    await mfgPage.goto();
    await mfgPage.expectVisible();
  });

  test('navigate to Fixtures — page loads', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const fixturesPage = new FixturesPage(page);
    await fixturesPage.goto();
    await fixturesPage.expectVisible();
  });

  test('navigate to Users — list loads via Admin toggle', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const sidebar = new SidebarComponent(page);
    await sidebar.expandSection('Admin');
    await sidebar.navigateTo('Users');
    const usersPage = new UsersPage(page);
    await usersPage.expectVisible();
  });

  test('navigate to Kubernetes via System toggle', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const sidebar = new SidebarComponent(page);
    await sidebar.expandSection('System');
    await sidebar.navigateTo('Kubernetes');
    await expect(page).toHaveURL(/kubernetes/);
  });

  // ── View-As-Role ─────────────────────────────────────────

  test('View-As-Role dropdown is available', async ({ page }) => {
    await loginAdminAndGoHome(page);
    // The View As button is inside the sidebar <aside> and shows "View as..." or "Viewing as ..."
    const viewAsBtn = page.locator('aside button').filter({ hasText: /view(?:ing)? as/i });
    await expect(viewAsBtn).toBeVisible({ timeout: 10_000 });
  });

  test('View-As Maintainer — sidebar changes after reload', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const sidebar = new SidebarComponent(page);

    await sidebar.viewAsRole('Maintainer');

    await expect(page.locator('text=Viewing as Maintainer')).toBeVisible({ timeout: 10_000 });

    // Maintainer still has system:view and users:view
    await sidebar.expectItems(['Dashboard', 'Products', 'Builds', 'Validation', 'Manufacturing', 'Fixtures']);
    await sidebar.expandSection('System');
    await sidebar.expectItems(['Kubernetes']);
  });

  test('View-As Developer — hides Kubernetes and Users', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const sidebar = new SidebarComponent(page);

    await sidebar.viewAsRole('Developer');

    await expect(page.locator('text=Viewing as Developer')).toBeVisible({ timeout: 10_000 });
    await sidebar.expectItems(['Dashboard', 'Products', 'Builds', 'Validation', 'Manufacturing', 'Fixtures']);

    const systemBtn = page.locator('aside button').filter({ hasText: 'System' });
    await expect(systemBtn).not.toBeVisible();
    const adminBtn = page.locator('aside button').filter({ hasText: 'Admin' });
    await expect(adminBtn).not.toBeVisible();
  });

  test('View-As Operator — only Dashboard and Manufacturing', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const sidebar = new SidebarComponent(page);

    await sidebar.viewAsRole('Operator');

    await expect(page.locator('text=Viewing as Operator')).toBeVisible({ timeout: 10_000 });
    await sidebar.expectItems(['Dashboard', 'Manufacturing']);
    await sidebar.expectHidden(['Products', 'Builds', 'Validation', 'Fixtures']);
  });

  test('Reset View-As — full Admin access restored', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const sidebar = new SidebarComponent(page);

    // Set to Operator (most restricted)
    await sidebar.viewAsRole('Operator');
    await expect(page.locator('text=Viewing as Operator')).toBeVisible({ timeout: 10_000 });
    await sidebar.expectHidden(['Products', 'Builds', 'Validation', 'Fixtures']);

    // Reset
    await sidebar.viewAsRole(null);

    // Full Admin sidebar should be restored
    await sidebar.expectItems(['Dashboard', 'Products', 'Builds', 'Validation', 'Manufacturing', 'Fixtures']);
    await sidebar.expandSection('System');
    await sidebar.expectItems(['Kubernetes']);
    await sidebar.expandSection('Admin');
    await sidebar.expectItems(['Users']);

    const viewAsValue = await page.evaluate(() =>
      localStorage.getItem('concord-view-as-role')
    );
    expect(viewAsValue).toBeNull();
  });

  // ── API Permission Verification ──────────────────────────

  test('create user via API succeeds (users:manage)', async ({ page }) => {
    await loginAdminAndGoHome(page);

    // Use a unique email to avoid conflicts with soft-deleted users
    const uniqueEmail = `s15-admin-${Date.now()}@e2e.dev`;
    const res = await page.request.post(`${API_URL}/v2/users`, {
      headers: {
        Authorization: `ApiKey ${ADMIN_API_KEY}`,
        'Content-Type': 'application/json',
      },
      data: { email: uniqueEmail, name: 's15-Admin Test User' },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body?.data?.email).toBe(uniqueEmail);

    // Soft-delete the test user (cleanup)
    const userId = body?.data?.id;
    if (userId) {
      await page.request.delete(`${API_URL}/v2/users/${userId}`, {
        headers: { Authorization: `ApiKey ${ADMIN_API_KEY}` },
      });
    }
  });

  test('create product via API succeeds (products:manage)', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const res = await page.request.post(`${API_URL}/v2/products`, {
      headers: {
        Authorization: `ApiKey ${ADMIN_API_KEY}`,
        'Content-Type': 'application/json',
      },
      data: { name: 's15-Admin Test Product', slug: 's15-admin-test-product' },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body?.data?.name).toBe('s15-Admin Test Product');
  });

  test('create permission set via API succeeds (permissions:manage)', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const res = await page.request.post(`${API_URL}/v2/permissions`, {
      headers: {
        Authorization: `ApiKey ${ADMIN_API_KEY}`,
        'Content-Type': 'application/json',
      },
      data: { name: 's15-Admin Test PermSet', permissions: ['products:view'] },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body?.data?.name).toBe('s15-Admin Test PermSet');
  });

  test('create API key via API succeeds (api-keys:manage)', async ({ page }) => {
    await loginAdminAndGoHome(page);
    // API key creation requires JWT auth (ApiKey auth returns 500 for this endpoint)
    const loginRes = await page.request.post(`${API_URL}/v2/auth/dev-login`, {
      data: { email: 'admin@concord.dev' },
    });
    const loginBody = await loginRes.json();
    const adminToken = loginBody?.data?.token;

    const res = await page.request.post(`${API_URL}/v2/api-keys`, {
      headers: {
        Authorization: `Bearer ${adminToken}`,
        'Content-Type': 'application/json',
      },
      data: { name: 's15-Admin Test Key' },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body?.data?.key).toBeTruthy();
    expect(body?.data?.key).toMatch(/^ck_live_/);
  });

  test('admin can access every permission-gated GET endpoint', async ({ page }) => {
    await loginAdminAndGoHome(page);

    const endpoints = [
      '/v2/products',
      '/v2/builds/runs',
      '/v2/sessions',
      '/v2/fixtures',
      '/v2/fixtures/designs',
      '/v2/users',
      '/v2/permissions',
      '/v2/api-keys',
    ];

    for (const endpoint of endpoints) {
      const res = await page.request.get(`${API_URL}${endpoint}`, {
        headers: { Authorization: `ApiKey ${ADMIN_API_KEY}` },
      });
      expect(res.status(), `GET ${endpoint} should be 200`).toBe(200);
    }
  });

  // ── Cleanup ──────────────────────────────────────────────

  test('cleanup: delete test users', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const res = await page.request.get(`${API_URL}/v2/users`, {
      headers: { Authorization: `ApiKey ${ADMIN_API_KEY}` },
    });
    const body = await res.json();
    const users = body?.data?.data ?? body?.data ?? [];
    for (const u of users) {
      if ((u as any).email?.startsWith('s15-')) {
        await page.request.delete(`${API_URL}/v2/users/${(u as any).id}`, {
          headers: { Authorization: `ApiKey ${ADMIN_API_KEY}` },
        });
      }
    }
  });

  test('cleanup: delete test product', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const res = await page.request.get(`${API_URL}/v2/products`, {
      headers: { Authorization: `ApiKey ${ADMIN_API_KEY}` },
    });
    const body = await res.json();
    const products = body?.data?.data ?? body?.data ?? [];
    const testProduct = products.find((p: any) => p.slug === 's15-admin-test-product');
    if (testProduct) {
      const delRes = await page.request.delete(`${API_URL}/v2/products/${testProduct.id}`, {
        headers: { Authorization: `ApiKey ${ADMIN_API_KEY}` },
      });
      expect(delRes.status()).toBe(200);
    }
  });

  test('cleanup: delete test permission set', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const res = await page.request.get(`${API_URL}/v2/permissions`, {
      headers: { Authorization: `ApiKey ${ADMIN_API_KEY}` },
    });
    const body = await res.json();
    const sets = body?.data?.data ?? body?.data ?? [];
    const testSet = sets.find((s: any) => s.name === 's15-Admin Test PermSet');
    if (testSet) {
      const delRes = await page.request.delete(`${API_URL}/v2/permissions/${testSet.id}`, {
        headers: { Authorization: `ApiKey ${ADMIN_API_KEY}` },
      });
      expect(delRes.status()).toBe(200);
    }
  });

  test('cleanup: delete test API key', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const res = await page.request.get(`${API_URL}/v2/api-keys`, {
      headers: { Authorization: `ApiKey ${ADMIN_API_KEY}` },
    });
    const body = await res.json();
    const keys = body?.data?.data ?? body?.data ?? [];
    const testKey = keys.find((k: any) => k.name === 's15-Admin Test Key');
    if (testKey) {
      const delRes = await page.request.delete(`${API_URL}/v2/api-keys/${testKey.id}`, {
        headers: { Authorization: `ApiKey ${ADMIN_API_KEY}` },
      });
      expect(delRes.status()).toBe(200);
    }
  });
});
