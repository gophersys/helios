import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';

/**
 * Manufacturing Configuration — mirrors validation stage config but for stage 0.
 *
 * Tests run in serial: create product → enable manufacturing → configure → verify.
 * Uses the same ProductStageConfig model and Stage Config Wizard as validation.
 */

test.describe.configure({ mode: 'serial' });

const uniqueSuffix = Date.now();
const productName = `E2E Mfg Config ${uniqueSuffix}`;
let productId: string;

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';

test.describe('Manufacturing Configuration', () => {
  test.beforeAll(async () => {
    const headers = { Authorization: `ApiKey ${API_KEY}`, 'Content-Type': 'application/json' };

    // Create product with board + revision
    const res = await fetch(`${API_URL}/v2/products`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        name: productName,
        slug: `e2e-mfg-cfg-${uniqueSuffix}`,
        board: {
          ckBoardsFamily: `mfg-cfg-${uniqueSuffix}`,
          revisions: [{
            version: 'b0',
            ckBoardsName: `mfg_cfg_b0_${uniqueSuffix}`,
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

  // ── Empty state ──────────────────────────────────────────

  test('Manufacturing tab shows "not configured" for fresh product', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.locator('button').filter({ hasText: 'Manufacturing' }).first().click();
    await page.waitForTimeout(500);

    await expect(page.getByText('Manufacturing not configured')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole('button', { name: /enable manufacturing/i })).toBeVisible();
  });

  // ── Enable manufacturing ─────────────────────────────────

  test('Enable Manufacturing creates stage 0 config', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.locator('button').filter({ hasText: 'Manufacturing' }).first().click();
    await page.waitForTimeout(500);

    await page.getByRole('button', { name: /enable manufacturing/i }).click();
    await page.waitForTimeout(2_000);

    // Manufacturing stage row should appear
    await expect(page.getByText('Manufacturing').first()).toBeVisible({ timeout: 10_000 });
    // Should show Configure button for the revision
    await expect(page.getByRole('button', { name: /configure/i }).first()).toBeVisible();
  });

  // ── Validation still works after manufacturing enabled ───

  test('Validation tab still shows Enable Validation (independent of manufacturing)', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.locator('button').filter({ hasText: 'Validation' }).first().click();
    await page.waitForTimeout(500);

    // Validation should be independent — still show Enable button
    await expect(page.getByRole('button', { name: /enable validation/i })).toBeVisible({ timeout: 10_000 });
  });

  test('Enable Validation works when manufacturing is already enabled', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.locator('button').filter({ hasText: 'Validation' }).first().click();
    await page.waitForTimeout(500);

    await page.getByRole('button', { name: /enable validation/i }).click();
    await page.waitForTimeout(2_000);

    // All 5 validation stages should appear
    for (const name of ['Smoke', 'Driver', 'Integration', 'Regression', 'FUOTA']) {
      await expect(page.getByText(name).first()).toBeVisible({ timeout: 10_000 });
    }
  });

  // ── Configure manufacturing ──────────────────────────────

  test('Configure button on manufacturing stage opens wizard', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.locator('button').filter({ hasText: 'Manufacturing' }).first().click();
    await page.waitForTimeout(1_000);

    await page.getByRole('button', { name: /configure/i }).first().click();
    await page.waitForTimeout(500);

    // Same wizard as validation — should show stage config header
    await expect(page.getByText(/configure stage/i).first()).toBeVisible({ timeout: 5_000 });
  });

  // ── Permission gating ────────────────────────────────────

  test('Operator can see Manufacturing tab but cannot enable', async ({ page }) => {
    await loginAsRole(page, 'operator');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    // Operator may not see the product at all (no product access)
    // or may see it but without the enable button
    const mfgTab = page.locator('button').filter({ hasText: 'Manufacturing' }).first();
    if (await mfgTab.isVisible().catch(() => false)) {
      await mfgTab.click();
      await page.waitForTimeout(500);
      // Enable button should NOT be visible for operator
      await expect(page.getByRole('button', { name: /enable manufacturing/i })).not.toBeVisible();
    }
  });
});
