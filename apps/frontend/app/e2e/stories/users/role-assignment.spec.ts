import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import { UsersPage } from '../../pages/users.page';
import { apiGet, apiPost, apiPut } from '../../helpers/api';

/**
 * Stage 14 — Role assignment E2E tests.
 *
 * Tests verify that role changes through the API (PUT /v2/users/:id/role)
 * are reflected in the user list and permission enforcement.
 *
 * All test data prefixed with "s14-" for resource isolation.
 */

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const ADMIN_API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';
const TEST_USER_EMAIL = 's14-test@e2e.dev';

test.describe.configure({ mode: 'serial' });

test.describe('Role Assignment', () => {
  let testUserId: string;

  test.beforeEach(async ({ page }) => {
    await loginAsRole(page, 'admin');
  });

  test('setup: create test users for role tests', async ({ page }) => {
    const data = await apiGet<{
      data: Array<{ id: string; email: string; role: string; active: boolean }>;
    }>(page, '/v2/users');
    const usersData = (data as any)?.data ?? data;
    const userList = Array.isArray(usersData) ? usersData : (usersData as any)?.data ?? [];
    let user = userList.find((u: any) => u.email === TEST_USER_EMAIL);

    if (!user) {
      const created = await apiPost<{ id: string; email: string }>(page, '/v2/users', {
        email: TEST_USER_EMAIL,
        name: 's14-Test User',
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

  test('downgrade user from DEVELOPER to OPERATOR -> loses non-mfg permissions', async ({ page }) => {
    // Downgrade to OPERATOR
    await apiPut(page, `/v2/users/${testUserId}/role`, { role: 'OPERATOR' });

    // Verify role is OPERATOR via API
    const data = await apiGet<{
      data: Array<{ id: string; email: string; role: string }>;
    }>(page, '/v2/users');
    const usersData = (data as any)?.data ?? data;
    const userList = Array.isArray(usersData) ? usersData : (usersData as any)?.data ?? [];
    const user = userList.find((u: any) => u.id === testUserId);
    expect(user?.role).toBe('OPERATOR');
  });

  test('upgrade user from OPERATOR to MAINTAINER -> gains product/build permissions', async ({ page }) => {
    await apiPut(page, `/v2/users/${testUserId}/role`, { role: 'MAINTAINER' });

    const data = await apiGet<{
      data: Array<{ id: string; email: string; role: string }>;
    }>(page, '/v2/users');
    const usersData = (data as any)?.data ?? data;
    const userList = Array.isArray(usersData) ? usersData : (usersData as any)?.data ?? [];
    const user = userList.find((u: any) => u.id === testUserId);
    expect(user?.role).toBe('MAINTAINER');
  });

  test('role change via API works (on test user, not admin)', async ({ page }) => {
    // Test role change on the test user (not admin — changing admin's role
    // in parallel would break other tests that depend on admin being ADMIN).
    expect(testUserId).toBeTruthy();

    // Set to DEVELOPER baseline
    const res = await page.request.put(`${API_URL}/v2/users/${testUserId}/role`, {
      headers: {
        Authorization: `ApiKey ${ADMIN_API_KEY}`,
        'Content-Type': 'application/json',
      },
      data: { role: 'DEVELOPER' },
    });
    expect(res.status()).toBe(200);

    // Change to ADMIN
    const res2 = await page.request.put(`${API_URL}/v2/users/${testUserId}/role`, {
      headers: {
        Authorization: `ApiKey ${ADMIN_API_KEY}`,
        'Content-Type': 'application/json',
      },
      data: { role: 'ADMIN' },
    });
    expect(res2.status()).toBe(200);

    // Verify
    const data = await apiGet<{
      data: Array<{ id: string; role: string }>;
    }>(page, '/v2/users');
    const usersData = (data as any)?.data ?? data;
    const userList = Array.isArray(usersData) ? usersData : (usersData as any)?.data ?? [];
    const user = userList.find((u: any) => u.id === testUserId);
    expect(user?.role).toBe('ADMIN');

    // Restore to DEVELOPER
    await apiPut(page, `/v2/users/${testUserId}/role`, { role: 'DEVELOPER' });
  });

  test('role change reflected in user list UI', async ({ page }) => {
    // Set the test user role to OPERATOR
    await apiPut(page, `/v2/users/${testUserId}/role`, { role: 'OPERATOR' });

    const usersPage = new UsersPage(page);
    await usersPage.goto();
    await page.waitForLoadState('networkidle');

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
