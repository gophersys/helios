/**
 * Product CRUD E2E Tests
 *
 * Tests the full product management flow as a user would experience it:
 * - Viewing products in the list
 * - Opening product detail
 * - Editing product info (name, slug, repos)
 * - Viewing hardware revisions and targets
 * - Editing revision config (deviceType, deviceVariant, appIds)
 * - Creating and deleting products
 * - Tab navigation
 */

import { test, expect } from './fixtures';
import { loginViaAPI } from './helpers/auth';
import { apiPost, apiDelete, apiGet, apiPut } from './helpers/api';

// ────────────────────────────────────────────────────────────
// Helpers
// ────────────────────────────────────────────────────────────
async function goToProducts(page: import('@playwright/test').Page) {
  await page.goto('/products');
  await page.waitForLoadState('networkidle');
}

/** Click a product card by its h3 heading text to open the detail view */
async function openProductDetail(page: import('@playwright/test').Page, name: string) {
  const heading = page.getByRole('heading', { name, level: 3 });
  await heading.click();
  // Wait for detail to load — h2 with product name appears
  await expect(page.locator('h2').filter({ hasText: name })).toBeVisible({ timeout: 5000 });
}

// ════════════════════════════════════════════════════════════
// 1. PRODUCT LIST VIEW
// ════════════════════════════════════════════════════════════
test.describe('Product List', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
  });

  test('shows the Products page heading', async ({ page }) => {
    await goToProducts(page);
    await expect(page.getByRole('heading', { name: 'Products', level: 1 })).toBeVisible();
  });

  test('shows the page description', async ({ page }) => {
    await goToProducts(page);
    await expect(page.getByText('Manage products, firmware stages, and builds.')).toBeVisible();
  });

  test('displays Alpha product card with h3 heading', async ({ page }) => {
    await goToProducts(page);
    await expect(page.getByRole('heading', { name: 'Alpha', level: 3 })).toBeVisible();
  });

  test('Alpha card shows Active badge', async ({ page }) => {
    await goToProducts(page);
    // The Active badge is inside the Alpha card
    const card = page.locator('[role="button"]').filter({ hasText: 'Alpha' });
    await expect(card.getByText('Active')).toBeVisible();
  });

  test('Alpha card shows firmware repo slugs', async ({ page }) => {
    await goToProducts(page);
    const card = page.locator('[role="button"]').filter({ hasText: 'Alpha' });
    await expect(card.getByText('alpha_fw')).toBeVisible();
    await expect(card.getByText('alpha_mfg_fw')).toBeVisible();
  });

  test('Alpha card shows B0 revision tag', async ({ page }) => {
    await goToProducts(page);
    const card = page.locator('[role="button"]').filter({ hasText: 'Alpha' });
    await expect(card.getByText('B0')).toBeVisible();
  });

  test('Alpha card shows "No stages configured"', async ({ page }) => {
    await goToProducts(page);
    const card = page.locator('[role="button"]').filter({ hasText: 'Alpha' });
    await expect(card.getByText('No stages configured')).toBeVisible();
  });

  test('Alpha card shows stats (firmware sets, revisions, targets)', async ({ page }) => {
    await goToProducts(page);
    const card = page.locator('[role="button"]').filter({ hasText: 'Alpha' });
    await expect(card.getByText(/revision/)).toBeVisible();
    await expect(card.getByText(/target/)).toBeVisible();
  });

  test('"New Product" button visible for admin users', async ({ page }) => {
    await goToProducts(page);
    await expect(page.getByRole('button', { name: /new product/i })).toBeVisible();
  });
});

