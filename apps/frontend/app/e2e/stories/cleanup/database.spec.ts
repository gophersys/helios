import { test, expect } from '../../fixtures';

/**
 * Stage 16 — Database zero-state verification.
 *
 * Verifies the database has returned to a clean state after the full E2E suite.
 * Uses API calls to list resources and assert they are empty (or contain only
 * seed data). AuditLog entries are excluded from zero-state checks — they are
 * append-only by design.
 *
 * Seed data expected to persist:
 * - 4 dev users: admin, maintainer, developer, operator (@concord.dev)
 * - Default permission sets (built-in)
 * - Default roles (built-in)
 */

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';

const SEED_USER_EMAILS = [
  'admin@concord.dev',
  'maintainer@concord.dev',
  'developer@concord.dev',
  'operator@concord.dev',
];

async function apiGet<T = unknown>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { Authorization: `ApiKey ${API_KEY}` },
  });
  if (!res.ok) {
    throw new Error(`GET ${path} failed (${res.status})`);
  }
  const body = await res.json();
  return body.data;
}

/** Extract array from paginated or direct responses */
function extractList(data: unknown): unknown[] {
  if (Array.isArray(data)) return data;
  if (data && typeof data === 'object' && 'data' in data) {
    const inner = (data as Record<string, unknown>).data;
    if (Array.isArray(inner)) return inner;
  }
  return [];
}

test.describe.configure({ mode: 'serial', timeout: 60_000 });

test.describe('Cleanup: Database Zero-State', () => {
  test('zero products remain', async () => {
    const data = await apiGet('/v2/products');
    const products = extractList(data);

    console.log(`[cleanup] Products found: ${products.length}`);
    expect(products).toHaveLength(0);
  });

  test('zero fixture designs remain', async () => {
    const data = await apiGet('/v2/fixtures/designs');
    const designs = extractList(data);

    console.log(`[cleanup] Fixture designs found: ${designs.length}`);
    expect(designs).toHaveLength(0);
  });

  test('zero fixture instances remain', async () => {
    const data = await apiGet('/v2/fixtures');
    const fixtures = extractList(data);

    console.log(`[cleanup] Fixture instances found: ${fixtures.length}`);
    expect(fixtures).toHaveLength(0);
  });

  test('zero build runs remain', async () => {
    const data = await apiGet('/v2/builds/runs');
    const runs = extractList(data);

    console.log(`[cleanup] Build runs found: ${runs.length}`);
    expect(runs).toHaveLength(0);
  });

  test('zero validation queue entries remain', async () => {
    const data = await apiGet('/v2/sessions/queue');
    const entries = extractList(data);

    // Filter to only active entries (QUEUED, ASSIGNED, RUNNING).
    // COMPLETED/CANCELLED/FAILED are terminal and may linger if the API
    // returns them by default. The key assertion is no stuck-active entries.
    const activeEntries = entries.filter((e: any) =>
      ['QUEUED', 'ASSIGNED', 'RUNNING'].includes(e?.status),
    );

    console.log(`[cleanup] Queue entries total: ${entries.length}, active: ${activeEntries.length}`);
    expect(activeEntries).toHaveLength(0);
  });

  test('zero custom permission sets remain (only defaults)', async () => {
    const data = await apiGet('/v2/auth/permission-sets');
    const sets = extractList(data);

    // Default/built-in permission sets have isDefault or isBuiltIn flags.
    // Custom sets created by E2E tests should all be deleted.
    const customSets = sets.filter((s: any) => {
      // A set is custom if it is NOT built-in and NOT a default set.
      // Different APIs may use different field names for this.
      const isBuiltIn = s?.isDefault === true || s?.isBuiltIn === true || s?.builtIn === true;
      return !isBuiltIn;
    });

    console.log(
      `[cleanup] Permission sets total: ${sets.length}, custom: ${customSets.length}`,
    );

    // If the API doesn't distinguish built-in from custom, we just verify
    // the total count is reasonable (seed creates a small number of defaults)
    if (customSets.length === sets.length && sets.length > 0) {
      // API may not expose isBuiltIn — fall back to checking for E2E prefixes
      const e2eSets = sets.filter((s: any) =>
        s?.name?.startsWith('s14-') || s?.name?.startsWith('e2e-') || s?.name?.startsWith('E2E'),
      );
      console.log(`[cleanup] E2E-prefixed permission sets: ${e2eSets.length}`);
      expect(e2eSets).toHaveLength(0);
    } else {
      expect(customSets).toHaveLength(0);
    }
  });

  test('zero non-seed users remain (only dev users)', async () => {
    const data = await apiGet('/v2/users');
    const users = extractList(data);

    // Filter out the 4 seed dev users
    const nonSeedUsers = users.filter((u: any) => {
      const email = u?.email ?? '';
      return !SEED_USER_EMAILS.includes(email);
    });

    console.log(
      `[cleanup] Users total: ${users.length}, non-seed: ${nonSeedUsers.length}`,
    );

    if (nonSeedUsers.length > 0) {
      console.log('[cleanup] Non-seed users found:');
      for (const u of nonSeedUsers) {
        console.log(`  - ${(u as any)?.email ?? (u as any)?.id ?? 'unknown'}`);
      }
    }

    expect(nonSeedUsers).toHaveLength(0);
  });
});
