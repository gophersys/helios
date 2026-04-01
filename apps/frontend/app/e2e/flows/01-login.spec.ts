import { test, expect } from '../fixtures';
import { loginViaAPI, loginViaUI } from '../helpers/auth';

test.describe('Login & Navigation', () => {
  test('login page renders with branding', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Concord' })).toBeVisible();
    await expect(page.getByPlaceholder('you@company.com')).toBeVisible();
    await expect(page.getByPlaceholder('Enter your password')).toBeVisible();
    await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
  });

  test('can log in with dev credentials via UI', async ({ page }) => {
    await loginViaUI(page);
    // Should redirect away from /login
    await expect(page).not.toHaveURL(/\/login/);
    // Sidebar should be visible
    await expect(page.getByText('Products')).toBeVisible();
  });

  test('sidebar shows navigation items after login', async ({ page }) => {
    await loginViaAPI(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Primary nav
    await expect(page.getByRole('link', { name: 'Products' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Builds' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Validation' })).toBeVisible();
  });

  test('auth token persists across page refresh', async ({ page }) => {
    await loginViaAPI(page);
    await page.goto('/products');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('Products')).toBeVisible();

    await page.reload();
    await page.waitForLoadState('networkidle');
    // Should NOT be redirected to login
    await expect(page).not.toHaveURL(/\/login/);
  });

  test('can navigate between sections', async ({ page }) => {
    await loginViaAPI(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.getByRole('link', { name: 'Products' }).click();
    await expect(page).toHaveURL(/\/products/);

    await page.getByRole('link', { name: 'Builds' }).click();
    await expect(page).toHaveURL(/\/builds/);

    await page.getByRole('link', { name: 'Validation' }).click();
    await expect(page).toHaveURL(/\/validation/);
  });
});
