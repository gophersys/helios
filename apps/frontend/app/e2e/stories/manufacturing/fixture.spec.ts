import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import {
  createProductViaAPI,
  createFixtureDesign,
  createFixture,
  createNode,
  assignNodeToSlot,
  deleteFixture,
  deleteFixtureDesign,
  deleteNode,
} from '../../helpers/api-extended';

/**
 * Manufacturing Fixture Setup — Create MANUFACTURING fixture, assign node, verify on /manufacturing.
 *
 * Tests run in serial: create design → create fixture → assign node → verify UI.
 */

test.describe.configure({ mode: 'serial' });

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';

async function apiPost<T = unknown>(path: string, data: unknown): Promise<T> {
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

async function apiDelete(path: string): Promise<void> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'DELETE',
    headers: { Authorization: `ApiKey ${API_KEY}` },
  });
  if (!res.ok && res.status !== 404) {
    const body = await res.text();
    throw new Error(`DELETE ${path} failed (${res.status}): ${body}`);
  }
}

test.describe('Manufacturing Fixture Setup', () => {
  const suffix = `e2e-mfg-fix-${Date.now()}`;
  let productId: string;
  let designId: string;
  let fixtureId: string;
  let nodeId: string;
  let slotId: string;

  test.beforeAll(async () => {
    // Create a product
    const product = await createProductViaAPI({
      name: `MFG Fixture Product ${suffix}`,
      slug: `mfg-fix-${suffix}`,
    });
    productId = product.id;
  });

  test.afterAll(async () => {
    // Cleanup in reverse order
    for (const [fn, id] of [
      [deleteFixture, fixtureId],
      [deleteFixtureDesign, designId],
      [deleteNode, nodeId],
      [() => apiDelete(`/v2/products/${productId}`), productId],
    ] as const) {
      if (id) {
        try {
          await (fn as (id: string) => Promise<void>)(id);
        } catch {
          // Best effort
        }
      }
    }
  });

  test('create MANUFACTURING fixture design for Alpha B0', async () => {
    // Fetch Alpha B0 revision ID dynamically
    const listRes = await fetch(`${API_URL}/v2/products`, {
      headers: { Authorization: `ApiKey ${API_KEY}` },
    });
    const listBody = await listRes.json();
    const products = listBody?.data?.data ?? [];
    const alpha = products.find((p: any) => p.slug === 'alpha');
    expect(alpha).toBeTruthy();
    const detailRes = await fetch(`${API_URL}/v2/products/${alpha.id}`, {
      headers: { Authorization: `ApiKey ${API_KEY}` },
    });
    const detailBody = await detailRes.json();
    const b0 = detailBody?.data?.boards
      ?.flatMap((b: any) => b.revisions ?? [])
      ?.find((r: any) => r.version === 'B0');
    expect(b0).toBeTruthy();

    const design = await createFixtureDesign({
      name: `MFG Design ${suffix}`,
      description: 'E2E manufacturing fixture design',
      boardRevisionId: b0.id,
      revision: '1.0',
    });

    expect(design).toBeTruthy();
    expect(design.id).toBeTruthy();
    designId = design.id;
  });

  test('create MANUFACTURING fixture instance', async () => {
    const fixture = await createFixture({
      name: `MFG Fixture ${suffix}`,
      productId,
      type: 'MANUFACTURING',
      designId,
      description: 'E2E manufacturing fixture',
      stationId: `MFG-${suffix}`,
      slots: [
        { slotIndex: 0, label: 'Slot 0' },
        { slotIndex: 1, label: 'Slot 1' },
      ],
    });

    expect(fixture).toBeTruthy();
    expect(fixture.id).toBeTruthy();
    expect(fixture.type || 'MANUFACTURING').toBe('MANUFACTURING');
    fixtureId = fixture.id;

    // Capture the first slot ID for node assignment
    if (fixture.slots && fixture.slots.length > 0) {
      slotId = fixture.slots[0].id;
    }
  });

  test('assign MTIB node to fixture slot', async () => {
    // Create a node (simulated MTIB)
    const node = await createNode({
      name: `MFG MTIB ${suffix}`,
      hostname: `mfg-mtib-${suffix}`,
      type: 'MANUFACTURING',
      ipAddress: '10.4.45.99',
      hardwareRevision: 'REV1.2',
    });
    expect(node).toBeTruthy();
    nodeId = node.id;

    // If we don't have a slot ID from fixture creation, create one
    if (!slotId) {
      const slot = await apiPost<{ id: string }>(`/v2/fixtures/${fixtureId}/slots`, {
        slotIndex: 0,
        label: 'Slot 0',
      });
      slotId = slot.id;
    }

    // Assign node to slot
    const result = await assignNodeToSlot(fixtureId, slotId, nodeId);
    expect(result).toBeTruthy();
  });

  test('fixture shows AVAILABLE on manufacturing page', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/manufacturing');
    await page.waitForLoadState('networkidle');

    // The fixtures tab is the default
    // Wait for fixture cards to load
    await page.waitForTimeout(1_000);

    // Look for our fixture by name
    const fixtureCard = page.getByText(`MFG Fixture ${suffix}`);
    await expect(fixtureCard).toBeVisible({ timeout: 10_000 });

    // Status badge should show AVAILABLE
    const availableBadge = page
      .locator('[class*="rounded-xl"]')
      .filter({ hasText: `MFG Fixture ${suffix}` })
      .getByText(/available/i);
    await expect(availableBadge).toBeVisible({ timeout: 5_000 });
  });

  test('manufacturing fixtures page shows fixture card with "New Session" button', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/manufacturing');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1_000);

    // Find the fixture card that contains our fixture name
    const card = page
      .locator('[class*="rounded-xl"]')
      .filter({ hasText: `MFG Fixture ${suffix}` });
    await expect(card).toBeVisible({ timeout: 10_000 });

    // The "New Session" button should be visible for admin (who has manufacturing:run)
    const newSessionBtn = card.getByRole('button', { name: /new session/i });
    await expect(newSessionBtn).toBeVisible();
  });

  test('Operator can see manufacturing fixtures (manufacturing:view)', async ({ page }) => {
    await loginAsRole(page, 'operator');
    await page.goto('/manufacturing');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1_000);

    // Operator should see the manufacturing page
    const heading = page.getByText('Manufacturing').first();
    await expect(heading).toBeVisible({ timeout: 10_000 });

    // Fixture should be visible
    const fixtureCard = page.getByText(`MFG Fixture ${suffix}`);
    await expect(fixtureCard).toBeVisible({ timeout: 10_000 });
  });
});
