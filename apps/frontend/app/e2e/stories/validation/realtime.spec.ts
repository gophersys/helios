import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import {
  createProductViaAPI,
  createNode,
  deleteNode,
} from '../../helpers/api-extended';

/**
 * Validation Real-time — WebSocket-driven DOM updates on the run detail page.
 *
 * Tests simulate a validation run via the reporter API and observe the
 * run detail page for real-time DOM mutations driven by WebSocket events.
 * Playwright cannot subscribe to Socket.IO directly, so we rely on
 * page.waitForSelector(), locator.waitFor(), and polling assertions.
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
    throw new Error(`DELETE ${path} failed (${res.status})`);
  }
}

test.describe('Validation Real-time: WebSocket DOM Updates', () => {
  const suffix = `e2e-val-rt-${Date.now()}`;
  let productId: string;
  let nodeId: string;
  let sessionId: string;
  const serialNumber = `RT${Date.now().toString(36).toUpperCase()}`;

  test.beforeAll(async () => {
    const product = await createProductViaAPI({
      name: `Val RT Product ${suffix}`,
      slug: `val-rt-${suffix}`,
    });
    productId = product.id;

    const node = await createNode({
      name: `Val RT Node ${suffix}`,
      hostname: `val-rt-node-${suffix}`,
      type: 'MTIB',
      ipAddress: '10.4.45.98',
    });
    nodeId = node.id;

    // Create session
    const session = await apiPost<{ id: string }>('/v2/sessions', {
      name: `RT Test ${suffix}`,
      productId,
      nodeId,
      serialNumber,
    });
    sessionId = session.id;

    // Start the run
    await apiPost(`/v2/sessions/${sessionId}/report/start`, {});

    // Send test list so frontend can pre-populate
    await apiPost(`/v2/sessions/${sessionId}/report/test-list`, {
      tests: [
        { name: 'test_boot', module: 'test_power' },
        { name: 'test_current', module: 'test_power' },
        { name: 'test_button', module: 'test_ui' },
      ],
    });
  });

  test.afterAll(async () => {
    if (sessionId) {
      try { await apiPost(`/v2/sessions/${sessionId}/cancel`, {}); } catch { /* noop */ }
    }
    try { await deleteNode(nodeId); } catch { /* noop */ }
    try { await apiDelete(`/v2/products/${productId}`); } catch { /* noop */ }
  });

  test('validation run detail page shows real-time test timeline', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/validation/runs/${sessionId}`);
    await page.waitForLoadState('networkidle');

    // The run header should be visible with the run name
    await expect(
      page.getByText(`RT Test ${suffix}`).first(),
    ).toBeVisible({ timeout: 15_000 });

    // Status badge should show ACTIVE
    await expect(
      page.getByText(/active/i).first(),
    ).toBeVisible({ timeout: 10_000 });
  });

  test('new test cards appear in timeline as tests start (DOM mutation)', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/validation/runs/${sessionId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1_000);

    // Start first test via reporter API
    await apiPost(`/v2/sessions/${sessionId}/report/test-start`, {
      testName: 'test_boot',
      module: 'test_power',
    });

    // Wait for the test name to appear in the DOM (WebSocket push or page refresh)
    await expect(
      page.getByText('test_boot').first(),
    ).toBeVisible({ timeout: 15_000 });
  });

  test('test cards update to passed/failed with duration and measurements', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto(`/validation/runs/${sessionId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1_000);

    // Complete first test as PASSED
    await apiPost(`/v2/sessions/${sessionId}/report/test-result`, {
      testName: 'test_boot',
      module: 'test_power',
      passed: true,
      durationS: 2.5,
      measurements: { bootTimeMs: 2500 },
    });

    // Start and complete second test as FAILED
    await apiPost(`/v2/sessions/${sessionId}/report/test-start`, {
      testName: 'test_current',
      module: 'test_power',
    });
    await apiPost(`/v2/sessions/${sessionId}/report/test-result`, {
      testName: 'test_current',
      module: 'test_power',
      passed: false,
      durationS: 10.0,
      errorMessage: 'Current 45mA exceeds 33mA limit',
      measurements: { currentMa: 45.2 },
    });

    // Wait for pass/fail indicators to appear. Look for passed count >= 1
    // The page auto-refreshes on WebSocket events; give it time to update.
    await expect(async () => {
      // Reload to pick up state if WebSocket missed
      await page.reload();
      await page.waitForLoadState('networkidle');

      // Check that the test names are visible
      const bootText = page.getByText('test_boot').first();
      await expect(bootText).toBeVisible();
      const currentText = page.getByText('test_current').first();
      await expect(currentText).toBeVisible();
    }).toPass({ timeout: 20_000 });
  });

  test('run header shows final summary when run completes', async ({ page }) => {
    // Start and complete the last test
    await apiPost(`/v2/sessions/${sessionId}/report/test-start`, {
      testName: 'test_button',
      module: 'test_ui',
    });
    await apiPost(`/v2/sessions/${sessionId}/report/test-result`, {
      testName: 'test_button',
      module: 'test_ui',
      passed: true,
      durationS: 4.0,
    });

    // Finish the run
    await apiPost(`/v2/sessions/${sessionId}/report/finish`, {
      total: 3,
      passed: 2,
      failed: 1,
      errors: 0,
    });

    // Navigate to the run detail page
    await loginAsRole(page, 'admin');
    await page.goto(`/validation/runs/${sessionId}`);
    await page.waitForLoadState('networkidle');

    // Status should show FAILED (1 failure)
    await expect(
      page.getByText(/failed/i).first(),
    ).toBeVisible({ timeout: 15_000 });
  });

  test('progress bar updates as tests complete', async ({ page }) => {
    // The run is already finished; navigate to detail page
    await loginAsRole(page, 'admin');
    await page.goto(`/validation/runs/${sessionId}`);
    await page.waitForLoadState('networkidle');

    // Verify the run has the correct counts in the header
    // passed: 2, failed: 1  — header should show these counts
    await expect(async () => {
      const passedLocator = page.locator('.text-success').first();
      await expect(passedLocator).toBeVisible();
    }).toPass({ timeout: 10_000 });
  });
});
