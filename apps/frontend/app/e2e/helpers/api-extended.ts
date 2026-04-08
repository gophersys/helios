/**
 * Extended API helpers for the E2E story suite.
 * Re-exports existing helpers and adds Bitbucket, CoreCloud, MTIB, Fixtures,
 * Users, Queue, Sessions, and cleanup helpers.
 *
 * Uses plain fetch (not Playwright's page.request) so they can be called from
 * global setup/teardown and non-page contexts.
 */

// Re-export the base helpers for convenience
export { apiGet, apiPost, apiPut, apiDelete, getProducts, createProduct, deleteProduct } from './api';

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';
const BB_API = 'https://api.bitbucket.org/2.0';

// ── Internal fetch wrappers ──────────────────────────────────

async function concordGet<T = unknown>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { Authorization: `ApiKey ${API_KEY}` },
  });
  const body = await res.json();
  if (!res.ok) throw new Error(`GET ${path} failed (${res.status}): ${JSON.stringify(body)}`);
  return body.data;
}

async function concordPost<T = unknown>(path: string, data: unknown): Promise<T> {
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

async function concordPut<T = unknown>(path: string, data: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'PUT',
    headers: {
      Authorization: `ApiKey ${API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(`PUT ${path} failed (${res.status}): ${JSON.stringify(body)}`);
  return body.data;
}

async function concordDelete(path: string): Promise<void> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'DELETE',
    headers: { Authorization: `ApiKey ${API_KEY}` },
  });
  if (!res.ok && res.status !== 404) {
    const body = await res.text();
    throw new Error(`DELETE ${path} failed (${res.status}): ${body}`);
  }
}

function bbHeaders(): Record<string, string> {
  const token = process.env.BITBUCKET_API_TOKEN;
  if (!token) throw new Error('BITBUCKET_API_TOKEN not set');
  return { Authorization: `Bearer ${token}` };
}

// ── Bitbucket ────────────────────────────────────────────────

export async function syncConcordMain(workspace: string, repo: string): Promise<void> {
  // No-op — the main branch is the source of truth; sync is implicit
}

export async function createBranch(
  workspace: string,
  repo: string,
  name: string,
  from: string,
): Promise<void> {
  const res = await fetch(`${BB_API}/repositories/${workspace}/${repo}/refs/branches`, {
    method: 'POST',
    headers: { ...bbHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      target: { hash: from },
    }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Create branch ${name} failed (${res.status}): ${body}`);
  }
}

export async function deleteBranch(workspace: string, repo: string, name: string): Promise<void> {
  const res = await fetch(
    `${BB_API}/repositories/${workspace}/${repo}/refs/branches/${name}`,
    { method: 'DELETE', headers: bbHeaders() },
  );
  if (!res.ok && res.status !== 404) {
    throw new Error(`Delete branch ${name} failed (${res.status})`);
  }
}

