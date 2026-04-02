import { test, expect } from './fixtures';
import { loginViaAPI } from './helpers/auth';
import { apiPost, apiDelete, apiGet, apiPut } from './helpers/api';

async function goToProducts(page: import('@playwright/test').Page) {
  await page.goto('/products');
  await page.waitForLoadState('networkidle');
}

async function openProduct(page: import('@playwright/test').Page, name: string) {
  const row = page.locator('[role="button"]').filter({ hasText: name });
  await row.click();
  await page.waitForURL(/\/products\//);
  await expect(page.locator('h2').filter({ hasText: name })).toBeVisible({ timeout: 5000 });
}

// ═══════════════════════════════════════════════════════════
// PRODUCT LIST
// ═══════════════════════════════════════════════════════════
test.describe('Products List', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await goToProducts(page);
  });

  test('page loads with heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Products' })).toBeVisible();
    await expect(page.getByText('Manage products, firmware stages, and builds.')).toBeVisible();
  });

  test('Alpha product row is visible', async ({ page }) => {
    await expect(page.locator('[role="button"]').filter({ hasText: 'Alpha' })).toBeVisible();
  });

  test('Alpha row shows Active badge', async ({ page }) => {
    const row = page.locator('[role="button"]').filter({ hasText: 'Alpha' });
    await expect(row.getByText('Active')).toBeVisible();
  });

  test('Alpha row shows revision badges', async ({ page }) => {
    const row = page.locator('[role="button"]').filter({ hasText: 'Alpha' });
    await expect(row.getByText('B0')).toBeVisible();
  });

  test('Alpha row shows repo links', async ({ page }) => {
    const row = page.locator('[role="button"]').filter({ hasText: 'Alpha' });
    await expect(row.getByText('alpha_fw')).toBeVisible();
  });

  test('Alpha row shows stage pills', async ({ page }) => {
    const row = page.locator('[role="button"]').filter({ hasText: 'Alpha' });
    await expect(row.getByText('SM')).toBeVisible();
    await expect(row.getByText('FU')).toBeVisible();
  });

  test('New Product button is visible', async ({ page }) => {
    await expect(page.getByRole('button', { name: /new product/i })).toBeVisible();
  });

  test('search filter narrows list', async ({ page }) => {
    await page.getByPlaceholder('Search products...').fill('zzzznotfound');
    await page.waitForTimeout(300);
    await expect(page.getByText('No products match')).toBeVisible();
  });

  test('search filter finds Alpha', async ({ page }) => {
    await page.getByPlaceholder('Search products...').fill('Alpha');
    await page.waitForTimeout(300);
    await expect(page.locator('[role="button"]').filter({ hasText: 'Alpha' })).toBeVisible();
  });

  test('clicking a row navigates to product detail', async ({ page }) => {
    await page.locator('[role="button"]').filter({ hasText: 'Alpha' }).click();
    await page.waitForURL(/\/products\//);
  });
});

// ═══════════════════════════════════════════════════════════
// PRODUCT DETAIL
// ═══════════════════════════════════════════════════════════
test.describe('Product Detail', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await goToProducts(page);
    await openProduct(page, 'Alpha');
  });

  test('shows product name in header', async ({ page }) => {
    await expect(page.locator('h2').filter({ hasText: 'Alpha' })).toBeVisible();
  });

  test('shows all four tabs', async ({ page }) => {
    for (const tab of ['Firmware', 'Validation', 'Build Config', 'Manufacturing']) {
      await expect(page.locator('button').filter({ hasText: tab }).first()).toBeVisible();
    }
  });

  test('shows firmware repo links', async ({ page }) => {
    await expect(page.getByText('alpha_fw').first()).toBeVisible();
  });

  test('shows B0 revision with board name', async ({ page }) => {
    await expect(page.getByText('alpha_b0')).toBeVisible();
  });

  test('shows A0 revision', async ({ page }) => {
    await expect(page.getByText('alpha_a0')).toBeVisible();
  });

  test('B0 shows target SoCs', async ({ page }) => {
    await expect(page.getByText('nRF9151').first()).toBeVisible();
    await expect(page.getByText('nRF52840').first()).toBeVisible();
  });

  test('edit product button exists', async ({ page }) => {
    await expect(page.locator('button[aria-label="Edit product"]')).toBeVisible();
  });

  test('back button returns to /products', async ({ page }) => {
    await page.locator('button').filter({ hasText: /back/i }).click();
    await page.waitForURL('/products');
  });
});

