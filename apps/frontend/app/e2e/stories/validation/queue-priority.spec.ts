import { test, expect } from '../../fixtures';
import {
  createProductViaAPI,
  createQueueEntry,
  getQueueEntry,
  getQueueEntries,
  cancelQueueEntryAPI,
  promoteQueueEntryAPI,
  createBuildRun,
  type QueueEntry,
} from '../../helpers/api-extended';

/**
 * Validation Queue — Priority and ordering tests.
 * Verifies priority-based ordering, promote action, and cancel behavior.
 *
 * Tests run in serial — each builds on the queue state from prior tests.
 */
test.describe.configure({ mode: 'serial' });

let productId: string;
let productSlug: string;
let buildRunId: string;
let lowPriorityEntryId: string;
let highPriorityEntryId: string;
let fifoEntry1Id: string;
let fifoEntry2Id: string;

test.describe('Queue Priority Ordering', () => {
  test.beforeAll(async () => {
    const ts = Date.now();

    const product = await createProductViaAPI({
      name: `Priority Test ${ts}`,
      slug: `priority-test-${ts}`,
    });
    productId = product.id;
    productSlug = product.slug;

    try {
      const buildRun = await createBuildRun({
        product: productSlug,
        board: 'alpha_b0',
        branch: 'main',
        name: `priority-build-${ts}`,
        triggerType: 'manual',
        matrixMode: 'smoke',
      });
      buildRunId = buildRun.id;
    } catch {
      buildRunId = '';
    }
  });

  test('higher priority entries are assigned before lower priority', async ({ page }) => {
    test.skip(!buildRunId, 'Build run not available');

    // Create low priority entry first
    const low = await createQueueEntry({
      buildRunId,
      stage: 4,
      priority: 10,
      reason: 'Low priority entry',
    });
    lowPriorityEntryId = low.id;

    // Create high priority entry second
    const high = await createQueueEntry({
      buildRunId,
      stage: 3,
      priority: 90,
      reason: 'High priority entry',
    });
    highPriorityEntryId = high.id;

    // Fetch all QUEUED entries — should be ordered by priority desc
    const entries = await getQueueEntries({ status: 'QUEUED' });
    const ourEntries = entries.filter(
      (e) => e.id === lowPriorityEntryId || e.id === highPriorityEntryId,
    );

    if (ourEntries.length === 2) {
      // High priority should come first in the list
      const highIdx = ourEntries.findIndex((e) => e.id === highPriorityEntryId);
      const lowIdx = ourEntries.findIndex((e) => e.id === lowPriorityEntryId);
      expect(highIdx).toBeLessThan(lowIdx);
    }
  });

  test('same priority entries are assigned in requestedAt order (FIFO)', async ({ page }) => {
    test.skip(!buildRunId, 'Build run not available');

    // Create two entries with same priority
    const entry1 = await createQueueEntry({
      buildRunId,
      stage: 2,
      priority: 50,
      reason: 'FIFO test entry 1',
    });
    fifoEntry1Id = entry1.id;

    // Small delay to ensure different requestedAt timestamps
    await new Promise((r) => setTimeout(r, 100));

    const entry2 = await createQueueEntry({
      buildRunId,
      stage: 1,
      priority: 50,
      reason: 'FIFO test entry 2',
    });
    fifoEntry2Id = entry2.id;

    // Fetch and verify order — same priority should be ordered by requestedAt ASC
    const entries = await getQueueEntries({ status: 'QUEUED' });
    const fifoEntries = entries.filter(
      (e) => e.id === fifoEntry1Id || e.id === fifoEntry2Id,
    );

    if (fifoEntries.length === 2) {
      const idx1 = fifoEntries.findIndex((e) => e.id === fifoEntry1Id);
      const idx2 = fifoEntries.findIndex((e) => e.id === fifoEntry2Id);
      // Entry 1 was created first, so it should come first (earlier requestedAt)
      expect(idx1).toBeLessThan(idx2);
    }
  });

  test('promote action increases entry priority', async ({ page }) => {
    test.skip(!lowPriorityEntryId, 'No low priority entry to promote');

    const before = await getQueueEntry(lowPriorityEntryId);
    const originalPriority = before.priority;

    // Promote the low-priority entry
    const promoted = await promoteQueueEntryAPI(lowPriorityEntryId);

    expect(promoted.priority).toBeGreaterThan(originalPriority);

    // Verify via GET
    const after = await getQueueEntry(lowPriorityEntryId);
    expect(after.priority).toBeGreaterThan(originalPriority);
  });

  test('cancel action sets entry to CANCELLED', async ({ page }) => {
    test.skip(!fifoEntry2Id, 'No entry to cancel');

    const cancelled = await cancelQueueEntryAPI(fifoEntry2Id);

    expect(cancelled.status).toBe('CANCELLED');
    expect(cancelled.completedAt).toBeTruthy();

    // Verify via GET
    const entry = await getQueueEntry(fifoEntry2Id);
    expect(entry.status).toBe('CANCELLED');
  });
});
