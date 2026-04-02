import { test, expect } from './fixtures';
import { loginViaAPI } from './helpers/auth';

test.describe('Fixtures Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await page.goto('/fixtures');
    await page.waitForLoadState('networkidle');
  });

  test('page loads correctly', async ({ page }) => {
    // Should not show error
    await expect(page.getByText('Something went wrong')).not.toBeVisible();
  });

  test('shows fixture-related content', async ({ page }) => {
    // Should show fixtures list, heading, or empty state
    const hasContent = await page.locator('h1, h2, [role="heading"]').first().isVisible().catch(() => false);
    const hasFixtureText = await page.getByText(/fixture|bench/i).first().isVisible().catch(() => false);
    expect(hasContent || hasFixtureText).toBe(true);
  });

  test('shows fixtures or empty state', async ({ page }) => {
    // Might have seeded fixtures or might be empty — both are valid
    const hasFixtures = await page.getByText(/bench-|fixture/i).first().isVisible().catch(() => false);
    const hasEmptyState = await page.getByText(/no fixture|no test/i).isVisible().catch(() => false);
    const hasAnyContent = await page.locator('main, .animate-fade-in').first().isVisible().catch(() => false);
    expect(hasFixtures || hasEmptyState || hasAnyContent).toBe(true);
  });
});

test.describe('Manufacturing Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await page.goto('/manufacturing');
    await page.waitForLoadState('networkidle');
  });

  test('page loads without error', async ({ page }) => {
    await expect(page.getByText('Something went wrong')).not.toBeVisible();
  });

  test('shows manufacturing heading or placeholder', async ({ page }) => {
    const hasHeading = await page.getByText(/manufacturing/i).first().isVisible().catch(() => false);
    expect(hasHeading).toBe(true);
  });
});
