import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import { apiGet, apiPost, apiDelete } from '../../helpers/api';

/**
 * API Key management E2E tests.
 *
 * API Keys are managed through the Settings modal (gear icon → API Keys tab),
 * not the Users page. Tests are ordered and cumulative.
 *
 * Key creation returns the full key ONCE. After that, only the prefix is visible.
 */

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const ADMIN_API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';
const TEST_KEY_NAME = 'E2E Test Key';

test.describe.configure({ mode: 'serial' });

test.describe('API Keys', () => {
  let createdKeyFull: string;
  let createdKeyId: string;

  test.beforeEach(async ({ page }) => {
    await loginAsRole(page, 'admin');
  });

  test('API Keys section shows existing keys for admin', async ({ page }) => {
    // Open settings modal
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Click gear/settings icon in sidebar or header
    const settingsBtn = page
      .locator('button[aria-label="Settings"], button[title="Settings"]')
      .or(page.locator('button').filter({ hasText: /settings/i }));
    await settingsBtn.first().click();
    await page.waitForTimeout(500);

    // Switch to API Keys tab
    await page.locator('text=API Keys').first().click();
    await page.waitForTimeout(500);

    // Should see the API Keys section content
    await expect(page.locator('text=/api keys|programmatic access/i')).toBeVisible();
  });

  test('create API key: returns full key shown once', async ({ page }) => {
    // Create via API to get the full key (UI also shows it once)
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

  test('after creation, only key prefix visible in list', async ({ page }) => {
    expect(createdKeyId).toBeTruthy();

    // List keys via API — should show prefix, NOT full key
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

  test('API key can be used to authenticate API requests', async ({ page }) => {
    expect(createdKeyFull).toBeTruthy();

    // Use the created key to make an authenticated request
    const res = await page.request.get(`${API_URL}/v2/auth/me`, {
      headers: { Authorization: `ApiKey ${createdKeyFull}` },
    });

    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body?.data?.email).toBe('admin@concord.dev');
  });

  test('revoke API key: key no longer works', async ({ page }) => {
    expect(createdKeyId).toBeTruthy();
    expect(createdKeyFull).toBeTruthy();

    // Delete the key
    const delRes = await page.request.delete(`${API_URL}/v2/api-keys/${createdKeyId}`, {
      headers: { Authorization: `ApiKey ${ADMIN_API_KEY}` },
    });
    expect(delRes.status()).toBe(200);

    // Now the key should not authenticate
    const res = await page.request.get(`${API_URL}/v2/auth/me`, {
      headers: { Authorization: `ApiKey ${createdKeyFull}` },
    });
    // Should return 401 (unauthorized)
    expect(res.status()).toBe(401);
  });

  test('expired API key returns 401', async ({ page }) => {
    // Create a key with expiresAt in the past
    const pastDate = new Date(Date.now() - 86400_000).toISOString(); // yesterday

    const res = await page.request.post(`${API_URL}/v2/api-keys`, {
      headers: {
        Authorization: `ApiKey ${ADMIN_API_KEY}`,
        'Content-Type': 'application/json',
      },
      data: { name: 'E2E Expired Key', expiresAt: pastDate },
    });

    expect(res.status()).toBe(201);
    const body = await res.json();
    const expiredKey = body?.data?.key;
    const expiredKeyId = body?.data?.id;
    expect(expiredKey).toBeTruthy();

    // Try to use the expired key
    const authRes = await page.request.get(`${API_URL}/v2/auth/me`, {
      headers: { Authorization: `ApiKey ${expiredKey}` },
    });
    expect(authRes.status()).toBe(401);

    // Cleanup
    await page.request.delete(`${API_URL}/v2/api-keys/${expiredKeyId}`, {
      headers: { Authorization: `ApiKey ${ADMIN_API_KEY}` },
    });
  });

  test('multiple API keys can coexist for same user', async ({ page }) => {
    // Create two keys
    const res1 = await page.request.post(`${API_URL}/v2/api-keys`, {
      headers: {
        Authorization: `ApiKey ${ADMIN_API_KEY}`,
        'Content-Type': 'application/json',
      },
      data: { name: 'E2E Multi Key 1' },
    });
    const body1 = await res1.json();
    const key1Full = body1?.data?.key;
    const key1Id = body1?.data?.id;

    const res2 = await page.request.post(`${API_URL}/v2/api-keys`, {
      headers: {
        Authorization: `ApiKey ${ADMIN_API_KEY}`,
        'Content-Type': 'application/json',
      },
      data: { name: 'E2E Multi Key 2' },
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