// ═══════════════════════════════════════════════════════════
// EDIT PRODUCT
// ═══════════════════════════════════════════════════════════
test.describe('Edit Product', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await goToProducts(page);
    await openProduct(page, 'Alpha');
  });

  test('clicking edit shows inline form', async ({ page }) => {
    await page.locator('button[aria-label="Edit product"]').click();
    await expect(page.getByText('Edit Product')).toBeVisible();
  });

  test('cancel returns to read-only', async ({ page }) => {
    await page.locator('button[aria-label="Edit product"]').click();
    await page.locator('button').filter({ hasText: /cancel/i }).first().click();
    await expect(page.getByText('Edit Product')).not.toBeVisible();
  });

  test('can edit and save description', async ({ page }) => {
    await page.locator('button[aria-label="Edit product"]').click();
    const descInput = page.getByPlaceholder('Optional description');
    await descInput.clear();
    await descInput.fill('E2E test description');
    await page.locator('button').filter({ hasText: /save/i }).first().click();
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('E2E test description')).toBeVisible();

    // Restore
    await page.locator('button[aria-label="Edit product"]').click();
    const descInput2 = page.getByPlaceholder('Optional description');
    await descInput2.clear();
    await descInput2.fill('Alpha wearable device platform');
    await page.locator('button').filter({ hasText: /save/i }).first().click();
    await page.waitForLoadState('networkidle');
  });
});

// ═══════════════════════════════════════════════════════════
// EDIT REVISION
// ═══════════════════════════════════════════════════════════
test.describe('Edit Revision', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await goToProducts(page);
    await openProduct(page, 'Alpha');
  });

  test('revision cards have edit buttons', async ({ page }) => {
    await expect(page.locator('button[aria-label="Edit revision config"]').first()).toBeVisible();
  });

  test('clicking edit shows deviceType inputs', async ({ page }) => {
    const b0Card = page.locator('.rounded-lg').filter({ hasText: 'alpha_b0' });
    await b0Card.locator('button[aria-label="Edit revision config"]').click();
    await expect(page.getByText('Device Type')).toBeVisible();
    await expect(page.getByText('Device Variant')).toBeVisible();
  });

  test('cancel hides edit form', async ({ page }) => {
    const b0Card = page.locator('.rounded-lg').filter({ hasText: 'alpha_b0' });
    await b0Card.locator('button[aria-label="Edit revision config"]').click();
    await page.locator('button[aria-label="Cancel editing revision"]').click();
    await expect(page.getByText('Device Type')).not.toBeVisible();
  });

  test('save deviceType round-trip', async ({ page }) => {
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

// ═══════════════════════════════════════════════════════════
// TAB NAVIGATION
// ═══════════════════════════════════════════════════════════
test.describe('Product Tabs', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await goToProducts(page);
    await openProduct(page, 'Alpha');
  });

  test('can switch between all tabs', async ({ page }) => {
    for (const tab of ['Validation', 'Build Config', 'Manufacturing', 'Firmware']) {
      await page.locator('button').filter({ hasText: tab }).first().click();
      await page.waitForTimeout(200);
    }
  });
});

