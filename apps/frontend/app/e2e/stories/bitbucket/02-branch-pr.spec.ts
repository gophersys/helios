import { test, expect } from '../../fixtures';
import {
  createBranch,
  createFileCommit,
  deleteBranch,
  listBranches,
  createPR,
  declinePR,
  listOpenPRs,
  cleanupE2EBranches,
  cleanupE2EPRs,
} from '../../helpers/bitbucket';

/**
 * Bitbucket branch & PR lifecycle tests.
 *
 * Exercises the full lifecycle: create branches, open PRs, verify state,
 * decline PRs, delete branches, verify cleanup.
 *
 * Prerequisite: concord-main must exist in alpha_fw (sync.spec.ts ensures this).
 */

const REPO = 'alpha_fw';
const timestamp = Date.now();
const BRANCH_1 = `e2e/s5-test-${timestamp}`;
const BRANCH_2 = `e2e/s5-cache-test-${timestamp}`;

const hasBitbucketCredentials =
  !!process.env.BITBUCKET_EMAIL && !!process.env.BITBUCKET_API_TOKEN;

test.describe.configure({ mode: 'serial', timeout: 300_000 });

test.describe('Bitbucket: branch & PR lifecycle', () => {
  // Skip entire suite when credentials are not available
  test.skip(!hasBitbucketCredentials, 'BITBUCKET_EMAIL and BITBUCKET_API_TOKEN are required');

  let pr1Id: number;
  let pr2Id: number;

  // Safety cleanup before suite in case a previous run left debris
  test.beforeAll(async () => {
    test.setTimeout(300_000);
    await cleanupE2EPRs(REPO);
    await cleanupE2EBranches(REPO);
  });

  // ── Branch creation ───────────────────────────────────

  test('create feature branch "e2e/s5-test-{timestamp}" from concord-main', async () => {
    await createBranch(REPO, BRANCH_1, 'concord-main');
    // If we get here without throwing, the branch was created
  });

  test('verify branch appears in Bitbucket branch list', async () => {
    const branches = await listBranches(REPO, 'e2e/');
    const names = branches.map((b) => b.name);
    expect(names).toContain(BRANCH_1);
  });

  // ── PR creation ───────────────────────────────────────

  test('open PR: e2e/s5-test-{timestamp} → concord-main with title "E2E Test PR"', async () => {
    // Create a commit so the branch diverges from concord-main (Bitbucket rejects empty PRs)
    await createFileCommit(
      REPO,
      BRANCH_1,
      '.e2e-test',
      `E2E test file created at ${timestamp}`,
      'chore: e2e test commit',
    );

    const result = await createPR(
      REPO,
      BRANCH_1,
      'concord-main',
      'E2E Test PR',
    );
    pr1Id = result.id;

    expect(result.id).toBeGreaterThan(0);
    expect(result.url).toContain('bitbucket.org');
  });

  test('verify PR appears in open PR list', async () => {
    const prs = await listOpenPRs(REPO, 'concord-main');
    const ids = prs.map((p) => p.id);
    expect(ids).toContain(pr1Id);
  });

  test('PR has correct source and target branches', async () => {
    const prs = await listOpenPRs(REPO, 'concord-main');
    const pr = prs.find((p) => p.id === pr1Id);

    expect(pr).toBeDefined();
    expect(pr!.source.branch.name).toBe(BRANCH_1);
    expect(pr!.destination.branch.name).toBe('concord-main');
    expect(pr!.title).toBe('E2E Test PR');
  });

  // ── Second branch + PR ────────────────────────────────

  test('create second branch "e2e/s5-cache-test-{timestamp}" from same commit', async () => {
    await createBranch(REPO, BRANCH_2, 'concord-main');

    const branches = await listBranches(REPO, 'e2e/');
    const names = branches.map((b) => b.name);
    expect(names).toContain(BRANCH_2);
  });

  test('open second PR for cache verification', async () => {
    // Create a commit so the branch diverges
    await createFileCommit(
      REPO,
      BRANCH_2,
      '.e2e-cache-test',
      `E2E cache test file created at ${timestamp}`,
      'chore: e2e cache test commit',
    );

    const result = await createPR(
      REPO,
      BRANCH_2,
      'concord-main',
      'E2E Cache Test PR',
    );
    pr2Id = result.id;

    expect(result.id).toBeGreaterThan(0);
    expect(result.id).not.toBe(pr1Id);
  });

  // ── Cleanup lifecycle ─────────────────────────────────

  test('decline/close PR via API', async () => {
    await declinePR(REPO, pr1Id);
    await declinePR(REPO, pr2Id);

    // Verify they're no longer in the open list
    const openPRs = await listOpenPRs(REPO, 'concord-main');
    const openIds = openPRs.map((p) => p.id);
    expect(openIds).not.toContain(pr1Id);
    expect(openIds).not.toContain(pr2Id);
  });

  test('delete feature branches via API', async () => {
    await deleteBranch(REPO, BRANCH_1);
    await deleteBranch(REPO, BRANCH_2);
  });

  test('verify branches no longer appear in list', async () => {
    const branches = await listBranches(REPO, 'e2e/');
    const names = branches.map((b) => b.name);
    expect(names).not.toContain(BRANCH_1);
    expect(names).not.toContain(BRANCH_2);
  });
});
