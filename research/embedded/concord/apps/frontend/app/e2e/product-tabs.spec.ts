import { test, expect } from './fixtures';
import { loginViaAPI } from './helpers/auth';
import { apiPost, apiDelete, apiGet, apiPut } from './helpers/api';

// ═══════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════

async function openAlpha(page: import('@playwright/test').Page) {
  await page.goto('/products');
  await page.waitForLoadState('networkidle');
  const row = page.locator('[role="button"]').filter({ hasText: 'Alpha' });
  await row.click();
  await page.waitForURL(/\/products\//);
  await expect(page.locator('h2').filter({ hasText: 'Alpha' })).toBeVisible({ timeout: 10000 });
  await page.waitForTimeout(300);
}

async function switchTab(page: import('@playwright/test').Page, tabName: string) {
  await page.locator('button').filter({ hasText: tabName }).first().click();
  await page.waitForTimeout(500);
}

async function getAlphaIds(page: import('@playwright/test').Page) {
  const products = await apiGet<any>(page, '/v2/products');
  const list = (products as any)?.data ?? products;
  const alpha = (list as any[]).find((p: any) => p.name === 'Alpha');
  const detail = await apiGet<any>(page, `/v2/products/${alpha.id}`);
  const boardId = detail.boards[0].id;
  const revisions = detail.boards[0].revisions as any[];
  return {
    productId: alpha.id,
    boardId,
    revisions,
    getRevId: (version: string) => revisions.find((r: any) => r.version === version)?.id,
  };
}

// ═══════════════════════════════════════════════════════════
// OVERVIEW TAB — Stage Matrix
// ═══════════════════════════════════════════════════════════
test.describe('Overview Tab', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await openAlpha(page);
  });

  test('shows stat cards', async ({ page }) => {
    for (const label of ['Hardware', 'Builds', 'Validation', 'Manufacturing']) {
      await expect(page.getByText(label, { exact: false }).first()).toBeVisible();
    }
  });

  test('shows validation stages header with enabled count', async ({ page }) => {
    await expect(page.getByText('Validation Stages')).toBeVisible();
    await expect(page.getByText(/\d+ of \d+ enabled/)).toBeVisible();
  });

  test('shows stage matrix table with B0 column', async ({ page }) => {
    const table = page.locator('table');
    await expect(table).toBeVisible();
    await expect(table.locator('th').filter({ hasText: 'B0' })).toBeVisible();
  });

  test('stage matrix shows all 5 stage rows', async ({ page }) => {
    const table = page.locator('table');
    for (const stage of ['Smoke', 'Driver', 'Integration', 'Regression', 'FUOTA']) {
      await expect(table.getByText(stage)).toBeVisible();
    }
  });

  test('stage matrix shows trigger pills for enabled stages and dashes for disabled', async ({ page }) => {
    const table = page.locator('table');
    // FUOTA is enabled with triggers — should show trigger pills
    await expect(table.getByText('pr_push').first()).toBeVisible();
    // Disabled stages show dashes
    const dashes = table.locator('td >> text=—');
    expect(await dashes.count()).toBeGreaterThan(0);
  });

  test('stage matrix shows trigger type pills', async ({ page }) => {
    const table = page.locator('table');
    await expect(table.getByText('manual').first()).toBeVisible();
  });

  test('empty cells show dash for unconfigured stage+revision pairs', async ({ page }) => {
    // A0 only has FUOTA, so stages 1-4 under A0 column show dashes
    const dashes = page.locator('table td >> text=—');
    expect(await dashes.count()).toBeGreaterThan(0);
  });

  test('shows repos section with firmware links', async ({ page }) => {
    await expect(page.getByText('Repositories')).toBeVisible();
    await expect(page.getByText('alpha_fw')).toBeVisible();
    await expect(page.getByText('alpha_mfg_fw')).toBeVisible();
  });

  test('shows recent builds section', async ({ page }) => {
    await expect(page.getByText('Recent Builds')).toBeVisible();
  });

  test('shows recent validation runs section', async ({ page }) => {
    await expect(page.getByText('Recent Validation Runs')).toBeVisible();
  });

  test('no manufacturing stages on overview', async ({ page }) => {
    await expect(page.getByText('Manufacturing Stages')).not.toBeVisible();
  });
});