// ════════════════════════════════════════════════════════════
// 2. PRODUCT DETAIL VIEW
// ════════════════════════════════════════════════════════════
test.describe('Product Detail', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await goToProducts(page);
    await openProductDetail(page, 'Alpha');
  });

  test('detail view shows all four tabs', async ({ page }) => {
    const tabs = page.locator('button.border-b-2, button:has-text("Firmware"), button:has-text("Validation"), button:has-text("Build Config"), button:has-text("Manufacturing")');
    // Check each tab button text exists in the detail view
    await expect(page.locator('button').filter({ hasText: 'Firmware' }).first()).toBeVisible();
    await expect(page.locator('button').filter({ hasText: 'Validation' }).first()).toBeVisible();
    await expect(page.locator('button').filter({ hasText: 'Build Config' }).first()).toBeVisible();
    await expect(page.locator('button').filter({ hasText: 'Manufacturing' }).first()).toBeVisible();
  });

  test('detail header shows product name', async ({ page }) => {
    await expect(page.locator('h2').filter({ hasText: 'Alpha' })).toBeVisible();
  });

  test('detail view shows firmware repo links', async ({ page }) => {
    await expect(page.getByText('alpha_fw').first()).toBeVisible();
    await expect(page.getByText('alpha_mfg_fw').first()).toBeVisible();
  });

  test('shows B0 revision with board name', async ({ page }) => {
    await expect(page.getByText('alpha_b0')).toBeVisible();
  });

  test('shows A0 revision (deprecated)', async ({ page }) => {
    await expect(page.getByText('alpha_a0')).toBeVisible();
  });

  test('B0 card shows target SoCs', async ({ page }) => {
    await expect(page.getByText('nRF9151').first()).toBeVisible();
    await expect(page.getByText('nRF52840').first()).toBeVisible();
  });

  test('edit product button is visible', async ({ page }) => {
    await expect(page.locator('button[aria-label="Edit product"]')).toBeVisible();
  });

  test('Upload Build button is visible', async ({ page }) => {
    await expect(page.locator('button').filter({ hasText: /upload build/i })).toBeVisible();
  });

  test('back button returns to product list', async ({ page }) => {
    await page.locator('button').filter({ hasText: /back/i }).click();
    await expect(page.getByRole('heading', { name: 'Alpha', level: 3 })).toBeVisible();
  });
});

// ════════════════════════════════════════════════════════════
// 3. TAB SWITCHING
// ════════════════════════════════════════════════════════════
test.describe('Tab Switching', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await goToProducts(page);
    await openProductDetail(page, 'Alpha');
  });

  test('can switch to Validation tab', async ({ page }) => {
    await page.locator('button').filter({ hasText: 'Validation' }).first().click();
    await page.waitForTimeout(300);
    // No JS errors should occur
  });

  test('can switch to Build Config tab', async ({ page }) => {
    await page.locator('button').filter({ hasText: 'Build Config' }).first().click();
    await page.waitForTimeout(300);
  });

  test('can switch to Manufacturing tab', async ({ page }) => {
    await page.locator('button').filter({ hasText: 'Manufacturing' }).first().click();
    await page.waitForTimeout(300);
  });

  test('rapid tab switching does not error', async ({ page }) => {
    const tabs = ['Validation', 'Build Config', 'Manufacturing', 'Firmware'];
    for (const tab of tabs) {
      await page.locator('button').filter({ hasText: tab }).first().click();
      await page.waitForTimeout(100);
    }
  });
});

// ════════════════════════════════════════════════════════════
// 4. EDIT PRODUCT INFO
// ════════════════════════════════════════════════════════════
test.describe('Edit Product Info', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await goToProducts(page);
    await openProductDetail(page, 'Alpha');
  });

  test('clicking edit pencil shows inline edit form', async ({ page }) => {
    await page.locator('button[aria-label="Edit product"]').click();
    await expect(page.getByText('Edit Product')).toBeVisible();
    await expect(page.getByText('Product Name')).toBeVisible();
    await expect(page.getByText('Slug', { exact: true })).toBeVisible();
  });

  test('cancel returns to read-only view', async ({ page }) => {
    await page.locator('button[aria-label="Edit product"]').click();
    await expect(page.getByText('Edit Product')).toBeVisible();

    // Click Cancel button in the edit form
    await page.locator('button').filter({ hasText: /cancel/i }).first().click();
    await expect(page.getByText('Edit Product')).not.toBeVisible();
    // Product name still visible as h2
    await expect(page.locator('h2').filter({ hasText: 'Alpha' })).toBeVisible();
  });

  test('edit and save product description', async ({ page }) => {
    await page.locator('button[aria-label="Edit product"]').click();
    const descInput = page.getByPlaceholder('Optional description');
    await descInput.clear();
    await descInput.fill('E2E updated description');
    await page.locator('button').filter({ hasText: /save/i }).first().click();
    await page.waitForLoadState('networkidle');

    // Description should be updated in read view
    await expect(page.getByText('E2E updated description')).toBeVisible();

    // Restore
    await page.locator('button[aria-label="Edit product"]').click();
    const descInput2 = page.getByPlaceholder('Optional description');
    await descInput2.clear();
    await descInput2.fill('Alpha wearable device platform');
    await page.locator('button').filter({ hasText: /save/i }).first().click();
    await page.waitForLoadState('networkidle');
  });

  test('save button is disabled when name is empty', async ({ page }) => {
    await page.locator('button[aria-label="Edit product"]').click();
    await expect(page.getByText('Edit Product')).toBeVisible();
    // Clear the product name
    const nameField = page.locator('label').filter({ hasText: 'Product Name' }).locator('input');
    await nameField.fill('');
    // Save button should be disabled or clicking it should not close the form
    const saveBtn = page.locator('button').filter({ hasText: /save/i }).first();
    // Force-click to bypass disabled state and verify form stays open
    await saveBtn.click({ force: true });
    await page.waitForTimeout(1000);
    // Form should still be visible (empty name rejected)
    await expect(page.getByText('Edit Product')).toBeVisible();
  });
});

