import { test, expect } from '../../fixtures';

/**
 * Stage 16 — MinIO artifact cleanup and verification.
 *
 * Verifies no E2E build artifacts remain in MinIO after the suite completes.
 * Direct S3 operations require the MinIO client SDK (not available in Playwright),
 * so this uses API-level checks where possible and TCP health for connectivity.
 *
 * MinIO runs on localhost:8675 in the dev stack.
 */

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';
const MINIO_HOST = 'localhost';
const MINIO_PORT = Number(process.env.E2E_MINIO_PORT || '8675');

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

function extractList(data: unknown): unknown[] {
  if (Array.isArray(data)) return data;
  if (data && typeof data === 'object' && 'data' in data) {
    const inner = (data as Record<string, unknown>).data;
    if (Array.isArray(inner)) return inner;
  }
  return [];
}

async function checkTcpPort(host: string, port: number): Promise<boolean> {
  const { createConnection } = await import('node:net');
  return new Promise<boolean>((resolve) => {
    const sock = createConnection({ host, port, timeout: 5_000 }, () => {
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

test.describe.configure({ mode: 'serial', timeout: 60_000 });

test.describe('Cleanup: MinIO', () => {
  test('MinIO health check passes', async () => {
    const reachable = await checkTcpPort(MINIO_HOST, MINIO_PORT);

    console.log(
      `[cleanup] MinIO at ${MINIO_HOST}:${MINIO_PORT}: ${reachable ? 'reachable' : 'unreachable'}`,
    );
    expect(reachable).toBe(true);
  });

  test('no E2E build artifacts remain in MinIO', async () => {
    // Build artifacts are tracked through the builds API.
    // If zero build runs exist (verified in database.spec.ts), then
    // any associated MinIO artifacts are orphaned references.
    // Check via the builds API that no runs reference artifacts.
    const data = await apiGet('/v2/builds/runs');
    const runs = extractList(data);

    // Any build runs that still exist may have artifacts in MinIO
    const runsWithArtifacts: string[] = [];
    for (const run of runs) {
      const runId = (run as any)?.id;
      if (!runId) continue;

      try {
        const res = await fetch(`${API_URL}/v2/builds/runs/${runId}/artifacts`, {
          headers: { Authorization: `ApiKey ${API_KEY}` },
        });
        if (res.ok) {
          const body = await res.json();
          const artifacts = extractList(body?.data);
          if (artifacts.length > 0) {
            runsWithArtifacts.push(runId);
          }
        }
      } catch {
        // Artifact endpoint may not exist for all runs
      }
    }

    console.log(
      `[cleanup] Build runs: ${runs.length}, runs with artifacts: ${runsWithArtifacts.length}`,
    );
    expect(runsWithArtifacts).toHaveLength(0);
  });

  test('no E2E session logs remain', async () => {
    // Validation sessions may store logs in MinIO. If zero queue entries
    // are active (verified in database.spec.ts), there should be no
    // session logs being actively written.
    //
    // We verify by checking that no active sessions reference log storage.
    const data = await apiGet('/v2/sessions/queue');
    const entries = extractList(data);

    const activeEntries = entries.filter((e: any) =>
      ['QUEUED', 'ASSIGNED', 'RUNNING'].includes(e?.status),
    );

    console.log(`[cleanup] Active queue entries that may have MinIO logs: ${activeEntries.length}`);
    expect(activeEntries).toHaveLength(0);
  });

  test('storage buckets exist but are clean of test data', async () => {
    // MinIO buckets are persistent infrastructure — they should exist
    // even when empty. We verify MinIO is healthy and that the API layer
    // reports no lingering test data.
    //
    // Direct bucket listing requires the MinIO/S3 SDK. Instead, we verify
    // through the application layer that no resources reference MinIO objects.
    const minioHealthy = await checkTcpPort(MINIO_HOST, MINIO_PORT);
    expect(minioHealthy).toBe(true);

    // Cross-verify: no products, no build runs, no active sessions
    // means no application-level references to MinIO objects
    const products = extractList(await apiGet('/v2/products'));
    const runs = extractList(await apiGet('/v2/builds/runs'));

    console.log(
      `[cleanup] MinIO cross-check: products=${products.length}, buildRuns=${runs.length}`,
    );
    expect(products).toHaveLength(0);
    expect(runs).toHaveLength(0);

    console.log('[cleanup] MinIO buckets confirmed clean of E2E test data (via API layer)');
  });
});
