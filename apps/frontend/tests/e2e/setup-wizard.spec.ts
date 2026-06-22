import { expect, test, type Page, type Route } from '@playwright/test';

// The SETUP WIZARD E2E — "the wizard is the supervisor's FSM made visible" (W4). It drives the
// in-workspace setup wizard (apps/frontend src/lib/chat/wizard/SetupWizard.svelte, rendered by the
// project-detail route when a project's status is `wizard`) over a FAKE supervisor file source + a
// fake session, so the WHOLE four-step content flow is provable WITHOUT a live supervisor (the live
// supervisor is the W6 end-to-end). Every gateway call the live wizard makes is INTERCEPTED here and
// served by an in-test fake supervisor:
//
//   GET  /gateway/projects/{id}                     → a project parked at status `wizard` with a
//                                                      supervisorAgentId (so the route mounts the wizard).
//   GET  /gateway/sessions/{id}/workspace           → the committed-file LIST (grows as the fake
//                                                      supervisor commits the questionnaire, then answers).
//   GET  /gateway/sessions/{id}/workspace/file?path → ONE committed file's text (questionnaire/answers).
//   POST /gateway/sessions/{id}/control             → the supervisor send: the BRIEF commits the
//                                                      questionnaire; each ANSWER commits that answer file.
//
// This exercises the real wiring (the real route, the real wizardSource → GatewayWorktreeSource read
// path, the real setupWizard parsing + advance guard) — only the BACKEND is faked, the browser code
// is the production code. The fake supervisor's committed files are the GROUND TRUTH the
// committed-asset assertions pin to.
//
// The matrix:
//   1 STACKS         the growable stack list renders; selecting/deselecting toggles; ≥1 gates Continue.
//   2 DESCRIBE       the 100-word limit is enforced; the brief posts to the supervisor (the control POST).
//   3 QUESTIONNAIRE  after the brief, the supervisor's committed questionnaire renders LIVE from the
//                    worktree (the exact committed file paths + bodies), and gates advancing to Q&A.
//   4 Q&A            each answer posts to the supervisor + commits an answers/* file; the open-question
//                    ADVANCE GUARD blocks Start-building until every question is answered.
//   + COMMITTED-ASSET RENDERING — the rendered questions are byte-for-byte the committed file bodies.
//   + UI-MATH a11y/contrast audit on the live wizard at each step (mechanical, non-vacuous).

const PROJECT_ID = 'proj-wizard-e2e';
const SUPERVISOR_ID = 'sess-supervisor-e2e';

// ── the fake supervisor's committed questionnaire (the GROUND TRUTH) ───────────────────────────────.
// One file = one question; the file body IS the question text. The wizard derives the question id
// from the filename (slug without extension) and sorts by path (the NN- prefix gives a stable order).
const QUESTIONNAIRE: { path: string; slug: string; body: string }[] = [
  {
    path: 'init/product/questionnaire/01-audience.md',
    slug: '01-audience',
    body: 'Who is the very first person who will use this, and what do they do today instead?',
  },
  {
    path: 'init/product/questionnaire/02-core-action.md',
    slug: '02-core-action',
    body: 'What is the single most important thing a user must be able to do on day one?',
  },
];

const BRIEF = 'A dashboard that turns my raw invoices into one clean monthly summary I can email.';

/** The fake supervisor's mutable committed-worktree state, mutated by the control POSTs: the brief
 *  commits the questionnaire; each answer commits an answers/<slug>.md file. The workspace LIST + the
 *  per-file READ are served straight off this map, so the wizard renders exactly what was committed. */
interface FakeWorktree {
  files: Map<string, string>; // worktree-relative path → committed text
}

/** installFakeSupervisor intercepts every gateway route the wizard touches and serves them from an
 *  in-test fake supervisor. Returns the worktree so a test can assert what was committed. */
