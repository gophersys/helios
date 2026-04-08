/**
 * Global teardown for the E2E story suite.
 * Cleans up s1-prefixed test data created during the run.
 */

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';

async function cleanupPrefixedProducts(prefix: string): Promise<void> {
  try {
    const res = await fetch(`${API_URL}/v2/products`, {
      headers: { Authorization: `ApiKey ${API_KEY}` },
    });
    if (!res.ok) return;
    const body = await res.json();
    const products = body?.data?.data ?? body?.data ?? [];
    for (const p of products) {
      if (p.name?.startsWith(prefix)) {
        await fetch(`${API_URL}/v2/products/${p.id}`, {
          method: 'DELETE',
          headers: { Authorization: `ApiKey ${API_KEY}` },
        }).catch(() => {});
      }
    }
  } catch {
    // Best-effort cleanup
  }
}

export default async function globalTeardown(): Promise<void> {
  console.log('[e2e] Global teardown starting...');

  // Clean up any s1-prefixed test data
  await cleanupPrefixedProducts('s1-');

  console.log('[e2e] Global teardown complete.');
}
