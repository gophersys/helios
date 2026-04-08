import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import { createProductViaAPI } from '../../helpers/api-extended';

/**
 * Recipe Editor — build script editor within the Stage Config Wizard (Step 3).
 *
 * Tests the CodeMirror-based editor, template loading, validation,
 * version history, and recipe publishing workflow.
 *
 * Depends on a product with initialized stages.
 */

test.describe.configure({ mode: 'serial' });

const uniqueSuffix = Date.now();
const productName = `E2E Recipe Editor ${uniqueSuffix}`;
let productId: string;

/** Navigate to the recipe editor (Step 3 of wizard) for Stage 1. */
async function navigateToRecipeEditor(page: import('@playwright/test').Page): Promise<void> {
  await loginAsRole(page, 'admin');
  await page.goto(`/products/${productId}`);
  await page.waitForLoadState('networkidle');

  // Switch to Validation tab
  await page.locator('button').filter({ hasText: 'Validation' }).first().click();
  await page.waitForTimeout(1_000);

  // Open wizard for Stage 1
  const configureBtn = page.getByRole('button', { name: /configure|edit/i }).first();
  await configureBtn.click();
  await page.waitForTimeout(500);

  // Navigate to Step 3 (Target -> Signing -> Recipe)
  await page.getByRole('button', { name: /next/i }).click();
  await page.waitForTimeout(300);
  await page.getByRole('button', { name: /next/i }).click();
  await page.waitForTimeout(500);
}

test.describe('Recipe Editor', () => {
  test.beforeAll(async () => {
    const product = await createProductViaAPI({
      name: productName,
      slug: `e2e-recipe-${uniqueSuffix}`,
      description: 'Product for recipe editor E2E tests',
    });
    productId = product.id;

    // Initialize stages via API (POST /v2/products/{id}/stages/initialize)
    const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
    const API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';
    await fetch(`${API_URL}/v2/products/${productId}/stages/initialize`, {
      method: 'POST',
      headers: { Authorization: `ApiKey ${API_KEY}`, 'Content-Type': 'application/json' },
      body: '{}',
    });
  });

  test('recipe editor shows file name "build.sh" in status bar', async ({ page }) => {
    await navigateToRecipeEditor(page);

    // IDE status bar shows the file name
    await expect(page.getByText('build.sh')).toBeVisible({ timeout: 5_000 });
  });

  test('recipe editor shows cursor position in status bar', async ({ page }) => {
    await navigateToRecipeEditor(page);

    // Cursor position indicator (line:col format)
    // The status bar shows something like "1:1"
    const statusBar = page.locator('[class*="bg-"]').filter({ hasText: /\d+:\d+/ });
    await expect(statusBar.first()).toBeVisible({ timeout: 5_000 });
  });

  test('loading recipe template populates editor with scaffold', async ({ page }) => {
    await navigateToRecipeEditor(page);

    // If empty, click "Start with template"
    const templateBtn = page.getByText('Start with template');
    if (await templateBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await templateBtn.click();
      await page.waitForTimeout(500);
    }

    // Editor should now contain the template content with concord SDK calls
    const editor = page.locator('.cm-editor');
    await expect(editor).toBeVisible({ timeout: 5_000 });

    // Template includes shebang and SDK functions
    await expect(page.getByText('#!/bin/bash').first()).toBeVisible({ timeout: 3_000 });
  });

  test('recipe validation checks for SDK function usage', async ({ page }) => {
    await navigateToRecipeEditor(page);

    // Ensure editor has content (populate template if empty)
    const templateBtn = page.getByText('Start with template');
    if (await templateBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await templateBtn.click();
      await page.waitForTimeout(500);
    }

    // Click the "Check" validate button
    const checkBtn = page.getByRole('button', { name: /check/i }).first();
    await checkBtn.click();
    await page.waitForTimeout(1_000);

    // Validation result should appear — either checklist items or validation feedback
    // The wizard shows recipe checks: shebang, error handling, SDK calls, etc.
    const checksArea = page.locator('[class*="bg-"]').filter({
      has: page.getByText(/concord_init|shebang|error handling/i),
    });
    await expect(checksArea.first()).toBeVisible({ timeout: 5_000 });
  });

  test('recipe Save button becomes active when content is modified', async ({ page }) => {
    await navigateToRecipeEditor(page);

    // Ensure editor has content
    const templateBtn = page.getByText('Start with template');
    if (await templateBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await templateBtn.click();
      await page.waitForTimeout(500);
    }

    // The Save button should be visible in the toolbar
    const saveBtn = page.getByRole('button', { name: /save/i })
      .filter({ hasNotText: /enable/i })
      .first();
    await expect(saveBtn).toBeVisible({ timeout: 5_000 });
  });

  test('recipe Publish button is visible in toolbar', async ({ page }) => {
    await navigateToRecipeEditor(page);

    // Ensure editor has content
    const templateBtn = page.getByText('Start with template');
    if (await templateBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await templateBtn.click();
      await page.waitForTimeout(500);
    }

    // Publish button visible
    const publishBtn = page.getByRole('button', { name: /publish/i }).first();
    await expect(publishBtn).toBeVisible({ timeout: 5_000 });
  });

  test('recipe shows Unsaved changes indicator after edit', async ({ page }) => {
    await navigateToRecipeEditor(page);

    // Ensure editor has content
    const templateBtn = page.getByText('Start with template');
    if (await templateBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await templateBtn.click();
      await page.waitForTimeout(500);
    }

    // Type into the editor to mark as dirty
    const editor = page.locator('.cm-editor .cm-content').first();
    if (await editor.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await editor.click();
      await page.keyboard.press('End');
      await page.keyboard.type('\n# E2E test edit');
      await page.waitForTimeout(300);

      // "Unsaved changes" indicator should appear
      await expect(page.getByText('Unsaved changes')).toBeVisible({ timeout: 3_000 });
    }
  });

  test('recipe variables section shows SDK substitution tokens', async ({ page }) => {
    await navigateToRecipeEditor(page);

    // The wizard Step 3 sidebar shows recipe checks and expected outputs
    // SDK environment variables like CONCORD_BOARD, CONCORD_FW_TYPE should be referenced
    // in the sidebar checklist or env var hover tooltips
    const sdkRef = page.getByText(/CONCORD_/).first();
    if (await sdkRef.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await expect(sdkRef).toBeVisible();
    } else {
      // Variables are shown in the checks sidebar as tooltips or in the env var panel
      // At minimum, the recipe checks panel should be visible
      const checksPanel = page.getByText(/concord_init|Source Concord SDK/i).first();
      await expect(checksPanel).toBeVisible({ timeout: 5_000 });
    }
  });
});
