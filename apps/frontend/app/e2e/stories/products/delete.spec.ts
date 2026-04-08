import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import { createProductViaAPI } from '../../helpers/api-extended';

/**
 * Product Delete — confirmation dialog, role gating, and constraint enforcement.
 * The ConfirmDeleteDialog requires typing the product name to confirm deletion.
 */

test.describe.configure({ mode: 'serial' });

test.describe('Product Delete', () => {
  const uniqueSuffix = Date.now();
  let deletableProductId: string;
  let deletableProductName: string;

  test.beforeAll(async () => {
    // Create a product that can be safely deleted
    deletableProductName = `E2E Delete Test ${uniqueSuffix}`;
    const product = await createProductViaAPI({
      name: deletableProductName,
      slug: `e2e-delete-${uniqueSuffix}`,
      description: 'Product created to test deletion',
    });
    deletableProductId = product.id;
  });

  test('delete button visible for Admin on product list', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    // Find the product row and hover to reveal delete button
    const productRow = page.locator('[role="button"]').filter({ hasText: deletableProductName }).first();
    await expect(productRow).toBeVisible({ timeout: 10_000 });

    // Hover to show the delete button (it's opacity-0 by default, opacity-100 on group-hover)
    await productRow.hover();

    const deleteBtn = productRow.getByRole('button', { name: /delete/i });
    await expect(deleteBtn).toBeVisible();
  });

  test('delete button visible for Maintainer on product list', async ({ page }) => {
    await loginAsRole(page, 'maintainer');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    const productRow = page.locator('[role="button"]').filter({ hasText: deletableProductName }).first();
    await expect(productRow).toBeVisible({ timeout: 10_000 });
    await productRow.hover();

    const deleteBtn = productRow.getByRole('button', { name: /delete/i });
    await expect(deleteBtn).toBeVisible();
  });

  test('delete button NOT visible for Developer on product list', async ({ page }) => {
    await loginAsRole(page, 'developer');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    const productRow = page.locator('[role="button"]').filter({ hasText: deletableProductName }).first();
    if (await productRow.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await productRow.hover();
      // Developer should not see any delete button
      const deleteBtn = productRow.getByRole('button', { name: /delete/i });
      await expect(deleteBtn).not.toBeVisible();
    }
  });

  test('clicking delete shows confirmation dialog', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    const productRow = page.locator('[role="button"]').filter({ hasText: deletableProductName }).first();
    await expect(productRow).toBeVisible({ timeout: 10_000 });
    await productRow.hover();

    // Click the delete button
    await productRow.getByRole('button', { name: /delete/i }).click();

    // Confirmation dialog should appear
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText('Delete product')).toBeVisible();
  });

  test('confirmation dialog requires typing product name', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    const productRow = page.locator('[role="button"]').filter({ hasText: deletableProductName }).first();
    await expect(productRow).toBeVisible({ timeout: 10_000 });
    await productRow.hover();
    await productRow.getByRole('button', { name: /delete/i }).click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 5_000 });

    // Delete button should be disabled initially
    const confirmBtn = dialog.getByRole('button', { name: /^delete$/i });
    await expect(confirmBtn).toBeDisabled();

    // Type partial name — still disabled
    const input = dialog.locator('#confirm-delete-input');
    await input.fill('wrong name');
    await expect(confirmBtn).toBeDisabled();

    // Type correct name — enabled
    await input.clear();
    await input.fill(deletableProductName);
    await expect(confirmBtn).toBeEnabled();
  });

  test('cancel button on confirmation dialog closes it', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    const productRow = page.locator('[role="button"]').filter({ hasText: deletableProductName }).first();
    await expect(productRow).toBeVisible({ timeout: 10_000 });
    await productRow.hover();
    await productRow.getByRole('button', { name: /delete/i }).click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 5_000 });

    // Click Cancel
    await dialog.getByRole('button', { name: /cancel/i }).click();

    // Dialog should close
    await expect(dialog).not.toBeVisible({ timeout: 3_000 });

    // Product still in list
    await expect(page.getByText(deletableProductName)).toBeVisible();
  });

  test('confirming delete removes product from list', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    // Verify product exists first
    await expect(page.getByText(deletableProductName)).toBeVisible({ timeout: 10_000 });

    const productRow = page.locator('[role="button"]').filter({ hasText: deletableProductName }).first();
    await productRow.hover();
    await productRow.getByRole('button', { name: /delete/i }).click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 5_000 });

    // Type exact product name to confirm
    await dialog.locator('#confirm-delete-input').fill(deletableProductName);

    // Click Delete
    await dialog.getByRole('button', { name: /^delete$/i }).click();

    // Product should disappear from the list
    await expect(page.getByText(deletableProductName)).not.toBeVisible({ timeout: 10_000 });
  });

  test('deleted product no longer appears in search', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    // Search for the deleted product name
    const searchInput = page.getByPlaceholder(/search/i);
    await searchInput.fill(deletableProductName);
    await page.waitForTimeout(600); // debounce

    // Should show no results or empty state
    const productText = page.getByText(deletableProductName);
    // Exclude the search input itself from the check
    const visibleProduct = page.locator('[role="button"]').filter({ hasText: deletableProductName });
    await expect(visibleProduct).not.toBeVisible({ timeout: 5_000 });
  });
});