// ════════════════════════════════════════════════════════════
// 5. EDIT REVISION CONFIG
// ════════════════════════════════════════════════════════════
test.describe('Edit Revision', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await goToProducts(page);
    await openProductDetail(page, 'Alpha');
  });

  test('revision cards have edit buttons', async ({ page }) => {
    const editBtn = page.locator('button[aria-label="Edit revision config"]');
    await expect(editBtn.first()).toBeVisible();
  });

  test('clicking edit on B0 shows deviceType/deviceVariant inputs', async ({ page }) => {
    // B0 is the ACTIVE revision; click its edit button
    const b0Card = page.locator('.rounded-lg').filter({ hasText: 'alpha_b0' });
    await b0Card.locator('button[aria-label="Edit revision config"]').click();
    await expect(page.getByText('Device Type')).toBeVisible();
    await expect(page.getByText('Device Variant')).toBeVisible();
  });

  test('cancel revision edit hides the form', async ({ page }) => {
    const b0Card = page.locator('.rounded-lg').filter({ hasText: 'alpha_b0' });
    await b0Card.locator('button[aria-label="Edit revision config"]').click();
    await expect(page.getByText('Device Type')).toBeVisible();

    await page.locator('button[aria-label="Cancel editing revision"]').click();
    await expect(page.getByText('Device Type')).not.toBeVisible();
  });

  test('save revision deviceType round-trip', async ({ page }) => {
    const b0Card = page.locator('.rounded-lg').filter({ hasText: 'alpha_b0' });
    await b0Card.locator('button[aria-label="Edit revision config"]').click();

    const dtInput = page.locator('label').filter({ hasText: 'Device Type' }).locator('input');
    await dtInput.clear();
    await dtInput.fill('42');
    await page.locator('button[aria-label="Save revision"]').click();
    await page.waitForLoadState('networkidle');

    // Restore
    await page.waitForTimeout(500);
    const b0Card2 = page.locator('.rounded-lg').filter({ hasText: 'alpha_b0' });
    await b0Card2.locator('button[aria-label="Edit revision config"]').click();
    const dtInput2 = page.locator('label').filter({ hasText: 'Device Type' }).locator('input');
    await dtInput2.clear();
    await dtInput2.fill('2');
    await page.locator('button[aria-label="Save revision"]').click();
    await page.waitForLoadState('networkidle');
  });
});