async function installFakeSupervisor(page: Page): Promise<FakeWorktree> {
  const worktree: FakeWorktree = { files: new Map() };
  const envelope = (data: unknown) => JSON.stringify({ data, errors: [] as string[], kind: 'ok' });

  // GET /projects/{id} — a project parked at `wizard` with a supervisor session id, so the
  // project-detail route mounts the SetupWizard against this supervisor. The glob is scoped to the
  // same-origin /gateway proxy prefix so it intercepts the API call, NOT the SvelteKit page nav to
  // /projects/{id} (which shares the path suffix).
  await page.route(`**/gateway/projects/${PROJECT_ID}`, async (route: Route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: envelope({
        id: PROJECT_ID,
        name: 'invoice-dashboard',
        idea: BRIEF,
        kind: 'application',
        status: 'wizard',
        harness: 'claude',
        stacks: ['go', 'svelte'],
        services: [],
        supervisorAgentId: SUPERVISOR_ID,
        createdAt: '2026-06-22T00:00:00Z',
        updatedAt: '2026-06-22T00:00:00Z',
      }),
    });
  });

  // GET /sessions/{id}/workspace — the committed-file LIST (bare JSON, mirroring workspace_handler.go).
  await page.route(`**/gateway/sessions/${SUPERVISOR_ID}/workspace`, async (route: Route) => {
    const files = [...worktree.files.keys()].sort().map((path) => ({
      path,
      size: worktree.files.get(path)!.length,
      modifiedUnix: 1_700_000_000,
    }));
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ files }) });
  });

  // GET /sessions/{id}/workspace/file?path=<rel> — ONE committed file's text (the file-READ contract).
  await page.route(`**/gateway/sessions/${SUPERVISOR_ID}/workspace/file*`, async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.searchParams.get('path') ?? '';
    const text = worktree.files.get(path);
    if (text === undefined) {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ kind: 'not-found', message: 'absent' }),
      });
      return;
    }
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ path, kind: path.endsWith('.md') ? 'markdown' : 'text', text }),
    });
  });

  // POST /sessions/{id}/control — the supervisor SEND. The fake supervisor reacts to the turn text:
  //   • the BRIEF ("Product brief: …") → commit the whole questionnaire,
  //   • an ANSWER ("Answer to \"<slug>\": …") → commit init/product/answers/<slug>.md.
  await page.route(`**/gateway/sessions/${SUPERVISOR_ID}/control`, async (route: Route) => {
    const body = route.request().postDataJSON() as { command?: string; text?: string };
    const text = body?.text ?? '';
    if (text.includes('Product brief:')) {
      for (const question of QUESTIONNAIRE) worktree.files.set(question.path, question.body);
    } else {
      const match = text.match(/^Answer to "([^"]+)":\s*([\s\S]*)$/);
      if (match) {
        const [, slug, answer] = match;
        worktree.files.set(`init/product/answers/${slug}.md`, answer.trim());
      }
    }
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ admittedSeq: 1 }),
    });
  });

  return worktree;
}

// ── UI-MATH audit — a mechanical a11y + contrast check on the LIVE wizard (engine-true, non-vacuous).
//    Mirrors the create-product audit: it resolves every CSS color via a canvas (so oklch()/color-mix
//    read true), computes WCAG contrast on rendered text, and asserts accessible names + viewport fit. ──
interface AuditResult {
  tokenResolves: boolean;
  accentPainted: boolean;
  samples: number;
  unnamedControls: string[];
  unlabeledFields: number;
  lowContrast: { sample: string; ratio: number }[];
  withinViewport: boolean;
  duplicateIds: string[];
}

