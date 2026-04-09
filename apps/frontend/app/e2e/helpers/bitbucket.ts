/**
 * Bitbucket Cloud API helpers for E2E tests.
 *
 * Uses Bitbucket App Password authentication (HTTP Basic auth).
 * Credentials come from environment variables:
 *   BITBUCKET_EMAIL — workspace user email
 *   BITBUCKET_API_TOKEN — app password (not OAuth, not PAT)
 */

const BB_API = 'https://api.bitbucket.org/2.0';
const WORKSPACE = process.env.BITBUCKET_WORKSPACE ?? 'corekinect';

// ── Auth ──────────────────────────────────────────────────

function authHeader(): string {
  const email = process.env.BITBUCKET_EMAIL;
  const token = process.env.BITBUCKET_API_TOKEN;
  if (!email || !token) {
    throw new Error(
      'BITBUCKET_EMAIL and BITBUCKET_API_TOKEN env vars are required',
    );
  }
  return `Basic ${Buffer.from(`${email}:${token}`).toString('base64')}`;
}

function headers(includeContentType = true): Record<string, string> {
  const h: Record<string, string> = {
    Authorization: authHeader(),
    Accept: 'application/json',
  };
  if (includeContentType) {
    h['Content-Type'] = 'application/json';
  }
  return h;
}

// ── Internal fetch wrapper with retry on 429 ─────────────

const MAX_RETRIES = 8;
const BASE_DELAY_MS = 3_000;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function bbFetch(
  path: string,
  opts: RequestInit = {},
): Promise<Response> {
  const url = `${BB_API}${path}`;
  const optsHeaders = opts.headers as Record<string, string> | undefined;
  const hasBody = opts.body != null;
  const hasExplicitCT = optsHeaders?.['Content-Type'] != null;
  const includeContentType = hasBody && !hasExplicitCT;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    const res = await fetch(url, {
      ...opts,
      headers: { ...headers(includeContentType), ...(optsHeaders ?? {}) },
    });
    if (res.status === 429 && attempt < MAX_RETRIES) {
      const retryAfter = res.headers.get('retry-after');
      const delayMs = retryAfter
        ? Number(retryAfter) * 1_000
        : BASE_DELAY_MS * Math.pow(2, attempt);
      await sleep(delayMs);
      continue;
    }
    return res;
  }
  // Unreachable, but TypeScript needs it
  throw new Error(`bbFetch: exhausted retries for ${path}`);
}

async function bbFetchJson<T = unknown>(
  path: string,
  opts: RequestInit = {},
): Promise<T> {
  const res = await bbFetch(path, opts);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(
      `Bitbucket API ${opts.method ?? 'GET'} ${path} → ${res.status}: ${body}`,
    );
  }
  return res.json() as Promise<T>;
}

// ── Types ─────────────────────────────────────────────────

export interface BranchInfo {
  name: string;
  target: { hash: string };
}

export interface PR {
  id: number;
  title: string;
  state: string;
  source: { branch: { name: string } };
  destination: { branch: { name: string } };
  links: { html: { href: string } };
}

interface PaginatedResponse<T> {
  values: T[];
  next?: string;
  size?: number;
}

// ── Branch Operations ─────────────────────────────────────

/**
 * Get the HEAD SHA of a branch in a repo.
 */
export async function getBranchSHA(
  repo: string,
  branch: string,
): Promise<string> {
  const data = await bbFetchJson<BranchInfo>(
    `/repositories/${WORKSPACE}/${repo}/refs/branches/${encodeURIComponent(branch)}`,
  );
  return data.target.hash;
}

/**
 * Create a new branch from an existing branch.
 */
export async function createBranch(
  repo: string,
  name: string,
  fromBranch: string,
): Promise<void> {
  const fromSha = await getBranchSHA(repo, fromBranch);
  await bbFetchJson(
    `/repositories/${WORKSPACE}/${repo}/refs/branches`,
    {
      method: 'POST',
      body: JSON.stringify({
        name,
        target: { hash: fromSha },
      }),
    },
  );
}

/**
 * Delete a branch from a repo.
 */
export async function deleteBranch(
  repo: string,
  name: string,
): Promise<void> {
  const res = await bbFetch(
    `/repositories/${WORKSPACE}/${repo}/refs/branches/${encodeURIComponent(name)}`,
    { method: 'DELETE' },
  );
  // 204 = success, 404 = already gone, 409 = branch has open PRs — all acceptable
  if (!res.ok && res.status !== 404 && res.status !== 409) {
    const body = await res.text();
    throw new Error(`deleteBranch ${name} → ${res.status}: ${body}`);
  }
}

