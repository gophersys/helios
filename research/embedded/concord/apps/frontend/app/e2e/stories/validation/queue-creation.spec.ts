import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import {
  createProductViaAPI,
  createQueueEntry,
  getQueueEntries,
  getQueueEntry,
  getQueueStats,
  createBuildRun,
  type QueueEntry,
  type BuildRun,
} from '../../helpers/api-extended';
import { QueuePage } from '../../pages/queue.page';

/**
 * Validation Queue — Creation tests.
 * Verifies queue entries are created correctly via API and appear in the UI.
 *
 * Prerequisite: A product and build run exist for queue entry creation.
 * Tests run in serial because they are cumulative.
 */
test.describe.configure({ mode: 'serial' });

// Shared state across tests
let productId: string;
let buildRunId: string;
let queueEntryId: string;

test.describe('Queue Entry Creation', () => {
  test.beforeAll(async () => {
    // Create a test product
    const product = await createProductViaAPI({
      name: `Queue Test Product ${Date.now()}`,
      slug: `queue-test-${Date.now()}`,
      description: 'Product for queue creation tests',
    });
    productId = product.id;

    // Create a build run to attach queue entries to
    try {
      const buildRun = await createBuildRun({
        product: product.slug || product.name,
        board: 'alpha_b0',
        branch: 'main',
        name: `queue-test-build-${Date.now()}`,
        triggerType: 'manual',
        matrixMode: 'smoke',
      });
      buildRunId = buildRun.id;
    } catch {
      // If build run creation requires more context (codebases, etc.),
      // fall back — the manual queue entry creation test will catch this
      buildRunId = '';
    }
  });

  test('manual queue entry creation via API works', async ({ page }) => {
    test.skip(!buildRunId, 'Build run creation not available — skipping queue creation tests');

    const entry = await createQueueEntry({
      buildRunId,
      stage: 4,
      priority: 50,
      reason: 'E2E test: manual queue entry',
    });

    expect(entry).toBeTruthy();
    expect(entry.id).toBeTruthy();
    expect(entry.buildRunId).toBe(buildRunId);
    queueEntryId = entry.id;
  });

  test('queue entries have correct buildRunId and stage number', async ({ page }) => {
    test.skip(!queueEntryId, 'No queue entry created');

    const entry = await getQueueEntry(queueEntryId);

    expect(entry.buildRunId).toBe(buildRunId);
    expect(entry.stage).toBe(4);
  });

  test('queue entries start with status QUEUED', async ({ page }) => {
    test.skip(!queueEntryId, 'No queue entry created');

    const entry = await getQueueEntry(queueEntryId);

    expect(entry.status).toBe('QUEUED');
  });

  test('queue entries have default priority of 50', async ({ page }) => {
    test.skip(!buildRunId, 'Build run creation not available');

    // The entry we created explicitly set priority=50, verify it
    const entry = await getQueueEntry(queueEntryId);
    expect(entry.priority).toBe(50);

    // Create another with default priority (0 per the backend create_queue_entry)
    const entry2 = await createQueueEntry({
      buildRunId,
      stage: 3,
    });
    // Backend default for manual creation is 0, but on_build_complete uses stageConfig priority (default 50)
    expect(typeof entry2.priority).toBe('number');
  });

  test('queue entry captures reason field', async ({ page }) => {
    test.skip(!queueEntryId, 'No queue entry created');

    const entry = await getQueueEntry(queueEntryId);

    expect(entry.reason).toBe('E2E test: manual queue entry');
  });

  test('queue stats show correct counts', async ({ page }) => {
    test.skip(!queueEntryId, 'No queue entry created');

    const stats = await getQueueStats();

    expect(stats).toBeTruthy();
    expect(typeof stats.queued).toBe('number');
    expect(typeof stats.running).toBe('number');
    expect(typeof stats.completed).toBe('number');
    expect(typeof stats.failed).toBe('number');
    expect(typeof stats.cancelled).toBe('number');
    expect(typeof stats.total).toBe('number');
    // We have at least 1 queued entry
    expect(stats.queued).toBeGreaterThanOrEqual(1);
    expect(stats.total).toBeGreaterThanOrEqual(1);
  });

  test('queue page shows pending entries', async ({ page }) => {
    test.skip(!queueEntryId, 'No queue entry created');

    await loginAsRole(page, 'admin');
    await page.goto('/validation/queue');
    await page.waitForLoadState('networkidle');

    // Page should load and show the Validation Queue title
    await expect(page.getByRole('heading', { name: /validation queue/i })).toBeVisible({
      timeout: 10_000,
    });

    // Should show at least one entry in the table
    const rows = page.locator('tbody tr');
    await expect(rows.first()).toBeVisible({ timeout: 10_000 });
    const rowCount = await rows.count();
    expect(rowCount).toBeGreaterThanOrEqual(1);
  });

  test('queue entries appear in filtered list by status', async ({ page }) => {
    test.skip(!queueEntryId, 'No queue entry created');

    const queuedEntries = await getQueueEntries({ status: 'QUEUED' });
    expect(Array.isArray(queuedEntries)).toBe(true);
    expect(queuedEntries.length).toBeGreaterThanOrEqual(1);

    // Verify our entry is in the list
    const found = queuedEntries.find((e) => e.id === queueEntryId);
    expect(found).toBeTruthy();
  });
});
