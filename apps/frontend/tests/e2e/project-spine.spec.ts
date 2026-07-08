import { expect, test, type Page, type Route } from '@playwright/test';

// W4 (doc 17 §5) — the project SPINE render test: the Overview + Insight views over a FAKE project +
// a FAKE codeinsight Report. The gateway is not booted: the surfaces the spine reads are intercepted
// with a PATHNAME-PREDICATE page.route (never a '**/gateway/**' glob — under `vite dev` that glob also
// matches the app's own /src/lib/gateway/*.ts source modules and 404s the app's JS, breaking the route
// chunk's dynamic import). Two arms:
//   • GET /projects/{id}          → an enveloped projectView parked at `building` (so [id] renders the
//                                    OVERVIEW spine, not the loading stepper).
//   • GET /projects/{id}/insight  → the bare codeinsight Report (NOT enveloped — the handler writes the
//                                    Report directly): the READY arm serves a real report with entities;
//                                    the DEGRADE arm 503s so the Insight view renders the honest EmptyState.
// A green run PROVES the Overview renders the real project coordinates + status, the spine tab nav
// composes, and the Insight view renders EITHER a real HotspotMap+summary OR the honest-degrade path —
// with zero pageerrors.

const PROJECT_ID = 'proj-spine-demo';
const SUPERVISOR_ID = 'sess-spine-supervisor';

/** The fake project the route reads (enveloped; getProject unwraps `.data`). Parked at `building` with
 *  a supervisor id + coordinates, so [id] renders the OVERVIEW. */
const FAKE_PROJECT = {
  data: {
    id: PROJECT_ID,
    name: 'Aurora Ledger',
    idea: 'A double-entry ledger service.',
    kind: 'service',
    status: 'building',
    harness: 'claude',
    stacks: ['go', 'svelte'],
    services: ['postgres'],
    supervisorAgentId: SUPERVISOR_ID,
    repoUrl: 'https://github.com/eden-demo/aurora-ledger',
    defaultBranch: 'init/seed',
    createdAt: '2026-06-22T10:00:00Z',
    updatedAt: '2026-06-22T10:05:00Z',
  },
  errors: [],
  kind: '',
};

/** A minimal-but-real codeinsight Report (the wire shape @eden/visualization renders). NOT enveloped —
 *  the insight handler writes the bare Report at 200. Two entities → the HotspotMap has points to plot. */
const FAKE_REPORT = {
  schemaVersion: '1.0.0',
  repository: {
    identifier: 'Aurora Ledger',
    headCommit: 'abcdef0123456789abcdef0123456789abcdef01',
    analyzedAt: '2026-06-22T10:06:00Z',
    commitCount: 42,
  },
  window: { toCommit: 'abcdef0123456789abcdef0123456789abcdef01', revisions: 42 },
  entities: [
    {
      path: 'internal/ledger/posting.go',
      kind: 'file',
      language: 'go',
      lines: 320,
      cyclomatic: 18,
      maintainability: 68,
      churnAbsolute: 210,
      churnRelative: 0.65,
      changeFrequency: 12,
      hotspotScore: 0.82,
    },
    {
      path: 'internal/ledger/balance.go',
      kind: 'file',
      language: 'go',
      lines: 140,
      cyclomatic: 6,
      maintainability: 84,
      churnAbsolute: 40,
      churnRelative: 0.28,
      changeFrequency: 4,
      hotspotScore: 0.31,
    },
  ],
  couplings: [],
  ownership: [],
  summary: {
    lines: 460,
    entityCount: 2,
    technicalDebtRatio: 0.08,
    maintainabilityRating: 'B',
    busFactor: 2,
  },
  trends: [],
  views: [],
};

/** Wire the two spine surfaces onto deterministic fixtures. `insightMode` picks whether the insight
 *  endpoint serves a real report or 503s (the honest-degrade arm). Matched by PATHNAME, not a glob. */
