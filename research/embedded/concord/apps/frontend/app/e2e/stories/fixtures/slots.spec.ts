import { test, expect } from '../../fixtures';
import {
  createFixture,
  getFixture,
  deleteFixture,
  createSlot,
  deleteSlot,
  createProductViaAPI,
  createNode,
  assignNodeToSlot,
  deleteNode,
} from '../../helpers/api-extended';

/**
 * Fixture slot management tests.
 * Slots are positions within a fixture where nodes (MTIBs) can be assigned.
 */

test.describe.configure({ mode: 'serial' });

test.describe('Fixture Slots: Management', () => {
  const uniqueSuffix = `e2e-slot-${Date.now()}`;
  let productId: string;
  let fixtureId: string;
  let initialSlotId: string;
  let additionalSlotId: string;
  let nodeId: string;

  test.beforeAll(async () => {
    const product = await createProductViaAPI({
      name: `E2E Slot Product ${uniqueSuffix}`,
      slug: `e2e-slot-${uniqueSuffix}`,
    });
    productId = product.id;
  });

  test.afterAll(async () => {
    // Cleanup: unassign node, delete fixture, delete node
    if (fixtureId && initialSlotId && nodeId) {
      try {
        await assignNodeToSlot(fixtureId, initialSlotId, null);
      } catch {
        // Best effort
      }
    }
    if (nodeId) {
      try {
        await deleteNode(nodeId);
      } catch {
        // Best effort
      }
    }
    if (fixtureId) {
      try {
        await deleteFixture(fixtureId);
      } catch {
        // Best effort
      }
    }
  });

  test('fixture created with initial slots (based on config)', async () => {
    const fixture = await createFixture({
      name: `Slot Test Fixture ${uniqueSuffix}`,
      productId,
      type: 'VALIDATION',
      slots: [
        { slotIndex: 0, label: 'Primary DUT' },
      ],
    });
    fixtureId = fixture.id;

    const detail = await getFixture(fixtureId);
    expect(detail.slots).toBeDefined();
    expect(detail.slots!.length).toBe(1);
    expect(detail.slots![0].slotIndex).toBe(0);
    expect(detail.slots![0].label).toBe('Primary DUT');
    initialSlotId = detail.slots![0].id;
  });

  test('add additional slot to fixture', async () => {
    const slot = await createSlot(fixtureId, {
      slotIndex: 1,
      label: 'Secondary DUT',
    });
    expect(slot).toBeTruthy();
    expect(slot.id).toBeTruthy();
    additionalSlotId = slot.id;

    const detail = await getFixture(fixtureId);
    expect(detail.slots!.length).toBe(2);
  });

  test('slot has label and slotIndex', async () => {
    const detail = await getFixture(fixtureId);
    const slot = detail.slots!.find((s) => s.id === additionalSlotId);
    expect(slot).toBeTruthy();
    expect(slot!.slotIndex).toBe(1);
    expect(slot!.label).toBe('Secondary DUT');
  });

  test('slot shows unassigned when no node linked', async () => {
    const detail = await getFixture(fixtureId);
    for (const slot of detail.slots!) {
      expect(slot.nodeId).toBeNull();
    }
  });

  test('duplicate slotIndex in same fixture returns conflict', async () => {
    try {
      await createSlot(fixtureId, {
        slotIndex: 0, // Same as initial slot
        label: 'Duplicate',
      });
      expect(true).toBe(false);
    } catch (error: any) {
      expect(error.message).toContain('409');
    }
  });

  test('remove slot when no test executions linked', async () => {
    await deleteSlot(fixtureId, additionalSlotId);

    const detail = await getFixture(fixtureId);
    expect(detail.slots!.length).toBe(1);
    expect(detail.slots![0].id).toBe(initialSlotId);
    additionalSlotId = ''; // Clear so cleanup doesn't try to delete again
  });

  test('slot shows assigned node after assignment', async () => {
    // Create a node to assign
    const node = await createNode({
      name: `Slot Test Node ${uniqueSuffix}`,
      hostname: `e2e-slot-node-${uniqueSuffix}`,
      type: 'VALIDATION',
      ipAddress: '10.0.0.99',
    });
    nodeId = node.id;

    await assignNodeToSlot(fixtureId, initialSlotId, nodeId);

    const detail = await getFixture(fixtureId);
    const slot = detail.slots!.find((s) => s.id === initialSlotId);
    expect(slot).toBeTruthy();
    expect(slot!.nodeId).toBe(nodeId);
  });

  test('unassign node from slot sets nodeId to null', async () => {
    await assignNodeToSlot(fixtureId, initialSlotId, null);

    const detail = await getFixture(fixtureId);
    const slot = detail.slots!.find((s) => s.id === initialSlotId);
    expect(slot!.nodeId).toBeNull();
  });
});
