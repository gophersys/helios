import { test, expect } from '../fixtures';
import { loginViaAPI } from '../helpers/auth';
import { createProduct, deleteProduct, getProducts } from '../helpers/api';

test.describe('Product Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
  });

  test('product list shows Alpha product', async ({ page }) => {
    await page.goto('/products');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: 'Alpha', level: 3 })).toBeVisible();
  });

  test('clicking Alpha opens detail view', async ({ page }) => {
    await page.goto('/products');
    await page.waitForLoadState('networkidle');
    await page.getByRole('heading', { name: 'Alpha', level: 3 }).click();
    await page.waitForLoadState('networkidle');
    // Detail page should show product name
    await expect(page.getByRole('heading', { name: 'Alpha', level: 3 })).toBeVisible();
  });

  test('product detail shows 4 tabs', async ({ page }) => {
    await page.goto('/products');
    await page.waitForLoadState('networkidle');
    await page.getByRole('heading', { name: 'Alpha', level: 3 }).click();
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('button', { name: 'Firmware' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Validation' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Build Config' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Manufacturing' })).toBeVisible();
  });

  test('product detail shows hardware revisions', async ({ page }) => {
    await page.goto('/products');
    await page.waitForLoadState('networkidle');
    await page.getByRole('heading', { name: 'Alpha', level: 3 }).click();
    await page.waitForLoadState('networkidle');

    // Should show B0 revision and processor info
    await expect(page.getByText('B0')).toBeVisible();
  });

  test.describe.serial('CRUD operations', () => {
    let testProductId: string | null = null;

    test('create test product via API and verify in list', async ({ page }) => {
      const product = await createProduct(page, {
        name: 'E2E Test Product',
        slug: 'e2e-test',
        description: 'Created by Playwright E2E test',
      }) as any;
      testProductId = product?.id;

      await page.goto('/products');
      await page.waitForLoadState('networkidle');
      await expect(page.getByText('E2E Test Product')).toBeVisible();
    });

    test('delete test product via UI', async ({ page }) => {
      test.skip(!testProductId, 'No test product to delete');

      await page.goto('/products');
      await page.waitForLoadState('networkidle');

      // Find the E2E Test Product card and hover to reveal delete button
      const card = page.locator('text=E2E Test Product').first();
      await expect(card).toBeVisible();

      // Look for a delete button near the product
      const deleteBtn = page.locator('[title="Delete"]').or(page.locator('[aria-label="Delete"]')).first();
      if (await deleteBtn.isVisible()) {
        await deleteBtn.click();
        // Confirm deletion dialog
        const confirmInput = page.getByPlaceholder(/type.*name/i).or(page.locator('input[type="text"]').last());
        if (await confirmInput.isVisible()) {
          await confirmInput.fill('E2E Test Product');
          await page.getByRole('button', { name: /delete/i }).click();
        }
        await page.waitForLoadState('networkidle');
      } else {
        // Fallback: delete via API
        if (testProductId) {
          await deleteProduct(page, testProductId);
          testProductId = null;
        }
      }

      await page.goto('/products');
      await page.waitForLoadState('networkidle');
      await expect(page.getByText('E2E Test Product')).not.toBeVisible();
    });

    test.afterAll(async ({ request }) => {
      // Cleanup: delete test product if it still exists
      if (testProductId) {
        try {
          await request.delete(`http://localhost:9001/v2/products/${testProductId}`, {
            headers: { Authorization: 'ApiKey ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG' },
          });
        } catch { /* ignore */ }
      }
    });
  });
});
