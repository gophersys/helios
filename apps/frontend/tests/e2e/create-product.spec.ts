import { expect, test, type Page, type Request, type Response } from '@playwright/test';

// The FIRST user-story E2E — "create a new project" — a comprehensive, REAL, full-stack Playwright
// journey with DATA verification at every step. It drives the production-shaped UI against a REAL
// agentgateway dev-serve over real REST + SSE (no mocked fetch/SSE): the dev-serve's DETERMINISTIC
// proposer (devserve/proposer.go) returns a real ProductConfig from the prompt, a REAL
// agentsession.Pool streams the agent, and the verdict-aware adapter drives the gate. NOTHING here
// is stubbed in the browser — the route intercepts below only OBSERVE the real wire traffic (and the
// one resilience case fails a request on purpose, which is a documented arm).
//
// The story (apps/frontend CreateProjectFlow.svelte + routes/chat/+page.svelte) — the animated,
// multi-screen "trust me" flow:
//   open app → start a new project → SPARK: say what you're building in one breath → THINKING:
//   Eden scopes it (POST /product/propose → a real ProductConfig) → SCOPE: the agent AUTO-SELECTS
//   the platform targets out of the palette; the project name is editable → STACK: the proposed
//   languages/frameworks/services reveal as chips → Build it → the session/product is created
//   carrying that spec (with the edited name) → the agent session opens and streams its first events.
//
// The matrix (each dimension asserts the ACTUAL captured data, never just "an element exists"):
//   1 FUNCTIONAL FLOW    every screen advances; Build creates a session.
//   2 DATA INTEGRITY     the rendered scope/stack reflect the propose RESPONSE; the create PAYLOAD
//                        carries the proposed config + the user's name edit (NOT a drifted shell).
//   3 FE⇄BE INTEGRATION  propose POST → rendered scope (no drift); create POST → a real session id;
//                        the real SSE events render (no drift backend→UI).
//   4 UI / DESIGN-MATH   a mechanical a11y + contrast audit on the LIVE flow at each screen, on
//                        Chromium AND WebKit; keyboard-navigable + focus visible; a generated theme
//                        token resolves (not empty) and the accent control is actually painted.
//   5 RESILIENCE         empty/whitespace intent validates (no propose call); a forced propose
//                        failure renders gracefully (no crash) and the user can retry.
//   6 LIFECYCLE          after creation the session stops cleanly; the UI returns to a sane state.
// Plus a visual sanity: the flow container stays within the viewport (no overflow/overlap).

// ── the deterministic dev-serve proposer output for INTENT (captured empirically against
//    devserve/proposer.go; this is the GROUND TRUTH the data-integrity assertions pin to) ──.
//   "Ship a payments backend storing records in postgres" →
//     productName "ship-payments-backend", kind "service", languages ["go"], frameworks [],
//     services ["postgres"], harness "claude", model "claude-fable-5",
//     sdlcPhases ["architecture","implementation","testing","qa"], posture "strict".
const INTENT = 'Ship a payments backend storing records in postgres';
const PROPOSED = {
  productName: 'ship-payments-backend',
  productKind: 'service',
  languages: ['go'],
  services: ['postgres'],
  harness: 'claude',
  model: 'claude-fable-5',
  phases: ['architecture', 'implementation', 'testing', 'qa'],
  posture: 'strict',
} as const;

// The EDIT the user makes in the flow: rename the project. The create payload MUST carry this name
// (proving the user's edit flows through), and the proposed spec otherwise rides faithfully.
const EDITED_NAME = 'acme-payments';

/** The ProductConfig shape the flow renders / posts (mirrors $lib/gateway/types ProductConfig). */
interface ProductConfig {
  productName: string;
  productKind: string;
  summary: string;
  stack: { languages: string[]; frameworks: string[] };
  services: string[];
  capabilities: { harness: string; model: string; toolGrants: string[] };
  sdlcPhases: string[];
  sandbox: { posture: string; egressAllow: string[] };
}

async function openChat(page: Page): Promise<void> {
  await page.goto('/chat');
  await expect(page.getByTestId('chat-app')).toBeVisible();
  // The gateway is reached same-origin through the vite `/gateway` proxy (the runner waited /healthz).
  await expect(page.getByTestId('gateway-health')).toHaveText('gateway up');
}

/** Capture the JSON body the dev-serve returned for POST /product/propose by OBSERVING the response
 *  (a passive listener — the request still hits the real backend). Returns the unwrapped data. */
function captureProposeResponse(page: Page): Promise<ProductConfig> {
  return page
    .waitForResponse(
      (r: Response) => r.url().includes('/product/propose') && r.request().method() === 'POST',
    )
    .then(async (r) => (await r.json()).data as ProductConfig);
}

/** Capture the JSON body the flow POSTed to /sessions by OBSERVING the request (passive). */
function captureCreateRequest(page: Page): Promise<{ harness: string; product?: ProductConfig }> {
  return page
    .waitForRequest((r: Request) => r.url().endsWith('/sessions') && r.method() === 'POST')
    .then((r) => r.postDataJSON() as { harness: string; product?: ProductConfig });
}

/** Capture the JSON body the flow POSTed to /projects (the Project the dashboard reads). */
function captureCreateProjectRequest(
  page: Page,
): Promise<{ name?: string; idea?: string; sessionId?: string; product?: ProductConfig }> {
  return page
    .waitForRequest((r: Request) => r.url().endsWith('/projects') && r.method() === 'POST')
    .then(
      (r) =>
        r.postDataJSON() as {
          name?: string;
          idea?: string;
          sessionId?: string;
          product?: ProductConfig;
        },
    );
}

