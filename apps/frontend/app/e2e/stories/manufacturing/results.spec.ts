import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import {
  createProductViaAPI,
  createFixture,
  deleteFixture,
} from '../../helpers/api-extended';

/**
 * Manufacturing Results — End session, verify results, check fixture release.
 *
 * Tests run in serial: set up a session with panels → end → verify results.
 *
 * NOTE: Panel results are simulated via the reporter API since MTIB may not
 * be reachable from the codespace.
 */

test.describe.configure({ mode: 'serial' });

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
  const text = await res.text();
  let body: any;
  try { body = JSON.parse(text); } catch { throw new Error(`POST ${path} failed (${res.status}): ${text.slice(0, 200)}`); }
  if (!res.ok) throw new Error(`POST ${path} failed (${res.status}): ${JSON.stringify(body)}`);
  return body.data;
}

async function apiGet<T = unknown>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { Authorization: `ApiKey ${API_KEY}` },
  });
  const text = await res.text();
  let body: any;
  try { body = JSON.parse(text); } catch { throw new Error(`GET ${path} failed (${res.status}): ${text.slice(0, 200)}`); }
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

test.describe('Manufacturing Results: End Session & Verification', () => {
  const suffix = `e2e-mfg-res-${Date.now()}`;
  let productId: string;
  let fixtureId: string;
  let sessionId: string;

  test.beforeAll(async () => {
    // Create product
    const product = await createProductViaAPI({
      name: `MFG Results Product ${suffix}`,
      slug: `mfg-res-${suffix}`,
    });
    productId = product.id;

    // Create MANUFACTURING fixture
    const fixture = await createFixture({
      name: `MFG Results Fixture ${suffix}`,
      productId,
      type: 'MANUFACTURING',
      description: 'E2E results fixture',
      stationId: `RES-${suffix}`,
      slots: [{ slotIndex: 0, label: 'Slot A' }],
    });
    fixtureId = fixture.id;

    // Start session via API
    const session = await apiPost<{ id: string }>('/v2/manufacturing/sessions', {
      productId,
      fixtureId,
    });
    sessionId = session.id;

    // Run a panel with 2 units
    const panel = await apiPost<{ id: string; units: Array<{ id: string }> }>(
      `/v2/manufacturing/sessions/${sessionId}/panels`,
      { qrCode: 'E2E-RES-PANEL-001', unitCount: 2 },
    );

    // Simulate results: 1 pass, 1 fail
    const [unit0, unit1] = panel.units;

    for (const unitId of [unit0.id, unit1.id]) {
      await apiPost(`/v2/manufacturing/sessions/${sessionId}/report/stage-result`, {
        unitId,
        stageName: 'electrical',
        status: 'PASSED',
        durationMs: 1000,
      });
    }

    await apiPost(`/v2/manufacturing/sessions/${sessionId}/report/unit-result`, {
      unitId: unit0.id,
      status: 'PASSED',
      serialNumber: 'SN-RES-001',
      durationMs: 5000,
    });
    await apiPost(`/v2/manufacturing/sessions/${sessionId}/report/unit-result`, {
      unitId: unit1.id,
      status: 'FAILED',
      serialNumber: 'SN-RES-002',
      errorMessage: 'Flash verification failed',
      durationMs: 5000,
    });
    await apiPost(`/v2/manufacturing/sessions/${sessionId}/report/panel-complete`, {
      panelId: panel.id,
      status: 'PASSED',
      passedUnits: 1,
      failedUnits: 1,
      durationMs: 6000,
    });
  });

  test.afterAll(async () => {
    // End session if still active
    try {
      await apiPost(`/v2/manufacturing/sessions/${sessionId}/end`, {});
    } catch {
      // May already be ended
    }
    try { await deleteFixture(fixtureId); } catch { /* best effort */ }
    try { await apiDelete(`/v2/products/${productId}`); } catch { /* best effort */ }
  });

  test('click "End Session" shows confirmation dialog', async ({ page }) => {
    await loginAsRole(page, 'operator');
    await page.goto(`/manufacturing/session/${sessionId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    // Click "End Session" button
    const endBtn = page.getByRole('button', { name: /end session/i });
    await expect(endBtn).toBeVisible({ timeout: 10_000 });
    await endBtn.click();

    // Confirmation dialog should appear
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible({ timeout: 5_000 });

    // Dialog text should mention ending the session
    await expect(dialog.getByText(/end.*manufacturing.*session/i)).toBeVisible();

    // Cancel and End Session buttons should be in dialog
    await expect(dialog.getByRole('button', { name: /cancel/i })).toBeVisible();
    await expect(dialog.getByRole('button', { name: /end session/i })).toBeVisible();
  });

  test('confirm end session changes status to COMPLETED', async ({ page }) => {
    await loginAsRole(page, 'operator');
    await page.goto(`/manufacturing/session/${sessionId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    // Click End Session
    await page.getByRole('button', { name: /end session/i }).click();
    await page.waitForTimeout(300);

    // Confirm in dialog
    const dialog = page.locator('[role="dialog"]');
    await dialog.getByRole('button', { name: /end session/i }).click();

    // Wait for status update
    await page.waitForTimeout(2_000);

    // Session status should now show COMPLETED
    await expect(page.getByText(/completed/i).first()).toBeVisible({ timeout: 10_000 });

    // QR input and control buttons should no longer be visible (session is not ACTIVE)
    const qrInput = page.getByPlaceholder(/scan.*qr|panel.*qr|qr.*code/i);
    await expect(qrInput).not.toBeVisible({ timeout: 3_000 });
  });

  test('fixture released to AVAILABLE after session end', async () => {
    // Verify fixture status via API
    const fixture = await apiGet<{ status: string }>(`/v2/fixtures/${fixtureId}`);
    expect(fixture.status).toBe('AVAILABLE');
  });

  test('session appears in Sessions tab on manufacturing page', async ({ page }) => {
    await loginAsRole(page, 'operator');
    await page.goto('/manufacturing');
    await page.waitForLoadState('networkidle');

    // Switch to Sessions tab
    const sessionsTab = page.getByText('Sessions', { exact: true });
    await sessionsTab.click();
    await page.waitForTimeout(1_000);

    // Session should appear in the list with product name
    const sessionRow = page.getByText(`MFG Results Product ${suffix}`);
    await expect(sessionRow).toBeVisible({ timeout: 10_000 });

    // Should show COMPLETED status
    // Find the session row container and check for COMPLETED badge
    const sessionContainer = page.locator('button').filter({ hasText: `MFG Results Product ${suffix}` });
    await expect(sessionContainer.getByText(/completed/i)).toBeVisible({ timeout: 5_000 });

    // Should show panel count
    await expect(sessionContainer.getByText(/1 panel/i)).toBeVisible();
  });

  test('session detail shows panels with per-unit results', async ({ page }) => {
    await loginAsRole(page, 'operator');
    await page.goto(`/manufacturing/session/${sessionId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1_000);

    // Session should be COMPLETED
    await expect(page.getByText(/completed/i).first()).toBeVisible({ timeout: 10_000 });

    // Panel QR code should be visible
    await expect(page.getByText('E2E-RES-PANEL-001')).toBeVisible();

    // Click to expand panel history if collapsed
    const panelRow = page.locator('button').filter({ hasText: /E2E-RES-PANEL-001/ });
    if (await panelRow.isVisible()) {
      await panelRow.click();
      await page.waitForTimeout(500);
    }

    // Unit serial numbers should be visible in the expanded panel
    await expect(page.getByText('SN-RES-001')).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText('SN-RES-002')).toBeVisible({ timeout: 5_000 });
  });

  test('session results aggregation correct', async ({ page }) => {
    await loginAsRole(page, 'operator');
    await page.goto(`/manufacturing/session/${sessionId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1_000);

    // Header should show pass count = 1
    const passCountEl = page.locator('.text-success').filter({ hasText: '1' });
    await expect(passCountEl.first()).toBeVisible({ timeout: 10_000 });

    // Fail count should be visible (text-error with 1)
    const failCountEl = page.locator('.text-error, [class*="text-error"]').filter({ hasText: '1' });
    await expect(failCountEl.first()).toBeVisible({ timeout: 5_000 });

    // Panel count = 1
    // The header stat "Panels" with value "1" should be visible
    const panelsStat = page.locator('.text-center').filter({ hasText: 'Panels' });
    await expect(panelsStat).toBeVisible({ timeout: 5_000 });
  });
});