export async function createPR(
  workspace: string,
  repo: string,
  source: string,
  target: string,
  title: string,
): Promise<number> {
  const res = await fetch(`${BB_API}/repositories/${workspace}/${repo}/pullrequests`, {
    method: 'POST',
    headers: { ...bbHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title,
      source: { branch: { name: source } },
      destination: { branch: { name: target } },
    }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Create PR failed (${res.status}): ${body}`);
  }
  const data = await res.json();
  return data.id;
}

export async function declinePR(workspace: string, repo: string, prId: number): Promise<void> {
  const res = await fetch(
    `${BB_API}/repositories/${workspace}/${repo}/pullrequests/${prId}/decline`,
    { method: 'POST', headers: bbHeaders() },
  );
  if (!res.ok && res.status !== 404) {
    throw new Error(`Decline PR #${prId} failed (${res.status})`);
  }
}

export interface PR {
  id: number;
  title: string;
  state: string;
  source: { branch: { name: string } };
}

export async function listPRs(workspace: string, repo: string): Promise<PR[]> {
  const res = await fetch(
    `${BB_API}/repositories/${workspace}/${repo}/pullrequests?state=OPEN&pagelen=50`,
    { headers: bbHeaders() },
  );
  if (!res.ok) return [];
  const data = await res.json();
  return data.values || [];
}

// ── CoreCloud ────────────────────────────────────────────────

export async function cleanupCorecloudDevice(_deviceId: string): Promise<void> {
  // CoreCloud device cleanup is a no-op for now — no delete endpoint exists.
  // Devices persist across test runs. Future: unregister if endpoint becomes available.
}

// ── MTIB ─────────────────────────────────────────────────────

export async function checkMtibHealth(host: string, port: number): Promise<boolean> {
  const { createConnection } = await import('node:net');
  return new Promise<boolean>((resolve) => {
    const sock = createConnection({ host, port, timeout: 3_000 }, () => {
      sock.destroy();
      resolve(true);
    });
    sock.on('error', () => {
      sock.destroy();
      resolve(false);
    });
    sock.on('timeout', () => {
      sock.destroy();
      resolve(false);
    });
  });
}

// ── Products (extended) ──────────────────────────────────────

export interface ProductConfig {
  name: string;
  slug?: string;
  description?: string;
}

export interface Product {
  id: string;
  name: string;
  slug: string;
  description?: string;
}

export async function createProductViaAPI(config: ProductConfig): Promise<Product> {
  return concordPost<Product>('/v2/products', config);
}

export interface StageConfig {
  watchBranch?: string;
  triggerTypes?: string[];
  recipe?: string;
  boardRevisionId?: string;
}

export async function configureStage(
  productId: string,
  stage: number,
  config: StageConfig,
): Promise<void> {
  await concordPut(`/v2/products/${productId}/stages/${stage}`, config);
}

// ── Fixtures ─────────────────────────────────────────────────

export interface DesignConfig {
  name: string;
  description?: string;
  boardRevisionId?: string;
  slotCount?: number;
}

export interface FixtureDesign {
  id: string;
  name: string;
}

export async function createFixtureDesign(config: DesignConfig): Promise<FixtureDesign> {
  return concordPost<FixtureDesign>('/v2/fixtures/designs', config);
}

export interface FixtureConfig {
  name: string;
  designId?: string;
  type?: string;
  productId?: string;
}

export interface Fixture {
  id: string;
  name: string;
}

export async function createFixture(config: FixtureConfig): Promise<Fixture> {
  return concordPost<Fixture>('/v2/fixtures', config);
}

export async function assignNodeToSlot(
  fixtureId: string,
  slotId: string,
  nodeId: string,
): Promise<void> {
  await concordPut(`/v2/fixtures/${fixtureId}/slots/${slotId}`, { nodeId });
}

export interface NodeConfig {
  hostname: string;
  type?: string;
  address?: string;
}

export interface Node {
  id: string;
  hostname: string;
}

export async function createNode(config: NodeConfig): Promise<Node> {
  return concordPost<Node>('/v2/nodes', config);
}

// ── Users ────────────────────────────────────────────────────

export interface UserConfig {
  email: string;
  name: string;
  role: string;
  password?: string;
  permissionSetId?: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
}

export async function createUserViaAPI(config: UserConfig): Promise<User> {
  return concordPost<User>('/v2/users', config);
}

export async function deleteUserViaAPI(userId: string): Promise<void> {
  await concordDelete(`/v2/users/${userId}`);
}

// ── Queue ────────────────────────────────────────────────────

export interface QueueFilters {
  status?: string;
  productId?: string;
}

export interface QueueEntry {
  id: string;
  status: string;
  productId?: string;
}

export async function getQueueEntries(filters?: QueueFilters): Promise<QueueEntry[]> {
  const params = new URLSearchParams();
  if (filters?.status) params.set('status', filters.status);
  if (filters?.productId) params.set('productId', filters.productId);
  const qs = params.toString();
  return concordGet<QueueEntry[]>(`/v2/validation/queue${qs ? `?${qs}` : ''}`);
}

// ── Sessions ─────────────────────────────────────────────────

export interface Session {
  id: string;
  status: string;
}

export async function waitForSessionComplete(
  sessionId: string,
  timeout = 300_000,
): Promise<Session> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const session = await concordGet<Session>(`/v2/validation/runs/${sessionId}`);
    if (['PASSED', 'FAILED', 'ERROR', 'CANCELLED'].includes(session.status)) {
      return session;
    }
    await new Promise((r) => setTimeout(r, 3_000));
  }
  throw new Error(`Session ${sessionId} did not complete within ${timeout / 1000}s`);
}

// ── Cleanup ──────────────────────────────────────────────────

export async function resetDatabase(): Promise<void> {
  // Database reset is handled in global-setup via prisma CLI.
  // This function is a no-op for in-test use.
}

export async function cleanupBitbucketBranches(prefix: string): Promise<void> {
  const workspace = process.env.BITBUCKET_WORKSPACE || 'corekinect';
  const repo = 'alpha_fw';
  try {
    const res = await fetch(
      `${BB_API}/repositories/${workspace}/${repo}/refs/branches?q=name ~ "${prefix}"&pagelen=100`,
      { headers: bbHeaders() },
    );
    if (!res.ok) return;
    const data = (await res.json()) as { values?: Array<{ name: string }> };
    for (const branch of data.values || []) {
      await deleteBranch(workspace, repo, branch.name);
    }
  } catch {
    // Best effort
  }
}

export async function cleanupMinioArtifacts(_prefix: string): Promise<void> {
  // MinIO cleanup is handled at teardown via DB reset orphaning references.
  // Direct S3 cleanup would require the MinIO client SDK.
}
