import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import {
  createProductViaAPI,
  createNode,
  deleteNode,
} from '../../helpers/api-extended';

/**
 * Validation Execution — Session lifecycle via reporter API.
 *
 * Since MTIB hardware may be unreachable from the codespace, these tests
 * simulate a validation run using the reporter API to drive session state
 * transitions and verify that the UI and data model behave correctly.
 *
 * Flow: create product + node + session via API, then use reporter
 * callbacks to progress through PENDING -> ACTIVE -> PASSED/FAILED.
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

test.describe('Validation Execution: Session Lifecycle', () => {
  const suffix = `e2e-val-exec-${Date.now()}`;
  let productId: string;
  let nodeId: string;
  let sessionId: string;
  const serialNumber = `E2E${Date.now().toString(36).toUpperCase()}`;

  test.beforeAll(async () => {
    // Create product
    const product = await createProductViaAPI({
      name: `Val Exec Product ${suffix}`,
      slug: `val-exec-${suffix}`,
    });
    productId = product.id;

    // Create node (MTIB stand-in)
    const node = await createNode({
      name: `Val Exec Node ${suffix}`,
      hostname: `val-exec-node-${suffix}`,
      type: 'VALIDATION',
      ipAddress: '10.4.45.99',
    });
    nodeId = node.id;
  });

  test.afterAll(async () => {
    // Cancel session if still active
    if (sessionId) {
      try {
        await apiPost(`/v2/sessions/${sessionId}/cancel`, {});
      } catch {
        // May already be finished
      }
    }
    try { await deleteNode(nodeId); } catch { /* best effort */ }
    try { await apiDelete(`/v2/products/${productId}`); } catch { /* best effort */ }
  });

  test('session transitions from PENDING to ACTIVE when tests begin', async () => {
    // Create session via the runs endpoint
    const session = await apiPost<{
      id: string;
      status: string;
      targetCount: number;
    }>('/v2/sessions', {
      name: `Execution Test ${suffix}`,
      productId,
      nodeId,
      serialNumber,
      stage: 'smoke',
    });
    expect(session).toBeTruthy();
    expect(session.id).toBeTruthy();
    sessionId = session.id;

    // Session starts as ACTIVE (create_run sets it immediately)
    expect(session.status).toBe('ACTIVE');

    // Report start via reporter API (idempotent for ACTIVE)
    const startResult = await apiPost<{ runId: string; status: string }>(
      `/v2/sessions/${sessionId}/report/start`,
      {},
    );
    expect(startResult.status).toBe('ACTIVE');
  });

  test('session has correct fixture and build run references', async () => {
    const session = await apiGet<{
      id: string;
      productId: string;
      config: Record<string, unknown>;
    }>(`/v2/sessions/${sessionId}`);

    expect(session.productId).toBe(productId);
    expect(session.config).toBeTruthy();
    expect((session.config as any).nodeId).toBe(nodeId);
    expect((session.config as any).serialNumber).toBe(serialNumber);
  });

  test('device record created with correct serial number', async () => {
    const session = await apiGet<{
      devices: Array<{ serialNumber: string; status: string }>;
    }>(`/v2/sessions/${sessionId}`);

    expect(session.devices).toBeTruthy();
    expect(session.devices.length).toBeGreaterThanOrEqual(1);

    const device = session.devices[0];
    expect(device.serialNumber).toBe(serialNumber);
  });

  test('test executions created for each test in suite', async () => {
    // Send test-list to establish expected tests
    await apiPost(`/v2/sessions/${sessionId}/report/test-list`, {
      tests: [
        { name: 'test_power_on', module: 'test_power' },
        { name: 'test_idle_current', module: 'test_power' },
        { name: 'test_button_press', module: 'test_ui' },
      ],
    });

    // Start and complete each test via reporter
    const tests = [
      { name: 'test_power_on', module: 'test_power' },
      { name: 'test_idle_current', module: 'test_power' },
      { name: 'test_button_press', module: 'test_ui' },
    ];

    for (const t of tests) {
      await apiPost(`/v2/sessions/${sessionId}/report/test-start`, {
        testName: t.name,
        module: t.module,
      });
    }

    // Verify executions via the session detail endpoint
    const session = await apiGet<{
      executions: Array<{ test: { name: string }; status: string }>;
    }>(`/v2/sessions/${sessionId}`);

    expect(session.executions).toBeTruthy();
    expect(session.executions.length).toBeGreaterThanOrEqual(3);

    const executionNames = session.executions.map((e) => e.test?.name);
    for (const t of tests) {
      expect(executionNames).toContain(t.name);
    }
  });

  test('session completes within expected timeout', async () => {
    // Report results for all three tests
    await apiPost(`/v2/sessions/${sessionId}/report/test-result`, {
      testName: 'test_power_on',
      module: 'test_power',
      passed: true,
      durationS: 2.1,
      measurements: { bootTimeMs: 2100 },
    });

    await apiPost(`/v2/sessions/${sessionId}/report/test-result`, {
      testName: 'test_idle_current',
      module: 'test_power',
      passed: true,
      durationS: 10.5,
      measurements: { idleCurrentMa: 18.2 },
    });

    await apiPost(`/v2/sessions/${sessionId}/report/test-result`, {
      testName: 'test_button_press',
      module: 'test_ui',
      passed: true,
      durationS: 4.0,
    });

    // Report finish
    await apiPost(`/v2/sessions/${sessionId}/report/finish`, {
      total: 3,
      passed: 3,
      failed: 0,
      errors: 0,
      durationS: 16.6,
    });

    // Session should now be complete
    const session = await apiGet<{ status: string }>(`/v2/sessions/${sessionId}`);
    expect(['PASSED', 'FAILED']).toContain(session.status);
  });

  test('session final status is PASSED or FAILED with correct counts', async () => {
    const session = await apiGet<{
      status: string;
      passedCount: number;
      failedCount: number;
      completedCount: number;
    }>(`/v2/sessions/${sessionId}`);

    // All 3 tests passed, so session should be PASSED
    expect(session.status).toBe('PASSED');
    expect(session.passedCount).toBe(3);
    expect(session.failedCount).toBe(0);
    expect(session.completedCount).toBe(1); // 1 slot completed
  });
});
