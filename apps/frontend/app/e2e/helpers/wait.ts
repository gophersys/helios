/**
 * Wait/polling helpers for the E2E story suite.
 * Used for async operations like builds, validation runs, queue assignment.
 */
import type { Page } from '@playwright/test';

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';

async function apiGetRaw<T = unknown>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { Authorization: `ApiKey ${API_KEY}` },
  });
  const body = await res.json();
  return body.data;
}

// ── Generic poller ───────────────────────────────────────────

interface WaitOptions {
  timeout: number;
  interval: number;
  message: string;
}

/**
 * Poll `fetchFn` until `condition` returns true or timeout is reached.
 */
export async function waitFor<T>(
  fetchFn: () => Promise<T>,
  condition: (result: T) => boolean,
  options: WaitOptions,
): Promise<T> {
  const start = Date.now();
  let lastResult: T | undefined;
  let lastError: Error | undefined;

  while (Date.now() - start < options.timeout) {
    try {
      lastResult = await fetchFn();
      if (condition(lastResult)) return lastResult;
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
    }
    await new Promise((r) => setTimeout(r, options.interval));
  }

  const elapsed = ((Date.now() - start) / 1000).toFixed(1);
  throw new Error(
    `${options.message} (timed out after ${elapsed}s)` +
      (lastError ? `\nLast error: ${lastError.message}` : ''),
  );
}

// ── Specific waiters ─────────────────────────────────────────

export interface BuildRun {
  id: string;
  status: string;
  [key: string]: unknown;
}

export interface SessionRun {
  id: string;
  status: string;
  [key: string]: unknown;
}

export interface QueueEntry {
  id: string;
  status: string;
  [key: string]: unknown;
}

const TERMINAL_BUILD_STATUSES = ['SUCCESS', 'FAILED', 'ERROR', 'CANCELLED'];
const TERMINAL_SESSION_STATUSES = ['PASSED', 'FAILED', 'ERROR', 'CANCELLED'];

/**
 * Wait for a build run to reach a terminal state.
 */
export async function waitForBuildComplete(
  _page: Page,
  buildRunId: string,
  timeout = 600_000,
): Promise<BuildRun> {
  return waitFor(
    () => apiGetRaw<BuildRun>(`/v2/builds/runs/${buildRunId}`),
    (run) => TERMINAL_BUILD_STATUSES.includes(run.status),
    { timeout, interval: 5_000, message: `Build ${buildRunId} did not complete` },
  );
}

/**
 * Wait for a validation session to reach a terminal state.
 */
export async function waitForValidationComplete(
  _page: Page,
  sessionId: string,
  timeout = 600_000,
): Promise<SessionRun> {
  return waitFor(
    () => apiGetRaw<SessionRun>(`/v2/validation/runs/${sessionId}`),
    (run) => TERMINAL_SESSION_STATUSES.includes(run.status),
    { timeout, interval: 5_000, message: `Validation ${sessionId} did not complete` },
  );
}

/**
 * Wait for a queue entry to be assigned to a fixture.
 */
export async function waitForQueueAssignment(
  _page: Page,
  entryId: string,
  timeout = 120_000,
): Promise<QueueEntry> {
  return waitFor(
    () => apiGetRaw<QueueEntry>(`/v2/validation/queue/${entryId}`),
    (entry) => entry.status === 'ASSIGNED' || entry.status === 'RUNNING',
    { timeout, interval: 3_000, message: `Queue entry ${entryId} was not assigned` },
  );
}

/**
 * Wait for the git-poller to detect a change and create a build run.
 */
export async function waitForGitPollerDetection(
  _page: Page,
  productId: string,
  _branch: string,
  timeout = 120_000,
): Promise<BuildRun> {
  return waitFor(
    async () => {
      const runs = await apiGetRaw<BuildRun[] | { data: BuildRun[] }>(
        `/v2/builds/runs?productId=${productId}&limit=1`,
      );
      const list = Array.isArray(runs) ? runs : (runs as any)?.data || [];
      return list[0] as BuildRun;
    },
    (run) => !!run && !!run.id,
    { timeout, interval: 5_000, message: `Git-poller did not create a build for product ${productId}` },
  );
}
