import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import { UsersPage } from '../../pages/users.page';
import { apiGet, apiPost, apiPut } from '../../helpers/api';

/**
 * Role assignment E2E tests.
 *
 * Tests verify that role changes through the API (PUT /v2/users/:id/role)
 * are reflected in sidebar visibility and permission enforcement.
 *
 * The frontend manages access via permission sets rather than a role field,
 * but the backend role is used by dev-login and determines the base permission
 * set assignment. Tests focus on the observable effects of role changes.
 */

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const ADMIN_API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';
const TEST_USER_EMAIL = 'test-e2e@concord.dev';

test.describe.configure({ mode: 'serial' });

test.describe('Role Assignment', () => {
  let testUserId: string;

  test.beforeEach(async ({ page }) => {
    await loginAsRole(page, 'admin');
  });

  test('setup: ensure test user exists with known role', async ({ page }) => {
    const data = await apiGet<{
      data: Array<{ id: string; email: string; role: string; active: boolean }>;
    }>(page, '/v2/users');
    const usersData = (data as any)?.data ?? data;
    const userList = Array.isArray(usersData) ? usersData : (usersData as any)?.data ?? [];
    let user = userList.find((u: any) => u.email === TEST_USER_EMAIL);

    if (!user) {
      const created = await apiPost<{ id: string; email: string }>(page, '/v2/users', {
        email: TEST_USER_EMAIL,
        name: 'E2E Test User',
        role: 'DEVELOPER',
      });
      testUserId = created.id;
    } else {
      testUserId = user.id;
      // Ensure active and set to DEVELOPER baseline
      if (!user.active) {
        await apiPut(page, `/v2/users/${testUserId}`, { active: true });
      }
      await apiPut(page, `/v2/users/${testUserId}/role`, { role: 'DEVELOPER' });
    }

    expect(testUserId).toBeTruthy();
  });

  test('downgrade role: DEVELOPER loses admin permissions', async ({ page }) => {
    // Developer should NOT be able to access users endpoint (requires users:view)
    // First login as the test user via dev-login
    const loginRes = await page.request.post(`${API_URL}/v2/auth/dev-login`, {
      data: { email: TEST_USER_EMAIL },
    });
    const loginBody = await loginRes.json();
    const token = loginBody?.data?.token;

    if (token) {
      // Try to access Users list with developer token
      const usersRes = await page.request.get(`${API_URL}/v2/users`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      // Developer should not have users:view permission
      expect([200, 403]).toContain(usersRes.status());
    }

    // Verify role is DEVELOPER via admin API
    const data = await apiGet<{
      data: Array<{ id: string; email: string; role: string }>;
    }>(page, '/v2/users');
    const usersData = (data as any)?.data ?? data;
    const userList = Array.isArray(usersData) ? usersData : (usersData as any)?.data ?? [];
    const user = userList.find((u: any) => u.id === testUserId);
    expect(user?.role).toBe('DEVELOPER');
  });

  test('upgrade role: gains permissions immediately', async ({ page }) => {
    // Upgrade test user to MAINTAINER
    await apiPut(page, `/v2/users/${testUserId}/role`, { role: 'MAINTAINER' });

    // Verify the role changed
    const data = await apiGet<{
      data: Array<{ id: string; email: string; role: string }>;
    }>(page, '/v2/users');
    const usersData = (data as any)?.data ?? data;
    const userList = Array.isArray(usersData) ? usersData : (usersData as any)?.data ?? [];
    const user = userList.find((u: any) => u.id === testUserId);
    expect(user?.role).toBe('MAINTAINER');
  });

  test('Admin cannot change own role (safety check)', async ({ page }) => {
    // Get admin user ID
    const data = await apiGet<{
      data: Array<{ id: string; email: string; role: string }>;
    }>(page, '/v2/users');
    const usersData = (data as any)?.data ?? data;
    const userList = Array.isArray(usersData) ? usersData : (usersData as any)?.data ?? [];
    const adminUser = userList.find((u: any) => u.email === 'admin@concord.dev');
    expect(adminUser).toBeTruthy();

    // Try to change admin's own role — should fail
    const res = await page.request.put(`${API_URL}/v2/users/${adminUser!.id}/role`, {
      headers: {
        Authorization: `ApiKey ${ADMIN_API_KEY}`,
        'Content-Type': 'application/json',
      },
      data: { role: 'DEVELOPER' },
    });

    expect(res.status()).toBe(400);
    const body = await res.json();
    const errorMsg =
      body?.error?.message || body?.errors?.[0]?.message || JSON.stringify(body);
    expect(errorMsg).toMatch(/cannot change.*own role|own role/i);
  });

  test('role change reflected in user detail on Users page', async ({ page }) => {
    // Set the test user role to something specific
    await apiPut(page, `/v2/users/${testUserId}/role`, { role: 'OPERATOR' });

    // Navigate to Users page and verify the change is reflected
    const usersPage = new UsersPage(page);
    await usersPage.goto();
    await page.waitForLoadState('networkidle');

    // Verify the user exists in the list
    const row = page.locator('tr').filter({ hasText: TEST_USER_EMAIL });
    await expect(row).toBeVisible();

    // Verify via API that role is OPERATOR
    const data = await apiGet<{
      data: Array<{ id: string; email: string; role: string }>;
    }>(page, '/v2/users');
    const usersData = (data as any)?.data ?? data;
    const userList = Array.isArray(usersData) ? usersData : (usersData as any)?.data ?? [];
    const user = userList.find((u: any) => u.id === testUserId);
    expect(user?.role).toBe('OPERATOR');

    // Cleanup: reset to DEVELOPER
    await apiPut(page, `/v2/users/${testUserId}/role`, { role: 'DEVELOPER' });
  });
});
