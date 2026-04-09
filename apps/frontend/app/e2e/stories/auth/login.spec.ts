import { test, expect } from '../../fixtures';
import { LoginPage } from '../../pages/login.page';
import { loginAsRole } from '../../helpers/auth-extended';

test.describe('Login flows', () => {
  test('login page shows 4 role buttons in dev mode', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.expectRoleButtons();
  });

  test('click Admin button logs in as admin@concord.dev and redirects to dashboard', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.loginAsRole('admin');
    await expect(page).toHaveURL('/');
  });

  test('click Maintainer button logs in as maintainer@concord.dev', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.loginAsRole('maintainer');
    await expect(page).toHaveURL('/');
  });

  test('click Developer button logs in as developer@concord.dev', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.loginAsRole('developer');
    await expect(page).toHaveURL('/');
  });

  test('click Operator button logs in as operator@concord.dev', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.loginAsRole('operator');
    await expect(page).toHaveURL('/');
  });

  test('JWT token stored in localStorage after login', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.loginAsRole('admin');

    const token = await page.evaluate(() => localStorage.getItem('concord-token'));
    expect(token).toBeTruthy();
    // JWT tokens have 3 dot-separated base64 parts
    expect(token!.split('.')).toHaveLength(3);
  });

  test('logout clears token and redirects to login page', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.loginAsRole('admin');

    // Click logout button
    const logoutBtn = page.locator('button[aria-label="Log out"]');
    await logoutBtn.click();

    await expect(page).toHaveURL('/login');

    const token = await page.evaluate(() => localStorage.getItem('concord-token'));
    expect(token).toBeNull();
  });

  test('expired/invalid token redirects to login page', async ({ page }) => {
    // When AUTH_ENABLED=false (dev mode), the backend accepts any token
    // and returns a valid user, so the frontend won't redirect.
    // This test only applies when auth is enabled.
    const res = await page.request.get('http://localhost:9001/v2/auth/me');
    const body = await res.json();
    const authDisabled = body?.data?.email === 'admin@concord.local';
    test.skip(authDisabled, 'Auth is disabled — backend accepts all tokens');

    // Set an invalid token before navigating
    await page.addInitScript(() => {
      localStorage.setItem('concord-token', 'invalid.token.value');
    });

    await page.goto('/');
    await expect(page).toHaveURL('/login');
  });

  test('environment badge shows development on login page', async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('networkidle');

    // The login page shows "DEVELOPMENT" badge in dev mode
    const badge = page.locator('text=DEVELOPMENT');
    await expect(badge).toBeVisible();
  });

  test('login page shows animated planes background', async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('networkidle');

    // The planes animation uses a canvas element with class "planes-canvas"
    const canvas = page.locator('canvas.planes-canvas');
    await expect(canvas).toBeVisible();
  });
});
