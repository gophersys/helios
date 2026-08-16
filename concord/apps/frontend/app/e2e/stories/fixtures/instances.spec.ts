import { test, expect } from '../../fixtures';
import {
  createFixture,
  getFixture,
  updateFixture,
  deleteFixture,
  listFixtures,
  createProductViaAPI,
} from '../../helpers/api-extended';

/**
 * Fixture instance CRUD tests.
 * Fixtures are physical test rigs (VALIDATION or MANUFACTURING) bound to a product.
 */

test.describe.configure({ mode: 'serial' });

test.describe('Fixture Instances: CRUD', () => {
  const uniqueSuffix = `e2e-${Date.now()}`;
  let productId: string;
  let valFixtureId: string;
  let mfgFixtureId: string;

  test.beforeAll(async () => {
    // Create a product to bind fixtures to
    const product = await createProductViaAPI({
      name: `E2E Fixture Product ${uniqueSuffix}`,
      slug: `e2e-fix-${uniqueSuffix}`,
    });
    productId = product.id;
  });

  test.afterAll(async () => {
    // Cleanup fixtures
    for (const id of [valFixtureId, mfgFixtureId]) {
      if (id) {
        try {
          await deleteFixture(id);
        } catch {
          // Best effort
        }
      }
    }
  });

  test('create VALIDATION fixture with name, product, and type', async () => {
    const fixture = await createFixture({
      name: `Val Fixture ${uniqueSuffix}`,
      productId,
      type: 'VALIDATION',
      description: 'E2E validation fixture',
      stationId: `VAL-${uniqueSuffix}`,
      slots: [{ slotIndex: 0, label: 'Slot 0' }],
    });

    expect(fixture).toBeTruthy();
    expect(fixture.id).toBeTruthy();
    valFixtureId = fixture.id;
  });

  test('fixture appears in list with correct product and type', async () => {
    const fixtures = await listFixtures();
    const list = Array.isArray(fixtures) ? fixtures : [];
    const found = list.find((f: any) => f.id === valFixtureId);
    expect(found).toBeTruthy();
    expect(found!.type).toBe('VALIDATION');
  });

  test('fixture detail page shows slots section', async () => {
    const fixture = await getFixture(valFixtureId);
    expect(fixture).toBeTruthy();
    expect(fixture.slots).toBeDefined();
    expect(Array.isArray(fixture.slots)).toBe(true);
    expect(fixture.slots!.length).toBeGreaterThanOrEqual(1);
  });

  test('fixture status is AVAILABLE after creation', async () => {
    const fixture = await getFixture(valFixtureId);
    expect(fixture.status).toBe('AVAILABLE');
  });

  test('create MANUFACTURING fixture for same product', async () => {
    const fixture = await createFixture({
      name: `Mfg Fixture ${uniqueSuffix}`,
      productId,
      type: 'MANUFACTURING',
      description: 'E2E manufacturing fixture',
      stationId: `MFG-${uniqueSuffix}`,
    });

    expect(fixture).toBeTruthy();
    expect(fixture.id).toBeTruthy();
    mfgFixtureId = fixture.id;
  });

  test('manufacturing fixture appears with correct type', async () => {
    const fixture = await getFixture(mfgFixtureId);
    expect(fixture.type).toBe('MANUFACTURING');
  });

  test('edit fixture: update name and description', async () => {
    const newName = `Val Fixture Updated ${uniqueSuffix}`;
    const updated = await updateFixture(valFixtureId, {
      name: newName,
      description: 'Updated description',
    } as any);
    expect(updated).toBeTruthy();

    const fetched = await getFixture(valFixtureId);
    expect((fetched as any).name).toBe(newName);
  });

  test('fixture stationId must be unique (conflict error on duplicate)', async () => {
    try {
      await createFixture({
        name: `Dup Station Fixture ${uniqueSuffix}`,
        productId,
        type: 'VALIDATION',
        stationId: `VAL-${uniqueSuffix}`, // Same as existing
      });
      expect(true).toBe(false); // Should not reach here
    } catch (error: any) {
      expect(error.message).toContain('409');
    }
  });

  test('fixture name must be unique (conflict error on duplicate)', async () => {
    try {
      await createFixture({
        name: `Mfg Fixture ${uniqueSuffix}`, // Same as existing
        productId,
        type: 'VALIDATION',
      });
      expect(true).toBe(false);
    } catch (error: any) {
      expect(error.message).toContain('409');
    }
  });
});
