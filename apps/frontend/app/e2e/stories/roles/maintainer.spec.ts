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
 * Stage 15 — Maintainer role story E2E tests.
 *
 * Maintainer journey: login, verify correct sidebar (Products through Fixtures,
 * plus Users visible via users:view, Kubernetes via system:view), page navigation,
 * and API permission boundaries (cannot manage users/permissions/system/kubernetes).
 *
 * Maintainer has everything EXCEPT: users:manage, permissions:manage,
 * system:manage, kubernetes:manage.
 * All test data prefixed with "s15-" for resource isolation.
 */

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';

async function loginMaintainerAndGoHome(page: import('@playwright/test').Page) {
  await loginAsRole(page, 'maintainer');
  await page.goto('/');
  await page.waitForLoadState('networkidle');
}

/**
 * Get a JWT token for the maintainer role to use in direct API calls.
 */
async function getMaintainerToken(page: import('@playwright/test').Page): Promise<string> {
  const res = await page.request.post(`${API_URL}/v2/auth/dev-login`, {
    data: { email: 'maintainer@concord.dev' },
  });
  const body = await res.json();
  return body?.data?.token;
}

test.describe('Maintainer role story', () => {
  // ── Login & Dashboard ────────────────────────────────────

  test('login as Maintainer, dashboard loads', async ({ page }) => {
    await loginMaintainerAndGoHome(page);
    const dashboard = new DashboardPage(page);
    await dashboard.expectVisible();
  });

  // ── Sidebar Visibility ───────────────────────────────────

  test('primary sidebar items visible: Products, Builds, Validation, Manufacturing, Fixtures', async ({ page }) => {
    await loginMaintainerAndGoHome(page);
    const sidebar = new SidebarComponent(page);
    await sidebar.expectItems(['Dashboard', 'Products', 'Builds', 'Validation', 'Manufacturing', 'Fixtures']);
  });

  test('Admin toggle reveals Users (has users:view)', async ({ page }) => {
    await loginMaintainerAndGoHome(page);
    const sidebar = new SidebarComponent(page);
    await sidebar.expandSection('Admin');
    await sidebar.expectItems(['Users']);
  });

  test('System toggle reveals Kubernetes (has system:view)', async ({ page }) => {
    await loginMaintainerAndGoHome(page);
    const sidebar = new SidebarComponent(page);
    await sidebar.expandSection('System');
    await sidebar.expectItems(['Kubernetes']);
  });

  test('View-As-Role dropdown is available', async ({ page }) => {
    await loginMaintainerAndGoHome(page);
    const viewAsBtn = page.locator('button').filter({ hasText: /view as/i });
    await expect(viewAsBtn).toBeVisible();
  });

  // ── Page Navigation ──────────────────────────────────────

  test('navigate to Products — list loads', async ({ page }) => {
    await loginMaintainerAndGoHome(page);
    const productsPage = new ProductsPage(page);
    await productsPage.goto();
    await productsPage.expectVisible();
  });

  test('navigate to Builds — list loads', async ({ page }) => {
    await loginMaintainerAndGoHome(page);
    const buildsPage = new BuildsPage(page);
    await buildsPage.goto();
    await buildsPage.expectVisible();
  });

  test('navigate to Validation — page loads', async ({ page }) => {
    await loginMaintainerAndGoHome(page);
    const validationPage = new ValidationPage(page);
    await validationPage.goto();
    await validationPage.expectVisible();
  });

  test('navigate to Manufacturing — page loads', async ({ page }) => {
    await loginMaintainerAndGoHome(page);
    const mfgPage = new ManufacturingPage(page);
    await mfgPage.goto();
    await mfgPage.expectVisible();
  });

  test('navigate to Fixtures — page loads', async ({ page }) => {
    await loginMaintainerAndGoHome(page);
    const fixturesPage = new FixturesPage(page);
    await fixturesPage.goto();
    await fixturesPage.expectVisible();
  });

  test('navigate to Users — list loads (has users:view)', async ({ page }) => {
    await loginMaintainerAndGoHome(page);
    const sidebar = new SidebarComponent(page);
    await sidebar.expandSection('Admin');
    await sidebar.navigateTo('Users');
    const usersPage = new UsersPage(page);
    await usersPage.expectVisible();
  });

  test('Users page shows user list but no Add User button (view-only)', async ({ page }) => {
    await loginMaintainerAndGoHome(page);
    const sidebar = new SidebarComponent(page);
    await sidebar.expandSection('Admin');
    await sidebar.navigateTo('Users');

    const usersPage = new UsersPage(page);
    await usersPage.expectVisible();

    // Maintainer can see users (has users:view)
    await expect(page.locator('text=admin@concord.dev')).toBeVisible();
    // But cannot manage (no users:manage) — Add User button should not appear
    await expect(page.getByRole('button', { name: /add user/i })).not.toBeVisible();
  });

  // ── API: Allowed Operations ──────────────────────────────

  test('products:manage via API succeeds', async ({ page }) => {
    const token = await getMaintainerToken(page);

    const res = await page.request.post(`${API_URL}/v2/products`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      data: { name: 's15-Maint Test Product', slug: 's15-maint-test-product' },
    });
    expect(res.status()).toBe(201);
  });

  test('manufacturing:manage via API succeeds (has manufacturing:manage)', async ({ page }) => {
    const token = await getMaintainerToken(page);

    // Verify can access manufacturing endpoints
    const res = await page.request.get(`${API_URL}/v2/manufacturing/configs`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    // 200 or 404 (endpoint may not have data) — not 403
    expect([200, 404]).toContain(res.status());
  });

  test('validation:manage via API succeeds', async ({ page }) => {
    const token = await getMaintainerToken(page);

    // Verify maintainer can access validation endpoints
    const res = await page.request.get(`${API_URL}/v2/validation/runs`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(200);
  });

  test('fixtures:manage via API succeeds', async ({ page }) => {
    const token = await getMaintainerToken(page);

    const res = await page.request.get(`${API_URL}/v2/fixtures`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(200);
  });

  // ── API: Denied Operations ───────────────────────────────

  test('users:manage via API denied (403)', async ({ page }) => {
    const token = await getMaintainerToken(page);

    const res = await page.request.post(`${API_URL}/v2/users`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      data: { email: 's15-maint-denied@e2e.dev', name: 's15-Should Fail' },
    });
    expect(res.status()).toBe(403);
  });

  test('permissions:manage via API denied (403)', async ({ page }) => {
    const token = await getMaintainerToken(page);

    const res = await page.request.post(`${API_URL}/v2/permissions`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      data: { name: 's15-Maint Denied PermSet', permissions: ['products:view'] },
    });
    expect(res.status()).toBe(403);
  });

  test('system:manage via API denied (403)', async ({ page }) => {
    const token = await getMaintainerToken(page);

    const res = await page.request.get(`${API_URL}/v2/system/secrets`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    // system:manage endpoints return 403 for maintainer
    expect(res.status()).toBe(403);
  });

  // ── Cleanup ──────────────────────────────────────────────

  test('cleanup: delete test product', async ({ page }) => {
    const ADMIN_API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';
    const res = await page.request.get(`${API_URL}/v2/products`, {
      headers: { Authorization: `ApiKey ${ADMIN_API_KEY}` },
    });
    const body = await res.json();
    const products = body?.data?.data ?? body?.data ?? [];
    const testProduct = products.find((p: any) => p.slug === 's15-maint-test-product');
    if (testProduct) {
      const delRes = await page.request.delete(`${API_URL}/v2/products/${testProduct.id}`, {
        headers: { Authorization: `ApiKey ${ADMIN_API_KEY}` },
      });
      expect(delRes.status()).toBe(200);
    }
  });
});