// ── the UI-MATH audit: a mechanical, NON-VACUOUS a11y + contrast check on the LIVE rendered flow.
//    This runs in-page (real getComputedStyle), so it is engine-true on both Chromium and WebKit. It
//    is the design-math dimension the user requires as a first-class mechanical test — stricter than
//    a smoke check: it computes the WCAG contrast ratio on rendered text and fails on a real defect. ──

interface AuditResult {
  tokenResolves: boolean; // a generated theme var resolves to a non-empty value
  accentPainted: boolean; // the accent control is actually painted (not transparent) — catches the orphan-token bug
  samples: number; // how many text nodes the contrast pass actually judged (guards against a vacuous audit)
  unnamedControls: string[]; // interactive controls with no accessible name (a11y violation)
  unlabeledFields: number; // form inputs with neither a label nor an aria-label
  lowContrast: { sample: string; ratio: number }[]; // text below WCAG AA on the flow
  withinViewport: boolean; // the flow container fits the viewport (no overflow/overlap)
  duplicateIds: string[]; // duplicate element ids inside the flow (a11y/structure violation)
}

async function auditFlow(page: Page): Promise<AuditResult> {
  return page.evaluate(() => {
    const root = document.querySelector('[data-testid="create-flow"]') as HTMLElement;

    // Resolve ANY CSS color string (oklch(), rgb(), rgba(), color-mix(), a named color) to its
    // actual painted sRGB + alpha by letting a 2D canvas rasterize it. The generated @eden/theme
    // emits colors as oklch(...) and uses color-mix(...), which a naive rgb() regex cannot read —
    // the canvas is the engine-true resolver (Chromium AND WebKit), so the contrast judges the real
    // painted pixels, not a parse guess. A color the engine cannot paint resolves to transparent.
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
      probeCtx.fillStyle = c; // an unparseable color leaves the prior value; we cleared to transparent first
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
    // Composite a (possibly translucent) foreground over the nearest opaque ancestor background.
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
      // Composite the text color over its background by its alpha (so translucent text is judged fairly).
      const cr = fr * fa + br * (1 - fa);
      const cg = fg2 * fa + bg * (1 - fa);
      const cb = fb * fa + bb * (1 - fa);
      const l1 = lum(cr, cg, cb);
      const l2 = lum(br, bg, bb);
      const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
      return (hi + 0.05) / (lo + 0.05);
    };

    // A generated theme token resolves to a real value (the flow reads the C21 math substrate).
    const cs = getComputedStyle(document.documentElement);
    const tokenResolves = cs.getPropertyValue('--color-primary').trim().length > 0;

    // The accent control (Let's build it / Looks right / Build it) is actually painted — the orphan-
    // token bug left it transparent. Assert the primary action has a non-transparent background.
    const accentBtn = root.querySelector(
      '[data-testid="create-start"], [data-testid="create-launch"]',
    ) as HTMLElement | null;
    const accentPainted = accentBtn
      ? parse(getComputedStyle(accentBtn).backgroundColor)[3] > 0
      : false;

    // Interactive controls must each have an accessible name.
    const controls = Array.from(
      root.querySelectorAll(
        'button, a[href], input, textarea, select, [role="radio"], [role="button"]',
      ),
    ) as HTMLElement[];
    const accName = (el: HTMLElement): string => {
      const aria = el.getAttribute('aria-label');
      if (aria && aria.trim()) return aria.trim();
      const labelledby = el.getAttribute('aria-labelledby');
      if (labelledby) {
        const t = labelledby
          .split(/\s+/)
          .map((id) => document.getElementById(id)?.textContent ?? '')
          .join(' ')
          .trim();
        if (t) return t;
      }
      if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
        const labels = (el as HTMLInputElement).labels;
        if (labels && labels.length && (labels[0].textContent ?? '').trim())
          return labels[0].textContent!.trim();
        if (el.placeholder?.trim()) return el.placeholder.trim();
      }
      return (el.textContent ?? '').trim();
    };
    const unnamedControls = controls
      .filter((el) => getComputedStyle(el).display !== 'none' && accName(el).length === 0)
      .map((el) => `${el.tagName.toLowerCase()}.${el.className}`);

    // Form fields must be labelled (an aria-label, or — acceptably for a free text box — a placeholder).
    const fields = Array.from(root.querySelectorAll('input, textarea')) as HTMLElement[];
    const unlabeledFields = fields.filter((el) => accName(el).length === 0).length;

    // Contrast on the flow's rendered text vs its background (sample the eyebrow, leads, targets,
    // chips, runline, buttons). WCAG AA is 4.5:1 for normal text; we sample visible text nodes.
    const textEls = Array.from(
      root.querySelectorAll(
        '.eyebrow, .lead, .summary, .screen__title, .targets__caption, .target__label, .target__hint, .chip, .runline, .btn, .thinking-line',
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

    // The flow container fits the viewport (no overflow/overlap at a standard viewport).
    const rect = root.getBoundingClientRect();
    const withinViewport =
      rect.left >= -1 &&
      rect.top >= -1 &&
      rect.right <= window.innerWidth + 1 &&
      rect.bottom <= window.innerHeight + 1;

    // Duplicate ids inside the flow.
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

/** Assert the audit is clean (used at each screen). Fails LOUDLY with the offending data so a real
 *  regression names the exact control/sample — never a vacuous green. */
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
  expect(audit.withinViewport, `${where}: the flow must fit the viewport`).toBe(true);
}

test.describe('create a new project — full-stack journey against a real dev-serve (FAKE arm)', () => {
  test('spark → scope (auto-selected targets) → stack → build with the edited name → stream first events → stop', async ({
    page,
  }, testInfo) => {
    // Track real runtime faults across the journey. An uncaught exception (pageerror) is a hard
    // crash and is asserted to be zero. Console errors are captured WITHOUT exclusions: the gateway
    // now drives the SINGLE opening turn from the product preamble and the client only records the
    // user bubble locally (no redundant follow-up prompt), so there is no illegal-prompt 409 and no
    // failed-fetch line to filter out. A non-empty console_errors set is therefore a real fault —
    // this guard is what would now catch a regression to the old double-send.
    const pageErrors: string[] = [];
    page.on('pageerror', (e) => pageErrors.push(e.message));
    const console_errors: string[] = [];
    page.on('console', (m) => {
      if (m.type() === 'error') console_errors.push(m.text());
    });

    await openChat(page);

    // ── 1. FUNCTIONAL FLOW + 4. UI-MATH: open the flow (SPARK) ───────────────────.
    await page.getByTestId('new-session').first().click();
    const flow = page.getByTestId('create-flow');
    await expect(flow).toBeVisible();
    await expect(flow).toHaveAttribute('data-step', 'spark');
    assertCleanAudit(await auditFlow(page), 'SPARK');

    // ── 5. RESILIENCE (validation): a whitespace-only intent must NOT propose ─────.
    await page.getByTestId('create-spark').fill('   ');
    await expect(page.getByTestId('create-start')).toBeDisabled();
    let proposedWhileBlank = false;
    const blankWatcher = page
      .waitForRequest((r) => r.url().includes('/product/propose'), { timeout: 1200 })
      .then(() => {
        proposedWhileBlank = true;
      })
      .catch(() => {});
    await page
      .getByTestId('create-start')
      .click({ force: true })
      .catch(() => {});
    await blankWatcher;
    expect(proposedWhileBlank, 'a blank intent must not trigger a propose').toBe(false);

    // ── type the real intent → SPARK → propose → SCOPE. Capture the propose RESPONSE. ──.
    await page.getByTestId('create-spark').fill(INTENT);
    const proposeBody = captureProposeResponse(page);
    await page.getByTestId('create-start').click();
    const proposed = await proposeBody;
    // W3: the create flow is full-screen on WizardShell and collapses SCOPE+STACK into ONE editable
    // REVIEW screen — the data-step walk is now spark → thinking → review (was spark/thinking/scope/
    // stack). SPARK advances straight to REVIEW after the propose round-trip.
    await expect(flow).toHaveAttribute('data-step', 'review');

    // ── 2 + 3. DATA INTEGRITY / FE⇄BE: the propose RESPONSE carried the deterministic config ──.
    expect(proposed.productName).toBe(PROPOSED.productName);
    expect(proposed.productKind).toBe(PROPOSED.productKind);
    expect(proposed.stack.languages).toEqual(PROPOSED.languages);
    expect(proposed.services).toEqual(PROPOSED.services);
    expect(proposed.capabilities.harness).toBe(PROPOSED.harness);
    expect(proposed.capabilities.model).toBe(PROPOSED.model);
    expect(proposed.sdlcPhases).toEqual(PROPOSED.phases);
    expect(proposed.sandbox.posture).toBe(PROPOSED.posture);

    // ── the RENDERED review reflects that response (no drift backend→UI). The name seeds editable;
    //    the summary shows; and the agent AUTO-SELECTED the right platform target (a Go service →
    //    the "service" target is selected, the app-only targets are not). W3: SCOPE + STACK are one
    //    REVIEW screen now, so the targets AND the stack chips AND the run-line all render together. ──.
    await expect(page.getByTestId('create-name')).toHaveValue(PROPOSED.productName);
    await expect(page.getByTestId('create-summary')).toContainText(proposed.summary);
    const serviceTarget = page.locator('[data-testid="create-target"][data-target-id="service"]');
    await expect(serviceTarget).toHaveAttribute('data-selected', 'true');
    await expect(serviceTarget).toContainText('Service');
    // At least one target is selected (the agent always picks something buildable).
    await expect(
      page.locator('[data-testid="create-target"][data-selected="true"]').first(),
    ).toBeVisible();

    // ── the proposed stack reveals as chips (the language + the service), and the build harness/model
    //    are named (the capability binding, no drift) — all on the same REVIEW screen. ──.
    await expect(
      page.locator('[data-testid="create-stack-item"]').filter({ hasText: PROPOSED.languages[0] }),
    ).toHaveCount(1);
    await expect(
      page.locator('[data-testid="create-stack-item"]').filter({ hasText: PROPOSED.services[0] }),
    ).toHaveCount(1);
    await expect(page.getByTestId('create-runline')).toContainText(PROPOSED.harness);
    await expect(page.getByTestId('create-runline')).toContainText(PROPOSED.model);
    assertCleanAudit(await auditFlow(page), 'REVIEW');

    // ── the user EDIT: rename the project. It must land in the create payload (NOT the proposed name). ──.
    await page.getByTestId('create-name').fill(EDITED_NAME);
    await expect(page.getByTestId('create-name')).toHaveValue(EDITED_NAME);

    // ── 4. KEYBOARD NAV + FOCUS: drive the flow with the keyboard. Focus the dialog, Tab through it,
    //    and assert focus lands on a real interactive control INSIDE the flow (keyboard-navigable,
    //    not a focus trap on the body) AND that the focused control shows a visible focus indicator
    //    (a non-none outline or a box-shadow — :focus-visible activates on keyboard nav). ──.
    await page.getByTestId('create-flow').focus();
    let landedInFlow = false;
    let focusIndicatorVisible = false;
    for (let i = 0; i < 12; i++) {
      await page.keyboard.press('Tab');
      const probe = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        if (!el || el.tagName.toLowerCase() === 'body') return null;
        if (!el.closest('[data-testid="create-flow"]')) return { inFlow: false, indicator: false };
        const s = getComputedStyle(el);
        const indicator =
          (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) ||
          (s.boxShadow !== 'none' && s.boxShadow.trim().length > 0);
        return { inFlow: true, indicator };
      });
      if (probe?.inFlow) {
        landedInFlow = true;
        if (probe.indicator) {
          focusIndicatorVisible = true;
          break;
        }
      }
    }
    expect(landedInFlow, 'Tab must move focus to a control inside the flow').toBe(true);
    expect(
      focusIndicatorVisible,
      'a keyboard-focused flow control must show a visible focus indicator',
    ).toBe(true);

    // ── 1 + 2 + 3. BUILD: capture the create REQUEST, then Build it. The payload MUST carry the
    //    proposed config + the user's name edit (NOT a drifted shell). ──.
    const createBody = captureCreateRequest(page);
    const projectBody = captureCreateProjectRequest(page);
    const projectResponse = page.waitForResponse(
      (r) => r.url().endsWith('/projects') && r.request().method() === 'POST',
    );
    const createResponse = page.waitForResponse(
      (r) => r.url().endsWith('/sessions') && r.request().method() === 'POST',
    );
    await page.getByTestId('create-launch').click();
    const created = await createBody;
    const createdRes = await (await createResponse).json();

    // The create payload carries a `product` ProductConfig == proposed + the name edit.
    expect(created.product, 'the create payload must carry the product spec').toBeTruthy();
    const product = created.product!;
    // EDIT present: the renamed project flows through (and is NOT the proposed name).
    expect(product.productName).toBe(EDITED_NAME);
    expect(product.productName).not.toBe(PROPOSED.productName);
    // The proposed spec otherwise rides faithfully (no drift).
    expect(product.productKind).toBe(PROPOSED.productKind);
    expect(product.capabilities.harness).toBe(PROPOSED.harness);
    expect(product.stack.languages).toEqual([...PROPOSED.languages]);
    expect(product.services).toEqual([...PROPOSED.services]);
    expect(product.sdlcPhases).toContain('architecture');
    expect(product.sdlcPhases).toContain('implementation');
    // The create returned a REAL session id (FE⇄BE: a live session, not a placeholder).
    expect(createdRes.id, 'create must return a real session id').toBeTruthy();
    expect(typeof createdRes.id).toBe('string');

    // ── 2 + 3. PERSISTENCE: the Project was persisted (the dashboard's record), carrying the edited
    //    name and linked to the build session just created. Assert BOTH the request payload AND that
    //    the store ACCEPTED it (201) — a broken /projects handler (503/400/500) must fail the test,
    //    not slip through as a correct-but-rejected payload (the create flow logs+continues on a
    //    persistence fault, so the response status is the only real signal). ──.
    const persistedProject = await projectBody;
    expect(persistedProject.product?.productName).toBe(EDITED_NAME);
    expect(persistedProject.sessionId).toBe(createdRes.id);
    expect(
      (await projectResponse).status(),
      'the Project must actually persist (POST /projects 201)',
    ).toBe(201);

    // ── the flow closes and the chat view opens bound to the chosen harness ──────.
    await expect(flow).toBeHidden();
    await expect(page.getByTestId('active-harness')).toHaveText(PROPOSED.harness);

    // LAYOUT: the composer must sit WITHIN the visible viewport — the chat chrome (top bar + two
    // status bars) must not push it below the fold (the off-screen-composer defect).
    await expect(page.getByTestId('composer-input')).toBeInViewport();

    // ── the bottom STATUS BAR (the TUI status line) goes live. Before any assistant text the agent
    //    THINKS: the bar surfaces a running thinking-token count (the thinking-progress heartbeats),
    //    proving that signal is wired end-to-end — without it the count would never leave 0. The
    //    count is RETAINED after the turn, so 260 (the fake's thinking ramp peak) is deterministic. ──.
    const statusBar = page.getByTestId('agent-status');
    await expect(statusBar).toBeVisible();
    await expect(statusBar.getByTestId('agent-status-label')).toContainText('Thinking', {
      timeout: 10_000,
    });
    await expect(statusBar).toHaveAttribute('data-busy', 'true');
    await expect(page.getByTestId('agent-status-tokens')).toContainText('thinking tokens');
    await expect(statusBar).toHaveAttribute('data-thinking-tokens', '260', { timeout: 10_000 });

    // ── 3. the created session reflects that spec: it appears in the live session list under its
    //    real id (located by id, not position — the in-memory dev record plane may retain prior
    //    stopped records across the two engine runs sharing one dev-serve, so position is not stable). ──.
    await expect(
      page.locator(`[data-testid="session-item"][data-session-id="${createdRes.id}"]`),
    ).toHaveCount(1);

    // ── 3. REAL SSE EVENTS render (no drift between the backend events and the UI). The user's intent
    //    bubble renders, then the canonical streamed turn arrives over the REAL SSE stream. ──.
    await expect(page.getByTestId('user-message')).toContainText(INTENT);
    // The opening turn is driven once, by the gateway — the client never fires a redundant second
    // prompt, so NO illegal-prompt conflict notice renders (the regression guard for the double-send
    // 409 that used to be filtered away above).
    await expect(page.getByTestId('notice').filter({ hasText: /illegal|conflict/i })).toHaveCount(
      0,
    );
    await expect(page.getByTestId('assistant-text')).toContainText('Hello, world', {
      timeout: 15_000,
    });
    // The reasoning is shown EXPANDED in the distinct thinking box (not folded away) — the agent's
    // thinking is visible, not just a token count.
    await expect(page.getByTestId('thinking-block')).toBeVisible();
    await expect(page.getByTestId('thinking-content')).toContainText('considering the request');
    const toolCard = page.getByTestId('tool-card').first();
    await expect(toolCard).toContainText('Write');
    await expect(toolCard.getByTestId('tool-result')).toContainText('wrote 12 bytes');

    // ── the CONTEXT bar (the second TUI status line) shows real-time observability: the tool-use
    //    and turn counters ticked as the agent worked (live increments, not only the terminal
    //    ledger), the model is attributed, and the context-window gauge reads a %. ──.
    const contextBar = page.getByTestId('agent-context');
    await expect(contextBar).toBeVisible();
    await expect(page.getByTestId('context-tools')).toHaveText('1');
    await expect(page.getByTestId('context-turns')).toHaveText('1');
    await expect(page.getByTestId('context-model')).toContainText('fake-fable-5');
    await expect(page.getByTestId('context-window')).toContainText('% ctx');

    // ── the AGENT-TYPE-AWARE RIGHT PANEL (the workspace's third region): an implementer session
    //    mounts the Workspace widget, which lists the files the agent generated — derived LIVE from
    //    its tool stream (the canonical Write touched note.txt). The session-navigator dot reflects
    //    the live agent state. ──.
    const panel = page.getByTestId('agent-panel');
    await expect(panel).toBeVisible();
    await expect(panel).toHaveAttribute('data-agent-type', 'implementer');
    await expect(page.getByTestId('panel-agent-type')).toContainText('Implementer');
    await expect(page.getByTestId('workspace-widget')).toBeVisible();
    const file = page.getByTestId('workspace-file').first();
    await expect(file).toBeVisible();
    await expect(file).toHaveAttribute('data-path', 'note.txt');
    await expect(page.getByTestId('workspace-widget')).toHaveAttribute('data-count', '1');
    // The implementer panel also mounts the on-disk Files widget (its own collapsible section).
    await expect(page.getByTestId('filetree-widget')).toBeVisible();
    // The navigator shows a live status dot for the session.
    await expect(page.getByTestId('session-dot').first()).toBeVisible();

    // The live meter reconciled against the real terminal ledger (the canonical script's values).
    // The usage/cost is a concise dock pinned bottom-right: it shows the model + cost (header)
    // reconciled against the terminal ledger.
    await expect(page.getByTestId('usage-dock')).toBeVisible();
    await expect(page.getByTestId('usage-dock-cost')).toContainText('0.001500');
    await expect(page.getByTestId('usage-dock-model')).toContainText('fake-fable-5');
    await expect(page.getByTestId('terminal-banner')).toHaveAttribute('data-outcome', 'completed');
    await expect(page.getByTestId('sse-status')).toHaveText('ended');
    // The status bar settled on the terminal verb and stopped spinning, but retained the turn's
    // thinking-token summary (the "thought for N" recap).
    await expect(statusBar).toHaveAttribute('data-activity', 'done');
    await expect(statusBar).toHaveAttribute('data-busy', 'false');
    await expect(statusBar).toHaveAttribute('data-thinking-tokens', '260');

    // ── 6. LIFECYCLE: stop the session; the UI returns to the empty state cleanly ────.
    await page.getByTestId('stop').getByRole('button').click();
    await expect(page.getByTestId('empty-state')).toBeVisible();
    await expect(page.getByTestId('transcript')).toHaveCount(0);

    // No uncaught exceptions and no app-logged console errors across the whole journey (catches the
    // dumb runtime things). With the single-driver opening turn there is NO illegal-prompt 409 to
    // exclude — the console-error set must be genuinely empty.
    expect(pageErrors, `uncaught exceptions during the journey: ${pageErrors.join(' | ')}`).toEqual(
      [],
    );
    expect(
      console_errors,
      `unexpected console errors during the journey: ${console_errors.join(' | ')}`,
    ).toEqual([]);

    // Attach the captured payloads to the report so a reviewer SEES the data the assertions pinned.
    await testInfo.attach('proposed-config.json', {
      body: JSON.stringify(proposed, null, 2),
      contentType: 'application/json',
    });
    await testInfo.attach('create-payload.json', {
      body: JSON.stringify(created, null, 2),
      contentType: 'application/json',
    });
  });

  // ── the THINKING screen (the "nice animation" while Eden scopes) is shown between SPARK and SCOPE.
  //    Delay the real propose just enough to OBSERVE it deterministically, then let it resolve. ──.
  test('the scoping animation shows while Eden proposes, then resolves to scope', async ({
    page,
  }) => {
    await openChat(page);
    await page.getByTestId('new-session').first().click();
    await expect(page.getByTestId('create-flow')).toBeVisible();

    // Hold the FIRST propose ~600ms so the THINKING screen is observable (the request still hits the
    // real backend — we only delay the round-trip, we do not stub the body).
    let held = false;
    await page.route('**/product/propose', async (route) => {
      if (!held) {
        held = true;
        await new Promise((resolve) => setTimeout(resolve, 600));
      }
      await route.continue();
    });

    await page.getByTestId('create-spark').fill(INTENT);
    await page.getByTestId('create-start').click();
    // The transient scoping screen renders with a live status line.
    await expect(page.getByTestId('create-flow')).toHaveAttribute('data-step', 'thinking');
    await expect(page.getByTestId('create-thinking')).toBeVisible();
    await expect(page.getByTestId('create-thinking-line')).not.toBeEmpty();
    // Then it resolves to the REVIEW screen with the real proposed config (W3: scope+stack merged).
    await expect(page.getByTestId('create-flow')).toHaveAttribute('data-step', 'review', {
      timeout: 10_000,
    });
    await expect(page.getByTestId('create-name')).toHaveValue(PROPOSED.productName);
  });

  // ── 5. RESILIENCE: a propose FAILURE renders gracefully (the dev-serve fake never errors, so we
  //    force ONE /product/propose request to fail at the network seam — a documented intercept — and
  //    assert the flow surfaces the error, returns to SPARK, does NOT crash, and the user can retry
  //    successfully against the REAL backend once the intercept is spent). ──.
  test('a propose failure renders gracefully and the user can retry', async ({ page }) => {
    const console_errors: string[] = [];
    page.on('console', (m) => {
      if (m.type() === 'error' && !/Failed to load resource/i.test(m.text()))
        console_errors.push(m.text());
    });
    const pageErrors: string[] = [];
    page.on('pageerror', (e) => pageErrors.push(e.message)); // an uncaught exception == a crash

    await openChat(page);
    await page.getByTestId('new-session').first().click();
    await expect(page.getByTestId('create-flow')).toBeVisible();

    // Fail the FIRST propose only, then let subsequent ones through to the real backend.
    let failed = false;
    await page.route('**/product/propose', async (route) => {
      if (!failed) {
        failed = true;
        await route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: '{"kind":"unavailable","message":"scoping unavailable","errors":["unavailable"]}',
        });
        return;
      }
      await route.continue();
    });

    await page.getByTestId('create-spark').fill(INTENT);
    await page.getByTestId('create-start').click();

    // The flow surfaces the gateway's error message and returns to SPARK (no crash, no dead advance).
    await expect(page.getByTestId('create-error')).toBeVisible();
    await expect(page.getByTestId('create-error')).toContainText('scoping unavailable');
    await expect(page.getByTestId('create-flow')).toHaveAttribute('data-step', 'spark');
    expect(
      pageErrors,
      `a propose failure must not crash the app: ${pageErrors.join(' | ')}`,
    ).toEqual([]);

    // Retry: the second propose hits the REAL backend and advances to REVIEW with the real config.
    await page.getByTestId('create-start').click();
    await expect(page.getByTestId('create-flow')).toHaveAttribute('data-step', 'review', {
      timeout: 10_000,
    });
    await expect(page.getByTestId('create-name')).toHaveValue(PROPOSED.productName);

    // Close cleanly (no orphan session was created — propose does not create). Back to SPARK, cancel.
    await page.getByTestId('create-back').click();
    await page.getByTestId('create-cancel').click();
    await expect(page.getByTestId('create-flow')).toBeHidden();
    await expect(page.getByTestId('empty-state')).toBeVisible();
    expect(console_errors, `unexpected console errors: ${console_errors.join(' | ')}`).toEqual([]);
    expect(pageErrors, `uncaught exceptions: ${pageErrors.join(' | ')}`).toEqual([]);
  });

  test('the top bar + ⌘K command palette open the create flow', async ({ page }) => {
    const pageErrors: string[] = [];
    page.on('pageerror', (e) => pageErrors.push(e.message));
    await openChat(page);

    // The workspace TOP BAR is present (brand + the ⌘K affordance).
    await expect(page.getByTestId('top-bar')).toBeVisible();
    await expect(page.getByTestId('palette-open')).toBeVisible();

    // ⌘K / Ctrl-K opens the command palette from anywhere.
    await page.keyboard.press('ControlOrMeta+k');
    const palette = page.getByRole('dialog', { name: /command palette/i });
    await expect(palette).toBeVisible();

    // It lists the actions; selecting "New project" opens the create flow.
    await expect(palette.getByText('New project…')).toBeVisible();
    await palette.getByText('New project…').click();
    await expect(page.getByTestId('create-flow')).toBeVisible();

    // Escape closes the flow even with focus INSIDE it (the dialog subtree must honor Escape, not
    // swallow it) — then reopen and close via the Cancel button.
    await page.getByTestId('create-spark').click();
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('create-flow')).toBeHidden();
    await page.getByTestId('new-session').first().click();
    await expect(page.getByTestId('create-flow')).toBeVisible();
    await page.getByTestId('create-cancel').first().click();
    await expect(page.getByTestId('create-flow')).toBeHidden();

    expect(pageErrors, `uncaught exceptions: ${pageErrors.join(' | ')}`).toEqual([]);
  });

  test('settings open from the top bar and dismiss', async ({ page }) => {
    const pageErrors: string[] = [];
    page.on('pageerror', (e) => pageErrors.push(e.message));
    await openChat(page);

    // W4: the Build top-bar `settings-open` and the dashboard `user-settings-open` now open the ONE
    // Settings surface (doc 17 §7, @eden/primitives SettingsSurface) — the two legacy surfaces
    // (chat/SettingsPanel + dashboard/SettingsModal) are deleted. The unified sheet root testid is
    // `settings-surface`; the top-bar entry deep-links to the Appearance section (the colour mode this
    // affordance historically surfaced). Every FUNCTIONAL assertion below is preserved unweakened:
    // the surface opens, the colour-mode control (`settings-colormode`, unchanged) is visible, and
    // Escape dismisses (the bits-ui Dialog behavior the SettingsSurface composes).
    await page.getByTestId('settings-open').click();
    await expect(page.getByTestId('settings-surface')).toBeVisible();
    // It surfaces the real settings (colour mode), and Escape dismisses it.
    await expect(page.getByTestId('settings-colormode')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('settings-surface')).toBeHidden();

    expect(pageErrors, `uncaught exceptions: ${pageErrors.join(' | ')}`).toEqual([]);
  });

  // ── the dashboard's Settings → Agents tab is a REAL editor: edit a per-agent-type config, save it
  //    (the PUT carries the parsed config), and prove it PERSISTS across a reload (loaded from the
  //    dev-serve's real AgentConfigStore — the same surface liveserve backs with Postgres). ──.
  test('settings → agents: edit a per-agent-type config, save, and persist it', async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    page.on('pageerror', (e) => pageErrors.push(e.message));

    await page.goto('/projects');
    await expect(page.getByTestId('projects-dashboard')).toBeVisible();
    // W4: `user-settings-open` now opens the ONE Settings surface (`settings-surface`) deep-linked to
    // the Agents section (was the dashboard's `settings-modal`, deleted). The agent-config CRUD testids
    // + the PUT wire shape ({model, toolGrants[], sandboxPosture}) + the reload-persistence walk are all
    // UNCHANGED — every functional assertion below survives the merge.
    await page.getByTestId('user-settings-open').click();
    await expect(page.getByTestId('settings-surface')).toBeVisible();

    // Edit the implementer card (Agents is the deep-linked section).
    const card = page.locator('[data-testid="agent-type-config"][data-agent-type="implementer"]');
    await card.getByTestId('agent-type-config-model-input').fill('claude-opus-4-8');
    await card.getByTestId('agent-type-config-grants-input').fill('Read, Write');
    await card.getByTestId('agent-type-config-posture-input').selectOption('strict');

    // Save → the PUT carries the parsed config (grants split from the comma list); the card confirms.
    const putBody = page
      .waitForRequest((r) => r.url().includes('/agent-configs/implementer') && r.method() === 'PUT')
      .then(
        (r) => r.postDataJSON() as { model: string; toolGrants: string[]; sandboxPosture: string },
      );
    await card.getByTestId('agent-type-config-save').click();
    const put = await putBody;
    expect(put.model).toBe('claude-opus-4-8');
    expect(put.toolGrants).toEqual(['Read', 'Write']);
    expect(put.sandboxPosture).toBe('strict');
    await expect(card.getByTestId('agent-type-config-saved')).toBeVisible();

    // Editing a field clears the "✓ saved" badge — it must not linger next to a now-dirty draft.
    // (Change it to a DIFFERENT real model, so the edit→persist is proven with a clean value.)
    await card.getByTestId('agent-type-config-model-input').fill('claude-sonnet-4-6');
    await expect(card.getByTestId('agent-type-config-saved')).toBeHidden();
    // Re-save so the persistence-reload assertion below reads a clean, saved value.
    await card.getByTestId('agent-type-config-save').click();
    await expect(card.getByTestId('agent-type-config-saved')).toBeVisible();

    // PERSISTENCE: reload the dashboard, reopen Settings → the saved config loads from the store
    // (proving the round-trip persisted, not just an in-memory UI edit).
    await page.reload();
    await page.getByTestId('user-settings-open').click();
    const reloaded = page.locator(
      '[data-testid="agent-type-config"][data-agent-type="implementer"]',
    );
    await expect(reloaded.getByTestId('agent-type-config-model-input')).toHaveValue(
      'claude-sonnet-4-6',
    );
    await expect(reloaded.getByTestId('agent-type-config-grants-input')).toHaveValue('Read, Write');
    await expect(reloaded.getByTestId('agent-type-config-posture-input')).toHaveValue('strict');

    expect(pageErrors, `uncaught exceptions: ${pageErrors.join(' | ')}`).toEqual([]);
  });
});

