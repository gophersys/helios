import { expect, test, type Page, type Request, type Response } from '@playwright/test';

// The FIRST user-story E2E — "create a new product" — a comprehensive, REAL, full-stack Playwright
// journey with DATA verification at every step. It drives the production-shaped UI against a REAL
// agentgateway dev-serve over real REST + SSE (no mocked fetch/SSE): the dev-serve's DETERMINISTIC
// proposer (devserve/proposer.go) returns a real ProductConfig from the prompt, a REAL
// agentsession.Pool streams the agent, and the verdict-aware adapter drives the gate. NOTHING here
// is stubbed in the browser — the route intercepts below only OBSERVE the real wire traffic (and the
// one resilience case fails a request on purpose, which is a documented arm).
//
// The story (apps/frontend ProductWizard.svelte + routes/chat/+page.svelte):
//   open app → start a new product → type an intent → propose → a ProductConfig (kind/stack/services)
//   → the user EDITS it (add a service, drop an SDLC phase) → confirm → the session/product is created
//   carrying that EDITED spec → the agent session opens and streams its first events.
//
// The matrix (each dimension asserts the ACTUAL captured data, never just "an element exists"):
//   1 FUNCTIONAL FLOW    every wizard step advances; the confirm creates a session.
//   2 DATA INTEGRITY     the rendered wizard reflects the propose RESPONSE; the create PAYLOAD carries
//                        the proposed config + the user's edits (NOT the original).
//   3 FE⇄BE INTEGRATION  propose POST → rendered config (no drift); create POST → a real session id;
//                        the real SSE events render (no drift backend→UI).
//   4 UI / DESIGN-MATH   a mechanical a11y + contrast audit on the LIVE wizard at each step, on
//                        Chromium AND WebKit; keyboard-navigable + focus visible; a generated theme
//                        token resolves (not empty) and the accent control is actually painted.
//   5 RESILIENCE         empty/whitespace intent validates (no propose call); a forced propose
//                        failure renders gracefully (no crash) and the user can retry.
//   6 LIFECYCLE          after creation the session stops cleanly; the UI returns to a sane state.
// Plus a visual sanity: the wizard container stays within the viewport (no overflow/overlap).

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

// The EDIT the user makes in the wizard: add the "nats" service and DROP the "qa" SDLC phase. The
// create payload MUST carry the edited spec — services ["postgres","nats"] and phases without "qa".
const ADDED_SERVICE = 'nats';
const DROPPED_PHASE = 'qa';

/** The ProductConfig shape the wizard renders / posts (mirrors $lib/gateway/types ProductConfig). */
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

/** Capture the JSON body the wizard POSTed to /sessions by OBSERVING the request (passive). */
function captureCreateRequest(page: Page): Promise<{ harness: string; product?: ProductConfig }> {
  return page
    .waitForRequest((r: Request) => r.url().endsWith('/sessions') && r.method() === 'POST')
    .then((r) => r.postDataJSON() as { harness: string; product?: ProductConfig });
}

// ── the UI-MATH audit: a mechanical, NON-VACUOUS a11y + contrast check on the LIVE rendered wizard.
//    This runs in-page (real getComputedStyle), so it is engine-true on both Chromium and WebKit. It
//    is the design-math dimension the user requires as a first-class mechanical test — stricter than
//    a smoke check: it computes the WCAG contrast ratio on rendered text and fails on a real defect. ──

interface AuditResult {
  tokenResolves: boolean; // a generated theme var resolves to a non-empty value
  accentPainted: boolean; // the accent control is actually painted (not transparent) — catches the orphan-token bug
  unnamedControls: string[]; // interactive controls with no accessible name (a11y violation)
  unlabeledFields: number; // form inputs with neither a label nor an aria-label
  lowContrast: { sample: string; ratio: number }[]; // text below WCAG AA on the wizard
  withinViewport: boolean; // the wizard container fits the viewport (no overflow/overlap)
  duplicateIds: string[]; // duplicate element ids inside the wizard (a11y/structure violation)
}

