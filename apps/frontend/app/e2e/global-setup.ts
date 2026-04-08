import { execSync } from 'node:child_process';

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const FRONTEND_URL = process.env.E2E_BASE_URL || 'http://localhost:4200';
const POSTGRES_PORT = process.env.E2E_POSTGRES_PORT || '5433';
const MINIO_PORT = process.env.E2E_MINIO_PORT || '8675';

async function checkService(name: string, url: string): Promise<void> {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(5_000) });
    if (!res.ok && res.status >= 500) {
      throw new Error(`${name} returned status ${res.status}`);
    }
  } catch (err) {
    throw new Error(
      `${name} is not reachable at ${url}. ` +
        `Start the dev stack with "nx start platform" before running E2E tests.\n` +
        `Original error: ${err instanceof Error ? err.message : err}`,
    );
  }
}

async function checkTcpPort(name: string, host: string, port: number): Promise<void> {
  const { createConnection } = await import('node:net');
  return new Promise<void>((resolve, reject) => {
    const sock = createConnection({ host, port, timeout: 3_000 }, () => {
      sock.destroy();
      resolve();
    });
    sock.on('error', (err) => {
      sock.destroy();
      reject(
        new Error(
          `${name} is not reachable at ${host}:${port}. ` +
            `Start the dev stack before running E2E tests.\n` +
            `Original error: ${err.message}`,
        ),
      );
    });
    sock.on('timeout', () => {
      sock.destroy();
      reject(new Error(`${name} connection timed out at ${host}:${port}`));
    });
  });
}

async function waitForApiHealth(maxWaitMs = 30_000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    try {
      const res = await fetch(`${API_URL}/v2/docs`, { signal: AbortSignal.timeout(3_000) });
      if (res.ok) return;
    } catch {
      // keep trying
    }
    await new Promise((r) => setTimeout(r, 1_000));
  }
  throw new Error(`API health check did not pass within ${maxWaitMs / 1000}s`);
}

function resetDatabase(): void {
  const repoRoot = execSync('git rev-parse --show-toplevel', { encoding: 'utf-8' }).trim();
  try {
    execSync(
      'npx prisma migrate reset --force --skip-generate',
      {
        cwd: repoRoot,
        env: {
          ...process.env,
          DATABASE_URL: `postgresql://concord:concord@localhost:${POSTGRES_PORT}/concord`,
        },
        stdio: 'pipe',
        timeout: 60_000,
      },
    );
  } catch (err) {
    const msg = err instanceof Error ? (err as any).stderr?.toString() || err.message : String(err);
    throw new Error(`Database reset failed:\n${msg}`);
  }
}

function runPlatformSeed(): void {
  const repoRoot = execSync('git rev-parse --show-toplevel', { encoding: 'utf-8' }).trim();
  try {
    execSync(
      'npx prisma db seed',
      {
        cwd: repoRoot,
        env: {
          ...process.env,
          DATABASE_URL: `postgresql://concord:concord@localhost:${POSTGRES_PORT}/concord`,
        },
        stdio: 'pipe',
        timeout: 60_000,
      },
    );
  } catch (err) {
    const msg = err instanceof Error ? (err as any).stderr?.toString() || err.message : String(err);
    throw new Error(`Database seed failed:\n${msg}`);
  }
}

async function checkExternalConnectivity(): Promise<void> {
  const warnings: string[] = [];

  // Bitbucket API — non-critical (some tests may skip)
  try {
    const res = await fetch('https://api.bitbucket.org/2.0/', { signal: AbortSignal.timeout(5_000) });
    if (!res.ok) warnings.push(`Bitbucket API returned ${res.status}`);
  } catch {
    warnings.push('Bitbucket API unreachable — Bitbucket-dependent tests will fail');
  }

  // CoreCloud — non-critical
  try {
    await checkTcpPort('CoreCloud auth', 'auth.office.corekinect.cloud', 2013);
  } catch {
    warnings.push('CoreCloud auth unreachable — CoreCloud-dependent tests will fail');
  }

  // K8s cluster — non-critical (only needed for MTIB stages)
  try {
    execSync('kubectl cluster-info 2>&1', { timeout: 5_000, stdio: 'pipe' });
  } catch {
    warnings.push('kubectl cluster-info failed — K8s/MTIB tests will fail');
  }

  // MTIB node — non-critical
  try {
    execSync('kubectl get node verdin-imx8mm-15005665 2>&1', { timeout: 5_000, stdio: 'pipe' });
  } catch {
    warnings.push('MTIB node not reachable — hardware-in-loop tests will fail');
  }

  if (warnings.length > 0) {
    console.warn('\n--- External connectivity warnings ---');
    for (const w of warnings) console.warn(`  [WARN] ${w}`);
    console.warn('--------------------------------------\n');
  }
}

/**
 * Global setup for the E2E story suite.
 *
 * 1. Verify docker-compose services are running (fail fast if not).
 * 2. Wipe + re-migrate the database.
 * 3. Run the platform seed (roles, permission sets, dev users).
 * 4. Wait for the API to become healthy after the reset.
 * 5. Check external connectivity (non-fatal warnings).
 */
export default async function globalSetup(): Promise<void> {
  console.log('\n[e2e] Global setup starting...');

  // 1 — Docker-compose services must be running
  console.log('[e2e] Checking docker-compose services...');
  await checkService('http-api', `${API_URL}/v2/docs`);
  await checkTcpPort('postgres', 'localhost', Number(POSTGRES_PORT));
  await checkTcpPort('minio', 'localhost', Number(MINIO_PORT));
  console.log('[e2e] All local services reachable.');

  // 2 — Database wipe + migration (DISABLED for resource pooling — other stages share the platform)
  // To enable for isolated runs, set E2E_RESET_DB=1
  if (process.env.E2E_RESET_DB === '1') {
    console.log('[e2e] Resetting database (prisma migrate reset --force)...');
    resetDatabase();
    console.log('[e2e] Database reset complete.');

    // 3 — Seed platform data
    console.log('[e2e] Seeding platform data...');
    runPlatformSeed();
    console.log('[e2e] Seed complete.');
  } else {
    console.log('[e2e] Skipping DB reset (E2E_RESET_DB not set — resource pooling mode).');
  }

  // 4 — Wait for API health
  console.log('[e2e] Waiting for API health...');
  await waitForApiHealth();
  console.log('[e2e] API is healthy.');

  // 5 — External connectivity (warnings only)
  await checkExternalConnectivity();

  // Store URLs in env for helpers
  process.env.E2E_API_URL = API_URL;
  process.env.E2E_BASE_URL = FRONTEND_URL;

  console.log('[e2e] Global setup complete.\n');
}
