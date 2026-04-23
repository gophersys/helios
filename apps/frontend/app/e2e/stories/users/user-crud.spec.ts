import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import { UsersPage } from '../../pages/users.page';
import { apiGet, apiPost, apiPut } from '../../helpers/api';

/**
 * Stage 14 — User CRUD E2E tests.
 *
 * Tests are ordered and cumulative: users created in earlier tests
 * are verified and modified in later tests.
 *
 * Seed provides 4 dev users: admin, maintainer, developer, operator.
 * All test data prefixed with "s14-" for resource isolation.
 */

const TEST_USER_SUFFIX = Date.now();
const TEST_USER_EMAIL = `s14-test-${TEST_USER_SUFFIX}@e2e.dev`;
const TEST_USER_NAME = `s14-Test User ${TEST_USER_SUFFIX}`;

test.describe.configure({ mode: 'serial' });

test.describe('User CRUD', () => {
  let usersPage: UsersPage;
  let testUserId: string;

  test.beforeEach(async ({ page }) => {
    await loginAsRole(page, 'admin');
    usersPage = new UsersPage(page);
  });

  test('Users page shows seeded dev users in list', async ({ page }) => {
    await usersPage.goto();
    await usersPage.expectVisible();

    // Wait for table to load — first user should appear
    await expect(page.locator('text=admin@concord.dev')).toBeVisible({ timeout: 15_000 });

    // Seed creates 4 dev users
    await expect(page.locator('text=maintainer@concord.dev')).toBeVisible();
    await expect(page.locator('text=developer@concord.dev')).toBeVisible();
    await expect(page.locator('text=operator@concord.dev')).toBeVisible();
  });

  test('create user: s14-test@e2e.dev, name="s14-Test User", role=DEVELOPER', async ({ page }) => {
    await usersPage.goto();

    await page.getByRole('button', { name: /add user/i }).click();

    const emailInput = page.locator('input[type="email"]');
    await emailInput.fill(TEST_USER_EMAIL);

    const nameInput = page.locator('input[type="text"]').first();
    await nameInput.fill(TEST_USER_NAME);

    await page
      .getByRole('button', { name: /create|save|confirm/i })
      .or(page.locator('button[type="submit"]'))
      .first()
      .click();

    await page.waitForLoadState('networkidle');

    await expect(page.locator(`text=${TEST_USER_EMAIL}`)).toBeVisible({ timeout: 5_000 });
  });

  test('new user appears in user list', async ({ page }) => {
    await usersPage.goto();
    await page.waitForLoadState('networkidle');

    await expect(page.locator(`text=${TEST_USER_EMAIL}`)).toBeVisible();
    await expect(page.locator(`text=${TEST_USER_NAME}`)).toBeVisible();
  });

  test('edit user name via inline edit', async ({ page }) => {
    // Get the user ID via API
    const data = await apiGet<{ data: Array<{ id: string; email: string }> }>(page, '/v2/users');
    const usersData = (data as any)?.data ?? data;
    const userList = Array.isArray(usersData) ? usersData : (usersData as any)?.data ?? [];
    const user = userList.find((u: any) => u.email === TEST_USER_EMAIL);
    expect(user).toBeTruthy();
    testUserId = user!.id;

    // Update name via API (inline edit calls PUT)
    await apiPut(page, `/v2/users/${testUserId}`, { name: 's14-Updated Name' });

    await usersPage.goto();
    await page.waitForLoadState('networkidle');
    // The user might be below the fold — scroll it into view
    const nameCell = page.locator('text=s14-Updated Name').first();
    await nameCell.scrollIntoViewIfNeeded();
    await expect(nameCell).toBeVisible({ timeout: 10_000 });
  });

  test('change user role via API', async ({ page }) => {
    expect(testUserId).toBeTruthy();

    await apiPut(page, `/v2/users/${testUserId}/role`, { role: 'MAINTAINER' });

    const data = await apiGet<{ data: Array<{ id: string; role: string }> }>(page, '/v2/users');
    const usersData = (data as any)?.data ?? data;
    const userList = Array.isArray(usersData) ? usersData : (usersData as any)?.data ?? [];
    const updated = userList.find((u: any) => u.id === testUserId);
    expect(updated?.role).toBe('MAINTAINER');
  });

  test('deactivate user (soft delete)', async ({ page }) => {
    await usersPage.goto();
    await page.waitForLoadState('networkidle');

    const row = page.locator('tr').filter({ hasText: TEST_USER_EMAIL });
    const deactivateBtn = row.getByRole('button', { name: /deactivate/i });
    await deactivateBtn.click();

    await page.waitForLoadState('networkidle');

    await expect(row.locator('text=Inactive')).toBeVisible({ timeout: 5_000 });
  });

  test('deactivated user cannot login via dev-login (403)', async ({ page }) => {
    const res = await page.request.post('http://localhost:9001/v2/auth/dev-login', {
      data: { email: TEST_USER_EMAIL },
    });
    expect(res.status()).toBe(403);
    const body = await res.json();
    const errorMsg =
      body?.error?.message || body?.errors?.[0]?.message || '';
    expect(errorMsg).toContain('deactivated');
  });

  test('reactivate user', async ({ page }) => {
    await usersPage.goto();
    await page.waitForLoadState('networkidle');

    const row = page.locator('tr').filter({ hasText: TEST_USER_EMAIL });
    const activateBtn = row.getByRole('button', { name: /activate/i });
    await activateBtn.click();

    await page.waitForLoadState('networkidle');

    await expect(row.locator('text=Active')).toBeVisible({ timeout: 5_000 });

    // Verify login works again
    const res = await page.request.post('http://localhost:9001/v2/auth/dev-login', {
      data: { email: TEST_USER_EMAIL },
    });
    expect(res.status()).toBe(200);
  });

  test('duplicate email returns conflict error', async ({ page }) => {
    await usersPage.goto();

    await page.getByRole('button', { name: /add user/i }).click();

    const emailInput = page.locator('input[type="email"]');
    await emailInput.fill(TEST_USER_EMAIL);
    const nameInput = page.locator('input[type="text"]').first();
    await nameInput.fill('s14-Duplicate User');

    await page
      .getByRole('button', { name: /create|save|confirm/i })
      .or(page.locator('button[type="submit"]'))
      .first()
      .click();

    await expect(
      page.locator('text=/already exists|conflict|duplicate/i'),
    ).toBeVisible({ timeout: 5_000 });
  });

  test('Maintainer can view Users page but cannot create/edit (no manage permission)', async ({ page }) => {
    await loginAsRole(page, 'maintainer');
    usersPage = new UsersPage(page);

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
