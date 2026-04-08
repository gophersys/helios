import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import { UsersPage } from '../../pages/users.page';
import { createUserViaAPI, deleteUserViaAPI } from '../../helpers/api-extended';
import { apiGet, apiPost, apiPut } from '../../helpers/api';

/**
 * User CRUD E2E tests.
 *
 * Tests are ordered and cumulative: users created in earlier tests
 * are verified and modified in later tests.
 *
 * Seed provides 4 dev users: admin, maintainer, developer, operator.
 */

const TEST_USER_EMAIL = 'test-e2e@concord.dev';
const TEST_USER_NAME = 'E2E Test User';

test.describe.configure({ mode: 'serial' });

test.describe('User CRUD', () => {
  let usersPage: UsersPage;
  let testUserId: string;

  test.beforeEach(async ({ page }) => {
    await loginAsRole(page, 'admin');
    usersPage = new UsersPage(page);
  });

  test('Users page shows list of existing dev users', async ({ page }) => {
    await usersPage.goto();
    await usersPage.expectVisible();

    // Seed creates 4 dev users
    await expect(page.locator('text=admin@concord.dev')).toBeVisible();
    await expect(page.locator('text=maintainer@concord.dev')).toBeVisible();
    await expect(page.locator('text=developer@concord.dev')).toBeVisible();
    await expect(page.locator('text=operator@concord.dev')).toBeVisible();
  });

  test('create new user: test-e2e@concord.dev', async ({ page }) => {
    await usersPage.goto();

    // Click "Add user" button to open form
    await page.getByRole('button', { name: /add user/i }).click();

    // Fill email
    const emailInput = page.locator('input[type="email"]');
    await emailInput.fill(TEST_USER_EMAIL);

    // Fill name
    const nameInput = page.locator('input[type="text"]').first();
    await nameInput.fill(TEST_USER_NAME);

    // Submit the form (click the check/submit button)
    await page
      .getByRole('button', { name: /create|save|confirm/i })
      .or(page.locator('button[type="submit"]'))
      .first()
      .click();

    await page.waitForLoadState('networkidle');

    // Verify success — the user should now appear
    await expect(page.locator(`text=${TEST_USER_EMAIL}`)).toBeVisible({ timeout: 5_000 });
  });

  test('new user appears in user list', async ({ page }) => {
    await usersPage.goto();
    await page.waitForLoadState('networkidle');

    await expect(page.locator(`text=${TEST_USER_EMAIL}`)).toBeVisible();
    await expect(page.locator(`text=${TEST_USER_NAME}`)).toBeVisible();
  });

  test('edit user: change name', async ({ page }) => {
    // Get the user ID via API for later use
    const data = await apiGet<{ data: Array<{ id: string; email: string }> }>(page, '/v2/users');
    const usersData = (data as any)?.data ?? data;
    const userList = Array.isArray(usersData) ? usersData : (usersData as any)?.data ?? [];
    const user = userList.find((u: any) => u.email === TEST_USER_EMAIL);
    expect(user).toBeTruthy();
    testUserId = user!.id;

    // Update name via API (the UI uses inline edits via permission set dropdown,
    // and the name edit is done through the PUT endpoint)
    await apiPut(page, `/v2/users/${testUserId}`, { name: 'E2E Updated Name' });

    // Verify the change on the page
    await usersPage.goto();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=E2E Updated Name')).toBeVisible();
  });

  test('edit user: change role via API', async ({ page }) => {
    // The frontend doesn't have a role column/editor — roles are managed via
    // permission sets. Test the role endpoint directly.
    expect(testUserId).toBeTruthy();

    await apiPut(page, `/v2/users/${testUserId}/role`, { role: 'MAINTAINER' });

    // Verify via API
    const data = await apiGet<{ data: Array<{ id: string; role: string }> }>(page, '/v2/users');
    const usersData = (data as any)?.data ?? data;
    const userList = Array.isArray(usersData) ? usersData : (usersData as any)?.data ?? [];
    const updated = userList.find((u: any) => u.id === testUserId);
    expect(updated?.role).toBe('MAINTAINER');
  });

  test('deactivate user via UI toggle', async ({ page }) => {
    await usersPage.goto();
    await page.waitForLoadState('networkidle');

    // Find the row with our test user and click Deactivate
    const row = page.locator('tr').filter({ hasText: TEST_USER_EMAIL });
    const deactivateBtn = row.getByRole('button', { name: /deactivate/i });
    await deactivateBtn.click();

    // Wait for update
    await page.waitForLoadState('networkidle');

    // User should now show Inactive badge
    await expect(row.locator('text=Inactive')).toBeVisible({ timeout: 5_000 });
  });

  test('deactivated user cannot log in via dev-login', async ({ page }) => {
    // Try dev-login with the deactivated user's email
    const res = await page.request.post('http://localhost:9001/v2/auth/dev-login', {
      data: { email: TEST_USER_EMAIL },
    });
    const body = await res.json();
    // Should get a 403 forbidden
    expect(res.status()).toBe(403);
    expect(body?.error?.message || body?.errors?.[0]?.message || '').toContain('deactivated');
  });

  test('reactivate user via UI toggle', async ({ page }) => {
    await usersPage.goto();
    await page.waitForLoadState('networkidle');

    // Find the row and click Activate
    const row = page.locator('tr').filter({ hasText: TEST_USER_EMAIL });
    const activateBtn = row.getByRole('button', { name: /activate/i });
    await activateBtn.click();

    await page.waitForLoadState('networkidle');

    // User should now show Active badge
    await expect(row.locator('text=Active')).toBeVisible({ timeout: 5_000 });

    // Verify login works again
    const res = await page.request.post('http://localhost:9001/v2/auth/dev-login', {
      data: { email: TEST_USER_EMAIL },
    });
    expect(res.status()).toBe(200);
  });

  test('duplicate email returns conflict error', async ({ page }) => {
    await usersPage.goto();

    // Open form
    await page.getByRole('button', { name: /add user/i }).click();

    // Fill with existing email
    const emailInput = page.locator('input[type="email"]');
    await emailInput.fill(TEST_USER_EMAIL);
    const nameInput = page.locator('input[type="text"]').first();
    await nameInput.fill('Duplicate User');

    // Submit
    await page
      .getByRole('button', { name: /create|save|confirm/i })
      .or(page.locator('button[type="submit"]'))
      .first()
      .click();

    // Should show error about duplicate/conflict
    await expect(
      page.locator('text=/already exists|conflict|duplicate/i'),
    ).toBeVisible({ timeout: 5_000 });
  });

  test('Maintainer can view Users page but cannot manage', async ({ page }) => {
    await loginAsRole(page, 'maintainer');
    usersPage = new UsersPage(page);

    // Expand Admin section in sidebar, then navigate
    const sidebar = usersPage.sidebar();
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await sidebar.expandSection('Admin');
    await sidebar.navigateTo('Users');

    await usersPage.expectVisible();

    // Maintainer can see users but "Add user" button should NOT be visible
    await expect(page.locator(`text=${TEST_USER_EMAIL}`)).toBeVisible();
    await expect(page.getByRole('button', { name: /add user/i })).not.toBeVisible();

    // Deactivate buttons should also not be visible
    const row = page.locator('tr').filter({ hasText: TEST_USER_EMAIL });
    await expect(row.getByRole('button', { name: /deactivate/i })).not.toBeVisible();
  });
});
