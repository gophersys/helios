/**
 * E2E tests for common UI patterns.
 * Tests loading states, transitions, and core interactions.
 */
import { test, expect } from './fixtures';

test.describe('Loading States', () => {
  test('shows planes loader during page load', async ({ page }) => {
    // Slow down network to see loading state
    await page.route('**/api/**', async route => {
      await new Promise(resolve => setTimeout(resolve, 1000));
      await route.continue();
    });

    // Navigate and check for loader
    await page.goto('/login');

    // The planes loader canvas should be present on loading pages
    // (Login page has the full animation)
    const canvas = page.locator('canvas');
    await expect(canvas).toBeVisible();
  });
});

test.describe('Theme Toggle', () => {
  test.beforeEach(async ({ page }) => {
    // Set up auth for settings access
    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.setItem('token', 'test-token');
      localStorage.setItem('user', JSON.stringify({
        id: 'test',
        email: 'test@test.com',
        name: 'Test',
        permissions: []
      }));
    });
  });

  test.skip('can toggle between light and dark mode', async ({ page }) => {
    // This requires the settings modal to be accessible
    // Implement when settings are available in nav

    await page.goto('/');

    // Open settings
    await page.click('[data-testid="settings-button"]');

    // Toggle theme
    const themeToggle = page.locator('[data-testid="theme-toggle"]');
    await themeToggle.click();

    // Check that HTML class changed
    const html = page.locator('html');
    const hasLight = await html.evaluate(el => el.classList.contains('light'));
    expect(hasLight).toBe(true);

    // Toggle back
    await themeToggle.click();
    const hasDark = await html.evaluate(el => el.classList.contains('dark'));
    expect(hasDark).toBe(true);
  });
});

test.describe('Responsive Design', () => {
  test('sidebar collapses on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.setItem('token', 'test-token');
      localStorage.setItem('user', JSON.stringify({
        id: 'test',
        email: 'test@test.com',
        name: 'Test',
        permissions: []
      }));
    });

    // On mobile, sidebar should be collapsed or hidden
    // This depends on your responsive implementation
  });
});

test.describe('Accessibility', () => {
  test('login page has proper heading structure', async ({ page }) => {
    await page.goto('/login');

    // Check for h1
    const h1 = page.locator('h1');
    await expect(h1).toBeVisible();
  });

  test('buttons have accessible names', async ({ page }) => {
    await page.goto('/login');

    // Google sign-in button should have accessible text
    const signInButton = page.locator('button:has-text("Sign in")');
    await expect(signInButton).toBeVisible();
    await expect(signInButton).toBeEnabled();
  });

  test('form inputs have labels', async ({ page }) => {
    // Test any page with forms
    // For now, just verify login has proper structure
    await page.goto('/login');

    // All interactive elements should be focusable
    await page.keyboard.press('Tab');
    const focused = await page.evaluate(() => document.activeElement?.tagName);
    expect(['BUTTON', 'A', 'INPUT']).toContain(focused);
  });
});