async function auditWizard(page: Page): Promise<AuditResult> {
  return page.evaluate(() => {
    const root = document.querySelector('[data-testid="product-wizard"]') as HTMLElement;

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

    // A generated theme token resolves to a real value (the wizard reads the C21 math substrate).
    const cs = getComputedStyle(document.documentElement);
    const tokenResolves = cs.getPropertyValue('--color-primary').trim().length > 0;

    // The accent control (Scope/Next/Launch) is actually painted — the orphan-token bug left it
    // transparent. Assert the primary action has a non-transparent background.
    const accentBtn = root.querySelector(
      '[data-testid="wizard-next"], [data-testid="wizard-launch"]',
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

    // Form fields must be labelled (a label wrapping, an aria-label, or — acceptably for a free text
    // box — a placeholder). Count the ones with none.
    const fields = Array.from(root.querySelectorAll('input, textarea')) as HTMLElement[];
    const unlabeledFields = fields.filter((el) => accName(el).length === 0).length;

    // Contrast on the wizard's rendered text vs its background (sample the labels, leads, buttons,
    // review values). WCAG AA is 4.5:1 for normal text; we sample visible text nodes.
    const textEls = Array.from(
      root.querySelectorAll(
        '.field__label, .lead, .hint, .eyebrow, .review dt, .review dd, .pillgroup__label, .chipinput__label, .btn, .steps__name',
      ),
    ) as HTMLElement[];
    const lowContrast: { sample: string; ratio: number }[] = [];
    for (const el of textEls) {
      const text = (el.textContent ?? '').trim();
      if (!text || getComputedStyle(el).display === 'none') continue;
      const style = getComputedStyle(el);
      const size = parseFloat(style.fontSize);
      const weight = parseInt(style.fontWeight, 10) || 400;
      const large = size >= 24 || (size >= 18.66 && weight >= 700);
      const min = large ? 3 : 4.5;
      const cr = ratio(style.color, el);
      if (cr + 0.05 < min)
        lowContrast.push({ sample: text.slice(0, 40), ratio: Math.round(cr * 100) / 100 });
    }

    // The wizard container fits the viewport (no overflow/overlap at a standard viewport).
    const rect = root.getBoundingClientRect();
    const withinViewport =
      rect.left >= -1 &&
      rect.top >= -1 &&
      rect.right <= window.innerWidth + 1 &&
      rect.bottom <= window.innerHeight + 1;

    // Duplicate ids inside the wizard.
    const ids = Array.from(root.querySelectorAll('[id]')).map((el) => el.id);
    const duplicateIds = ids.filter((id, i) => ids.indexOf(id) !== i);

    return {
      tokenResolves,
      accentPainted,
      unnamedControls,
      unlabeledFields,
      lowContrast,
      withinViewport,
      duplicateIds,
    } satisfies AuditResult;
  });
}

/** Assert the audit is clean (used at each wizard step). Fails LOUDLY with the offending data so a
 *  real regression names the exact control/sample — never a vacuous green. */
function assertCleanAudit(audit: AuditResult, where: string): void {
  expect(audit.tokenResolves, `${where}: a generated theme token must resolve`).toBe(true);
  expect(
    audit.accentPainted,
    `${where}: the accent control must be painted (orphan-token guard)`,
  ).toBe(true);
  expect(
    audit.unnamedControls,
    `${where}: every interactive control needs an accessible name`,
  ).toEqual([]);
  expect(audit.unlabeledFields, `${where}: every form field needs a label`).toBe(0);
  expect(audit.duplicateIds, `${where}: no duplicate ids`).toEqual([]);
  expect(audit.lowContrast, `${where}: text must meet WCAG AA contrast`).toEqual([]);
  expect(audit.withinViewport, `${where}: the wizard must fit the viewport`).toBe(true);
}

test.describe('create a new product — full-stack journey against a real dev-serve (FAKE arm)', () => {
  test('propose → render the real config → edit → create with the edited spec → stream first events → stop', async ({
    page,
  }, testInfo) => {
    // Track real runtime faults across the journey. An uncaught exception (pageerror) is a hard
    // crash and is asserted to be zero. For console errors we exclude the EXPECTED terminal-state
    // resource line: the dev fake is a SINGLE-TURN script, so the opening turn (driven from the
    // product preamble at create) reaches its terminal Result, and the UI's follow-up opening prompt
    // is correctly rejected 409 by the gateway (the browser logs the failed fetch). That 409 is the
    // gateway behaving correctly on a single-turn fake — NOT a UI bug; the UI surfaces it as a notice.
    // A real defect (an uncaught exception, or a console.error the app itself logged) is still caught.
    const pageErrors: string[] = [];
    page.on('pageerror', (e) => pageErrors.push(e.message));
    const console_errors: string[] = [];
    page.on('console', (m) => {
      if (m.type() === 'error' && !/Failed to load resource/i.test(m.text()))
        console_errors.push(m.text());
    });

    await openChat(page);

    // ── 1. FUNCTIONAL FLOW + 4. UI-MATH: open the wizard (DEFINE) ────────────────.
    await page.getByTestId('new-session').first().click();
    const wizard = page.getByTestId('product-wizard');
    await expect(wizard).toBeVisible();
    await expect(wizard).toHaveAttribute('data-step', 'define');
    assertCleanAudit(await auditWizard(page), 'DEFINE');

    // ── 5. RESILIENCE (validation): a whitespace-only intent must NOT propose ────.
    await page.getByTestId('wizard-prompt').fill('   ');
    // wizard-next is a raw <button> (not an @eden/primitives Button wrapper), so the testid IS the button.
    await expect(page.getByTestId('wizard-next')).toBeDisabled();
    // No /product/propose fired for the blank intent (race a click against a short window).
    let proposedWhileBlank = false;
    const blankWatcher = page
      .waitForRequest((r) => r.url().includes('/product/propose'), { timeout: 1200 })
      .then(() => {
        proposedWhileBlank = true;
      })
      .catch(() => {});
    await page
      .getByTestId('wizard-next')
      .click({ force: true })
      .catch(() => {});
    await blankWatcher;
    expect(proposedWhileBlank, 'a blank intent must not trigger a propose').toBe(false);

    // ── type the real intent → DEFINE → propose → STACK. Capture the propose RESPONSE. ──.
    await page.getByTestId('wizard-prompt').fill(INTENT);
    const proposeBody = captureProposeResponse(page);
    await page.getByTestId('wizard-next').click();
    const proposed = await proposeBody;
    await expect(wizard).toHaveAttribute('data-step', 'stack');

    // ── 2 + 3. DATA INTEGRITY / FE⇄BE: the propose RESPONSE carried the deterministic config ──.
    expect(proposed.productName).toBe(PROPOSED.productName);
    expect(proposed.productKind).toBe(PROPOSED.productKind);
    expect(proposed.stack.languages).toEqual(PROPOSED.languages);
    expect(proposed.services).toEqual(PROPOSED.services);
    expect(proposed.capabilities.harness).toBe(PROPOSED.harness);
    expect(proposed.capabilities.model).toBe(PROPOSED.model);
    expect(proposed.sdlcPhases).toEqual(PROPOSED.phases);
    expect(proposed.sandbox.posture).toBe(PROPOSED.posture);

    // ── the RENDERED wizard reflects that response (no drift backend→UI) ─────────.
    await expect(page.getByTestId('wizard-name-stack')).toHaveValue(PROPOSED.productName);
    await expect(page.getByTestId(`wizard-kind-${PROPOSED.productKind}`)).toHaveAttribute(
      'aria-checked',
      'true',
    );
    await expect(page.getByTestId('wizard-summary')).toHaveValue(proposed.summary);
    await expect(page.getByTestId('wizard-languages-chip')).toContainText(PROPOSED.languages[0]);
    await expect(page.getByTestId('wizard-services-chip')).toHaveCount(PROPOSED.services.length);
    await expect(page.getByTestId('wizard-services-chip').first()).toContainText(
      PROPOSED.services[0],
    );
    assertCleanAudit(await auditWizard(page), 'STACK');

    // ── the user EDIT #1: add a service (chip-input). It must land in the rendered list. ──.
    await page.getByTestId('wizard-services-input').fill(ADDED_SERVICE);
    await page.getByTestId('wizard-services-input').press('Enter');
    await expect(page.getByTestId('wizard-services-chip')).toHaveCount(
      PROPOSED.services.length + 1,
    );
    await expect(
      page.getByTestId('wizard-services-chip').filter({ hasText: ADDED_SERVICE }),
    ).toHaveCount(1);

    // ── STACK → CAPABILITIES → PROCESS ──────────────────────────────────────────.
    await page.getByTestId('wizard-next').click();
    await expect(wizard).toHaveAttribute('data-step', 'capabilities');
    // The proposed harness/model render here (capability binding, no drift).
    await expect(page.getByTestId(`wizard-harness-${PROPOSED.harness}`)).toHaveAttribute(
      'aria-checked',
      'true',
    );
    await expect(page.getByTestId('wizard-model')).toHaveValue(PROPOSED.model);
    assertCleanAudit(await auditWizard(page), 'CAPABILITIES');

    await page.getByTestId('wizard-next').click();
    await expect(wizard).toHaveAttribute('data-step', 'process');
    // The proposed phases render selected; EDIT #2: DROP the "qa" phase (toggle it off).
    for (const phase of PROPOSED.phases) {
      await expect(page.getByTestId(`wizard-phases-${phase}`)).toHaveAttribute(
        'aria-pressed',
        'true',
      );
    }
    await page.getByTestId(`wizard-phases-${DROPPED_PHASE}`).click();
    await expect(page.getByTestId(`wizard-phases-${DROPPED_PHASE}`)).toHaveAttribute(
      'aria-pressed',
      'false',
    );
    assertCleanAudit(await auditWizard(page), 'PROCESS');

    // ── PROCESS → SAFETY → REVIEW ───────────────────────────────────────────────.
    await page.getByTestId('wizard-next').click();
    await expect(wizard).toHaveAttribute('data-step', 'safety');
    await expect(page.getByTestId(`wizard-posture-${PROPOSED.posture}`)).toHaveAttribute(
      'aria-checked',
      'true',
    );
    assertCleanAudit(await auditWizard(page), 'SAFETY');

    await page.getByTestId('wizard-next').click();
    await expect(wizard).toHaveAttribute('data-step', 'review');

    // ── the REVIEW reflects the edited spec (the added service shows; the dropped phase is gone) ──.
    await expect(page.getByTestId('review-name')).toContainText(PROPOSED.productName);
    await expect(page.getByTestId('review-kind')).toContainText(PROPOSED.productKind);
    await expect(page.getByTestId('review-harness')).toContainText(PROPOSED.harness);
    const reviewPhases = (await page.getByTestId('review-phases').textContent()) ?? '';
    expect(reviewPhases).toContain('architecture');
    expect(reviewPhases).not.toContain(DROPPED_PHASE);
    assertCleanAudit(await auditWizard(page), 'REVIEW');

    // ── 4. KEYBOARD NAV + FOCUS: drive the wizard with the keyboard. Focus the dialog, Tab through
    //    it, and assert focus lands on a real interactive control INSIDE the wizard (keyboard-
    //    navigable, not a focus trap on the body) AND that the focused control shows a visible focus
    //    indicator (a non-none outline or a box-shadow — :focus-visible activates on keyboard nav). ──.
    await page.getByTestId('product-wizard').focus();
    let landedInWizard = false;
    let focusIndicatorVisible = false;
    for (let i = 0; i < 12; i++) {
      await page.keyboard.press('Tab');
      const probe = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        if (!el || el.tagName.toLowerCase() === 'body') return null;
        if (!el.closest('[data-testid="product-wizard"]'))
          return { inWizard: false, indicator: false };
        const s = getComputedStyle(el);
        const indicator =
          (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) ||
          (s.boxShadow !== 'none' && s.boxShadow.trim().length > 0);
        return { inWizard: true, indicator };
      });
      if (probe?.inWizard) {
        landedInWizard = true;
        if (probe.indicator) {
          focusIndicatorVisible = true;
          break;
        }
      }
    }
    expect(landedInWizard, 'Tab must move focus to a control inside the wizard').toBe(true);
    expect(
      focusIndicatorVisible,
      'a keyboard-focused wizard control must show a visible focus indicator',
    ).toBe(true);

    // ── 1 + 2 + 3. CONFIRM: capture the create REQUEST, then Launch. The payload MUST carry the
    //    proposed config + BOTH edits (NOT the original). ──.
    const createBody = captureCreateRequest(page);
    const createResponse = page.waitForResponse(
      (r) => r.url().endsWith('/sessions') && r.request().method() === 'POST',
    );
    await page.getByTestId('wizard-launch').click();
    const created = await createBody;
    const createdRes = await (await createResponse).json();

    // The create payload carries a `product` ProductConfig == proposed + the edits.
    expect(created.product, 'the create payload must carry the product spec').toBeTruthy();
    const product = created.product!;
    expect(product.productName).toBe(PROPOSED.productName);
    expect(product.productKind).toBe(PROPOSED.productKind);
    expect(product.capabilities.harness).toBe(PROPOSED.harness);
    // EDIT #1 present: services include the ADDED service AND the original (not the original alone).
    expect(product.services).toContain(PROPOSED.services[0]);
    expect(product.services).toContain(ADDED_SERVICE);
    expect(product.services).not.toEqual(PROPOSED.services); // proves it is NOT the un-edited original
    // EDIT #2 present: the dropped phase is gone; the kept phases remain.
    expect(product.sdlcPhases).not.toContain(DROPPED_PHASE);
    expect(product.sdlcPhases).toContain('architecture');
    expect(product.sdlcPhases).toContain('implementation');
    // The create returned a REAL session id (FE⇄BE: a live session, not a placeholder).
    expect(createdRes.id, 'create must return a real session id').toBeTruthy();
    expect(typeof createdRes.id).toBe('string');

    // ── the wizard closes and the chat view opens bound to the chosen harness ────.
    await expect(wizard).toBeHidden();
    await expect(page.getByTestId('active-harness')).toHaveText(PROPOSED.harness);

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
    await expect(page.getByTestId('assistant-text')).toContainText('Hello, world', {
      timeout: 15_000,
    });
    await expect(page.getByTestId('thinking-block')).toBeVisible();
    const toolCard = page.getByTestId('tool-card').first();
    await expect(toolCard).toContainText('Write');
    await expect(toolCard.getByTestId('tool-result')).toContainText('wrote 12 bytes');
    // The live meter reconciled against the real terminal ledger (the canonical script's values).
    await expect(page.getByTestId('meter-input')).toHaveText('100');
    await expect(page.getByTestId('meter-output')).toHaveText('40');
    await expect(page.getByTestId('meter-cost')).toContainText('0.001500');
    await expect(page.getByTestId('meter-model')).toContainText('fake-fable-5');
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
    // dumb runtime things). The expected single-turn-fake terminal 409 is excluded above.
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

  // ── 5. RESILIENCE: a propose FAILURE renders gracefully (the dev-serve fake never errors, so we
  //    force ONE /product/propose request to fail at the network seam — a documented intercept — and
  //    assert the wizard surfaces the error, does NOT advance, does NOT crash, and the user can retry
  //    successfully against the REAL backend once the intercept is removed). ──.
  test('a propose failure renders gracefully and the user can retry', async ({ page }) => {
    // Collect console errors EXCEPT the expected resource-load failure for the request we force to
    // fail (the browser always logs a failed fetch); a genuine crash (an uncaught exception) is NOT
    // a resource-load line, so this still catches a real defect.
    const console_errors: string[] = [];
    page.on('console', (m) => {
      if (m.type() === 'error' && !/Failed to load resource/i.test(m.text()))
        console_errors.push(m.text());
    });
    const pageErrors: string[] = [];
    page.on('pageerror', (e) => pageErrors.push(e.message)); // an uncaught exception == a crash

    await openChat(page);
    await page.getByTestId('new-session').first().click();
    await expect(page.getByTestId('product-wizard')).toBeVisible();

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

    await page.getByTestId('wizard-prompt').fill(INTENT);
    await page.getByTestId('wizard-next').click();

    // The wizard surfaces the gateway's error message and stays on DEFINE (no crash, no dead advance).
    await expect(page.getByTestId('wizard-error')).toBeVisible();
    await expect(page.getByTestId('wizard-error')).toContainText('scoping unavailable');
    await expect(page.getByTestId('product-wizard')).toHaveAttribute('data-step', 'define');
    expect(
      pageErrors,
      `a propose failure must not crash the app: ${pageErrors.join(' | ')}`,
    ).toEqual([]);

    // Retry: the second propose hits the REAL backend and advances to STACK with the real config.
    await page.getByTestId('wizard-next').click();
    await expect(page.getByTestId('product-wizard')).toHaveAttribute('data-step', 'stack');
    await expect(page.getByTestId('wizard-name-stack')).toHaveValue(PROPOSED.productName);

    // Close cleanly (no orphan session was created — propose does not create). We are on STACK now,
    // where the left footer button is "Back"; close via the header ✕ (its onclick is oncancel).
    await page.getByRole('button', { name: 'Cancel' }).click();
    await expect(page.getByTestId('product-wizard')).toBeHidden();
    await expect(page.getByTestId('empty-state')).toBeVisible();
    expect(console_errors, `unexpected console errors: ${console_errors.join(' | ')}`).toEqual([]);
    expect(pageErrors, `uncaught exceptions: ${pageErrors.join(' | ')}`).toEqual([]);
  });
});

// ── LIVE arm — the SAME journey, but propose hits REAL claude (liveserve) and the created agent is
//    REAL. Honest-skipped unless CREATE_PRODUCT_LIVE=1 (exported by run-create-product-live.sh when a
//    claude token is present in /workspace/.env.development). The token is NEVER read or logged here —
//    the runner injects it into the agentgateway-live process env only; this spec just drives the UI. ──
test.describe('create a new product — LIVE arm (real claude propose + real agent)', () => {
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
    await expect(page.getByTestId('product-wizard')).toBeVisible();

    // A concrete intent a real model scopes into a sane ProductConfig.
    const liveIntent =
      'Build a Go service that ingests invoices over NATS and persists them to Postgres.';
    const proposeBody = page
      .waitForResponse(
        (r) => r.url().includes('/product/propose') && r.request().method() === 'POST',
        {
          timeout: 60_000,
        },
      )
      .then(async (r) => (await r.json()).data as ProductConfig);
    await page.getByTestId('wizard-prompt').fill(liveIntent);
    await page.getByTestId('wizard-next').click();
    const proposed = await proposeBody;

    // The REAL propose returned a sane, NON-EMPTY config (a productName, a kind, and a non-empty
    // language set — the live model actually scoped a product, not an empty shell).
    await expect(page.getByTestId('product-wizard')).toHaveAttribute('data-step', 'stack', {
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

    // Edit (add a service), then drive to REVIEW → Launch (create a REAL agent session).
    await page.getByTestId('wizard-services-input').fill('vault');
    await page.getByTestId('wizard-services-input').press('Enter');
    for (const step of ['capabilities', 'process', 'safety', 'review']) {
      await page.getByTestId('wizard-next').click();
      await expect(page.getByTestId('product-wizard')).toHaveAttribute('data-step', step, {
        timeout: 60_000,
      });
    }
    await page.getByTestId('wizard-launch').click();
    await expect(page.getByTestId('product-wizard')).toBeHidden({ timeout: 60_000 });

    // The REAL agent begins its turn over the live SSE stream. A real implementer agent's FIRST
    // emitted event kind is non-deterministic — it may lead with a thinking block, a tool call, an
    // out-of-grant permission request, or plain assistant text. So we wait for ANY of those to
    // render (not assistant-text specifically): every one of them proves the live FE⇄gateway⇄claude
    // stream is alive and the real agent is doing real work. (The simple-prompt path is exercised
    // exactly — `Hello from Eden.` — by tests/e2e/run-create-product-live.sh's transcript probe.)
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

    // The bottom STATUS BAR reflects the REAL agent's live activity: it becomes busy (spinner on)
    // and surfaces a real running thinking-token count > 0 (claude's thinking_tokens heartbeats,
    // normalized to thinking-progress) — the fix for the dead "no thinking, no loading" screen.
    const liveStatus = page.getByTestId('agent-status');
    await expect(liveStatus).toBeVisible();
    await expect
      .poll(
        async () =>
          Number((await liveStatus.getAttribute('data-thinking-tokens')) ?? '0'),
        { timeout: 120_000, message: 'the status bar must show a real thinking-token count > 0' },
      )
      .toBeGreaterThan(0);

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