// ── LIVE arm — the SAME journey, but propose hits REAL claude (liveserve) and the created agent is
//    REAL. Honest-skipped unless CREATE_PRODUCT_LIVE=1 (exported by run-create-product-live.sh when a
//    claude token is present in /workspace/.env.development). The token is NEVER read or logged here —
//    the runner injects it into the agentgateway-live process env only; this spec just drives the UI. ──
test.describe('create a new project — LIVE arm (real claude propose + real agent)', () => {
  test.skip(
    process.env.CREATE_PRODUCT_LIVE !== '1',
    'live claude harness/token unavailable — run tests/e2e/run-create-product-live.sh with a CLAUDEADAPTER_LIVE_TOKEN in /workspace/.env.development',
  );

  test('real propose returns a sane config; the real agent streams its first response', async ({
    page,
  }) => {
    // A real claude turn (propose + a live agent starting work) takes far longer than the suite
    // default — and longer than this test's own inner waits. Give it a real budget so the test
    // never guillotines its own assertions (the 60s-default-vs-90s-wait bug this arm first hit).
    test.setTimeout(240_000);
    await openChat(page);
    await page.getByTestId('new-session').first().click();
    await expect(page.getByTestId('create-flow')).toBeVisible();

    // A concrete intent a real model scopes into a sane ProductConfig.
    const liveIntent =
      'Build a Go service that ingests invoices over NATS and persists them to Postgres.';
    const proposeBody = page
      .waitForResponse(
        (r) => r.url().includes('/product/propose') && r.request().method() === 'POST',
        { timeout: 60_000 },
      )
      .then(async (r) => (await r.json()).data as ProductConfig);
    await page.getByTestId('create-spark').fill(liveIntent);
    await page.getByTestId('create-start').click();
    const proposed = await proposeBody;

    // The REAL propose returned a sane, NON-EMPTY config (a productName, a kind, and a non-empty
    // language set — the live model actually scoped a product, not an empty shell).
    await expect(page.getByTestId('create-flow')).toHaveAttribute('data-step', 'review', {
      timeout: 60_000,
    });
    expect(proposed.productName.trim().length).toBeGreaterThan(0);
    expect(['service', 'library', 'application', 'cli', 'ui', 'other']).toContain(
      proposed.productKind,
    );
    expect(
      proposed.stack.languages.length,
      'a real config must name at least one language',
    ).toBeGreaterThan(0);

    // The agent auto-selected at least one platform target out of the palette.
    await expect(
      page.locator('[data-testid="create-target"][data-selected="true"]').first(),
    ).toBeVisible();

    // Drive REVIEW → Build (create a REAL agent session). W3: scope+stack are one REVIEW screen, so
    // Build is available directly (no intermediate create-next step).
    await page.getByTestId('create-launch').click();
    await expect(page.getByTestId('create-flow')).toBeHidden({ timeout: 60_000 });

    // The REAL agent begins its turn over the live SSE stream. A real implementer agent's FIRST
    // emitted event kind is non-deterministic — it may lead with a thinking block, a tool call, an
    // out-of-grant permission request, or plain assistant text. So we wait for ANY of those to
    // render (not assistant-text specifically): every one of them proves the live FE⇄gateway⇄claude
    // stream is alive and the real agent is doing real work.
    await expect(page.getByTestId('active-harness')).toHaveText('claude');
    const firstActivity = page
      .getByTestId('assistant-text')
      .or(page.getByTestId('thinking-block'))
      .or(page.getByTestId('tool-call'))
      .or(page.getByTestId('permission-card'))
      .first();
    await expect(firstActivity, 'the real agent must stream a first response').toBeVisible({
      timeout: 120_000,
    });

    // The bottom STATUS BAR reflects the REAL agent's live activity: it becomes busy and surfaces a
    // real running thinking-token count > 0 (claude's thinking_tokens heartbeats, normalized to
    // thinking-progress) — the fix for the dead "no thinking, no loading" screen.
    const liveStatus = page.getByTestId('agent-status');
    await expect(liveStatus).toBeVisible();
    await expect
      .poll(async () => Number((await liveStatus.getAttribute('data-thinking-tokens')) ?? '0'), {
        timeout: 120_000,
        message: 'the status bar must show a real thinking-token count > 0',
      })
      .toBeGreaterThan(0);

    // The CONTEXT bar reflects the REAL agent's observability live: as the agent does work, the
    // turn/tool counters tick in real time (not only at the terminal ledger). We count EITHER
    // (a real agent may lead with a tool or with prose) so the proof is robust to its first move.
    const liveContext = page.getByTestId('agent-context');
    await expect(liveContext).toBeVisible();
    await expect
      .poll(
        async () =>
          Number((await liveContext.getAttribute('data-turns')) ?? '0') +
          Number((await liveContext.getAttribute('data-tool-uses')) ?? '0'),
        {
          timeout: 120_000,
          message: 'the context bar must count real agent work (turns or tool-uses) live',
        },
      )
      .toBeGreaterThan(0);

    // The real assistant text token-streams into the bubble (non-empty) — the smooth-typing path
    // end-to-end against the live agent (the narration directive makes it lead with prose).
    await expect(page.getByTestId('assistant-text').first()).not.toBeEmpty({ timeout: 120_000 });

    // The agent-type-aware RIGHT PANEL is mounted for the live session (an implementer workspace).
    await expect(page.getByTestId('agent-panel')).toBeVisible();
    await expect(page.getByTestId('panel-agent-type')).toContainText('Implementer');
    await expect(page.getByTestId('workspace-widget')).toBeVisible();

    // If the live agent asks for an out-of-grant tool, the permission card is interactive (Allow it).
    const card = page.getByTestId('permission-card');
    if (await card.isVisible().catch(() => false)) {
      await card.getByRole('button', { name: 'Allow once' }).click();
      await expect(page.getByTestId('permission-decision')).toHaveText('allowed', {
        timeout: 90_000,
      });
    }

    // Lifecycle: stop the real session cleanly.
    await page.getByTestId('stop').getByRole('button').click();
    await expect(page.getByTestId('empty-state')).toBeVisible({ timeout: 60_000 });
  });
});