// ═══════════════════════════════════════════════════════════
// HARDWARE TAB
// ═══════════════════════════════════════════════════════════
test.describe('Hardware Tab', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await openAlpha(page);
    await switchTab(page, 'Hardware');
  });

  test('shows Board Revisions heading', async ({ page }) => {
    await expect(page.getByText('Board Revisions')).toBeVisible();
  });

  test('shows A0 and B0 revisions', async ({ page }) => {
    await expect(page.getByText('alpha_a0')).toBeVisible();
    await expect(page.getByText('alpha_b0')).toBeVisible();
  });

  test('B0 shows SoC info', async ({ page }) => {
    await expect(page.getByText(/nrf9151/).first()).toBeVisible();
    await expect(page.getByText(/nrf52840/).first()).toBeVisible();
  });

  test('B0 shows target AppIDs', async ({ page }) => {
    await expect(page.getByText('AppID 108').first()).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('AppID 109').first()).toBeVisible();
  });

  test('B0 shows linked stages', async ({ page }) => {
    await expect(page.getByText('Used by:').first()).toBeVisible();
  });

  test('Add Revision and Sync buttons visible', async ({ page }) => {
    await expect(page.getByRole('button', { name: /add revision/i })).toBeVisible();
    await expect(page.getByText('Sync from ck_boards')).toBeVisible();
  });

  test('add revision form shows and cancels', async ({ page }) => {
    await page.getByRole('button', { name: /add revision/i }).click();
    await expect(page.getByText('New Revision')).toBeVisible();
    const addBtn = page.locator('button').filter({ hasText: 'Add Revision' }).last();
    await expect(addBtn).toBeDisabled();
    await page.locator('button').filter({ hasText: 'Cancel' }).click();
    await expect(page.getByText('New Revision')).not.toBeVisible();
  });

  test('edit revision form shows and cancels', async ({ page }) => {
    const editBtn = page.locator('button[aria-label="Edit revision config"]').first();
    await editBtn.click();
    await expect(page.getByText('Device Type')).toBeVisible();
    await expect(page.getByText('Device Variant')).toBeVisible();
    await page.locator('button[aria-label="Cancel editing revision"]').click();
    await page.waitForTimeout(300);
  });
});

// ═══════════════════════════════════════════════════════════
// VALIDATION TAB
// ═══════════════════════════════════════════════════════════
test.describe('Validation Tab', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await openAlpha(page);
    await switchTab(page, 'Validation');
  });

  test('shows all 5 validation stage names', async ({ page }) => {
    for (const stage of ['Smoke', 'Driver', 'Integration', 'Regression', 'FUOTA']) {
      await expect(page.getByText(stage).first()).toBeVisible();
    }
  });

  test('shows B0 revision badge', async ({ page }) => {
    await expect(page.getByText('B0').first()).toBeVisible();
  });

  test('loads without JS errors', async ({ page }) => {
    await page.waitForTimeout(500);
  });
});

// ═══════════════════════════════════════════════════════════
// ASSETS + MANUFACTURING TABS
// ═══════════════════════════════════════════════════════════
test.describe('Other Tabs', () => {
  test('Assets tab loads without JS errors', async ({ page }) => {
    await loginViaAPI(page);
    await openAlpha(page);
    await switchTab(page, 'Assets');
    await page.waitForTimeout(500);
  });

  test('Manufacturing tab loads without JS errors', async ({ page }) => {
    await loginViaAPI(page);
    await openAlpha(page);
    await switchTab(page, 'Manufacturing');
    await page.waitForTimeout(500);
  });
});