async function auditWizard(page: Page): Promise<AuditResult> {
  return page.evaluate(() => {
    const root = document.querySelector('[data-testid="setup-wizard"]') as HTMLElement;
    const probeCanvas = document.createElement('canvas');
    probeCanvas.width = probeCanvas.height = 1;
    const probeCtx = probeCanvas.getContext('2d', { willReadFrequently: true })!;
    const colorCache = new Map<string, [number, number, number, number]>();
    const parse = (c: string): [number, number, number, number] => {
      if (!c) return [0, 0, 0, 0];
      const hit = colorCache.get(c);
      if (hit) return hit;
      probeCtx.clearRect(0, 0, 1, 1);
      probeCtx.fillStyle = '#000';
      probeCtx.fillStyle = c;
      probeCtx.fillRect(0, 0, 1, 1);
      const [r, g, b, a] = probeCtx.getImageData(0, 0, 1, 1).data;
      const out: [number, number, number, number] = [r, g, b, a / 255];
      colorCache.set(c, out);
      return out;
    };
    const lum = (r: number, g: number, b: number): number => {
      const f = (v: number) => {
        const s = v / 255;
        return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
      };
      return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
    };
    const opaqueBg = (el: HTMLElement): [number, number, number] => {
      let node: HTMLElement | null = el;
      while (node) {
        const [r, g, b, a] = parse(getComputedStyle(node).backgroundColor);
        if (a > 0) return [r, g, b];
        node = node.parentElement;
      }
      return [255, 255, 255];
    };
    const ratio = (fg: string, el: HTMLElement): number => {
      const [fr, fg2, fb, fa] = parse(fg);
      const [br, bg, bb] = opaqueBg(el);
      const cr = fr * fa + br * (1 - fa);
      const cg = fg2 * fa + bg * (1 - fa);
      const cb = fb * fa + bb * (1 - fa);
      const l1 = lum(cr, cg, cb);
      const l2 = lum(br, bg, bb);
      const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
      return (hi + 0.05) / (lo + 0.05);
    };

    const cs = getComputedStyle(document.documentElement);
    const tokenResolves = cs.getPropertyValue('--color-primary').trim().length > 0;
    const accentBtn = root.querySelector(
      '[data-testid="setup-next"], [data-testid="setup-send-brief"], [data-testid="setup-finish"]',
    ) as HTMLElement | null;
    const accentPainted = accentBtn
      ? parse(getComputedStyle(accentBtn).backgroundColor)[3] > 0
      : false;

    const controls = Array.from(
      root.querySelectorAll('button, a[href], input, textarea, select, [role="button"]'),
    ) as HTMLElement[];
    const accName = (el: HTMLElement): string => {
      const aria = el.getAttribute('aria-label');
      if (aria && aria.trim()) return aria.trim();
      if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
        if (el.placeholder?.trim()) return el.placeholder.trim();
      }
      return (el.textContent ?? '').trim();
    };
    const unnamedControls = controls
      .filter((el) => getComputedStyle(el).display !== 'none' && accName(el).length === 0)
      .map((el) => `${el.tagName.toLowerCase()}.${el.className}`);
    const fields = Array.from(root.querySelectorAll('input, textarea')) as HTMLElement[];
    const unlabeledFields = fields.filter((el) => accName(el).length === 0).length;

    const textEls = Array.from(
      root.querySelectorAll(
        '.eyebrow, .lead, .screen__title, .stack__label, .stack__hint, .question__prompt, .question__path, .question__answer, .brief__count, .btn',
      ),
    ) as HTMLElement[];
    const lowContrast: { sample: string; ratio: number }[] = [];
    let samples = 0;
    for (const el of textEls) {
      const text = (el.textContent ?? '').trim();
      if (!text || getComputedStyle(el).display === 'none') continue;
      const style = getComputedStyle(el);
      const size = parseFloat(style.fontSize);
      const weight = parseInt(style.fontWeight, 10) || 400;
      const large = size >= 24 || (size >= 18.66 && weight >= 700);
      const min = large ? 3 : 4.5;
      const cr = ratio(style.color, el);
      samples++;
      if (cr + 0.05 < min)
        lowContrast.push({ sample: text.slice(0, 40), ratio: Math.round(cr * 100) / 100 });
    }

    const rect = root.getBoundingClientRect();
    const withinViewport =
      rect.left >= -1 &&
      rect.top >= -1 &&
      rect.right <= window.innerWidth + 1 &&
      rect.bottom <= window.innerHeight + 1;
    const ids = Array.from(root.querySelectorAll('[id]')).map((el) => el.id);
    const duplicateIds = ids.filter((id, i) => ids.indexOf(id) !== i);

    return {
      tokenResolves,
      accentPainted,
      samples,
      unnamedControls,
      unlabeledFields,
      lowContrast,
      withinViewport,
      duplicateIds,
    } satisfies AuditResult;
  });
}

