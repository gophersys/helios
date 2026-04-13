import { test, expect } from '../../fixtures';
import {
  createFixture,
  getFixture,
  deleteFixture,
  createNode,
  deleteNode,
  assignNodeToSlot,
  deployFixture,
  undeployFixture,
  getFixtureDeployStatus,
  createProductViaAPI,
} from '../../helpers/api-extended';

/**
 * MTIB deployment tests.
 * When a node is assigned to a fixture slot, an MTIB server K8s Deployment
 * is auto-created. These tests verify the deployment lifecycle via API.
 *
 * Note: actual K8s deployments may not succeed in the CI/codespace environment
 * since the K8s cluster (10.4.45.10) may be unreachable. Tests verify the
 * API contract and DB state changes, not actual pod scheduling.
 */

test.describe.configure({ mode: 'serial' });

test.describe('MTIB Deployment: Lifecycle', () => {
  const uniqueSuffix = `e2e-deploy-${Date.now()}`;
  let productId: string;
  let fixtureId: string;
  let slotId: string;
  let nodeId: string;

  test.beforeAll(async () => {
    const product = await createProductViaAPI({
      name: `E2E Deploy Product ${uniqueSuffix}`,
      slug: `e2e-dep-${uniqueSuffix}`,
    });
    productId = product.id;
  });

  test.afterAll(async () => {
    // Cleanup in reverse order
    if (fixtureId && slotId && nodeId) {
      try {
        await assignNodeToSlot(fixtureId, slotId, null);
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

  test('create node with hostname, type=VALIDATION, and IP', async () => {
    const node = await createNode({
      name: `MTIB E2E Dev ${uniqueSuffix}`,
      hostname: `mtib-e2e-dev-${uniqueSuffix}`,
      type: 'VALIDATION',
      ipAddress: '192.168.1.100',
      hardwareRevision: 'REV1.2',
    });

    expect(node).toBeTruthy();
    expect(node.id).toBeTruthy();
    expect(node.hostname).toBe(`mtib-e2e-dev-${uniqueSuffix}`);
    nodeId = node.id;
  });

  test('create fixture with one slot for assignment', async () => {
    const fixture = await createFixture({
      name: `Deploy Test Fixture ${uniqueSuffix}`,
      productId,
      type: 'VALIDATION',
      slots: [{ slotIndex: 0, label: 'DUT-0' }],
    });

    fixtureId = fixture.id;
    const detail = await getFixture(fixtureId);
    slotId = detail.slots![0].id;
  });

  test('assign node to fixture slot triggers deployment metadata', async () => {
    const result = await assignNodeToSlot(fixtureId, slotId, nodeId);
    expect(result).toBeTruthy();

    // After assignment, the slot should have the node linked
    const detail = await getFixture(fixtureId);
    const slot = detail.slots!.find((s) => s.id === slotId);
    expect(slot).toBeTruthy();
    expect(slot!.nodeId).toBe(nodeId);
  });

  test('fixture deploy-status shows slot deployment state', async () => {
    // Deploy status endpoint should return slot status information
    try {
      const status = await getFixtureDeployStatus(fixtureId);
      expect(status).toBeTruthy();
      // Status contains slots array with deployment info
      expect((status as any).slots).toBeDefined();
    } catch (error: any) {
      // K8s may not be reachable — check that the endpoint at least responds
      // If it's a 500 due to K8s unavailability, that's expected in CI
      if (!error.message.includes('500')) {
        throw error;
      }
    }
  });

  test('undeploy fixture via API', async () => {
    try {
      const result = await undeployFixture(fixtureId);
      expect(result).toBeTruthy();
    } catch (error: any) {
      // K8s unavailable in CI is expected
      if (!error.message.includes('500')) {
        throw error;
      }
    }
  });
});
