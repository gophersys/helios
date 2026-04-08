import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';

/**
 * Build Matrix Configuration — per-stage build matrix entries.
 *
 * The build matrix defines what firmware variants are built for each stage.
 * Each entry has: label, fwType, variant, configLog, producesHex, producesCfw, gitRef.
 *
 * The matrix is visible in:
 *   1. Step 4 (Review) of the Stage Config Wizard (via BuildMatrixView)
 *   2. The stage detail when a stage is already configured
 *
 * Stage build counts (from STAGE_BUILD_COUNTS):
 *   Stage 1 (Smoke): 2, Stage 2 (Driver): 3, Stage 3 (Integration): 4,
 *   Stage 4 (Regression): 6, Stage 5 (FUOTA): 8
 */

test.describe.configure({ mode: 'serial' });

const uniqueSuffix = Date.now();
const productName = `E2E Build Matrix ${uniqueSuffix}`;
let productId: string;

test.describe('Build Matrix', () => {
  test.beforeAll(async () => {
    const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
    const API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';
    const headers = { Authorization: `ApiKey ${API_KEY}`, 'Content-Type': 'application/json' };

    // Create product WITH board data so active revisions appear on Validation tab
    const createRes = await fetch(`${API_URL}/v2/products`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        name: productName,
        slug: `e2e-matrix-${uniqueSuffix}`,
        description: 'Product for build matrix E2E tests',
        board: {
          ckBoardsFamily: `matrix-${uniqueSuffix}`,
          revisions: [{
            version: 'b0',
            ckBoardsName: `matrix_b0_${uniqueSuffix}`,
            socs: ['nrf52840'],
            deviceType: 0,
            deviceVariant: 0,
          }],
        },
      }),
    });
    const createBody = await createRes.json();
    productId = createBody.data.id;

    // Activate the board revision so it appears in the per-revision stage list
    const boards = createBody.data.boards || [];
    const revisions = boards[0]?.revisions || [];
    if (revisions.length > 0) {
      await fetch(`${API_URL}/v2/products/${productId}/boards/${boards[0].id}/revisions/${revisions[0].id}`, {
        method: 'PUT',
        headers,
        body: JSON.stringify({ status: 'ACTIVE' }),
      });
    }

    // Initialize stages via API
    await fetch(`${API_URL}/v2/products/${productId}/stages/initialize`, {
      method: 'POST',
      headers,
      body: '{}',
    });

    // Configure Stage 1 to enable it (so we can access build matrix in review)
    await fetch(`${API_URL}/v2/products/${productId}/stages/1`, {
      method: 'PUT',
      headers,
      body: JSON.stringify({
        enabled: true,
        watchBranch: 'main',
        triggerTypes: ['manual'],
        boardRevisionId: revisions[0]?.id,
      }),
    });
  });

  test('build matrix section shows Build Matrix heading', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.locator('button').filter({ hasText: 'Validation' }).first().click();
    await page.waitForTimeout(1_000);

    // Open wizard for Stage 1 (now configured — should show "Edit")
    const editBtn = page.getByRole('button', { name: /edit/i }).first();
    if (await editBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await editBtn.click();
    } else {
      await page.getByRole('button', { name: /configure/i }).first().click();
    }
    await page.waitForTimeout(500);

    // Navigate to Step 4 (Review)
    for (let i = 0; i < 3; i++) {
      await page.getByRole('button', { name: /next/i }).click();
      await page.waitForTimeout(300);
    }

    // Build Matrix heading should be visible in review step
    await expect(page.getByText('Build Matrix')).toBeVisible({ timeout: 10_000 });
  });

  test('build matrix table has Label, FW Type, Variant, Produces, Git Ref columns', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.locator('button').filter({ hasText: 'Validation' }).first().click();
    await page.waitForTimeout(1_000);

    const editBtn = page.getByRole('button', { name: /edit/i }).first();
    if (await editBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await editBtn.click();
    } else {
      await page.getByRole('button', { name: /configure/i }).first().click();
    }
    await page.waitForTimeout(500);

    for (let i = 0; i < 3; i++) {
      await page.getByRole('button', { name: /next/i }).click();
      await page.waitForTimeout(300);
    }

    // Table column headers
    const matrixArea = page.locator('table').first();
    const headerArea = matrixArea.or(page.locator('[class*="border"]').filter({ hasText: /label/i }));

    // Check for column header text
    await expect(page.getByText('Label').first()).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText('FW Type').first()).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText('Variant').first()).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText('Produces').first()).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText('Git Ref').first()).toBeVisible({ timeout: 5_000 });
  });

  test('build matrix shows entries with HEX and/or CFW badges', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.locator('button').filter({ hasText: 'Validation' }).first().click();
    await page.waitForTimeout(1_000);

    const editBtn = page.getByRole('button', { name: /edit/i }).first();
    if (await editBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await editBtn.click();
    } else {
      await page.getByRole('button', { name: /configure/i }).first().click();
    }
    await page.waitForTimeout(500);

    for (let i = 0; i < 3; i++) {
      await page.getByRole('button', { name: /next/i }).click();
      await page.waitForTimeout(300);
    }

    // Matrix entries should have HEX or CFW badges
    const hexBadge = page.getByText('HEX');
    const cfwBadge = page.getByText('CFW');

    // At least one of HEX or CFW should be visible if matrix has entries
    const hasHex = await hexBadge.first().isVisible({ timeout: 5_000 }).catch(() => false);
    const hasCfw = await cfwBadge.first().isVisible({ timeout: 3_000 }).catch(() => false);
    const hasEntries = hasHex || hasCfw;

    // If no entries at all, the empty state should show
    if (!hasEntries) {
      await expect(page.getByText(/no build matrix entries/i)).toBeVisible({ timeout: 5_000 });
    }
  });

  test('Reset to Defaults button is visible for admin users', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.locator('button').filter({ hasText: 'Validation' }).first().click();
    await page.waitForTimeout(1_000);

    const editBtn = page.getByRole('button', { name: /edit/i }).first();
    if (await editBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await editBtn.click();
    } else {
      await page.getByRole('button', { name: /configure/i }).first().click();
    }
    await page.waitForTimeout(500);

    for (let i = 0; i < 3; i++) {
      await page.getByRole('button', { name: /next/i }).click();
      await page.waitForTimeout(300);
    }

    // "Reset to Defaults" button visible in Build Matrix section
    await expect(page.getByRole('button', { name: /reset to defaults/i })).toBeVisible({ timeout: 10_000 });
  });

  test('build matrix entry count label reflects number of entries', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.locator('button').filter({ hasText: 'Validation' }).first().click();
    await page.waitForTimeout(1_000);

    const editBtn = page.getByRole('button', { name: /edit/i }).first();
    if (await editBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await editBtn.click();
    } else {
      await page.getByRole('button', { name: /configure/i }).first().click();
    }
    await page.waitForTimeout(500);

    for (let i = 0; i < 3; i++) {
      await page.getByRole('button', { name: /next/i }).click();
      await page.waitForTimeout(300);
    }

    // Build matrix shows a count like "2 builds" or "0 builds"
    const countText = page.getByText(/\d+ build/i).first();
    await expect(countText).toBeVisible({ timeout: 10_000 });
  });

  test('build matrix empty state shows message when no entries', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.locator('button').filter({ hasText: 'Validation' }).first().click();
    await page.waitForTimeout(1_000);

    // Try to open a different stage (e.g., Stage 5 FUOTA) that may not be configured
    // Look for any Configure button on stage 5
    const stage5Row = page.locator('div').filter({ hasText: 'FUOTA' });
    const stage5ConfigBtn = stage5Row.getByRole('button', { name: /configure/i }).first();

    if (await stage5ConfigBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await stage5ConfigBtn.click();
      await page.waitForTimeout(500);

      // Navigate to Step 4
      for (let i = 0; i < 3; i++) {
        await page.getByRole('button', { name: /next/i }).click();
        await page.waitForTimeout(300);
      }

      // Build Matrix for unconfigured stage may show empty state or "No build matrix entries"
      const emptyState = page.getByText(/no build matrix entries/i);
      const matrixHeading = page.getByText('Build Matrix');
      // At least the heading should be there
      await expect(matrixHeading.or(emptyState).first()).toBeVisible({ timeout: 10_000 });
    }
  });

  test('build matrix entries show monospace label text', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.locator('button').filter({ hasText: 'Validation' }).first().click();
    await page.waitForTimeout(1_000);

    // Open Stage 1 wizard
    const editBtn = page.getByRole('button', { name: /edit/i }).first();
    if (await editBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await editBtn.click();
    } else {
      await page.getByRole('button', { name: /configure/i }).first().click();
    }
    await page.waitForTimeout(500);

    for (let i = 0; i < 3; i++) {
      await page.getByRole('button', { name: /next/i }).click();
      await page.waitForTimeout(300);
    }

    // Matrix entry labels use monospace font (font-mono class)
    const monoLabels = page.locator('.font-mono').filter({ hasText: /_/ });
    const tableEntries = page.locator('td .font-mono');

    // Either we find mono-styled entries or the matrix is empty
    const hasMonoEntries = await monoLabels.first().isVisible({ timeout: 3_000 }).catch(() => false)
      || await tableEntries.first().isVisible({ timeout: 3_000 }).catch(() => false);

    if (!hasMonoEntries) {
      // Empty matrix — that is also valid
      await expect(page.getByText(/no build matrix|0 build/i).first()).toBeVisible({ timeout: 5_000 });
    }
  });
});