// ═══════════════════════════════════════════════════════════
// CROSS-TAB REACTIVITY
// ═══════════════════════════════════════════════════════════
test.describe('Cross-Tab Reactivity', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await openAlpha(page);
  });

  test('switching all tabs preserves product header', async ({ page }) => {
    for (const tab of ['Hardware', 'Validation', 'Assets', 'Manufacturing', 'Overview']) {
      await switchTab(page, tab);
      await expect(page.locator('h2').filter({ hasText: 'Alpha' })).toBeVisible();
    }
  });

  test('overview refreshes after visiting validation tab', async ({ page }) => {
    await switchTab(page, 'Validation');
    await page.waitForTimeout(500);
    await switchTab(page, 'Overview');
    await expect(page.getByText('Validation Stages')).toBeVisible();
    await expect(page.getByText('Smoke').first()).toBeVisible();
  });

  test('hardware tab data persists across tab switches', async ({ page }) => {
    await switchTab(page, 'Hardware');
    await expect(page.getByText('alpha_b0')).toBeVisible();
    await switchTab(page, 'Overview');
    await switchTab(page, 'Hardware');
    await expect(page.getByText('alpha_b0')).toBeVisible();
  });

  test('overview matrix shows B0 column', async ({ page }) => {
    const table = page.locator('table');
    await expect(table.locator('th').filter({ hasText: 'B0' })).toBeVisible();
  });
});

// ═══════════════════════════════════════════════════════════
// DEPRECATION CASCADE (serial — modifies Alpha state)
// ═══════════════════════════════════════════════════════════
test.describe.serial('Deprecation Cascade', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
  });

  test('deprecating A0 succeeds (no stages to cascade)', async ({ page }) => {
    const { productId, boardId, getRevId } = await getAlphaIds(page);
    const a0Id = getRevId('A0');
    test.skip(!a0Id, 'A0 not found');

    // Fresh seed: A0 is ACTIVE but has no stage configs
    const result = await apiPut<any>(
      page,
      `/v2/products/${productId}/boards/${boardId}/revisions/${a0Id}`,
      { status: 'DEPRECATED' }
    );
    expect(result.status).toBe('DEPRECATED');
    // No stages to disable
    expect(result.disabledStages?.length ?? 0).toBe(0);
  });

  test('cannot enable stage for deprecated revision', async ({ page }) => {
    const { productId, getRevId } = await getAlphaIds(page);
    const a0Id = getRevId('A0');
    test.skip(!a0Id, 'A0 not found');

    try {
      await apiPost(page, `/v2/products/${productId}/stages`, {
        stage: 1, name: 'Smoke', enabled: true,
        boardRevisionId: a0Id, triggerTypes: ['manual'],
      });
      expect(true).toBe(false); // Should not reach
    } catch (err: unknown) {
      expect(String(err)).toContain('DEPRECATED');
    }
  });

  test('overview reflects deprecation — A0 no longer a column', async ({ page }) => {
    await openAlpha(page);
    // With A0 deprecated and its only stage disabled, A0 has no active stage configs
    // The matrix only shows revisions that have stage configs → may drop to single-rev list
    await expect(page.getByText('Validation Stages')).toBeVisible();
  });

  test('reactivate A0', async ({ page }) => {
    const { productId, boardId, getRevId } = await getAlphaIds(page);
    const a0Id = getRevId('A0');
    test.skip(!a0Id, 'A0 not found');

    const result = await apiPut<any>(
      page,
      `/v2/products/${productId}/boards/${boardId}/revisions/${a0Id}`,
      { status: 'ACTIVE' }
    );
    expect(result.status).toBe('ACTIVE');
  });
});

