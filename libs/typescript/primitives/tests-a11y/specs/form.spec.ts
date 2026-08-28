/**
 * Form-action group — the A11Y-EVIDENCE lane (ADR-0024 / RD-16). The browser-level layer of the
 * three-layer a11y stack for the FORM/ACTION components (Button variants incl. danger, IconButton,
 * Input, Textarea, Field): axe-core on the REAL Chromium AND WebKit engines + Playwright keyboard
 * assertions. The noted SR matrix lives in a11y-evidence/form-action-group.md (the third layer).
 * Wired as the `a11y` ctl verb and a phase-gate qa BLOCKER. Every assertion is weaken-to-confirm
 * guarded against a vacuous pass (axe must walk a real rule set; the token color must be real).
 */
import { test, expect } from '@playwright/test';
import { ensureAxe, runAxeFull, seriousOrCritical } from '../axe-helper.js';

async function resolvedToken(
  page: import('@playwright/test').Page,
  prop: string,
  kind: 'bg' | 'color',
): Promise<string> {
  return await page.evaluate(
    ({ prop, kind }) => {
      const probe = document.createElement('div');
      if (kind === 'bg') probe.style.backgroundColor = `var(${prop})`;
      else probe.style.color = `var(${prop})`;
      document.body.appendChild(probe);
      const cs = getComputedStyle(probe);
      const out = kind === 'bg' ? cs.backgroundColor : cs.color;
      probe.remove();
      return out;
    },
    { prop, kind },
  );
}

