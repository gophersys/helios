import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import { createProductViaAPI } from '../../helpers/api-extended';

/**
 * Product Edit — inline editing of product fields on the detail page.
 * Tests verify role-based edit permissions and save/cancel behavior.
 */

test.describe.configure({ mode: 'serial' });

test.describe('Product Edit', () => {
  const uniqueSuffix = Date.now();
  const originalName = `E2E Edit Test ${uniqueSuffix}`;
  let productId: string;

  test.beforeAll(async () => {
    const product = await createProductViaAPI({
      name: originalName,
      slug: `e2e-edit-${uniqueSuffix}`,
      description: 'Original description for edit tests',
    });
    productId = product.id;
  });

  test('Admin can see edit button on product detail', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    // Edit button (Pencil icon) should be visible next to product name
    const editBtn = page.getByRole('button', { name: /edit product/i });
    await expect(editBtn).toBeVisible({ timeout: 10_000 });
  });

  test('Admin can edit product name inline', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    // Click edit button
    await page.getByRole('button', { name: /edit product/i }).click();

    // Edit form should appear with "Edit Product" heading
    await expect(page.getByText('Edit Product')).toBeVisible();

    // Find the Product Name input and change it
    const nameInput = page.locator('span:has-text("Product Name") + input, label:has-text("Product Name") input').first();
    // Alternative approach: look for the input within the edit form
    const editForm = page.locator('.space-y-3').first();
    const firstInput = editForm.locator('input[type="text"]').first();
    await firstInput.clear();
    const updatedName = `E2E Edit Updated ${uniqueSuffix}`;
    await firstInput.fill(updatedName);
  });

  test('Admin can edit product description', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /edit product/i }).click();
    await expect(page.getByText('Edit Product')).toBeVisible();

    // Description input
    const descInput = page.locator('input[placeholder="Optional description"]');
    await expect(descInput).toBeVisible();
    await descInput.clear();
    await descInput.fill('Updated description via E2E test');
  });

  test('Admin can edit firmware repo slug', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /edit product/i }).click();
    await expect(page.getByText('Edit Product')).toBeVisible();

    // Firmware Repo Slug input
    const fwInput = page.locator('input[placeholder*="alpha_fw"]').first();
    await expect(fwInput).toBeVisible();
    await fwInput.clear();
    await fwInput.fill('test_fw_repo');
  });

  test('save button submits changes and shows success', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /edit product/i }).click();
    await expect(page.getByText('Edit Product')).toBeVisible();

    // Update the description
    const descInput = page.locator('input[placeholder="Optional description"]');
    await descInput.clear();
    await descInput.fill('Saved description via E2E');

    // Click Save
    await page.getByRole('button', { name: /save/i }).click();

    // Edit form should close (Edit Product heading gone)
    await expect(page.getByText('Edit Product')).not.toBeVisible({ timeout: 5_000 });

    // The updated description should appear in the detail view
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('Saved description via E2E')).toBeVisible({ timeout: 10_000 });
  });

  test('cancel button reverts changes', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    // Get the current description before editing
    const currentDesc = page.getByText('Saved description via E2E');
    await expect(currentDesc).toBeVisible({ timeout: 10_000 });

    await page.getByRole('button', { name: /edit product/i }).click();
    await expect(page.getByText('Edit Product')).toBeVisible();

    // Change description
    const descInput = page.locator('input[placeholder="Optional description"]');
    await descInput.clear();
    await descInput.fill('This should be reverted');

    // Click Cancel
    await page.getByRole('button', { name: /cancel/i }).first().click();

    // Edit form should close
    await expect(page.getByText('Edit Product')).not.toBeVisible({ timeout: 5_000 });

    // Original description should still show (not the reverted one)
    await expect(page.getByText('Saved description via E2E')).toBeVisible();
    await expect(page.getByText('This should be reverted')).not.toBeVisible();
  });

  test('Maintainer can edit product fields', async ({ page }) => {
    await loginAsRole(page, 'maintainer');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    // Maintainer should see the edit button
    const editBtn = page.getByRole('button', { name: /edit product/i });
    await expect(editBtn).toBeVisible({ timeout: 10_000 });

    // Click and verify edit form opens
    await editBtn.click();
    await expect(page.getByText('Edit Product')).toBeVisible();
  });

  test('Developer cannot edit product fields (no edit button visible)', async ({ page }) => {
    await loginAsRole(page, 'developer');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    // Wait for page to fully load
    await expect(page.getByText(/E2E Edit/i).first()).toBeVisible({ timeout: 10_000 });

    // Developer should NOT see the edit button
    const editBtn = page.getByRole('button', { name: /edit product/i });
    await expect(editBtn).not.toBeVisible();
  });

  test('editing name to empty shows disabled save', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /edit product/i }).click();
    await expect(page.getByText('Edit Product')).toBeVisible();

    // Clear the name field entirely
    const editForm = page.locator('.space-y-3').first();
    const nameInput = editForm.locator('input[type="text"]').first();
    await nameInput.clear();

    // Save button should be disabled when name is empty
    const saveBtn = page.getByRole('button', { name: /save/i });
    await expect(saveBtn).toBeDisabled();
  });
});
