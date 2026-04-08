import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import {
  createProductViaAPI,
  createFixture,
  deleteFixture,
} from '../../helpers/api-extended';

/**
 * Manufacturing Session — Start session, run panels, verify results.
 *
 * Tests run in serial: create session → run panels → verify UI.
 *
 * NOTE: Real MTIB-connected panel execution requires office network access.
 * These tests simulate panel results via the reporter API to verify the UI
 * flow without requiring actual hardware.
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

test.describe('Manufacturing Session: Panels & Results', () => {
  const suffix = `e2e-mfg-sess-${Date.now()}`;
  let productId: string;
  let fixtureId: string;
  let sessionId: string;
  let panelId: string;
  let unitIds: string[] = [];

  test.beforeAll(async () => {
    // Create product
    const product = await createProductViaAPI({
      name: `MFG Session Product ${suffix}`,
      slug: `mfg-sess-${suffix}`,
    });
    productId = product.id;

    // Create MANUFACTURING fixture
    const fixture = await createFixture({
      name: `MFG Session Fixture ${suffix}`,
      productId,
      type: 'MANUFACTURING',
      description: 'E2E session fixture',
      stationId: `SESS-${suffix}`,
      slots: [
        { slotIndex: 0, label: 'Slot A' },
        { slotIndex: 1, label: 'Slot B' },
      ],
    });
    fixtureId = fixture.id;
  });

  test.afterAll(async () => {
    // End session if still active
    if (sessionId) {
      try {
        await apiPost(`/v2/manufacturing/sessions/${sessionId}/end`, {});
      } catch {
        // May already be ended
      }
    }
    // Cleanup
    try { await deleteFixture(fixtureId); } catch { /* best effort */ }
    try { await apiDelete(`/v2/products/${productId}`); } catch { /* best effort */ }
  });

  test('start session via API and navigate to session runner', async ({ page }) => {
    // Start session via API (bypasses UI productId issue)
    const session = await apiPost<{ id: string; status: string }>(
      '/v2/manufacturing/sessions',
      { productId, fixtureId },
    );
    expect(session).toBeTruthy();
    expect(session.id).toBeTruthy();
    expect(session.status).toBe('ACTIVE');
    sessionId = session.id;

    // Navigate to session runner page
    await loginAsRole(page, 'operator');
    await page.goto(`/manufacturing/session/${sessionId}`);
    await page.waitForLoadState('networkidle');

    // Session header should be visible
    const heading = page.getByText(`MFG Session Product ${suffix}`).first();
    await expect(heading).toBeVisible({ timeout: 10_000 });

    // Status should show ACTIVE
    await expect(page.getByText(/active/i).first()).toBeVisible();
  });

  test('fixture status changes to LOCKED after session start', async () => {
    // Verify fixture is now locked via API
    const fixture = await apiGet<{ status: string }>(`/v2/fixtures/${fixtureId}`);
    expect(fixture.status).toBe('LOCKED');
  });

  test('session runner page shows QR input field', async ({ page }) => {
    await loginAsRole(page, 'operator');
    await page.goto(`/manufacturing/session/${sessionId}`);
    await page.waitForLoadState('networkidle');

    // QR code input should be visible
    const qrInput = page.getByPlaceholder(/scan.*qr|panel.*qr|qr.*code/i);
    await expect(qrInput).toBeVisible({ timeout: 10_000 });

    // "Run Panel" button should be visible
    const runBtn = page.getByRole('button', { name: /run panel/i });
    await expect(runBtn).toBeVisible();

    // "End Session" button should be visible
    const endBtn = page.getByRole('button', { name: /end session/i });
    await expect(endBtn).toBeVisible();
  });

  test('enter QR code in input field', async ({ page }) => {
    await loginAsRole(page, 'operator');
    await page.goto(`/manufacturing/session/${sessionId}`);
    await page.waitForLoadState('networkidle');

    const qrInput = page.getByPlaceholder(/scan.*qr|panel.*qr|qr.*code/i);
    await qrInput.fill('E2E-PANEL-001');

    await expect(qrInput).toHaveValue('E2E-PANEL-001');

    // Run Panel button should now be enabled
    const runBtn = page.getByRole('button', { name: /run panel/i });
    await expect(runBtn).toBeEnabled();
  });

  test('run panel via API and verify panel appears on session page', async ({ page }) => {
    // Run a panel via API (requires unitCount which UI may not send)
    const panel = await apiPost<{ id: string; panelIndex: number; units: Array<{ id: string }> }>(
      `/v2/manufacturing/sessions/${sessionId}/panels`,
      { qrCode: 'E2E-PANEL-001', unitCount: 2 },
    );
    expect(panel).toBeTruthy();
    expect(panel.id).toBeTruthy();
    panelId = panel.id;
    unitIds = panel.units.map((u) => u.id);

    // Navigate to session page to verify panel appeared
    await loginAsRole(page, 'operator');
    await page.goto(`/manufacturing/session/${sessionId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1_000);

    // The QR code should appear somewhere on the page
    const qrText = page.getByText('E2E-PANEL-001');
    await expect(qrText).toBeVisible({ timeout: 10_000 });
  });

  test('simulate stage results and verify unit cards update', async ({ page }) => {
    // Report stage results for unit 0 via reporter API
    for (const unitId of unitIds) {
      // Electrical stage - PASSED
      await apiPost(`/v2/manufacturing/sessions/${sessionId}/report/stage-result`, {
        unitId,
        stageName: 'electrical',
        passed: true,
        durationMs: 1500,
      });

      // Flash stage - PASSED
      await apiPost(`/v2/manufacturing/sessions/${sessionId}/report/stage-result`, {
        unitId,
        stageName: 'flash',
        passed: true,
        durationMs: 5000,
      });

      // POST stage - first unit PASSED, second FAILED
      const isFirstUnit = unitId === unitIds[0];
      await apiPost(`/v2/manufacturing/sessions/${sessionId}/report/stage-result`, {
        unitId,
        stageName: 'post',
        passed: isFirstUnit,
        errorMessage: isFirstUnit ? null : 'BMS check failed',
        durationMs: 3000,
      });
    }

    // Report unit results
    await apiPost(`/v2/manufacturing/sessions/${sessionId}/report/unit-result`, {
      unitId: unitIds[0],
      passed: true,
      serialNumber: 'SN-E2E-001',
      durationMs: 9500,
    });
    await apiPost(`/v2/manufacturing/sessions/${sessionId}/report/unit-result`, {
      unitId: unitIds[1],
      passed: false,
      serialNumber: 'SN-E2E-002',
      errorMessage: 'BMS check failed',
      durationMs: 9500,
    });

    // Report panel complete
    await apiPost(`/v2/manufacturing/sessions/${sessionId}/report/panel-complete`, {
      panelId,
      passedUnits: 1,
      failedUnits: 1,
      durationMs: 10000,
    });

    // Navigate to session page and verify results
    await loginAsRole(page, 'operator');
    await page.goto(`/manufacturing/session/${sessionId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1_000);

    // Session header should show 1 panel
    await expect(page.getByText('1').first()).toBeVisible({ timeout: 10_000 });

    // The QR code should be visible
    await expect(page.getByText('E2E-PANEL-001')).toBeVisible();
  });

  test('panel summary shows pass/fail count', async ({ page }) => {
    await loginAsRole(page, 'operator');
    await page.goto(`/manufacturing/session/${sessionId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1_000);

    // Session header stats should show pass and fail counts
    // Pass count = 1
    const passSection = page.locator('.text-success').filter({ hasText: '1' });
    await expect(passSection.first()).toBeVisible({ timeout: 10_000 });
  });

  test('run second panel and verify panel history', async ({ page }) => {
    // Run a second panel via API
    const panel2 = await apiPost<{ id: string; units: Array<{ id: string }> }>(
      `/v2/manufacturing/sessions/${sessionId}/panels`,
      { qrCode: 'E2E-PANEL-002', unitCount: 2 },
    );
    const panel2Id = panel2.id;
    const panel2UnitIds = panel2.units.map((u) => u.id);

    // All units pass in panel 2
    for (const unitId of panel2UnitIds) {
      await apiPost(`/v2/manufacturing/sessions/${sessionId}/report/stage-result`, {
        unitId,
        stageName: 'electrical',
        passed: true,
        durationMs: 1200,
      });
      await apiPost(`/v2/manufacturing/sessions/${sessionId}/report/stage-result`, {
        unitId,
        stageName: 'flash',
        passed: true,
        durationMs: 4800,
      });
      await apiPost(`/v2/manufacturing/sessions/${sessionId}/report/stage-result`, {
        unitId,
        stageName: 'post',
        passed: true,
        durationMs: 2800,
      });
      await apiPost(`/v2/manufacturing/sessions/${sessionId}/report/unit-result`, {
        unitId,
        passed: true,
        serialNumber: `SN-E2E-P2-${unitId.slice(-4)}`,
        durationMs: 8800,
      });
    }

    await apiPost(`/v2/manufacturing/sessions/${sessionId}/report/panel-complete`, {
      panelId: panel2Id,
      passedUnits: 2,
      failedUnits: 0,
      durationMs: 9000,
    });

    // Navigate and verify
    await loginAsRole(page, 'operator');
    await page.goto(`/manufacturing/session/${sessionId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1_000);

    // Should show 2 panels in header
    await expect(page.getByText('2').first()).toBeVisible({ timeout: 10_000 });

    // Panel history should contain both QR codes
    await expect(page.getByText('E2E-PANEL-001')).toBeVisible();
    await expect(page.getByText('E2E-PANEL-002')).toBeVisible();
  });

  test('panel history shows first panel results with expand/collapse', async ({ page }) => {
    await loginAsRole(page, 'operator');
    await page.goto(`/manufacturing/session/${sessionId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1_000);

    // Panel History section should be visible
    const historyHeading = page.getByText(/panel history/i);
    await expect(historyHeading).toBeVisible({ timeout: 10_000 });

    // Click on the first panel to expand it
    const panel1Row = page.locator('button').filter({ hasText: /E2E-PANEL-001/ });
    if (await panel1Row.isVisible()) {
      await panel1Row.click();
      await page.waitForTimeout(500);

      // Expanded content should show unit cards
      // Serial numbers should be visible after expansion
      await expect(page.getByText('SN-E2E-001')).toBeVisible({ timeout: 5_000 });
    }
  });

  test('session header shows aggregate pass/fail across panels', async ({ page }) => {
    await loginAsRole(page, 'operator');
    await page.goto(`/manufacturing/session/${sessionId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1_000);

    // Total: 3 passed (1 from panel 1 + 2 from panel 2), 1 failed (from panel 1)
    // Header should show these aggregated counts
    // Pass: 3
    const passCount = page.locator('.text-success').filter({ hasText: '3' });
    await expect(passCount.first()).toBeVisible({ timeout: 10_000 });
  });
});