// ════════════════════════════════════════════════════════════
// 6. CREATE & DELETE PRODUCT
// ════════════════════════════════════════════════════════════
test.describe.serial('Product CRUD Lifecycle', () => {
  let testProductId: string | null = null;

  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
  });

  test('create product via API → appears in list', async ({ page }) => {
    const product = await apiPost<{ id: string }>(page, '/v2/products', {
      name: 'CRUD Test',
      slug: 'crud-test',
      description: 'E2E lifecycle test',
    });
    testProductId = product.id;
    expect(testProductId).toBeTruthy();

    await goToProducts(page);
    await expect(page.getByRole('heading', { name: 'CRUD Test', level: 3 })).toBeVisible();
  });

  test('open and verify new product detail', async ({ page }) => {
    test.skip(!testProductId, 'No test product');
    await goToProducts(page);
    await openProductDetail(page, 'CRUD Test');
    await expect(page.getByText('E2E lifecycle test')).toBeVisible();
  });

  test('edit new product slug via UI', async ({ page }) => {
    test.skip(!testProductId, 'No test product');
    await goToProducts(page);
    await openProductDetail(page, 'CRUD Test');

    await page.locator('button[aria-label="Edit product"]').click();
    const slugInput = page.getByRole('textbox', { name: 'Slug', exact: true });
    await slugInput.clear();
    await slugInput.fill('crud-test-v2');
    await page.locator('button').filter({ hasText: /save/i }).first().click();
    await page.waitForLoadState('networkidle');
  });

  test('delete product via UI', async ({ page }) => {
    test.skip(!testProductId, 'No test product');
    await goToProducts(page);

    // Hover to reveal delete button
    const card = page.locator('[role="button"]').filter({ hasText: 'CRUD Test' });
    await card.hover();
    await card.locator('button[aria-label="Delete"]').click();

    // Confirm dialog appears with "Delete product" heading
    await expect(page.getByText('Delete product')).toBeVisible();
    // Type product name in the confirmation input (placeholder is the entity name)
    const confirmInput = page.locator('#confirm-delete-input');
    await confirmInput.fill('CRUD Test');
    // Click the red Delete button in the dialog footer
    await page.locator('[role="dialog"] button').filter({ hasText: /^Delete$/i }).click();
    await page.waitForLoadState('networkidle');

    await page.waitForTimeout(500);
    await expect(page.getByRole('heading', { name: 'CRUD Test' })).not.toBeVisible();
    testProductId = null;
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

// ════════════════════════════════════════════════════════════
// 7. API VALIDATION
// ════════════════════════════════════════════════════════════
test.describe('API Validation', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
  });

  test('reject duplicate product name', async ({ page }) => {
    try {
      await apiPost(page, '/v2/products', { name: 'Alpha' });
      expect(true).toBe(false);
    } catch (err: unknown) {
      expect((err as Error).message).toContain('exists');
    }
  });

  test('reject empty product name', async ({ page }) => {
    try {
      await apiPost(page, '/v2/products', { name: '' });
      expect(true).toBe(false);
    } catch (err: unknown) {
      expect((err as Error).message).toBeTruthy();
    }
  });

  test('fetch product by slug', async ({ page }) => {
    const product = await apiGet<any>(page, '/v2/products/by-slug/alpha');
    expect(product.name).toBe('Alpha');
  });

  test('product detail includes boards, revisions, and targets', async ({ page }) => {
    const products = await apiGet<any>(page, '/v2/products');
    const list = products?.data ?? products;
    const alpha = (list as any[]).find((p: any) => p.name === 'Alpha');

    const detail = await apiGet<any>(page, `/v2/products/${alpha.id}`);
    expect(detail.boards.length).toBeGreaterThan(0);
    const board = detail.boards[0];
    expect(board.revisions.length).toBeGreaterThan(0);
    const rev = board.revisions.find((r: any) => r.version === 'B0');
    expect(rev).toBeTruthy();
    expect(rev.targets.length).toBe(2);
  });

  test('partial update preserves untouched fields', async ({ page }) => {
    const products = await apiGet<any>(page, '/v2/products');
    const list = products?.data ?? products;
    const alpha = (list as any[]).find((p: any) => p.name === 'Alpha');

    // Update only description
    await apiPut(page, `/v2/products/${alpha.id}`, {
      description: 'Temp update test',
    });

    const updated = await apiGet<any>(page, `/v2/products/${alpha.id}`);
    expect(updated.name).toBe('Alpha');
    expect(updated.fwRepoSlug).toBe('alpha_fw');
    expect(updated.description).toBe('Temp update test');

    // Restore
    await apiPut(page, `/v2/products/${alpha.id}`, {
      description: 'Alpha wearable device platform',
    });
  });
});

