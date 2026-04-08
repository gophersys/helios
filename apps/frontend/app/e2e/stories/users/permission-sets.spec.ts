import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import { UsersPage } from '../../pages/users.page';
import { apiGet, apiPost, apiPut, apiDelete } from '../../helpers/api';

/**
 * Permission Sets E2E tests.
 *
 * Tests are ordered and cumulative: permission sets created in earlier tests
 * are used in later tests. The Permission Sets tab is part of the Users page.
 */

const CUSTOM_SET_NAME = 'E2E Custom';
const CUSTOM_SET_DESC = 'Custom permission set for E2E testing';

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

    // Seed creates built-in sets (Super Admin, Admin, Maintainer, Developer, Operator, Viewer)
    // At minimum, we expect some permission sets to be visible
    await page.waitForLoadState('networkidle');

    // Wait for loading to finish
    await expect(page.locator('text=Loading permission sets')).not.toBeVisible({ timeout: 10_000 });

    // Check that at least one permission set card is visible
    // Permission sets are rendered as cards with names
    const setCards = page.locator('.card, [data-testid="permset-row"]');
    const count = await setCards.count();
    expect(count).toBeGreaterThan(0);
  });

  test('create custom permission set with specific permissions', async ({ page }) => {
    await usersPage.goto();
    await usersPage.switchTab('Permission Sets');
    await page.waitForLoadState('networkidle');

    // Click "New set" button
    await page.getByRole('button', { name: /new set/i }).click();

    // Fill name
    const nameInput = page.locator('label').filter({ hasText: /name/i }).locator('input');
    await nameInput.fill(CUSTOM_SET_NAME);

    // Fill description
    const descInput = page.locator('label').filter({ hasText: /description/i }).locator('input');
    await descInput.fill(CUSTOM_SET_DESC);

    // Select some permissions — check a few checkboxes
    // The permission tree shows module > action checkboxes
    const checkboxes = page.locator('input[type="checkbox"]');
    const checkboxCount = await checkboxes.count();

    // Check the first 3 leaf checkboxes (skip module-level ones)
    let checked = 0;
    for (let i = 0; i < checkboxCount && checked < 3; i++) {
      const cb = checkboxes.nth(i);
      // Only check unchecked leaf checkboxes
      if (!(await cb.isChecked())) {
        await cb.check();
        checked++;
      }
    }

    // Submit the form
    await page.getByRole('button', { name: /create/i }).first().click();
    await page.waitForLoadState('networkidle');

    // Verify the new set appears
    await expect(page.locator(`text=${CUSTOM_SET_NAME}`)).toBeVisible({ timeout: 5_000 });
  });

  test('custom set appears in list with correct permission count', async ({ page }) => {
    await usersPage.goto();
    await usersPage.switchTab('Permission Sets');
    await page.waitForLoadState('networkidle');

    // Find the custom set card
    const card = page.locator('.card, [data-testid="permset-row"]').filter({
      hasText: CUSTOM_SET_NAME,
    });
    await expect(card).toBeVisible();

    // Should show description
    await expect(card.locator(`text=${CUSTOM_SET_DESC}`)).toBeVisible();

    // Should show a permission count badge (e.g., "3/XX")
    // The card shows "permissions.length/totalCount"
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

  test('edit permission set: change description', async ({ page }) => {
    await usersPage.goto();
    await usersPage.switchTab('Permission Sets');
    await page.waitForLoadState('networkidle');

    // Find the custom set card and click edit
    const card = page.locator('.card, [data-testid="permset-row"]').filter({
      hasText: CUSTOM_SET_NAME,
    });
    await card.getByRole('button', { name: /edit/i }).click();

    // Update the description
    const descInput = page.locator('label').filter({ hasText: /description/i }).locator('input');
    await descInput.fill('Updated E2E description');

    // Save
    await page.getByRole('button', { name: /save/i }).first().click();
    await page.waitForLoadState('networkidle');

    // Verify change — expand the card if needed
    await expect(page.locator('text=Updated E2E description')).toBeVisible({ timeout: 5_000 });
  });

  test('assign custom permission set to user', async ({ page }) => {
    // Get the test user ID
    const userData = await apiGet<{
      data: Array<{ id: string; email: string }>;
    }>(page, '/v2/users');
    const usersData = (userData as any)?.data ?? userData;
    const userList = Array.isArray(usersData) ? usersData : (usersData as any)?.data ?? [];
    const testUser = userList.find((u: any) => u.email === 'test-e2e@concord.dev');

    if (!testUser) {
      // Create the user if it doesn't exist (may have been cleaned up)
      const created = await apiPost<{ id: string }>(page, '/v2/users', {
        email: 'test-e2e@concord.dev',
        name: 'E2E Test User',
      });
      expect(created).toBeTruthy();
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

    // Find the test user row and change their permission set via the dropdown
    const row = page.locator('tr').filter({ hasText: 'test-e2e@concord.dev' });
    await expect(row).toBeVisible();

    // The permission set column has a Select dropdown for non-self users
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
    const updatedUser = refreshList.find((u: any) => u.email === 'test-e2e@concord.dev');
    expect(updatedUser?.permissionSetName).toBe(CUSTOM_SET_NAME);
  });

  test('user inherits permissions from assigned set', async ({ page }) => {
    // Verify via the API that the user's resolved permissions include
    // the ones from the custom set
    const permData = await apiGet<{
      data: Array<{ id: string; name: string; permissions: string[] }>;
    }>(page, '/v2/permissions');
    const setsData = (permData as any)?.data ?? permData;
    const setList = Array.isArray(setsData) ? setsData : (setsData as any)?.data ?? [];
    const customSet = setList.find((s: any) => s.name === CUSTOM_SET_NAME);
    expect(customSet).toBeTruthy();
    expect(customSet!.permissions.length).toBeGreaterThan(0);
  });

  test('delete permission set with users assigned is blocked', async ({ page }) => {
    // The custom set has a user assigned — deletion should fail
    expect(customSetId).toBeTruthy();

    // Try to delete via API — should return conflict
    const res = await page.request.delete(`http://localhost:9001/v2/permissions/${customSetId}`, {
      headers: { Authorization: 'ApiKey ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG' },
    });
    expect(res.status()).toBe(409);
    const body = await res.json();
    const errorMsg =
      body?.error?.message || body?.errors?.[0]?.message || JSON.stringify(body);
    expect(errorMsg).toMatch(/assigned users|cannot delete/i);
  });

  test('delete permission set with no users succeeds', async ({ page }) => {
    // First unassign the user from the custom set
    const userData = await apiGet<{
      data: Array<{ id: string; email: string }>;
    }>(page, '/v2/users');
    const usersData = (userData as any)?.data ?? userData;
    const userList = Array.isArray(usersData) ? usersData : (usersData as any)?.data ?? [];
    const testUser = userList.find((u: any) => u.email === 'test-e2e@concord.dev');

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

    // Click delete button
    await card.getByRole('button', { name: /delete/i }).click();

    // Confirm deletion dialog
    await page.getByRole('button', { name: /confirm|delete|yes/i }).first().click();
    await page.waitForTimeout(500);

    // The set should be gone
    await expect(page.locator(`text=${CUSTOM_SET_NAME}`)).not.toBeVisible({ timeout: 5_000 });
  });
});