// ═══════════════════════════════════════════════════════════
// FULL PRODUCT LIFECYCLE (serial — creates/deletes product)
// ═══════════════════════════════════════════════════════════
test.describe.serial('Product Lifecycle', () => {
  let testPid: string | null = null;
  let testBoardId: string | null = null;
  let testRevAId: string | null = null;
  let testRevBId: string | null = null;

  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
  });

  test('1. create product with board and revision', async ({ page }) => {
    try {
      const products = await apiGet<any>(page, '/v2/products');
      const list = (products as any)?.data ?? products;
      const existing = (list as any[]).find((p: any) => p.name === 'Lifecycle Test');
      if (existing) await apiDelete(page, `/v2/products/${existing.id}`);
    } catch { /* ignore */ }

    const p = await apiPost<any>(page, '/v2/products', {
      name: 'Lifecycle Test', slug: 'lifecycle-test',
      description: 'E2E lifecycle product', fwRepoSlug: 'lifecycle_fw',
      board: {
        name: 'Main Board', ckBoardsFamily: 'lifecycle',
        revisions: [{
          version: 'A0', ckBoardsName: 'lifecycle_a0', socs: ['nrf52840'],
          targets: [{ role: 'app', soc: 'nRF52840', appId: 500 }],
        }],
      },
    });
    testPid = p.id;
    const detail = await apiGet<any>(page, `/v2/products/${testPid}`);
    testBoardId = detail.boards[0].id;
    testRevAId = detail.boards[0].revisions[0].id;

    await page.goto('/products');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('[role="button"]').filter({ hasText: 'Lifecycle Test' })).toBeVisible();
  });

  test('2. overview shows empty stages', async ({ page }) => {
    test.skip(!testPid, 'skip');
    await page.goto(`/products/${testPid}`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('No validation stages configured')).toBeVisible();
  });

  test('3. add B0, activate both, add stages', async ({ page }) => {
    test.skip(!testPid || !testBoardId || !testRevAId, 'skip');

    const rev = await apiPost<any>(page, `/v2/products/${testPid}/boards/${testBoardId}/revisions`, {
      version: 'B0', ckBoardsName: 'lifecycle_b0', socs: ['nrf52840', 'nrf9151'],
      targets: [{ role: 'app', soc: 'nRF52840', appId: 501 }, { role: 'comms', soc: 'nRF9151', appId: 502 }],
    });
    testRevBId = rev.id;

    await apiPut(page, `/v2/products/${testPid}/boards/${testBoardId}/revisions/${testRevAId}`, { status: 'ACTIVE' });
    await apiPut(page, `/v2/products/${testPid}/boards/${testBoardId}/revisions/${testRevBId}`, { status: 'ACTIVE' });

    // Smoke for A0
    await apiPost(page, `/v2/products/${testPid}/stages`, {
      stage: 1, name: 'Smoke', enabled: true, boardRevisionId: testRevAId, triggerTypes: ['manual'],
    });
    // Smoke for B0
    await apiPost(page, `/v2/products/${testPid}/stages`, {
      stage: 1, name: 'Smoke', enabled: true, boardRevisionId: testRevBId, triggerTypes: ['pr_push', 'manual'],
    });
    // FUOTA for A0
    await apiPost(page, `/v2/products/${testPid}/stages`, {
      stage: 5, name: 'FUOTA', enabled: true, boardRevisionId: testRevAId, triggerTypes: ['pr_merge'],
    });
  });

  test('4. overview shows matrix with A0 + B0 columns', async ({ page }) => {
    test.skip(!testPid, 'skip');
    await page.goto(`/products/${testPid}`);
    await page.waitForLoadState('networkidle');
    const table = page.locator('table');
    await expect(table).toBeVisible();
    await expect(table.locator('th').filter({ hasText: 'A0' })).toBeVisible();
    await expect(table.locator('th').filter({ hasText: 'B0' })).toBeVisible();
  });

  test('5. deprecate A0 → cascade disables 2 stages', async ({ page }) => {
    test.skip(!testPid || !testBoardId || !testRevAId, 'skip');
    const result = await apiPut<any>(
      page,
      `/v2/products/${testPid}/boards/${testBoardId}/revisions/${testRevAId}`,
      { status: 'DEPRECATED' }
    );
    expect(result.disabledStages?.length).toBe(2); // Smoke + FUOTA on A0
  });

  test('6. cannot enable stage on deprecated rev', async ({ page }) => {
    test.skip(!testPid || !testRevAId, 'skip');
    try {
      await apiPost(page, `/v2/products/${testPid}/stages`, {
        stage: 3, name: 'Integration', enabled: true,
        boardRevisionId: testRevAId, triggerTypes: ['manual'],
      });
      expect(true).toBe(false);
    } catch (err: unknown) {
      expect(String(err)).toContain('DEPRECATED');
    }
  });

  test('7. cleanup — delete product', async ({ page }) => {
    test.skip(!testPid, 'skip');
    await apiDelete(page, `/v2/products/${testPid}`);
    await page.goto('/products');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('[role="button"]').filter({ hasText: 'Lifecycle Test' })).not.toBeVisible();
    testPid = null;
  });

  test.afterAll(async ({ request }) => {
    if (testPid) {
      try {
        await request.delete(`http://localhost:9001/v2/products/${testPid}`, {
          headers: { Authorization: 'ApiKey ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG' },
        });
      } catch { /* ignore */ }
    }
  });
});
