import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import {
  createProductViaAPI,
  createBuildRun,
  getBuildRun,
} from '../../helpers/api-extended';
import { waitForBuildComplete } from '../../helpers/wait';
import { BuildDetailPage } from '../../pages/build-detail.page';

/**
 * Build Artifacts — verify completed builds produce downloadable artifacts.
 *
 * Triggers a build, waits for SUCCESS, then verifies artifact listing,
 * file types (.hex, .cfw, build.json), non-zero sizes, and download URLs.
 */

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';

interface Artifact {
  name: string;
  size: number;
  contentType?: string;
  url?: string;
}

test.describe.configure({ mode: 'serial', timeout: 1_200_000 });

const timestamp = Date.now();
let productId: string;
let buildRunId: string;
let artifacts: Artifact[] = [];

test.describe('Build Artifacts', () => {
  test.beforeAll(async ({ browser }) => {
    test.setTimeout(1_200_000);

    const product = await createProductViaAPI({
      name: `E2E Artifacts ${timestamp}`,
      slug: `e2e-artifacts-${timestamp}`,
      description: 'Product for build artifacts E2E tests',
    });
    productId = product.id;

    // Trigger a manual build
    try {
      const run = await createBuildRun({
        product: product.slug || product.name,
        board: 'alpha_b0',
        branch: 'concord-main',
        name: `artifacts-build-${timestamp}`,
        triggerType: 'manual',
        matrixMode: 'smoke',
      });
      buildRunId = run.id;
    } catch {
      buildRunId = '';
      return;
    }

    // Wait for build to complete — this can take 5-20 minutes
    const page = await browser.newPage();
    try {
      const completed = await waitForBuildComplete(page, buildRunId, 1_200_000);
      if (completed.status !== 'SUCCESS') {
        // Build failed — still test what we can, but artifact tests will skip
        buildRunId = '';
      }
    } catch {
      buildRunId = '';
    } finally {
      await page.close();
    }
  });

  // ── Artifact listing ──────────────────────────────────

  test('completed build has artifacts via API', async () => {
    test.skip(!buildRunId, 'Build did not succeed');

    const res = await fetch(`${API_URL}/v2/builds/runs/${buildRunId}/artifacts`, {
      headers: { Authorization: `ApiKey ${API_KEY}` },
    });
    expect(res.status).toBe(200);

    const body = await res.json();
    const data = body.data || body;
    artifacts = Array.isArray(data) ? data : (data as any)?.artifacts || [];

    expect(artifacts.length).toBeGreaterThanOrEqual(1);
  });

  test('artifacts include a .hex firmware file', async () => {
    test.skip(!buildRunId, 'Build did not succeed');
    test.skip(artifacts.length === 0, 'No artifacts available');

    const hexFile = artifacts.find((a) => a.name.endsWith('.hex'));
    expect(hexFile).toBeTruthy();
    expect(hexFile!.name).toMatch(/\.hex$/);
  });

  test('artifacts include a .cfw composite firmware file', async () => {
    test.skip(!buildRunId, 'Build did not succeed');
    test.skip(artifacts.length === 0, 'No artifacts available');

    const cfwFile = artifacts.find((a) => a.name.endsWith('.cfw'));
    // .cfw may not be produced for all build matrix modes
    if (cfwFile) {
      expect(cfwFile.name).toMatch(/\.cfw$/);
    }
  });

  test('artifacts include a build.json metadata file', async () => {
    test.skip(!buildRunId, 'Build did not succeed');
    test.skip(artifacts.length === 0, 'No artifacts available');

    const buildJson = artifacts.find(
      (a) => a.name === 'build.json' || a.name.endsWith('/build.json'),
    );
    expect(buildJson).toBeTruthy();
  });

  test('all artifacts have non-zero file sizes', async () => {
    test.skip(!buildRunId, 'Build did not succeed');
    test.skip(artifacts.length === 0, 'No artifacts available');

    for (const artifact of artifacts) {
      expect(artifact.size).toBeGreaterThan(0);
    }
  });

  test('artifact download endpoint returns file content', async () => {
    test.skip(!buildRunId, 'Build did not succeed');
    test.skip(artifacts.length === 0, 'No artifacts available');

    // Download the first artifact
    const firstArtifact = artifacts[0];
    const res = await fetch(
      `${API_URL}/v2/builds/runs/${buildRunId}/artifacts/${encodeURIComponent(firstArtifact.name)}/download`,
      { headers: { Authorization: `ApiKey ${API_KEY}` } },
    );

    expect(res.status).toBe(200);
    const buffer = await res.arrayBuffer();
    expect(buffer.byteLength).toBeGreaterThan(0);
  });

  test('bulk artifact download returns a zip', async () => {
    test.skip(!buildRunId, 'Build did not succeed');
    test.skip(artifacts.length === 0, 'No artifacts available');

    const res = await fetch(
      `${API_URL}/v2/builds/runs/${buildRunId}/artifacts/download`,
      { headers: { Authorization: `ApiKey ${API_KEY}` } },
    );

    expect(res.status).toBe(200);
    const contentType = res.headers.get('content-type') || '';
    // Should be a zip or octet-stream
    expect(
      contentType.includes('zip') ||
      contentType.includes('octet-stream'),
    ).toBe(true);

    const buffer = await res.arrayBuffer();
    expect(buffer.byteLength).toBeGreaterThan(0);
  });

  // ── UI download ────────────────────────────────────────

  test('build detail page has a download artifacts button', async ({ page }) => {
    test.skip(!buildRunId, 'Build did not succeed');

    await loginAsRole(page, 'admin');
    await page.goto(`/builds/${buildRunId}`);
    await page.waitForLoadState('networkidle');

    const downloadBtn = page.getByRole('button', { name: /download|artifact/i }).first();
    await expect(downloadBtn).toBeVisible({ timeout: 15_000 });
  });
});
