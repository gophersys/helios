import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import { createProductViaAPI } from '../../helpers/api-extended';

/**
 * Asset Management — per-revision tabs, modem upload, stage assets.
 *
 * Tests the redesigned Assets tab with revision tabs and upload flows.
 */

test.describe.configure({ mode: 'serial' });

const uniqueSuffix = Date.now();
let productId: string;

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';

test.describe('Asset Management', () => {
  test.beforeAll(async () => {
    const headers = { Authorization: `ApiKey ${API_KEY}`, 'Content-Type': 'application/json' };

    const res = await fetch(`${API_URL}/v2/products`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        name: `E2E Asset Test ${uniqueSuffix}`,
        slug: `e2e-asset-${uniqueSuffix}`,
        board: {
          ckBoardsFamily: `asset-${uniqueSuffix}`,
          revisions: [{
            version: 'b0',
            ckBoardsName: `asset_b0_${uniqueSuffix}`,
            socs: ['nrf52840'],
          }],
        },
      }),
    });
    const body = await res.json();
    productId = body.data.id;
  });

  test.afterAll(async () => {
    try {
      await fetch(`${API_URL}/v2/products/${productId}`, {
        method: 'DELETE',
        headers: { Authorization: `ApiKey ${API_KEY}` },
      });
    } catch { /* best effort */ }
  });

  test('Assets tab shows revision tabs', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.locator('button').filter({ hasText: 'Assets' }).first().click();
    await page.waitForTimeout(500);

    // Should show at least one revision tab
    await expect(page.getByText('b0').first()).toBeVisible({ timeout: 10_000 });
  });

  test('Modem firmware section shows upload button', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.locator('button').filter({ hasText: 'Assets' }).first().click();
    await page.waitForTimeout(500);

    await expect(page.getByText('Modem Firmware')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole('button', { name: /upload/i })).toBeVisible();
  });

  test('No stages shows appropriate message', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.locator('button').filter({ hasText: 'Assets' }).first().click();
    await page.waitForTimeout(500);

    await expect(page.getByText(/no stages configured/i)).toBeVisible({ timeout: 10_000 });
  });

  test('After enabling validation, stage sections appear in Assets tab', async ({ page }) => {
    await loginAsRole(page, 'admin');

    // Enable validation first
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');
    await page.locator('button').filter({ hasText: 'Validation' }).first().click();
    await page.waitForTimeout(500);
    await page.getByRole('button', { name: /enable validation/i }).click();
    await page.waitForTimeout(2_000);

    // Now check Assets tab
    await page.locator('button').filter({ hasText: 'Assets' }).first().click();
    await page.waitForTimeout(1_000);

    // Should show stage sections with Upload buttons
    await expect(page.getByText('Smoke').first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('Upload .zip').first()).toBeVisible();
  });

  test('Fixtures tab shows per-revision tabs', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.locator('button').filter({ hasText: 'Fixtures' }).first().click();
    await page.waitForTimeout(500);

    await expect(page.getByText('b0').first()).toBeVisible({ timeout: 10_000 });
  });
});
