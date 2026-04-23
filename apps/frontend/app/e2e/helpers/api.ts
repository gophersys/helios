import type { Page } from '@playwright/test';

const API_URL = 'http://localhost:9001';
const API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';

/**
 * Direct API calls using the known API key (bypasses JWT/browser).
 * Used for test setup/teardown that shouldn't go through the UI.
 */

export async function apiGet<T = unknown>(page: Page, path: string): Promise<T> {
  const res = await page.request.get(`${API_URL}${path}`, {
    headers: { Authorization: `ApiKey ${API_KEY}` },
  });
  const body = await res.json();
  return body.data;
}

export async function apiPost<T = unknown>(page: Page, path: string, data: unknown): Promise<T> {
  const res = await page.request.post(`${API_URL}${path}`, {
    data,
    headers: {
      Authorization: `ApiKey ${API_KEY}`,
      'Content-Type': 'application/json',
    },
  });
  const body = await res.json();
  if (body.errors?.length) {
    throw new Error(`API POST ${path} failed: ${body.errors[0].message}`);
  }
  return body.data;
}

export async function apiPut<T = unknown>(page: Page, path: string, data: unknown): Promise<T> {
  const res = await page.request.put(`${API_URL}${path}`, {
    data,
    headers: {
      Authorization: `ApiKey ${API_KEY}`,
      'Content-Type': 'application/json',
    },
  });
  const body = await res.json();
  return body.data;
}

export async function apiDelete(page: Page, path: string): Promise<void> {
  await page.request.delete(`${API_URL}${path}`, {
    headers: { Authorization: `ApiKey ${API_KEY}` },
  });
}

// ── Typed helpers ─────────────────────────────────────────

export async function getProducts(page: Page) {
  const data = await apiGet<{ data: unknown[] }>(page, '/v2/products');
  return (data as any)?.data ?? data;
}

export async function createProduct(page: Page, product: { name: string; description?: string; slug?: string }) {
  return apiPost(page, '/v2/products', product);
}

export async function deleteProduct(page: Page, id: string) {
  return apiDelete(page, `/v2/products/${id}`);
}

export async function getSecrets(page: Page) {
  return apiGet<unknown[]>(page, '/v2/system/secrets');
}

export async function createSecret(page: Page, secret: { name: string; type: string; value: string; description?: string }) {
  return apiPost(page, '/v2/system/secrets', secret);
}

export async function deleteSecret(page: Page, id: string) {
  return apiDelete(page, `/v2/system/secrets/${id}`);
}

export async function getBuildRuns(page: Page, params?: string) {
  const qs = params ? `?${params}` : '';
  const data = await apiGet<{ data: unknown[] }>(page, `/v2/builds/runs${qs}`);
  return (data as any)?.data ?? data;
}

export async function getStageConfigs(page: Page, productId: string) {
  return apiGet<unknown[]>(page, `/v2/products/${productId}/stages`);
}
