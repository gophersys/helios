import { test, expect } from '../../fixtures';
import {
  createFixtureDesign,
  deleteFixtureDesign,
  listFixtureDesigns,
  getFixtureDesign,
  updateFixtureDesign,
  createFixture,
  deleteFixture,
  createProductViaAPI,
} from '../../helpers/api-extended';
import { apiGet } from '../../helpers/api';

/**
 * Fixture Design CRUD tests.
 * Designs are versioned hardware specs that fixtures can reference.
 */

test.describe.configure({ mode: 'serial' });

test.describe('Fixture Designs: CRUD', () => {
  const uniqueSuffix = `e2e-${Date.now()}`;
  const designName = `Alpha E2E v1.2 ${uniqueSuffix}`;
  let designId: string;

  // Fetched dynamically from the seeded Alpha product's B0 revision
  let BOARD_REVISION_ID: string;

  test.beforeAll(async () => {
    // Fetch the seeded Alpha product's B0 revision ID
    const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
    const API_KEY = 'ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG';

    // First get the product list to find Alpha's ID
    const listRes = await fetch(`${API_URL}/v2/products`, {
      headers: { Authorization: `ApiKey ${API_KEY}` },
    });
    const listBody = await listRes.json();
    const products = listBody?.data?.data ?? listBody?.data ?? [];
    const alphaList = (Array.isArray(products) ? products : []).find((p: any) => p.slug === 'alpha');
    if (!alphaList) throw new Error('Seeded Alpha product not found');

    // Fetch product detail to get boards with revisions
    const detailRes = await fetch(`${API_URL}/v2/products/${alphaList.id}`, {
      headers: { Authorization: `ApiKey ${API_KEY}` },
    });
    const detailBody = await detailRes.json();
    const alpha = detailBody?.data;
    if (!alpha) throw new Error('Alpha product detail not found');

    const b0 = alpha.boards
      ?.flatMap((b: any) => b.revisions ?? [])
      ?.find((r: any) => r.version === 'B0');
    if (!b0) throw new Error('Alpha B0 revision not found');
    BOARD_REVISION_ID = b0.id;
  });

  test.afterAll(async () => {
    // Cleanup: delete design if it was created
    if (designId) {
      try {
        await deleteFixtureDesign(designId);
      } catch {
        // Best effort
      }
    }
  });

  test('create design with name, product, and revision', async () => {
    const design = await createFixtureDesign({
      name: designName,
      description: 'E2E test fixture design',
      boardRevisionId: BOARD_REVISION_ID,
      revision: '1.2',
    });

    expect(design).toBeTruthy();
    expect(design.id).toBeTruthy();
    designId = design.id;
  });

  test('design appears in list after creation', async () => {
    const designs = await listFixtureDesigns();
    // Designs endpoint returns paginated data
    const list = Array.isArray(designs) ? designs : [];
    const found = list.find((d: any) => d.id === designId);
    expect(found).toBeTruthy();
  });

  test('design detail returns correct fields', async () => {
    const design = await getFixtureDesign(designId);
    expect(design).toBeTruthy();
    expect((design as any).name).toBe(designName);
  });

  test('update design notes', async () => {
    const updated = await updateFixtureDesign(designId, {
      notes: 'Updated via E2E test',
    });
    expect(updated).toBeTruthy();
  });

  test('duplicate design name returns conflict error', async () => {
    try {
      await createFixtureDesign({
        name: designName,
        description: 'Duplicate name test',
        boardRevisionId: BOARD_REVISION_ID,
        revision: '1.2',
      });
      // Should not reach here
      expect(true).toBe(false);
    } catch (error: any) {
      expect(error.message).toContain('409');
    }
  });

  test('delete design with no fixture instances succeeds', async () => {
    // Create a temporary design to delete
    const tempDesign = await createFixtureDesign({
      name: `Temp Design ${uniqueSuffix}`,
      description: 'To be deleted',
      boardRevisionId: BOARD_REVISION_ID,
      revision: '1.0',
    });
    expect(tempDesign.id).toBeTruthy();

    await deleteFixtureDesign(tempDesign.id);

    // Verify it's gone
    try {
      await getFixtureDesign(tempDesign.id);
      expect(true).toBe(false); // Should 404
    } catch (error: any) {
      expect(error.message).toContain('404');
    }
  });
});

test.describe('Fixture Designs: Access Control', () => {
  // These tests verify that designs are accessible via API with correct permissions.
  // Role-based UI access is tested via the auth-extended helpers.

  test('designs endpoint returns data for authenticated user', async () => {
    const designs = await listFixtureDesigns();
    // Should not throw — returns empty list or array
    expect(designs).toBeDefined();
  });
});