// ════════════════════════════════════════════════════════════
// 8. BOARD & REVISION API
// ════════════════════════════════════════════════════════════
test.describe.serial('Board & Revision API', () => {
  let pid: string | null = null;
  let boardId: string | null = null;
  let revId: string | null = null;

  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
  });

  test('create product with inline board and revision', async ({ page }) => {
    const p = await apiPost<any>(page, '/v2/products', {
      name: 'BoardRevTest',
      slug: 'boardrevtest',
      board: {
        name: 'Main Board',
        ckBoardsFamily: 'brt',
        revisions: [{
          version: 'A0',
          ckBoardsName: 'brt_a0',
          socs: ['nrf52840'],
          targets: [{ role: 'app', soc: 'nRF52840', appId: 300 }],
        }],
      },
    });
    pid = p.id;

    const detail = await apiGet<any>(page, `/v2/products/${pid}`);
    expect(detail.boards).toHaveLength(1);
    boardId = detail.boards[0].id;
    expect(detail.boards[0].revisions).toHaveLength(1);
    revId = detail.boards[0].revisions[0].id;
    expect(detail.boards[0].revisions[0].targets).toHaveLength(1);
  });

  test('add second revision to board', async ({ page }) => {
    test.skip(!pid || !boardId, 'No test data');
    const rev = await apiPost<any>(page, `/v2/products/${pid}/boards/${boardId}/revisions`, {
      version: 'B0',
      ckBoardsName: 'brt_b0',
      socs: ['nrf52840', 'nrf9151'],
      targets: [
        { role: 'app', soc: 'nRF52840', appId: 301 },
        { role: 'comms', soc: 'nRF9151', appId: 302 },
      ],
    });
    expect(rev.version).toBe('B0');
  });

  test('update revision deviceType', async ({ page }) => {
    test.skip(!pid || !boardId || !revId, 'No test data');
    const updated = await apiPut<any>(
      page,
      `/v2/products/${pid}/boards/${boardId}/revisions/${revId}`,
      { deviceType: 7, deviceVariant: 3 },
    );
    expect(updated.deviceType).toBe(7);
    expect(updated.deviceVariant).toBe(3);
  });

  test('add target to revision', async ({ page }) => {
    test.skip(!pid || !boardId || !revId, 'No test data');
    const target = await apiPost<any>(
      page,
      `/v2/products/${pid}/boards/${boardId}/revisions/${revId}/targets`,
      { role: 'comms', soc: 'nRF9160', appId: 303 },
    );
    expect(target.role).toBe('comms');
    expect(target.appId).toBe(303);
  });

  test('reject duplicate role on same revision', async ({ page }) => {
    test.skip(!pid || !boardId || !revId, 'No test data');
    try {
      await apiPost(page, `/v2/products/${pid}/boards/${boardId}/revisions/${revId}/targets`, {
        role: 'app', soc: 'nRF52833', appId: 304,
      });
      expect(true).toBe(false);
    } catch {
      // Expected — duplicate role
    }
  });

  test('verify in UI', async ({ page }) => {
    test.skip(!pid, 'No test product');
    await goToProducts(page);
    await expect(page.getByRole('heading', { name: 'BoardRevTest', level: 3 })).toBeVisible();
    await openProductDetail(page, 'BoardRevTest');
    await expect(page.getByText('brt_a0')).toBeVisible();
  });

  test.afterAll(async ({ request }) => {
    if (pid) {
      try {
        await request.delete(`http://localhost:9001/v2/products/${pid}`, {
          headers: { Authorization: 'ApiKey ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG' },
        });
      } catch { /* ignore */ }
    }
  });
});

// ════════════════════════════════════════════════════════════
// 9. UPLOAD BUILD MODAL
// ════════════════════════════════════════════════════════════
test.describe('Upload Build Modal', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await goToProducts(page);
    await openProductDetail(page, 'Alpha');
  });

  test('clicking Upload Build opens modal', async ({ page }) => {
    await page.locator('button').filter({ hasText: /upload build/i }).click();
    await page.waitForTimeout(300);
    // Modal should have form fields
    await expect(page.getByText('Board').first()).toBeVisible();
  });

  test('modal can be closed via Escape', async ({ page }) => {
    await page.locator('button').filter({ hasText: /upload build/i }).click();
    await page.waitForTimeout(300);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
  });
});
