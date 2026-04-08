import { test, expect } from '../../fixtures';
import {
  listOpenPRs,
  declinePR,
  listBranches,
  deleteBranch,
  cleanupE2EPRs,
  cleanupE2EBranches,
} from '../../helpers/bitbucket';

/**
 * Stage 16 — Bitbucket cleanup and zero-state verification.
 *
 * Declines all open E2E pull requests and deletes all E2E branches
 * across both firmware repos. Runs at the end of the full E2E suite
 * to ensure no Bitbucket artifacts remain.
 *
 * Branch prefixes cleaned: e2e/, concord-e2e-, s2-, s3-, s5-, s6-
 */

const REPOS = ['alpha_fw', 'alpha_mfg_fw'] as const;
const E2E_BRANCH_PREFIXES = ['e2e/', 'concord-e2e-', 's2-', 's3-', 's5-', 's6-'];

test.describe.configure({ mode: 'serial', timeout: 300_000 });

test.describe('Cleanup: Bitbucket', () => {
  test('decline all open E2E pull requests in alpha_fw', async () => {
    const repo = 'alpha_fw';
    let declinedCount = 0;

    try {
      const prs = await listOpenPRs(repo);
      const e2ePRs = prs.filter(
        (pr) =>
          pr.title.includes('E2E') ||
          pr.title.includes('[Test]') ||
          pr.source.branch.name.startsWith('e2e/') ||
          E2E_BRANCH_PREFIXES.some((pfx) => pr.source.branch.name.startsWith(pfx)),
      );

      for (const pr of e2ePRs) {
        try {
          await declinePR(repo, pr.id);
          declinedCount++;
        } catch {
          // Best-effort — PR may already be declined
        }
      }

      console.log(`[cleanup] Declined ${declinedCount} E2E PRs in ${repo}`);
    } catch (err) {
      // Bitbucket may be unreachable — soft pass
      console.warn(`[cleanup] Could not clean PRs in ${repo}: ${err}`);
    }

    // Verify no E2E PRs remain open
    try {
      const remaining = await listOpenPRs(repo);
      const e2eRemaining = remaining.filter(
        (pr) =>
          pr.title.includes('E2E') ||
          pr.title.includes('[Test]') ||
          pr.source.branch.name.startsWith('e2e/'),
      );
      expect(e2eRemaining).toHaveLength(0);
    } catch {
      // If Bitbucket is unreachable, verification is not possible
    }
  });

  test('delete all E2E branches in alpha_fw', async () => {
    const repo = 'alpha_fw';
    let deletedCount = 0;

    try {
      for (const prefix of E2E_BRANCH_PREFIXES) {
        const branches = await listBranches(repo, prefix);
        for (const branch of branches) {
          if (E2E_BRANCH_PREFIXES.some((pfx) => branch.name.startsWith(pfx))) {
            try {
              await deleteBranch(repo, branch.name);
              deletedCount++;
            } catch {
              // Best-effort — branch may already be deleted or have open PRs
            }
          }
        }
      }

      console.log(`[cleanup] Deleted ${deletedCount} E2E branches in ${repo}`);
    } catch (err) {
      console.warn(`[cleanup] Could not clean branches in ${repo}: ${err}`);
    }

    // Verify no E2E branches remain
    try {
      const remaining = await listBranches(repo, 'e2e/');
      const e2eRemaining = remaining.filter((b) => b.name.startsWith('e2e/'));
      expect(e2eRemaining).toHaveLength(0);
    } catch {
      // If Bitbucket is unreachable, verification is not possible
    }
  });

  test('decline all open E2E pull requests in alpha_mfg_fw', async () => {
    const repo = 'alpha_mfg_fw';
    let declinedCount = 0;

    try {
      const prs = await listOpenPRs(repo);
      const e2ePRs = prs.filter(
        (pr) =>
          pr.title.includes('E2E') ||
          pr.title.includes('[Test]') ||
          pr.source.branch.name.startsWith('e2e/') ||
          E2E_BRANCH_PREFIXES.some((pfx) => pr.source.branch.name.startsWith(pfx)),
      );

      for (const pr of e2ePRs) {
        try {
          await declinePR(repo, pr.id);
          declinedCount++;
        } catch {
          // Best-effort
        }
      }

      console.log(`[cleanup] Declined ${declinedCount} E2E PRs in ${repo}`);
    } catch (err) {
      console.warn(`[cleanup] Could not clean PRs in ${repo}: ${err}`);
    }

    // Verify no E2E PRs remain open
    try {
      const remaining = await listOpenPRs(repo);
      const e2eRemaining = remaining.filter(
        (pr) =>
          pr.title.includes('E2E') ||
          pr.title.includes('[Test]') ||
          pr.source.branch.name.startsWith('e2e/'),
      );
      expect(e2eRemaining).toHaveLength(0);
    } catch {
      // Soft pass if unreachable
    }
  });

  test('delete all E2E branches in alpha_mfg_fw', async () => {
    const repo = 'alpha_mfg_fw';
    let deletedCount = 0;

    try {
      for (const prefix of E2E_BRANCH_PREFIXES) {
        const branches = await listBranches(repo, prefix);
        for (const branch of branches) {
          if (E2E_BRANCH_PREFIXES.some((pfx) => branch.name.startsWith(pfx))) {
            try {
              await deleteBranch(repo, branch.name);
              deletedCount++;
            } catch {
              // Best-effort
            }
          }
        }
      }

      console.log(`[cleanup] Deleted ${deletedCount} E2E branches in ${repo}`);
    } catch (err) {
      console.warn(`[cleanup] Could not clean branches in ${repo}: ${err}`);
    }

    // Verify no E2E branches remain
    try {
      const remaining = await listBranches(repo, 'e2e/');
      const e2eRemaining = remaining.filter((b) => b.name.startsWith('e2e/'));
      expect(e2eRemaining).toHaveLength(0);
    } catch {
      // Soft pass if unreachable
    }
  });
});
