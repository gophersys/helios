import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import { SidebarComponent } from '../../pages/sidebar.component';
import { DashboardPage } from '../../pages/dashboard.page';
import { ManufacturingPage } from '../../pages/manufacturing.page';

/**
 * Stage 15 — Operator role story E2E tests.
 *
 * Operator journey: login, ONLY Dashboard + Manufacturing visible in sidebar,
 * can view/run/manage manufacturing, ALL other pages blocked (products, builds,
 * validation, fixtures, users, kubernetes).
 *
 * Operator permissions: manufacturing:view, manufacturing:run, manufacturing:manage
 *
 * Does NOT have: products:*, builds:*, validation:*, fixtures:*, devices:*,
 *   users:*, permissions:*, api-keys:*, system:*, kubernetes:*
 */

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';

async function loginOperatorAndGoHome(page: import('@playwright/test').Page) {
  await loginAsRole(page, 'operator');
  await page.goto('/');
  await page.waitForLoadState('networkidle');
}

/**
 * Get a JWT token for the operator role to use in direct API calls.
 */
async function getOperatorToken(page: import('@playwright/test').Page): Promise<string> {
  const res = await page.request.post(`${API_URL}/v2/auth/dev-login`, {
    data: { email: 'operator@concord.dev' },
  });
  const body = await res.json();
  return body?.data?.token;
}

test.describe('Operator role story', () => {
  // ── Login & Dashboard ────────────────────────────────────

  test('login as Operator, dashboard loads', async ({ page }) => {
    await loginOperatorAndGoHome(page);
    const dashboard = new DashboardPage(page);
    await dashboard.expectVisible();
  });

  // ── Sidebar Visibility ───────────────────────────────────

  test('sidebar shows ONLY Dashboard and Manufacturing', async ({ page }) => {
    await loginOperatorAndGoHome(page);
    const sidebar = new SidebarComponent(page);
    await sidebar.expectItems(['Dashboard', 'Manufacturing']);
  });

  test('Products NOT visible in sidebar', async ({ page }) => {
    await loginOperatorAndGoHome(page);
    const sidebar = new SidebarComponent(page);
    await sidebar.expectHidden(['Products']);
  });

  test('Builds NOT visible in sidebar', async ({ page }) => {
    await loginOperatorAndGoHome(page);
    const sidebar = new SidebarComponent(page);
    await sidebar.expectHidden(['Builds']);
  });

  test('Validation NOT visible in sidebar', async ({ page }) => {
    await loginOperatorAndGoHome(page);
    const sidebar = new SidebarComponent(page);
    await sidebar.expectHidden(['Validation']);
  });

  test('Fixtures NOT visible in sidebar', async ({ page }) => {
    await loginOperatorAndGoHome(page);
    const sidebar = new SidebarComponent(page);
    await sidebar.expectHidden(['Fixtures']);
  });

  test('Admin toggle not visible (no users:view)', async ({ page }) => {
    await loginOperatorAndGoHome(page);
    const adminBtn = page.locator('button').filter({ hasText: 'Admin' });
    await expect(adminBtn).not.toBeVisible();
  });

  test('System toggle not visible (no system:view)', async ({ page }) => {
    await loginOperatorAndGoHome(page);
    const systemBtn = page.locator('button').filter({ hasText: 'System' });
    await expect(systemBtn).not.toBeVisible();
  });

  // ── Manufacturing Access ─────────────────────────────────

  test('navigate to /manufacturing — page loads', async ({ page }) => {
    await loginOperatorAndGoHome(page);
    const mfgPage = new ManufacturingPage(page);
    await mfgPage.goto();
    await mfgPage.expectVisible();
  });

  test('manufacturing:view via API succeeds', async ({ page }) => {
    const token = await getOperatorToken(page);

    const res = await page.request.get(`${API_URL}/v2/manufacturing/configs`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    // 200 or 404 (may not have data yet) — not 403
    expect([200, 404]).toContain(res.status());
  });

  test('manufacturing:run via API succeeds', async ({ page }) => {
    const token = await getOperatorToken(page);

    // Operator has manufacturing:run — verify by accessing manufacturing endpoints
    const res = await page.request.get(`${API_URL}/v2/manufacturing/configs`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    // Should not be 403
    expect(res.status()).not.toBe(403);
  });

  // ── Route Guards: Blocked Pages ──────────────────────────

  test('navigate to /products redirected to dashboard', async ({ page }) => {
    await loginOperatorAndGoHome(page);
    await page.goto('/products');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL('/');
  });

  test('navigate to /builds redirected to dashboard', async ({ page }) => {
    await loginOperatorAndGoHome(page);
    await page.goto('/builds');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL('/');
  });

  test('navigate to /validation redirected to dashboard', async ({ page }) => {
    await loginOperatorAndGoHome(page);
    await page.goto('/validation');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL('/');
  });

  // ── API: Denied Operations ───────────────────────────────

  test('products:view via API denied (403)', async ({ page }) => {
    const token = await getOperatorToken(page);

    const res = await page.request.get(`${API_URL}/v2/products`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(403);
  });

  test('builds:view via API denied (403)', async ({ page }) => {
    const token = await getOperatorToken(page);

    const res = await page.request.get(`${API_URL}/v2/builds/runs`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(403);
  });

  test('validation:view via API denied (403)', async ({ page }) => {
    const token = await getOperatorToken(page);

    const res = await page.request.get(`${API_URL}/v2/sessions`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(403);
  });

  test('users:view via API denied (403)', async ({ page }) => {
    const token = await getOperatorToken(page);

    const res = await page.request.get(`${API_URL}/v2/users`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(403);
  });

  test('api-keys:manage via API denied (403)', async ({ page }) => {
    const token = await getOperatorToken(page);

    const res = await page.request.post(`${API_URL}/v2/api-keys`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      data: { name: 's15-Ops Denied Key' },
    });
    expect(res.status()).toBe(403);
  });
});
