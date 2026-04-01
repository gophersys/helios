import { test, expect } from '../fixtures';
import { loginViaAPI } from '../helpers/auth';
import { createProduct, deleteProduct } from '../helpers/api';

test.describe('Product Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
  });

  test('product list shows Alpha product', async ({ page }) => {
    await page.goto('/products');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: 'Alpha', level: 3 })).toBeVisible();
  });

  test('clicking Alpha opens detail view with tabs', async ({ page }) => {
    await page.goto('/products');
    await page.waitForLoadState('networkidle');
    await page.getByRole('heading', { name: 'Alpha', level: 3 }).click();
    await page.waitForLoadState('networkidle');

    // Detail page shows tab buttons
    await expect(page.getByRole('button', { name: 'Firmware' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Validation' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Build Config' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Manufacturing' })).toBeVisible();
  });

  test('product detail shows hardware revision B0', async ({ page }) => {
    await page.goto('/products');
    await page.waitForLoadState('networkidle');
    await page.getByRole('heading', { name: 'Alpha', level: 3 }).click();
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('B0')).toBeVisible();
  });

  test('product detail shows firmware repo', async ({ page }) => {
    await page.goto('/products');
    await page.waitForLoadState('networkidle');
    await page.getByRole('heading', { name: 'Alpha', level: 3 }).click();
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('alpha_fw')).toBeVisible();
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
      await expect(page.getByRole('heading', { name: 'E2E Test Product', level: 3 })).toBeVisible();
    });

    test('delete test product', async ({ page }) => {
      test.skip(!testProductId, 'No test product to delete');
      await deleteProduct(page, testProductId!);
      testProductId = null;

      await page.goto('/products');
      await page.waitForLoadState('networkidle');
      await expect(page.getByRole('heading', { name: 'E2E Test Product' })).not.toBeVisible();
    });

    test.afterAll(async ({ request }) => {
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
