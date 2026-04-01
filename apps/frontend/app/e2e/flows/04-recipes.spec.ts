import { test, expect } from '../fixtures';
import { loginViaAPI } from '../helpers/auth';

test.describe('Build Recipe Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    // Navigate to Alpha product detail → Build Config tab
    await page.goto('/products');
    await page.waitForLoadState('networkidle');
    await page.getByRole('heading', { name: 'Alpha', level: 3 }).click();
    await page.waitForLoadState('networkidle');
    await page.getByRole('button', { name: 'Build Config' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('build config tab shows recipe heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Build Recipe' })).toBeVisible();
  });

  test('recipe textarea shows content', async ({ page }) => {
    const textarea = page.locator('textarea');
    await expect(textarea).toBeVisible();
    const content = await textarea.inputValue();
    expect(content).toContain('#!/bin/bash');
    expect(content).toContain('concord_init');
  });

  test('SDK reference section shows functions', async ({ page }) => {
    await expect(page.getByText('Concord Build SDK Reference')).toBeVisible();
    await expect(page.getByText('concord_init')).toBeVisible();
    await expect(page.getByText('concord_collect_hex')).toBeVisible();
    await expect(page.getByText('concord_finalize')).toBeVisible();
  });

  test('save button is disabled when no changes', async ({ page }) => {
    const saveBtn = page.getByRole('button', { name: 'Save Recipe' });
    await expect(saveBtn).toBeVisible();
    await expect(saveBtn).toBeDisabled();
  });

  test('validate button is clickable', async ({ page }) => {
    const validateBtn = page.getByRole('button', { name: 'Validate' });
    await expect(validateBtn).toBeVisible();
    await expect(validateBtn).toBeEnabled();
  });
});
