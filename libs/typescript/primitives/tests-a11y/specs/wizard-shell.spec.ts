/**
 * WizardShell (doc 17 §6) — the A11Y-EVIDENCE lane (ADR-0024 / RD-16). The browser-level layer of the
 * three-layer a11y stack: axe-core on the REAL Chromium AND WebKit engines + Playwright keyboard
 * assertions (the FOCUS TRAP, ESCAPE-exit, ENTER-advance, first-field AUTOFOCUS) + reduced-motion
 * static-bar evidence + the token-driven serif/mono voices. The noted SR matrix lives in
 * a11y-evidence/wizard-shell.md. Every assertion is weaken-to-confirm guarded against a vacuous pass.
 */
import { test, expect } from '@playwright/test';
import { runAxeFull, seriousOrCritical } from '../axe-helper.js';

test.describe('WizardShell — a11y evidence (axe + keyboard trap, Chromium & WebKit)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/wizard-shell.html');
    await expect(page.getByTestId('wizard')).toBeVisible();
  });

  test('axe: ZERO serious/critical violations across the full-screen wizard', async ({
    page,
  }, testInfo) => {
    const engine = testInfo.project.name;
    const full = await runAxeFull(page);
    const v = seriousOrCritical(full.violations);
    expect(v, `[${engine}] violations: ${JSON.stringify(v)}`).toEqual([]);
    // weaken-to-confirm: axe genuinely walked a non-trivial WCAG rule set.
    expect(full.ruleCount, `[${engine}] axe ran too few rules`).toBeGreaterThan(30);
    expect(full.passCount, `[${engine}] axe reported zero passing checks`).toBeGreaterThan(0);
  });

  test('the wizard is a named dialog region (aria-labelledby → the serif step title)', async ({
    page,
  }) => {
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    // the accessible name is the active step's title (the h1)
    await expect(dialog).toHaveAccessibleName(/What are we building\?/);
  });

  test('the first field auto-focuses on mount (the slot-forwarded autofocus action)', async ({
    page,
  }) => {
    // the answer input receives focus with no click (doc 17 §6 "a single input")
    await expect(page.getByTestId('answer')).toBeFocused();
  });

  test('the mono counter reads `1 / 3` and the serif title renders in a DIFFERENT family', async ({
    page,
  }) => {
    await expect(page.locator('.eden-wizard-shell-counter')).toHaveText('1 / 3');
    const titleFamily = await page
      .locator('.screen__title')
      .evaluate((el) => getComputedStyle(el).fontFamily);
    const leadFamily = await page
      .locator('.lead')
      .first()
      .evaluate((el) => getComputedStyle(el).fontFamily);
    const counterFamily = await page
      .locator('.eden-wizard-shell-counter')
      .evaluate((el) => getComputedStyle(el).fontFamily);
    // the serif title, the sans lead, and the mono counter are three distinct type voices (P-D4)
    expect(titleFamily).not.toBe(leadFamily);
    expect(counterFamily).not.toBe(titleFamily);
    expect(counterFamily.toLowerCase()).toContain('mono');
  });

  test('Enter advances the wizard (the "Enter advances" contract) — the counter moves to 2 / 3', async ({
    page,
  }) => {
    await page.getByTestId('answer').focus();
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('advanced')).toHaveText('1');
    // the shell drove the active step forward — the counter + serif title updated
    await expect(page.locator('.eden-wizard-shell-counter')).toHaveText('2 / 3');
    await expect(page.locator('.screen__title')).toHaveText('Name it.');
  });

  test('Escape fires the exit intent ("Esc offers exit")', async ({ page }) => {
    await page.getByTestId('answer').focus();
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('exited')).toHaveText('exited');
  });

  test('focus is TRAPPED within the wizard — Tab cycles the fields, never escaping to the page', async ({
    page,
  }) => {
    // the "before"/"after" page anchors are OUTSIDE the wizard; a trapped Tab cycle never lands on them.
    const before = page.getByTestId('before');
    const after = page.getByTestId('after');
    // start at the last focusable (the Next button), Tab forward → wraps to the first (the input),
    // NOT to the page's "after" anchor.
    await page.getByRole('button', { name: 'Next' }).focus();
    await page.keyboard.press('Tab');
    await expect(after).not.toBeFocused();
    await expect(before).not.toBeFocused();
    // focus wrapped back INSIDE the wizard subtree — never the page anchors.
    const inside = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      return el?.closest('[data-eden-wizard-shell]') !== null;
    });
    expect(inside).toBe(true);
  });

  test('Shift+Tab from the first field wraps to the last (backward trap)', async ({ page }) => {
    await page.getByTestId('answer').focus();
    await page.keyboard.press('Shift+Tab');
    // it wrapped to a control INSIDE the wizard (the last focusable), not the page's "before" anchor.
    await expect(page.getByTestId('before')).not.toBeFocused();
    const inside = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      return el?.closest('[data-eden-wizard-shell]') !== null;
    });
    expect(inside).toBe(true);
  });

  test('the progress fill reflects the step fraction (0 on the first screen, grows on advance)', async ({
    page,
  }) => {
    const fill = page.locator('.eden-wizard-shell-progress-fill');
    // on the first step the scaleX is 0 (an empty bar) — read the CSS var off the root.
    const first = await page
      .getByTestId('wizard')
      .evaluate((el) =>
        getComputedStyle(el).getPropertyValue('--eden-wizard-shell-progress').trim(),
      );
    expect(first).toBe('0');
    // advance → the fraction grows (0.5 for the middle of a 3-step wizard).
    await page.getByTestId('answer').focus();
    await page.keyboard.press('Enter');
    const second = await page
      .getByTestId('wizard')
      .evaluate((el) =>
        getComputedStyle(el).getPropertyValue('--eden-wizard-shell-progress').trim(),
      );
    expect(Number(second)).toBeCloseTo(0.5, 5);
    await expect(fill).toBeVisible();
  });

  test('reduced-motion: the progress fill carries NO transition (a static bar)', async ({
    browser,
  }) => {
    const context = await browser.newContext({ reducedMotion: 'reduce' });
    const page = await context.newPage();
    await page.goto('/wizard-shell.html');
    await expect(page.getByTestId('wizard')).toBeVisible();
    const transition = await page
      .locator('.eden-wizard-shell-progress-fill')
      .evaluate((el) => getComputedStyle(el).transitionDuration);
    // reduced-motion strips the animated growth — the duration is 0s (a static bar).
    expect(['0s', '0ms']).toContain(transition);
    await context.close();
  });
});
