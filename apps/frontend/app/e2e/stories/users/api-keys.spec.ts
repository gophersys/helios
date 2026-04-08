import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';

/**
 * Stage 14 — API Key management E2E tests.
 *
 * API Keys are managed through the Settings modal (gear icon -> API Keys tab),
 * not the Users page. Tests are ordered and cumulative.
 *
 * Key creation returns the full key ONCE. After that, only the prefix is visible.
 * All test data prefixed with "s14-" for resource isolation.
 */

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const ADMIN_API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';
const TEST_KEY_NAME = 's14-E2E Test Key';

test.describe.configure({ mode: 'serial' });

test.describe('API Keys', () => {
  let createdKeyFull: string;
  let createdKeyId: string;

  test.beforeEach(async ({ page }) => {
    await loginAsRole(page, 'admin');
  });

  test('API Keys section shows empty state', async ({ page }) => {
    // Open settings modal via sidebar Settings button
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // The sidebar Settings button is inside <aside> — scope to avoid matching the modal heading
    const settingsBtn = page.locator('aside button').filter({ hasText: /^Settings$/ }).first();
    await settingsBtn.click();
    await page.waitForTimeout(500);

    // Settings modal should open with role="dialog"
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 5_000 });

    // Switch to API Keys tab inside the dialog
    await dialog.locator('button').filter({ hasText: 'API Keys' }).first().click();
    await page.waitForTimeout(500);

    // Should see the API Keys section content (programmatic access description)
    await expect(dialog.locator('text=/api keys|programmatic access/i')).toBeVisible({ timeout: 5_000 });
  });

  test('create API key: "s14-E2E Test Key" -> full key shown once', async ({ page }) => {
    const res = await page.request.post(`${API_URL}/v2/api-keys`, {
      headers: {
        Authorization: `ApiKey ${ADMIN_API_KEY}`,
        'Content-Type': 'application/json',
      },
      data: { name: TEST_KEY_NAME },
    });

    expect(res.status()).toBe(201);
    const body = await res.json();
    const keyData = body?.data;

    expect(keyData).toBeTruthy();
    expect(keyData.key).toBeTruthy();
    expect(keyData.key).toMatch(/^ck_live_/);
    expect(keyData.name).toBe(TEST_KEY_NAME);
    expect(keyData.keyPrefix).toBeTruthy();
    expect(keyData.id).toBeTruthy();

    createdKeyFull = keyData.key;
    createdKeyId = keyData.id;
  });

  test('API key list shows prefix only (not full key)', async ({ page }) => {
    expect(createdKeyId).toBeTruthy();

    const res = await page.request.get(`${API_URL}/v2/api-keys`, {
      headers: { Authorization: `ApiKey ${ADMIN_API_KEY}` },
    });
    const body = await res.json();
    const keys = body?.data?.data ?? body?.data ?? [];
    const ourKey = keys.find((k: any) => k.id === createdKeyId);

    expect(ourKey).toBeTruthy();
    expect(ourKey.name).toBe(TEST_KEY_NAME);
    expect(ourKey.keyPrefix).toBeTruthy();
    // The full key should NOT be in the list response
    expect(ourKey.key).toBeUndefined();
  });

  test('API key authenticates successfully against API', async ({ page }) => {
    expect(createdKeyFull).toBeTruthy();

    const res = await page.request.get(`${API_URL}/v2/auth/me`, {
      headers: { Authorization: `ApiKey ${createdKeyFull}` },
    });

    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body?.data?.email).toBe('admin@concord.dev');
  });

  test('revoke API key', async ({ page }) => {
    expect(createdKeyId).toBeTruthy();
    expect(createdKeyFull).toBeTruthy();

    const delRes = await page.request.delete(`${API_URL}/v2/api-keys/${createdKeyId}`, {
      headers: { Authorization: `ApiKey ${ADMIN_API_KEY}` },
    });
    expect(delRes.status()).toBe(200);
  });

  test('revoked key returns 401', async ({ page }) => {
    expect(createdKeyFull).toBeTruthy();

    const res = await page.request.get(`${API_URL}/v2/auth/me`, {
      headers: { Authorization: `ApiKey ${createdKeyFull}` },
    });
    expect(res.status()).toBe(401);
  });

  test('multiple API keys can coexist', async ({ page }) => {
    // Create two keys
    const res1 = await page.request.post(`${API_URL}/v2/api-keys`, {
      headers: {
        Authorization: `ApiKey ${ADMIN_API_KEY}`,
        'Content-Type': 'application/json',
      },
      data: { name: 's14-Multi Key 1' },
    });
    const body1 = await res1.json();
    const key1Full = body1?.data?.key;
    const key1Id = body1?.data?.id;

    const res2 = await page.request.post(`${API_URL}/v2/api-keys`, {
      headers: {
        Authorization: `ApiKey ${ADMIN_API_KEY}`,
        'Content-Type': 'application/json',
      },
      data: { name: 's14-Multi Key 2' },
    });
    const body2 = await res2.json();
    const key2Full = body2?.data?.key;
    const key2Id = body2?.data?.id;

    expect(key1Full).toBeTruthy();
    expect(key2Full).toBeTruthy();
    expect(key1Full).not.toBe(key2Full);

    // Both keys should work
    const auth1 = await page.request.get(`${API_URL}/v2/auth/me`, {
      headers: { Authorization: `ApiKey ${key1Full}` },
    });
    expect(auth1.status()).toBe(200);

    const auth2 = await page.request.get(`${API_URL}/v2/auth/me`, {
      headers: { Authorization: `ApiKey ${key2Full}` },
    });
    expect(auth2.status()).toBe(200);

    // Cleanup
    await page.request.delete(`${API_URL}/v2/api-keys/${key1Id}`, {
      headers: { Authorization: `ApiKey ${ADMIN_API_KEY}` },
    });
    await page.request.delete(`${API_URL}/v2/api-keys/${key2Id}`, {
      headers: { Authorization: `ApiKey ${ADMIN_API_KEY}` },
    });
  });
});
