/**
 * Global teardown for the E2E story suite.
 *
 * Orchestrates cleanup across all external systems:
 * 1. Bitbucket — decline E2E PRs, delete E2E branches
 * 2. Database — clean prefixed test data (products, fixtures, etc.)
 * 3. MinIO — no-op (orphaned objects cleaned via DB reference removal)
 * 4. CoreCloud — no-op (no delete endpoint; devices persist by design)
 *
 * Database wipe/reset is NOT done here — that is handled by global-setup
 * via prisma migrate reset when E2E_RESET_DB=1.
 */

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';
const BB_API = 'https://api.bitbucket.org/2.0';
const BB_WORKSPACE = process.env.BITBUCKET_WORKSPACE || 'corekinect';
const BB_REPOS = ['alpha_fw', 'alpha_mfg_fw'];
const E2E_BRANCH_PREFIXES = ['e2e/', 'concord-e2e-', 's2-', 's3-', 's5-', 's6-'];
const E2E_DATA_PREFIXES = ['s1-', 's2-', 's3-', 's5-', 's6-', 's14-', 'e2e-', 'E2E'];

// ── Helpers ─────────────────────────────────────────────────

function bbHeaders(): Record<string, string> {
  const email = process.env.BITBUCKET_EMAIL;
  const token = process.env.BITBUCKET_API_TOKEN;
  if (!email || !token) return {};
  return {
    Authorization: `Basic ${Buffer.from(`${email}:${token}`).toString('base64')}`,
    Accept: 'application/json',
  };
}

async function cleanupBitbucketPRs(repo: string): Promise<number> {
  let declined = 0;
  try {
    const hdrs = bbHeaders();
    if (!hdrs.Authorization) return 0;

    const res = await fetch(
      `${BB_API}/repositories/${BB_WORKSPACE}/${repo}/pullrequests?state=OPEN&pagelen=50`,
      { headers: hdrs },
    );
    if (!res.ok) return 0;
    const data = await res.json();
    const prs = data.values || [];

    for (const pr of prs) {
      const isE2E =
        pr.title?.includes('E2E') ||
        pr.title?.includes('[Test]') ||
        E2E_BRANCH_PREFIXES.some((pfx: string) => pr.source?.branch?.name?.startsWith(pfx));

      if (isE2E) {
        try {
          await fetch(
            `${BB_API}/repositories/${BB_WORKSPACE}/${repo}/pullrequests/${pr.id}/decline`,
            { method: 'POST', headers: hdrs },
          );
          declined++;
        } catch {
          // Best-effort
        }
      }
    }
  } catch {
    // Bitbucket may be unreachable
  }
  return declined;
}

async function cleanupBitbucketBranches(repo: string): Promise<number> {
  let deleted = 0;
  try {
    const hdrs = bbHeaders();
    if (!hdrs.Authorization) return 0;

    for (const prefix of E2E_BRANCH_PREFIXES) {
      const res = await fetch(
        `${BB_API}/repositories/${BB_WORKSPACE}/${repo}/refs/branches?q=name+~+%22${encodeURIComponent(prefix)}%22&pagelen=100`,
        { headers: hdrs },
      );
      if (!res.ok) continue;
      const data = await res.json();

      for (const branch of data.values || []) {
        if (E2E_BRANCH_PREFIXES.some((pfx) => branch.name?.startsWith(pfx))) {
          try {
            await fetch(
              `${BB_API}/repositories/${BB_WORKSPACE}/${repo}/refs/branches/${encodeURIComponent(branch.name)}`,
              { method: 'DELETE', headers: hdrs },
            );
            deleted++;
          } catch {
            // Best-effort
          }
        }
      }
    }
  } catch {
    // Bitbucket may be unreachable
  }
  return deleted;
}

async function cleanupPrefixedProducts(): Promise<number> {
  let deleted = 0;
  try {
    const res = await fetch(`${API_URL}/v2/products`, {
      headers: { Authorization: `ApiKey ${API_KEY}` },
    });
    if (!res.ok) return 0;
    const body = await res.json();
    const products = body?.data?.data ?? body?.data ?? [];
    for (const p of products) {
      if (E2E_DATA_PREFIXES.some((pfx) => p.name?.startsWith(pfx))) {
        await fetch(`${API_URL}/v2/products/${p.id}`, {
          method: 'DELETE',
          headers: { Authorization: `ApiKey ${API_KEY}` },
        }).catch(() => {});
        deleted++;
      }
    }
  } catch {
    // Best-effort
  }
  return deleted;
}

async function cleanupPrefixedUsers(): Promise<number> {
  let deleted = 0;
  const seedEmails = [
    'admin@concord.dev',
    'maintainer@concord.dev',
    'developer@concord.dev',
    'operator@concord.dev',
  ];
  try {
    const res = await fetch(`${API_URL}/v2/users`, {
      headers: { Authorization: `ApiKey ${API_KEY}` },
    });
    if (!res.ok) return 0;
    const body = await res.json();
    const users = body?.data?.data ?? body?.data ?? [];
    for (const u of users) {
      if (!seedEmails.includes(u.email)) {
        await fetch(`${API_URL}/v2/users/${u.id}`, {
          method: 'DELETE',
          headers: { Authorization: `ApiKey ${API_KEY}` },
        }).catch(() => {});
        deleted++;
      }
    }
  } catch {
    // Best-effort
  }
  return deleted;
}

// ── Main ────────────────────────────────────────────────────

export default async function globalTeardown(): Promise<void> {
  console.log('\n[e2e] Global teardown starting...');
  const results: string[] = [];

  // 1. Bitbucket cleanup — decline PRs, delete branches
  console.log('[e2e] Cleaning up Bitbucket artifacts...');
  for (const repo of BB_REPOS) {
    const prsDeclined = await cleanupBitbucketPRs(repo);
    const branchesDeleted = await cleanupBitbucketBranches(repo);
    if (prsDeclined > 0 || branchesDeleted > 0) {
      results.push(`  ${repo}: ${prsDeclined} PRs declined, ${branchesDeleted} branches deleted`);
    }
  }

  // 2. Database cleanup — remove E2E-prefixed data
  console.log('[e2e] Cleaning up E2E test data...');
  const productsDeleted = await cleanupPrefixedProducts();
  const usersDeleted = await cleanupPrefixedUsers();
  if (productsDeleted > 0) results.push(`  Products: ${productsDeleted} deleted`);
  if (usersDeleted > 0) results.push(`  Users: ${usersDeleted} deleted`);

  // 3. MinIO — no direct cleanup (orphaned objects cleaned via DB removal)
  // 4. CoreCloud — no cleanup endpoint available

  // Summary
  if (results.length > 0) {
    console.log('[e2e] Cleanup results:');
    for (const line of results) console.log(line);
  } else {
    console.log('[e2e] No E2E artifacts found to clean up.');
  }

  console.log('[e2e] Global teardown complete.\n');
}