function assertCleanAudit(audit: AuditResult, where: string): void {
  expect(audit.tokenResolves, `${where}: a generated theme token must resolve`).toBe(true);
  expect(
    audit.accentPainted,
    `${where}: the accent control must be painted (orphan-token guard)`,
  ).toBe(true);
  expect(
    audit.samples,
    `${where}: the contrast audit must judge real text (non-vacuous)`,
  ).toBeGreaterThan(0);
  expect(
    audit.unnamedControls,
    `${where}: every interactive control needs an accessible name`,
  ).toEqual([]);
  expect(audit.unlabeledFields, `${where}: every form field needs a label`).toBe(0);
  expect(audit.duplicateIds, `${where}: no duplicate ids`).toEqual([]);
  expect(audit.lowContrast, `${where}: text must meet WCAG AA contrast`).toEqual([]);
  expect(audit.withinViewport, `${where}: the wizard must fit the viewport`).toBe(true);
}

test.describe('the setup wizard — the supervisor FSM made visible (FAKE supervisor)', () => {
  test('stacks → describe → questionnaire (live committed assets) → Q&A → start building', async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    page.on('pageerror', (e) => pageErrors.push(e.message));

    const worktree = await installFakeSupervisor(page);

    // Mount the wizard route. The fake `GET /projects/{id}` parks it at `wizard`, so the route renders
    // SetupWizard against the fake supervisor session.
    await page.goto(`/projects/${PROJECT_ID}`);
    const wizard = page.getByTestId('setup-wizard');
    await expect(wizard).toBeVisible();
    await expect(wizard).toHaveAttribute('data-step', 'stacks');
    await expect(page.getByTestId('setup-project-name')).toHaveText('invoice-dashboard');

    // ── 1. STACKS — the growable list renders; selecting/deselecting toggles; ≥1 gates Continue. ──.
    const stacks = page.getByTestId('setup-stack');
    await expect(stacks).toHaveCount(3); // web / desktop / mobile (growable)
    // 'web' is selected by default → Continue enabled.
    await expect(page.locator('[data-testid="setup-stack"][data-stack-id="web"]')).toHaveAttribute(
      'data-selected',
      'true',
    );
    await expect(page.getByTestId('setup-next')).toBeEnabled();
    // Deselect web → no stacks → Continue disabled (the ≥1 guard).
    await page.locator('[data-testid="setup-stack"][data-stack-id="web"]').click();
    await expect(page.getByTestId('setup-next')).toBeDisabled();
    // Select desktop + mobile → enabled again.
    await page.locator('[data-testid="setup-stack"][data-stack-id="desktop"]').click();
    await page.locator('[data-testid="setup-stack"][data-stack-id="mobile"]').click();
    await expect(page.getByTestId('setup-next')).toBeEnabled();
    assertCleanAudit(await auditWizard(page), 'STACKS');
    await page.getByTestId('setup-next').click();

    // ── 2. DESCRIBE — the 100-word limit is enforced; the brief posts to the supervisor. ──.
    await expect(wizard).toHaveAttribute('data-step', 'describe');
    await expect(page.getByTestId('setup-send-brief')).toBeDisabled(); // empty brief
    // An over-limit brief (101 words) disables the send and flags the counter.
    const tooLong = Array.from({ length: 101 }, (_unused, i) => `w${i}`).join(' ');
    await page.getByTestId('setup-brief').fill(tooLong);
    await expect(page.getByTestId('setup-brief-count')).toContainText('101 / 100');
    await expect(page.getByTestId('setup-send-brief')).toBeDisabled();
    // The real, within-limit brief → send enabled; submitting POSTs the control turn (the brief).
    await page.getByTestId('setup-brief').fill(BRIEF);
    await expect(page.getByTestId('setup-send-brief')).toBeEnabled();
    assertCleanAudit(await auditWizard(page), 'DESCRIBE');
    const briefControl = page.waitForRequest(
      (r) => r.url().includes(`/sessions/${SUPERVISOR_ID}/control`) && r.method() === 'POST',
    );
    await page.getByTestId('setup-send-brief').click();
    // FE⇄fake-BE: the posted turn carried the brief + the chosen stacks.
    const briefBody = (await briefControl).postDataJSON() as { text?: string };
    expect(briefBody.text).toContain('Product brief:');
    expect(briefBody.text).toContain(BRIEF);
    expect(briefBody.text).toContain('desktop');
    // The fake supervisor committed the questionnaire in reaction to the brief.
    expect(worktree.files.has(QUESTIONNAIRE[0].path)).toBe(true);

    // ── 3. QUESTIONNAIRE — the supervisor's committed questions render LIVE from the worktree. The
    //    wizard polls the worktree, so the questions appear once the commit lands. COMMITTED-ASSET
    //    RENDERING: each rendered question is byte-for-byte the committed file body + its path. ──.
    await expect(wizard).toHaveAttribute('data-step', 'questionnaire');
    const previews = page.getByTestId('setup-question-preview');
    await expect(previews).toHaveCount(QUESTIONNAIRE.length, { timeout: 10_000 });
    for (const question of QUESTIONNAIRE) {
      const card = page.locator(
        `[data-testid="setup-question-preview"][data-question-id="${question.slug}"]`,
      );
      await expect(card).toHaveAttribute('data-path', question.path);
      await expect(card.locator('.question__prompt')).toHaveText(question.body);
    }
    await expect(wizard).toHaveAttribute('data-ready', 'true');
    assertCleanAudit(await auditWizard(page), 'QUESTIONNAIRE');
    await page.getByTestId('setup-next').click();

    // ── 4. Q&A — the open-question ADVANCE GUARD blocks Start-building until every question is
    //    answered; each answer posts to the supervisor + commits an answers/* file. ──.
    await expect(wizard).toHaveAttribute('data-step', 'qa');
    await expect(wizard).toHaveAttribute('data-open-questions', 'true');
    await expect(page.getByTestId('setup-finish')).toBeDisabled(); // open questions gate the finish
    await expect(page.getByTestId('setup-qa-item')).toHaveCount(QUESTIONNAIRE.length);

    // Answer each question in turn; each commits the matching answers/<slug>.md file.
    for (const question of QUESTIONNAIRE) {
      const item = page.locator(
        `[data-testid="setup-qa-item"][data-question-id="${question.slug}"]`,
      );
      await expect(item).toHaveAttribute('data-open', 'true');
      const answerText = `Answer for ${question.slug}`;
      await item.locator('[data-testid="setup-qa-input"]').fill(answerText);
      const answerControl = page.waitForRequest(
        (r) => r.url().includes(`/sessions/${SUPERVISOR_ID}/control`) && r.method() === 'POST',
      );
      await item.locator('[data-testid="setup-qa-send"]').click();
      // FE⇄fake-BE: the answer turn names the question slug + the answer text.
      const answerBody = (await answerControl).postDataJSON() as { text?: string };
      expect(answerBody.text).toContain(`Answer to "${question.slug}"`);
      expect(answerBody.text).toContain(answerText);
      // The committed answer renders back (read from the worktree), so the item closes.
      await expect(item).toHaveAttribute('data-open', 'false', { timeout: 10_000 });
      await expect(item.locator('[data-testid="setup-qa-answer"]')).toHaveText(answerText);
      // The fake supervisor committed the answer file.
      expect(worktree.files.get(`init/product/answers/${question.slug}.md`)).toBe(answerText);
    }

    // All answered → the advance guard opens → Start building is enabled, and finishing routes off the
    // wizard (the host's onfinish → enterWorkspace → /chat).
    await expect(wizard).toHaveAttribute('data-open-questions', 'false');
    await expect(page.getByTestId('setup-finish')).toBeEnabled();
    assertCleanAudit(await auditWizard(page), 'QA');
    await page.getByTestId('setup-finish').click();
    await expect(page).toHaveURL(/\/chat/);

    // No uncaught runtime fault across the whole journey.
    expect(pageErrors, 'no uncaught page errors across the wizard journey').toEqual([]);
  });
});