async function stubGateway(page: Page, insightMode: 'report' | 'unavailable'): Promise<void> {
  await page.route(
    (url) => url.pathname.startsWith('/gateway/'),
    async (route: Route) => {
      const url = new URL(route.request().url());
      const path = url.pathname.replace(/^.*\/gateway/, '');

      if (path === `/projects/${PROJECT_ID}/insight`) {
        if (insightMode === 'report') {
          await route.fulfill({ json: FAKE_REPORT });
        } else {
          await route.fulfill({
            status: 503,
            json: {
              kind: 'unavailable',
              message: 'no worktree is materialized for this project yet',
            },
          });
        }
        return;
      }
      if (path === `/projects/${PROJECT_ID}`) {
        await route.fulfill({ json: FAKE_PROJECT });
        return;
      }
      if (path === '/healthz') {
        await route.fulfill({ json: { status: 'ok' } });
        return;
      }
      await route.fulfill({ status: 404, json: { kind: 'not-found', message: path } });
    },
  );
}

test.describe('project spine — Overview + Insight over a fake project + report', () => {
  test('the Overview renders the real project data + the spine tab nav', async ({ page }) => {
    const pageErrors: string[] = [];
    page.on('pageerror', (e) => pageErrors.push(e.message));

    await stubGateway(page, 'report');
    await page.goto(`/projects/${PROJECT_ID}`);

    // The OVERVIEW renders (not the loading stepper) — the real project name, status Badge, coordinates.
    await expect(page.getByTestId('project-overview')).toBeVisible();
    await expect(page.getByTestId('overview-name')).toHaveText('Aurora Ledger');
    await expect(page.getByTestId('overview-status')).toContainText('building');
    await expect(page.getByTestId('overview-idea')).toContainText('double-entry');
    // the coordinates are the real repo/branch/session (mono data).
    await expect(page.getByTestId('overview-repo')).toHaveAttribute(
      'href',
      'https://github.com/eden-demo/aurora-ledger',
    );
    await expect(page.getByTestId('overview-branch')).toHaveText('init/seed');
    await expect(page.getByTestId('overview-session')).toContainText(SUPERVISOR_ID);

    // the spine tab nav composes with Overview active.
    await expect(page.getByTestId('project-spine-nav')).toBeVisible();
    await expect(page.getByTestId('spine-overview')).toHaveAttribute('aria-current', 'page');
    await expect(page.getByTestId('spine-insight')).toBeVisible();

    expect(pageErrors, `uncaught exceptions: ${pageErrors.join(' | ')}`).toEqual([]);
  });

  test('the Insight view renders a real HotspotMap + summary numbers when the report is present', async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    page.on('pageerror', (e) => pageErrors.push(e.message));

    await stubGateway(page, 'report');
    await page.goto(`/projects/${PROJECT_ID}/insight`);

    // the Insight view resolves to the READY state — the summary numbers + the hotspot map render.
    await expect(page.getByTestId('project-insight')).toBeVisible();
    await expect(page.getByTestId('insight-hotspot')).toBeVisible();
    // the summary numbers are the real Report.summary (files = 2, maintainability = B).
    await expect(page.getByTestId('insight-commit')).toContainText('Aurora Ledger');
    await expect(page.locator('[data-value="2"]').first()).toBeVisible();
    await expect(page.getByText('B', { exact: true }).first()).toBeVisible();
    // the honest-degrade EmptyState is NOT shown (a real chart, not the apology).
    await expect(page.getByTestId('insight-empty')).toBeHidden();

    expect(pageErrors, `uncaught exceptions: ${pageErrors.join(' | ')}`).toEqual([]);
  });

  test('the Insight view degrades HONESTLY (an EmptyState, not a spinner-forever) on a 503', async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    page.on('pageerror', (e) => pageErrors.push(e.message));

    await stubGateway(page, 'unavailable');
    await page.goto(`/projects/${PROJECT_ID}/insight`);

    // the endpoint 503s → the Insight view renders the explanatory EmptyState, NEVER a hung spinner or
    // a fake chart (P-D6).
    await expect(page.getByTestId('insight-empty')).toBeVisible();
    await expect(page.getByTestId('insight-empty')).toContainText(
      /not available|time budget|worktree/i,
    );
    await expect(page.getByTestId('insight-hotspot')).toBeHidden();
    await expect(page.getByTestId('insight-loading')).toBeHidden();

    expect(pageErrors, `uncaught exceptions: ${pageErrors.join(' | ')}`).toEqual([]);
  });
});