/**
 * Force-sync a target branch to match the HEAD of a source branch.
 *
 * Bitbucket doesn't have a native "force update ref" API for branches.
 * Strategy: delete the target branch and re-create it pointing at source HEAD.
 * If the target doesn't exist yet, just create it.
 */
export async function forceSyncBranch(
  repo: string,
  target: string,
  source: string,
): Promise<void> {
  const sourceSha = await getBranchSHA(repo, source);

  // Check if target already at the right SHA
  try {
    const targetSha = await getBranchSHA(repo, target);
    if (targetSha === sourceSha) {
      return; // Already in sync
    }
  } catch {
    // Target doesn't exist — that's fine, we'll create it
  }

  // Delete target (if it exists) and re-create at source SHA
  await deleteBranch(repo, target);
  await bbFetchJson(
    `/repositories/${WORKSPACE}/${repo}/refs/branches`,
    {
      method: 'POST',
      body: JSON.stringify({
        name: target,
        target: { hash: sourceSha },
      }),
    },
  );
}

/**
 * List branches, optionally filtering by prefix.
 */
export async function listBranches(
  repo: string,
  prefix?: string,
): Promise<BranchInfo[]> {
  const q = prefix
    ? `?q=name+~+%22${encodeURIComponent(prefix)}%22`
    : '';
  const data = await bbFetchJson<PaginatedResponse<BranchInfo>>(
    `/repositories/${WORKSPACE}/${repo}/refs/branches${q}`,
  );
  return data.values;
}

/**
 * Create a commit on a branch by writing a file via the source endpoint.
 * Used to make branches diverge so PRs can be opened.
 */
export async function createFileCommit(
  repo: string,
  branch: string,
  filePath: string,
  content: string,
  message: string,
): Promise<void> {
  const form = new URLSearchParams();
  form.append('branch', branch);
  form.append('message', message);
  form.append(filePath, content);

  const res = await bbFetch(
    `/repositories/${WORKSPACE}/${repo}/src`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form.toString(),
    },
  );

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`createFileCommit → ${res.status}: ${body}`);
  }
}

// ── PR Operations ─────────────────────────────────────────

/**
 * Create a pull request.
 */
export async function createPR(
  repo: string,
  source: string,
  target: string,
  title: string,
): Promise<{ id: number; url: string }> {
  const data = await bbFetchJson<PR>(
    `/repositories/${WORKSPACE}/${repo}/pullrequests`,
    {
      method: 'POST',
      body: JSON.stringify({
        title,
        source: { branch: { name: source } },
        destination: { branch: { name: target } },
      }),
    },
  );
  return { id: data.id, url: data.links.html.href };
}

/**
 * Decline (close without merging) a pull request.
 */
export async function declinePR(
  repo: string,
  prId: number,
): Promise<void> {
  try {
    await bbFetchJson(
      `/repositories/${WORKSPACE}/${repo}/pullrequests/${prId}/decline`,
      { method: 'POST' },
    );
  } catch (err: any) {
    // Ignore "already closed" — the PR was closed by another process or prior cleanup
    if (err.message?.includes('already closed')) return;
    throw err;
  }
}

/**
 * List open pull requests, optionally filtered by target branch.
 */
export async function listOpenPRs(
  repo: string,
  target?: string,
): Promise<PR[]> {
  let q = 'state="OPEN"';
  if (target) {
    q += ` AND destination.branch.name="${target}"`;
  }
  const data = await bbFetchJson<PaginatedResponse<PR>>(
    `/repositories/${WORKSPACE}/${repo}/pullrequests?q=${encodeURIComponent(q)}`,
  );
  return data.values;
}

// ── Cleanup ───────────────────────────────────────────────

/**
 * Decline all open PRs that have "E2E" or "[Test]" in the title,
 * or that target concord-main from an e2e/* branch.
 */
export async function cleanupE2EPRs(repo: string): Promise<void> {
  const prs = await listOpenPRs(repo);
  const e2ePRs = prs.filter(
    (pr) =>
      pr.title.includes('E2E') ||
      pr.title.includes('[Test]') ||
      pr.source.branch.name.startsWith('e2e/'),
  );
  for (const pr of e2ePRs) {
    try {
      await declinePR(repo, pr.id);
    } catch {
      // Best-effort cleanup
    }
  }
}

/**
 * Delete all branches matching "e2e/*" pattern.
 */
export async function cleanupE2EBranches(repo: string): Promise<void> {
  const branches = await listBranches(repo, 'e2e/');
  for (const branch of branches) {
    if (branch.name.startsWith('e2e/')) {
      try {
        await deleteBranch(repo, branch.name);
      } catch {
        // Best-effort cleanup
      }
    }
  }
}
