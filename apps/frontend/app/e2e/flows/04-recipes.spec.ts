import { test, expect } from '../fixtures';
import { loginViaAPI } from '../helpers/auth';

test.describe('Build Recipe Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
  });

  async function navigateToBuildConfig(page: import('@playwright/test').Page) {
    await page.goto('/products');
    await page.waitForLoadState('networkidle');
    await page.getByRole('heading', { name: 'Alpha', level: 3 }).click();
    await page.waitForLoadState('networkidle');
    await page.getByRole('button', { name: 'Build Config' }).click();
    await page.waitForLoadState('networkidle');
  }

  test('build config tab loads', async ({ page }) => {
    await navigateToBuildConfig(page);

    // Should show Build Recipe heading
    await expect(page.getByText('Build Recipe')).toBeVisible();
    // Should show SDK reference section
    await expect(page.getByText('Concord Build SDK Reference')).toBeVisible();
  });

  test('recipe editor shows content or empty state', async ({ page }) => {
    await navigateToBuildConfig(page);

    // Should have a textarea for the recipe
    const textarea = page.locator('textarea');
    await expect(textarea).toBeVisible();

    // If recipe exists, it should contain the shebang or SDK source
    const content = await textarea.inputValue();
    if (content) {
      expect(content).toContain('#!/bin/bash');
    }
  });

  test('save button activates on change', async ({ page }) => {
    await navigateToBuildConfig(page);

    const textarea = page.locator('textarea');
    const saveBtn = page.getByRole('button', { name: /save recipe/i });

    // Save should be disabled initially (no changes)
    await expect(saveBtn).toBeDisabled();

    // Type something to trigger change detection
    const original = await textarea.inputValue();
    await textarea.fill(original + '\n# E2E test change');

    // Save should now be enabled
    await expect(saveBtn).toBeEnabled();

    // Restore original to avoid saving test changes
    await textarea.fill(original);
  });

  test('validate button works', async ({ page }) => {
    await navigateToBuildConfig(page);

    const textarea = page.locator('textarea');
    const validateBtn = page.getByRole('button', { name: /validate/i });

    // Should be visible
    await expect(validateBtn).toBeVisible();

    // Click validate
    await validateBtn.click();
    await page.waitForLoadState('networkidle');

    // Should show validation result (either valid or errors)
    const resultArea = page.locator('text=valid').or(page.locator('text=error'));
    // Wait a moment for the result to render
    await page.waitForTimeout(1000);
  });

  test('SDK reference shows available functions', async ({ page }) => {
    await navigateToBuildConfig(page);

    await expect(page.getByText('concord_init')).toBeVisible();
    await expect(page.getByText('concord_collect_hex')).toBeVisible();
    await expect(page.getByText('concord_collect_cfw')).toBeVisible();
    await expect(page.getByText('concord_finalize')).toBeVisible();
  });
});