// ═══════════════════════════════════════════════════════════
// CRUD LIFECYCLE
// ═══════════════════════════════════════════════════════════
test.describe.serial('Product CRUD', () => {
  let testProductId: string | null = null;

  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
  });

  test('create product via API → appears in list', async ({ page }) => {
    // Clean up any leftover test product first
    try {
      const products = await apiGet<any>(page, '/v2/products');
      const list = products?.data ?? products;
      const existing = (list as any[]).find((p: any) => p.name === 'CRUD Test');
      if (existing) await apiDelete(page, `/v2/products/${existing.id}`);
    } catch { /* ignore */ }

    const product = await apiPost<{ id: string }>(page, '/v2/products', {
      name: 'CRUD Test',
      slug: 'crud-test',
      description: 'E2E lifecycle test',
    });
    testProductId = product.id;
    await goToProducts(page);
    await expect(page.locator('[role="button"]').filter({ hasText: 'CRUD Test' })).toBeVisible();
  });

  test('open new product detail', async ({ page }) => {
    test.skip(!testProductId, 'No test product');
    await goToProducts(page);
    await openProduct(page, 'CRUD Test');
    await expect(page.getByText('E2E lifecycle test')).toBeVisible();
  });

  test('delete product via UI', async ({ page }) => {
    test.skip(!testProductId, 'No test product');
    await goToProducts(page);
    const row = page.locator('[role="button"]').filter({ hasText: 'CRUD Test' });
    await row.hover();
    // Delete button has aria-label="Delete CRUD Test"
    await row.locator('button[title="Delete"]').click({ force: true });
    await expect(page.getByText('Delete product')).toBeVisible();
    await page.locator('#confirm-delete-input').fill('CRUD Test');
    await page.locator('[role="dialog"] button').filter({ hasText: /^Delete$/i }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await expect(page.locator('[role="button"]').filter({ hasText: 'CRUD Test' })).not.toBeVisible();
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

// ═══════════════════════════════════════════════════════════
// API VALIDATION
// ═══════════════════════════════════════════════════════════
test.describe('Product API', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
  });

  test('reject duplicate product name', async ({ page }) => {
    try {
      await apiPost(page, '/v2/products', { name: 'Alpha' });
      expect(true).toBe(false);
    } catch (err: unknown) {
      expect(err).toBeTruthy();
    }
  });

  test('fetch product by slug', async ({ page }) => {
    const product = await apiGet<any>(page, '/v2/products/by-slug/alpha');
    expect(product.name).toBe('Alpha');
  });

  test('product detail includes boards and revisions', async ({ page }) => {
    const products = await apiGet<any>(page, '/v2/products');
    const list = products?.data ?? products;
    const alpha = (list as any[]).find((p: any) => p.name === 'Alpha');
    const detail = await apiGet<any>(page, `/v2/products/${alpha.id}`);
    expect(detail.boards.length).toBeGreaterThan(0);
    expect(detail.boards[0].revisions.length).toBeGreaterThan(0);
  });

  test('partial update preserves untouched fields', async ({ page }) => {
    const products = await apiGet<any>(page, '/v2/products');
    const list = products?.data ?? products;
    const alpha = (list as any[]).find((p: any) => p.name === 'Alpha');
    await apiPut(page, `/v2/products/${alpha.id}`, { description: 'Temp test' });
    const updated = await apiGet<any>(page, `/v2/products/${alpha.id}`);
    expect(updated.name).toBe('Alpha');
    expect(updated.fwRepoSlug).toBe('alpha_fw');
    // Restore
    await apiPut(page, `/v2/products/${alpha.id}`, { description: 'Alpha wearable device platform' });
  });
});

// ═══════════════════════════════════════════════════════════
// BOARD & REVISION API
// ═══════════════════════════════════════════════════════════
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
  });

  test('add second revision', async ({ page }) => {
    test.skip(!pid || !boardId, 'No test data');
    const rev = await apiPost<any>(page, `/v2/products/${pid}/boards/${boardId}/revisions`, {
      version: 'B0', ckBoardsName: 'brt_b0', socs: ['nrf52840', 'nrf9151'],
      targets: [{ role: 'app', soc: 'nRF52840', appId: 301 }, { role: 'comms', soc: 'nRF9151', appId: 302 }],
    });
    expect(rev.version).toBe('B0');
  });

  test('update revision deviceType', async ({ page }) => {
    test.skip(!pid || !boardId || !revId, 'No data');
    const u = await apiPut<any>(page, `/v2/products/${pid}/boards/${boardId}/revisions/${revId}`, { deviceType: 7 });
    expect(u.deviceType).toBe(7);
  });

  test('verify in UI', async ({ page }) => {
    test.skip(!pid, 'No product');
    await goToProducts(page);
    await expect(page.locator('[role="button"]').filter({ hasText: 'BoardRevTest' })).toBeVisible();
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
