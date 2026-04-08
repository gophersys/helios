import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import {
  createProductViaAPI,
  concordPost,
  concordGet,
  concordDelete,
} from '../../helpers/api-extended';

/**
 * Manufacturing Setup — Configuration wizard E2E.
 *
 * Tests run in serial because they are cumulative: each wizard step builds on
 * the previous one. A product with a board revision is created via API, then
 * the Manufacturing tab and config wizard are exercised through the UI.
 */

test.describe.configure({ mode: 'serial' });

// We need concordPost/concordGet not exported — use internal API helpers.
// Re-declare thin wrappers here since the helpers file doesn't export them.
const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';

async function apiPost<T = unknown>(path: string, data: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: {
      Authorization: `ApiKey ${API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(`POST ${path} failed (${res.status}): ${JSON.stringify(body)}`);
  return body.data;
}

async function apiGet<T = unknown>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { Authorization: `ApiKey ${API_KEY}` },
  });
  const body = await res.json();
  if (!res.ok) throw new Error(`GET ${path} failed (${res.status}): ${JSON.stringify(body)}`);
  return body.data;
}

async function apiDelete(path: string): Promise<void> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'DELETE',
    headers: { Authorization: `ApiKey ${API_KEY}` },
  });
  if (!res.ok && res.status !== 404) {
    const body = await res.text();
    throw new Error(`DELETE ${path} failed (${res.status}): ${body}`);
  }
}

test.describe('Manufacturing Setup: Config Wizard', () => {
  const suffix = `e2e-mfg-${Date.now()}`;
  let productId: string;
  let boardRevisionId: string;

  test.beforeAll(async () => {
    // Create product with a board + revision via API
    const product = await createProductViaAPI({
      name: `MFG Setup Product ${suffix}`,
      slug: `mfg-setup-${suffix}`,
    });
    productId = product.id;

    // Create a board family
    const board = await apiPost<{ id: string }>(`/v2/products/${productId}/boards`, {
      name: `Alpha Board ${suffix}`,
      chipset: 'nRF52840',
    });

    // Create a board revision
    const revision = await apiPost<{ id: string }>(
      `/v2/products/${productId}/boards/${board.id}/revisions`,
      {
        version: 'B0',
        status: 'ACTIVE',
      },
    );
    boardRevisionId = revision.id;
  });

  test.afterAll(async () => {
    // Cleanup: delete manufacturing config, then product
    try {
      await apiDelete(`/v2/products/${productId}/manufacturing`);
    } catch {
      // May not exist
    }
    try {
      await apiDelete(`/v2/products/${productId}`);
    } catch {
      // Best effort
    }
  });

  test('navigate to product detail and Manufacturing tab exists', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    // The product detail page should have a Manufacturing tab
    const mfgTab = page.getByText('Manufacturing', { exact: true }).first();
    await expect(mfgTab).toBeVisible({ timeout: 10_000 });
  });

  test('Manufacturing tab shows "not configured" initially', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    // Switch to Manufacturing tab
    const mfgTab = page.getByText('Manufacturing', { exact: true }).first();
    await mfgTab.click();
    await page.waitForTimeout(500);

    // Should show "Manufacturing not configured"
    const notConfigured = page.getByText(/not configured/i);
    await expect(notConfigured).toBeVisible({ timeout: 10_000 });
  });

  test('open Manufacturing Config Wizard', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    // Switch to Manufacturing tab
    await page.getByText('Manufacturing', { exact: true }).first().click();
    await page.waitForTimeout(500);

    // Click "Configure Manufacturing" button
    const configBtn = page.getByRole('button', { name: /configure manufacturing/i });
    await expect(configBtn).toBeVisible({ timeout: 5_000 });
    await configBtn.click();

    // Wizard modal should open with step 1
    const wizardTitle = page.getByText(/configure.*manufacturing/i).first();
    await expect(wizardTitle).toBeVisible({ timeout: 5_000 });

    // Step indicator should show "Base Config"
    const step1 = page.getByText('Base Config');
    await expect(step1).toBeVisible();
  });

  test('Step 1: select board revision', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.getByText('Manufacturing', { exact: true }).first().click();
    await page.waitForTimeout(500);

    await page.getByRole('button', { name: /configure manufacturing/i }).click();
    await page.waitForTimeout(300);

    // Select board revision from dropdown
    const revSelect = page.locator('select').first();
    await revSelect.selectOption({ label: /B0/i });

    // Next button should be enabled now
    const nextBtn = page.getByRole('button', { name: /next/i });
    await expect(nextBtn).toBeEnabled();
  });

  test('Step 2: configure stages (Electrical + Flash + POST)', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.getByText('Manufacturing', { exact: true }).first().click();
    await page.waitForTimeout(500);
    await page.getByRole('button', { name: /configure manufacturing/i }).click();
    await page.waitForTimeout(300);

    // Step 1: select revision and proceed
    const revSelect = page.locator('select').first();
    await revSelect.selectOption({ label: /B0/i });
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForTimeout(300);

    // Step 2: stages should be visible
    const stageConfig = page.getByText('Stage Configuration');
    await expect(stageConfig).toBeVisible({ timeout: 5_000 });

    // All three stages should be listed: electrical, flash, post
    await expect(page.getByText(/electrical/i).first()).toBeVisible();
    await expect(page.getByText(/flash/i).first()).toBeVisible();
    await expect(page.getByText(/post/i).first()).toBeVisible();
  });

  test('Step 2: firmware source defaults to latest build', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.getByText('Manufacturing', { exact: true }).first().click();
    await page.waitForTimeout(500);
    await page.getByRole('button', { name: /configure manufacturing/i }).click();
    await page.waitForTimeout(300);

    // Navigate to step 2
    await page.locator('select').first().selectOption({ label: /B0/i });
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForTimeout(300);

    // Firmware source section should be visible with "Latest Build" default
    const fwSection = page.getByText('Firmware Source');
    await expect(fwSection).toBeVisible();

    // "Latest Build" or "latest_build" should be selected
    await expect(page.getByText(/latest.*build/i).first()).toBeVisible();
  });

  test('Step 3: set pass criteria', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.getByText('Manufacturing', { exact: true }).first().click();
    await page.waitForTimeout(500);
    await page.getByRole('button', { name: /configure manufacturing/i }).click();
    await page.waitForTimeout(300);

    // Step 1 -> Step 2 -> Step 3
    await page.locator('select').first().selectOption({ label: /B0/i });
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForTimeout(300);
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForTimeout(300);

    // Step 3: Pass Criteria & Personalization
    const criteriaTitle = page.getByText(/pass criteria/i).first();
    await expect(criteriaTitle).toBeVisible({ timeout: 5_000 });

    // "All stages must pass" checkbox should be visible
    await expect(page.getByText(/all stages must pass/i)).toBeVisible();

    // Max retries input
    await expect(page.getByText(/max retries/i)).toBeVisible();
  });

  test('Step 4: review and save creates config', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/products/${productId}`);
    await page.waitForLoadState('networkidle');

    await page.getByText('Manufacturing', { exact: true }).first().click();
    await page.waitForTimeout(500);
    await page.getByRole('button', { name: /configure manufacturing/i }).click();
    await page.waitForTimeout(300);

    // Navigate through all steps
    // Step 1: select revision
    await page.locator('select').first().selectOption({ label: /B0/i });
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForTimeout(300);

    // Step 2: stages (defaults are fine)
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForTimeout(300);

    // Step 3: pass criteria (defaults are fine)
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForTimeout(300);

    // Step 4: Review & Save
    const reviewTitle = page.getByText('Review Configuration');
    await expect(reviewTitle).toBeVisible({ timeout: 5_000 });

    // Should show the board revision
    await expect(page.getByText('B0')).toBeVisible();

    // Click save
    const saveBtn = page.getByRole('button', { name: /create.*configuration/i });
    await expect(saveBtn).toBeVisible();
    await saveBtn.click();

    // Wait for save to complete — modal should close
    await page.waitForTimeout(2_000);

    // Manufacturing tab should now show config summary (not "not configured")
    const enabledBadge = page.getByText('Enabled').first();
    await expect(enabledBadge).toBeVisible({ timeout: 10_000 });
  });
});
