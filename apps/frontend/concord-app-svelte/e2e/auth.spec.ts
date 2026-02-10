/**
 * E2E tests for authentication flow.
 * These test what a real user would experience.
 */
import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test('redirects unauthenticated users to login', async ({ page }) => {
    // Try to access a protected page
    await page.goto('/products');

    // Should be redirected to login
    await expect(page).toHaveURL(/.*login/);
  });

  test('shows login page with branding', async ({ page }) => {
    await page.goto('/login');

    // Check for Concord branding
    await expect(page.locator('text=Concord')).toBeVisible();
    await expect(page.locator('text=CoreKinect')).toBeVisible();

    // Check for Google sign-in button
    await expect(page.locator('text=Sign in with Google')).toBeVisible();

    // Check for preregistered accounts notice
    await expect(page.locator('text=Only preregistered accounts can login')).toBeVisible();
  });

  test('planes animation is visible on login page', async ({ page }) => {
    await page.goto('/login');

    // Canvas should be present for the planes animation
    const canvas = page.locator('canvas');
    await expect(canvas).toBeVisible();
  });
});

// Helper to set up an authenticated session for tests that need it
test.describe('Authenticated Navigation', () => {
  test.beforeEach(async ({ page }) => {
    // Mock authenticated state by setting localStorage
    // In a real app, you'd use a test account or mock the auth provider
    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.setItem('token', 'test-token-for-e2e');
      localStorage.setItem('user', JSON.stringify({
        id: 'test-user',
        email: 'test@example.com',
        name: 'Test User',
        permissions: ['Concord.Admin.Catalog.View', 'Concord.Admin.Catalog.Manage']
      }));
    });
  });

  test.skip('can navigate to products page', async ({ page }) => {
    // This test is skipped because it requires a valid backend
    // Unskip and configure when backend is available
    await page.goto('/products');
    await expect(page.locator('h1, [data-testid="page-title"]')).toContainText(/products/i);
  });
});
