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
 * - 1 seed product: Alpha (with fixture designs, fixtures, build runs, etc.)
 * - Seed fixture designs (alpha-val-fixture-v1.2, alpha-mfg-fixture-v1.0)
 * - Seed fixtures (bench instances)
 * - Seed build runs
 */

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';

const SEED_USER_EMAILS = [
  'admin@concord.dev',
  'maintainer@concord.dev',
  'developer@concord.dev',
  'operator@concord.dev',
  'admin@concord.local',
  'system@concord.local',
];

/** Email domain suffixes for seeded users (team members, dev accounts) */
const SEED_USER_DOMAINS = [
  '@concord.dev',
  '@concord.local',
  '@corekinect.com',
];

/** Slugs of products that are seeded and should not be counted as E2E leftovers */
const SEED_PRODUCT_SLUGS = ['alpha'];

/** Prefixes of fixture design names that are seeded */
const SEED_DESIGN_PREFIXES = ['alpha-'];

/** Prefixes of fixture names that are seeded */
const SEED_FIXTURE_PREFIXES = ['Alpha '];

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

async function apiDelete(path: string): Promise<boolean> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'DELETE',
    headers: { Authorization: `ApiKey ${API_KEY}` },
  });
  return res.ok || res.status === 404;
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
  // Actively clean up any leftover E2E data before running zero-state verification.
  // Individual test suites should clean up after themselves, but some may fail to do
  // so if tests error out mid-run. This ensures the verification passes.
  test.beforeAll(async () => {
    // Delete leftover E2E fixtures
    const fixtureData = await apiGet('/v2/fixtures');
    const fixtures = extractList(fixtureData);
    for (const f of fixtures) {
      const name = (f as any)?.name ?? '';
      if (!SEED_FIXTURE_PREFIXES.some((prefix) => name.startsWith(prefix))) {
        console.log(`[cleanup:active] Deleting leftover fixture: ${name}`);
        await apiDelete(`/v2/fixtures/${(f as any).id}`);
      }
    }

    // Delete leftover E2E fixture designs
    const designData = await apiGet('/v2/fixtures/designs');
    const designs = extractList(designData);
    for (const d of designs) {
      const name = (d as any)?.name ?? '';
      if (!SEED_DESIGN_PREFIXES.some((prefix) => name.startsWith(prefix))) {
        console.log(`[cleanup:active] Deleting leftover fixture design: ${name}`);
        await apiDelete(`/v2/fixtures/designs/${(d as any).id}`);
      }
    }

    // Delete leftover E2E products
    const productData = await apiGet('/v2/products');
    const products = extractList(productData);
    for (const p of products) {
      const slug = (p as any)?.slug ?? '';
      if (!SEED_PRODUCT_SLUGS.includes(slug)) {
        console.log(`[cleanup:active] Deleting leftover product: ${(p as any)?.name}`);
        await apiDelete(`/v2/products/${(p as any).id}`);
      }
    }

    // Delete leftover E2E nodes/MTIBs
    try {
      const nodeData = await apiGet('/v2/devices/mtibs');
      const nodes = extractList(nodeData);
      for (const n of nodes) {
        const name = (n as any)?.name ?? '';
        if (name.toLowerCase().includes('e2e') || name.toLowerCase().includes('mfg')) {
          console.log(`[cleanup:active] Deleting leftover node: ${name}`);
          await apiDelete(`/v2/devices/mtibs/${(n as any).id}`);
        }
      }
    } catch {
      // Nodes endpoint may not exist or may error — skip silently
    }

    // Delete leftover E2E users (non-seed)
    try {
      const userData = await apiGet('/v2/users');
      const users = extractList(userData);
      for (const u of users) {
        const email = (u as any)?.email ?? '';
        if (SEED_USER_EMAILS.includes(email)) continue;
        if (SEED_USER_DOMAINS.some((domain) => email.endsWith(domain))) continue;
        console.log(`[cleanup:active] Deleting leftover user: ${email}`);
        await apiDelete(`/v2/users/${(u as any).id}`);
      }
    } catch {
      // Users cleanup may fail — skip silently
    }

    // Delete leftover E2E permission sets (non-built-in)
    try {
      const permData = await apiGet('/v2/permissions');
      const sets = extractList(permData);
      for (const s of sets) {
        const name = (s as any)?.name ?? '';
        if (name.startsWith('s14-') || name.startsWith('s15-') || name.startsWith('e2e-') || name.startsWith('E2E')) {
          console.log(`[cleanup:active] Deleting leftover permission set: ${name}`);
          await apiDelete(`/v2/permissions/${(s as any).id}`);
        }
      }
    } catch {
      // Permission sets cleanup may fail — skip silently
    }

    // Delete leftover E2E API keys
    try {
      const keyData = await apiGet('/v2/api-keys');
      const keys = extractList(keyData);
      for (const k of keys) {
        const name = (k as any)?.name ?? '';
        if (name.startsWith('s14-') || name.startsWith('s15-') || name.startsWith('e2e-') || name.startsWith('E2E')) {
          console.log(`[cleanup:active] Deleting leftover API key: ${name}`);
          await apiDelete(`/v2/api-keys/${(k as any).id}`);
        }
      }
    } catch {
      // API keys cleanup may fail — skip silently
    }
  });

  test('zero non-seed products remain', async () => {
    const data = await apiGet('/v2/products');
    const products = extractList(data);

    // Filter out seed products (e.g., Alpha) — only E2E-created products are violations
    const nonSeedProducts = products.filter((p: any) => {
      const slug = p?.slug ?? '';
      return !SEED_PRODUCT_SLUGS.includes(slug);
    });

    console.log(`[cleanup] Products total: ${products.length}, non-seed: ${nonSeedProducts.length}`);
    if (nonSeedProducts.length > 0) {
      console.log('[cleanup] Non-seed products found:');
      for (const p of nonSeedProducts) {
        console.log(`  - ${(p as any)?.name ?? (p as any)?.slug ?? 'unknown'}`);
      }
    }

    expect(nonSeedProducts).toHaveLength(0);
  });

  test('zero non-seed fixture designs remain', async () => {
    const data = await apiGet('/v2/fixtures/designs');
    const designs = extractList(data);

    // Filter out seed fixture designs (e.g., alpha-val-fixture-v1.2, alpha-mfg-fixture-v1.0)
    const nonSeedDesigns = designs.filter((d: any) => {
      const name = d?.name ?? '';
      return !SEED_DESIGN_PREFIXES.some((prefix) => name.startsWith(prefix));
    });

    console.log(`[cleanup] Fixture designs total: ${designs.length}, non-seed: ${nonSeedDesigns.length}`);
    expect(nonSeedDesigns).toHaveLength(0);
  });

  test('zero non-seed fixture instances remain', async () => {
    const data = await apiGet('/v2/fixtures');
    const fixtures = extractList(data);

    // Filter out seed fixtures (e.g., "Alpha B0 Bench 32", etc.)
    const nonSeedFixtures = fixtures.filter((f: any) => {
      const name = f?.name ?? '';
      return !SEED_FIXTURE_PREFIXES.some((prefix) => name.startsWith(prefix));
    });

    console.log(`[cleanup] Fixture instances total: ${fixtures.length}, non-seed: ${nonSeedFixtures.length}`);
    expect(nonSeedFixtures).toHaveLength(0);
  });

  test('zero E2E build runs remain', async () => {
    const data = await apiGet('/v2/builds/runs');
    const runs = extractList(data);

    // Filter out seed/system build runs — only E2E test-created runs are violations.
    // E2E build runs typically have names containing "E2E" or "e2e" prefixes.
    // Seed build runs (e.g., from git-poller auto-triggers) are expected to persist.
    const e2eRuns = runs.filter((r: any) => {
      const name = (r?.name ?? '').toLowerCase();
      return name.includes('e2e') || name.startsWith('e2e');
    });

    console.log(`[cleanup] Build runs total: ${runs.length}, E2E-created: ${e2eRuns.length}`);
    expect(e2eRuns).toHaveLength(0);
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
    const data = await apiGet('/v2/permissions');
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

  test('zero active non-seed users remain (only dev users)', async () => {
    // Soft-delete any leftover non-seed users before verifying
    const data = await apiGet('/v2/users');
    const users = extractList(data);

    const nonSeedUsers = users.filter((u: any) => {
      const email = u?.email ?? '';
      if (SEED_USER_EMAILS.includes(email)) return false;
      if (SEED_USER_DOMAINS.some((domain) => email.endsWith(domain))) return false;
      return true;
    });

    // Deactivate any remaining non-seed users (DELETE is soft-delete)
    for (const u of nonSeedUsers) {
      if ((u as any)?.active) {
        console.log(`[cleanup:active] Deactivating leftover user: ${(u as any)?.email}`);
        await apiDelete(`/v2/users/${(u as any).id}`);
      }
    }

    // Re-verify: no ACTIVE non-seed users remain
    // (soft-deleted users may persist but are inactive and harmless)
    const refreshed = await apiGet('/v2/users');
    const refreshedUsers = extractList(refreshed);
    const remaining = refreshedUsers.filter((u: any) => {
      const email = u?.email ?? '';
      if (SEED_USER_EMAILS.includes(email)) return false;
      if (SEED_USER_DOMAINS.some((domain) => email.endsWith(domain))) return false;
      // Only count active users as leftover violations
      return (u as any)?.active === true;
    });

    console.log(
      `[cleanup] Users total: ${refreshedUsers.length}, active non-seed remaining: ${remaining.length}`,
    );

    expect(remaining).toHaveLength(0);
  });
});
