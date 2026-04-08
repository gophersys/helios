import { test, expect } from '../../fixtures';
import {
  getBranchSHA,
  forceSyncBranch,
  cleanupE2EBranches,
  cleanupE2EPRs,
} from '../../helpers/bitbucket';

/**
 * Bitbucket sync tests — ensure concord-main tracks main in both firmware repos.
 *
 * These tests are ordered and cumulative: sync operations in earlier tests
 * set up state that later tests verify.
 */

const REPOS = ['alpha_fw', 'alpha_mfg_fw'] as const;

test.describe.configure({ mode: 'serial', timeout: 300_000 });

test.describe('Bitbucket: concord-main sync', () => {
  // Bitbucket API calls with rate-limit retries can take a while
  test.beforeAll(async () => {
    test.setTimeout(300_000);
    for (const repo of REPOS) {
      await cleanupE2EPRs(repo);
      await cleanupE2EBranches(repo);
    }
  });

  let alphaFwMainSha: string;
  let alphaFwConcordMainSha: string;

  test('fetch main branch HEAD SHA from alpha_fw', async () => {
    alphaFwMainSha = await getBranchSHA('alpha_fw', 'main');

    expect(alphaFwMainSha).toBeTruthy();
    expect(alphaFwMainSha).toMatch(/^[0-9a-f]{12,40}$/);
  });

  test('fetch concord-main branch HEAD SHA from alpha_fw', async () => {
    // concord-main may or may not exist yet — forceSyncBranch handles creation
    try {
      alphaFwConcordMainSha = await getBranchSHA('alpha_fw', 'concord-main');
      expect(alphaFwConcordMainSha).toMatch(/^[0-9a-f]{12,40}$/);
    } catch {
      // Branch doesn't exist yet — that's fine, sync test will create it
      alphaFwConcordMainSha = '';
    }
  });

  test('sync concord-main to match main HEAD (force update if diverged)', async () => {
    await forceSyncBranch('alpha_fw', 'concord-main', 'main');

    const sha = await getBranchSHA('alpha_fw', 'concord-main');
    const mainSha = await getBranchSHA('alpha_fw', 'main');
    expect(sha).toBe(mainSha);
  });

  test('sync concord-main for alpha_mfg_fw repo', async () => {
    await forceSyncBranch('alpha_mfg_fw', 'concord-main', 'main');

    const sha = await getBranchSHA('alpha_mfg_fw', 'concord-main');
    const mainSha = await getBranchSHA('alpha_mfg_fw', 'main');
    expect(sha).toBe(mainSha);
  });

  test('verify both repos have concord-main at same SHA as main', async () => {
    for (const repo of REPOS) {
      const mainSha = await getBranchSHA(repo, 'main');
      const concordMainSha = await getBranchSHA(repo, 'concord-main');
      expect(concordMainSha).toBe(mainSha);
    }
  });
});
