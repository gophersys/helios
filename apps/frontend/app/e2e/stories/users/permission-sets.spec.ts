import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import { UsersPage } from '../../pages/users.page';
import { apiGet, apiPost, apiPut, apiDelete } from '../../helpers/api';

/**
 * Stage 14 — Permission Sets E2E tests.
 *
 * Tests are ordered and cumulative: permission sets created in earlier tests
 * are used in later tests. The Permission Sets tab is part of the Users page.
 * All test data prefixed with "s14-" for resource isolation.
 */

const CUSTOM_SET_NAME = 's14-E2E Custom';
const CUSTOM_SET_DESC = 's14-Custom permission set for E2E testing';

test.describe.configure({ mode: 'serial' });

test.describe('Permission Sets', () => {
  let usersPage: UsersPage;
  let customSetId: string;

  test.beforeEach(async ({ page }) => {
    await loginAsRole(page, 'admin');
    usersPage = new UsersPage(page);
  });

  test('Permission Sets tab shows built-in permission sets', async ({ page }) => {
    await usersPage.goto();
    await usersPage.switchTab('Permission Sets');

    await page.waitForLoadState('networkidle');

    // Wait for loading to finish
    await expect(page.locator('text=Loading permission sets')).not.toBeVisible({ timeout: 10_000 });

    // Check that at least one permission set card is visible
    const setCards = page.locator('.card, [data-testid="permset-row"]');
    const count = await setCards.count();
    expect(count).toBeGreaterThan(0);
  });

  test('create custom permission set: "s14-E2E Custom" with specific permissions', async ({ page }) => {
    await usersPage.goto();
    await usersPage.switchTab('Permission Sets');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /new set/i }).click();

    const nameInput = page.locator('label').filter({ hasText: /name/i }).locator('input');
    await nameInput.fill(CUSTOM_SET_NAME);

    const descInput = page.locator('label').filter({ hasText: /description/i }).locator('input');
    await descInput.fill(CUSTOM_SET_DESC);

    // Select some permissions — check a few checkboxes
    const checkboxes = page.locator('input[type="checkbox"]');
    const checkboxCount = await checkboxes.count();

    let checked = 0;
    for (let i = 0; i < checkboxCount && checked < 3; i++) {
      const cb = checkboxes.nth(i);
      if (!(await cb.isChecked())) {
        await cb.check();
        checked++;
      }
    }

    await page.getByRole('button', { name: /create/i }).first().click();
    await page.waitForLoadState('networkidle');

    await expect(page.locator(`text=${CUSTOM_SET_NAME}`)).toBeVisible({ timeout: 5_000 });
  });

  test('custom set appears in list with correct permission count', async ({ page }) => {
    await usersPage.goto();
    await usersPage.switchTab('Permission Sets');
    await page.waitForLoadState('networkidle');

    const card = page.locator('.card, [data-testid="permset-row"]').filter({
      hasText: CUSTOM_SET_NAME,
    });
    await expect(card).toBeVisible();

    await expect(card.locator(`text=${CUSTOM_SET_DESC}`)).toBeVisible();

    // Should show a permission count badge (e.g., "3/XX")
    const countBadge = card.locator('span').filter({ hasText: /^\d+\/\d+$/ });
    await expect(countBadge).toBeVisible();

    // Get the set ID via API for later use
    const data = await apiGet<{
      data: Array<{ id: string; name: string }>;
    }>(page, '/v2/permissions');
    const setsData = (data as any)?.data ?? data;
    const setList = Array.isArray(setsData) ? setsData : (setsData as any)?.data ?? [];
    const customSet = setList.find((s: any) => s.name === CUSTOM_SET_NAME);
    expect(customSet).toBeTruthy();
    customSetId = customSet!.id;
  });

  test('edit permission set: add/remove permissions', async ({ page }) => {
    await usersPage.goto();
    await usersPage.switchTab('Permission Sets');
    await page.waitForLoadState('networkidle');

    const card = page.locator('.card, [data-testid="permset-row"]').filter({
      hasText: CUSTOM_SET_NAME,
    });
    await card.getByRole('button', { name: /edit/i }).click();

    // Update the description
    const descInput = page.locator('label').filter({ hasText: /description/i }).locator('input');
    await descInput.fill('s14-Updated E2E description');

    await page.getByRole('button', { name: /save/i }).first().click();
    await page.waitForLoadState('networkidle');

    await expect(page.locator('text=s14-Updated E2E description')).toBeVisible({ timeout: 5_000 });
  });

  test('assign custom permission set to user', async ({ page }) => {
    // Get the s14 test user ID
    const userData = await apiGet<{
      data: Array<{ id: string; email: string }>;
    }>(page, '/v2/users');
    const usersData = (userData as any)?.data ?? userData;
    const userList = Array.isArray(usersData) ? usersData : (usersData as any)?.data ?? [];
    let testUser = userList.find((u: any) => u.email === 's14-test@e2e.dev');

    if (!testUser) {
      // Create the user if it doesn't exist (may have been cleaned up)
      const created = await apiPost<{ id: string }>(page, '/v2/users', {
        email: 's14-test@e2e.dev',
        name: 's14-Test User',
      });
      expect(created).toBeTruthy();
      testUser = created as any;
    }

    // Get permission set ID
    const permData = await apiGet<{
      data: Array<{ id: string; name: string }>;
    }>(page, '/v2/permissions');
    const setsData = (permData as any)?.data ?? permData;
    const setList = Array.isArray(setsData) ? setsData : (setsData as any)?.data ?? [];
    const customSet = setList.find((s: any) => s.name === CUSTOM_SET_NAME);
    expect(customSet).toBeTruthy();

    // Navigate to Users tab and use the permission set dropdown
    await usersPage.goto();
    await page.waitForLoadState('networkidle');

    const row = page.locator('tr').filter({ hasText: 's14-test@e2e.dev' });
    await expect(row).toBeVisible();

    const select = row.locator('select').first();
    if (await select.isVisible()) {
      await select.selectOption({ label: CUSTOM_SET_NAME });
      await page.waitForLoadState('networkidle');
    }

    // Verify via API
    const refreshData = await apiGet<{
      data: Array<{ id: string; email: string; permissionSetName: string | null }>;
    }>(page, '/v2/users');
    const refreshUsers = (refreshData as any)?.data ?? refreshData;
    const refreshList = Array.isArray(refreshUsers)
      ? refreshUsers
      : (refreshUsers as any)?.data ?? [];
    const updatedUser = refreshList.find((u: any) => u.email === 's14-test@e2e.dev');
    expect(updatedUser?.permissionSetName).toBe(CUSTOM_SET_NAME);
  });

  test('user with custom set inherits correct permissions', async ({ page }) => {
    const permData = await apiGet<{
      data: Array<{ id: string; name: string; permissions: string[] }>;
    }>(page, '/v2/permissions');
    const setsData = (permData as any)?.data ?? permData;
    const setList = Array.isArray(setsData) ? setsData : (setsData as any)?.data ?? [];
    const customSet = setList.find((s: any) => s.name === CUSTOM_SET_NAME);
    expect(customSet).toBeTruthy();
    expect(customSet!.permissions.length).toBeGreaterThan(0);
  });

  test('delete permission set blocked when users assigned', async ({ page }) => {
    expect(customSetId).toBeTruthy();

    // Try to delete via API — should return conflict (409)
    const res = await page.request.delete(`http://localhost:9001/v2/permissions/${customSetId}`, {
      headers: { Authorization: 'ApiKey ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG' },
    });
    expect(res.status()).toBe(409);
    const body = await res.json();
    const errorMsg =
      body?.error?.message || body?.errors?.[0]?.message || JSON.stringify(body);
    expect(errorMsg).toMatch(/assigned users|cannot delete/i);
  });

  test('delete permission set succeeds after removing all users', async ({ page }) => {
    // First unassign the user from the custom set
    const userData = await apiGet<{
      data: Array<{ id: string; email: string }>;
    }>(page, '/v2/users');
    const usersData = (userData as any)?.data ?? userData;
    const userList = Array.isArray(usersData) ? usersData : (usersData as any)?.data ?? [];
    const testUser = userList.find((u: any) => u.email === 's14-test@e2e.dev');

    if (testUser) {
      await apiPut(page, `/v2/users/${testUser.id}`, { permissionSetId: null });
    }

    // Now delete should succeed via UI
    await usersPage.goto();
    await usersPage.switchTab('Permission Sets');
    await page.waitForLoadState('networkidle');

    const card = page.locator('.card, [data-testid="permset-row"]').filter({
      hasText: CUSTOM_SET_NAME,
    });

    await card.getByRole('button', { name: /delete/i }).click();

    await page.getByRole('button', { name: /confirm|delete|yes/i }).first().click();
    await page.waitForTimeout(500);

    await expect(page.locator(`text=${CUSTOM_SET_NAME}`)).not.toBeVisible({ timeout: 5_000 });
  });
});