test.describe('Form-action group — a11y evidence (axe + keyboard, Chromium & WebKit)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/form.html');
    await expect(page.getByRole('button', { name: 'Primary action' })).toBeVisible();
  });

  test('Eden tokens are injected at/above the document (the token context axe reads)', async ({
    page,
  }) => {
    const css = await page.evaluate(() => window.__EDEN_CSS__);
    expect(css).toContain('--color-surface');
    expect(css).toContain('--color-on-surface');
    expect(css).toContain('--color-primary');
    expect(css).toContain('--color-error');
    expect(css).toMatch(/--color-surface:\s*oklch\(/);
  });

  test('axe: ZERO serious/critical violations across the whole form-action group', async ({
    page,
  }, testInfo) => {
    const engine = testInfo.project.name;
    const full = await runAxeFull(page);
    const v = seriousOrCritical(full.violations);
    expect(v, `[${engine}] violations: ${JSON.stringify(v)}`).toEqual([]);
    // weaken-to-confirm: axe must have genuinely walked a non-trivial WCAG rule set.
    expect(full.ruleCount, `[${engine}] axe ran too few rules (${full.ruleCount})`).toBeGreaterThan(
      30,
    );
    expect(full.passCount, `[${engine}] axe reported zero passing checks`).toBeGreaterThan(0);
  });

  test('axe: color-contrast passes for every rendered control (button/icon-button/input/textarea)', async ({
    page,
  }) => {
    await ensureAxe(page);
    const contrast = await page.evaluate(async () => {
      const w = window as unknown as {
        axe: { run: (ctx: unknown, opt: unknown) => Promise<{ violations: { id: string }[] }> };
      };
      const r = await w.axe.run(
        document.querySelectorAll('.eden-button, .eden-icon-button, .eden-input, .eden-textarea'),
        { runOnly: { type: 'rule', values: ['color-contrast'] } },
      );
      return r.violations.map((x) => x.id);
    });
    expect(contrast).toEqual([]);
  });

  test('axe: every IconButton has an accessible name (the button-name rule passes)', async ({
    page,
  }) => {
    await ensureAxe(page);
    const nameViolations = await page.evaluate(async () => {
      const w = window as unknown as {
        axe: { run: (ctx: unknown, opt: unknown) => Promise<{ violations: { id: string }[] }> };
      };
      const r = await w.axe.run(document.querySelectorAll('.eden-icon-button'), {
        runOnly: { type: 'rule', values: ['button-name'] },
      });
      return r.violations.map((x) => x.id);
    });
    expect(nameViolations).toEqual([]);
    // and the names are the labels we passed (resolved by the role query on both engines).
    await expect(page.getByRole('button', { name: 'Close panel' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Delete item' })).toBeVisible();
  });

  test('keyboard: the enabled buttons are reachable by Tab in DOM order; the disabled one is skipped', async ({
    page,
  }) => {
    await page.getByTestId('before').focus();
    const labels: string[] = [];
    for (let i = 0; i < 6; i++) {
      await page.keyboard.press('Tab');
      const mark = await page.evaluate(() => {
        const el = document.activeElement;
        return el?.tagName === 'BUTTON'
          ? (el.textContent?.trim() ?? el.getAttribute('aria-label') ?? '')
          : '';
      });
      if (mark) labels.push(mark);
    }
    expect(labels).toContain('Primary action');
    expect(labels).toContain('Secondary action');
    expect(labels).toContain('Ghost action');
    expect(labels).toContain('Danger action');
    expect(labels).not.toContain('Disabled action');
    const enabledOrder = labels.filter((l) =>
      ['Primary action', 'Secondary action', 'Ghost action', 'Danger action'].includes(l),
    );
    expect(enabledOrder).toEqual([
      'Primary action',
      'Secondary action',
      'Ghost action',
      'Danger action',
    ]);
  });

  test('keyboard: a focused Button activates on Enter and on Space', async ({ page }) => {
    const danger = page.getByRole('button', { name: 'Danger action' });
    await danger.evaluate((el) => {
      (el as unknown as { __clicks: number }).__clicks = 0;
      el.addEventListener('click', () => {
        (el as unknown as { __clicks: number }).__clicks += 1;
      });
    });
    const clicks = (): Promise<number> =>
      danger.evaluate((el) => (el as unknown as { __clicks: number }).__clicks);

    await danger.focus();
    await expect(danger).toBeFocused();
    await page.keyboard.press('Enter');
    await expect.poll(clicks, { message: 'Enter must fire a click' }).toBeGreaterThanOrEqual(1);
    await danger.focus();
    await page.keyboard.press('Space');
    await expect
      .poll(clicks, { message: 'Space must fire a second click' })
      .toBeGreaterThanOrEqual(2);
  });

  test('keyboard: the Input and Textarea are reachable and accept typed text', async ({ page }) => {
    const search = page.getByRole('textbox', { name: 'Search' });
    await search.focus();
    await expect(search).toBeFocused();
    await page.keyboard.type('hello');
    await expect(search).toHaveValue('hello');

    const notes = page.getByRole('textbox', { name: 'Notes' });
    await notes.focus();
    await page.keyboard.type('a note');
    await expect(notes).toHaveValue('a note');
  });

  test('focus ring: a keyboard-focused control shows a visible (non-none) outline', async ({
    page,
  }) => {
    // :focus-visible is reliably matched only when focus arrives via the KEYBOARD — so we Tab to the
    // control (a programmatic .focus() does not engage focus-visible in every engine).
    const primary = page.getByRole('button', { name: 'Primary action' });
    await page.getByTestId('before').focus();
    await page.keyboard.press('Tab'); // → the first button
    await expect(primary).toBeFocused();
    expect(await primary.evaluate((el) => getComputedStyle(el).outlineStyle)).not.toBe('none');

    // Tab onward to the Search text input and assert its keyboard focus ring is visible too.
    const search = page.getByRole('textbox', { name: 'Search' });
    let reached = false;
    for (let i = 0; i < 12 && !reached; i++) {
      await page.keyboard.press('Tab');
      reached = await search.evaluate((el) => el === document.activeElement);
    }
    expect(reached, 'Tab traversal must reach the Search input').toBe(true);
    expect(await search.evaluate((el) => getComputedStyle(el).outlineStyle)).not.toBe('none');
  });

  test('token-driven color: the danger Button paints the resolved on-error / error tokens', async ({
    page,
  }) => {
    const danger = page.getByRole('button', { name: 'Danger action' });
    const fg = await danger.evaluate((el) => getComputedStyle(el).color);
    const bg = await danger.evaluate((el) => getComputedStyle(el).backgroundColor);
    const expectedFg = await resolvedToken(page, '--color-on-error', 'color');
    const expectedBg = await resolvedToken(page, '--color-error', 'bg');
    expect(fg).toBe(expectedFg);
    expect(bg).toBe(expectedBg);
    // weaken-to-confirm: real, distinct colors (a genuine destructive fg/bg pair, not transparent).
    expect(bg).not.toBe('rgba(0, 0, 0, 0)');
    expect(fg).not.toBe(bg);
  });

  test('hit target: every enabled Button, IconButton, Input, and Textarea meets the 44px floor', async ({
    page,
  }) => {
    const buttons = ['Primary action', 'Secondary action', 'Ghost action', 'Danger action'];
    for (const name of buttons) {
      const box = await page.getByRole('button', { name }).boundingBox();
      expect(box, `${name} has no box`).not.toBeNull();
      expect(box!.height, `${name} height ${box!.height} < 44`).toBeGreaterThanOrEqual(44);
      expect(box!.width, `${name} width ${box!.width} < 44`).toBeGreaterThanOrEqual(44);
    }
    for (const name of ['Close panel', 'Delete item']) {
      const box = await page.getByRole('button', { name }).boundingBox();
      expect(box!.height, `${name} height < 44`).toBeGreaterThanOrEqual(44);
      expect(box!.width, `${name} width < 44`).toBeGreaterThanOrEqual(44);
    }
    for (const name of ['Search', 'Notes']) {
      const box = await page.getByRole('textbox', { name }).boundingBox();
      expect(box!.height, `${name} height < 44`).toBeGreaterThanOrEqual(44);
    }
  });

  test('Field wiring: the label names the control, and the error is linked + announced', async ({
    page,
  }) => {
    // The valid Field: the visible label IS the accessible name (label/for resolves the role query).
    const email = page.getByRole('textbox', { name: 'Email address' });
    await expect(email).toBeVisible();
    expect(await email.getAttribute('aria-invalid')).toBeNull();

    // The erroring Field: the control is aria-invalid and described by the role=alert message.
    const message = page.getByRole('textbox', { name: 'Message' });
    expect(await message.getAttribute('aria-invalid')).toBe('true');
    const describedby = await message.getAttribute('aria-describedby');
    expect(describedby).toBeTruthy();
    const alert = page.getByRole('alert');
    await expect(alert).toHaveText('A message is required.');
    expect(await alert.getAttribute('id')).toBe(describedby);
  });

  test('disabled: the disabled Button is not operable and is excluded from the tab order', async ({
    page,
  }) => {
    const disabled = page.getByRole('button', { name: 'Disabled action' });
    await expect(disabled).toBeDisabled();
    await disabled.evaluate((el) => (el as HTMLButtonElement).focus());
    const focusedDisabled = await page.evaluate(
      () => document.activeElement?.textContent?.trim() === 'Disabled action',
    );
    expect(focusedDisabled).toBe(false);
  });
});
