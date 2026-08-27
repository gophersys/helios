/**
 * Button — the A11Y-EVIDENCE lane (ADR-0024 / RD-16). The browser-level layer of the three-layer
 * a11y stack: axe-core on the REAL Chromium AND WebKit engines + Playwright keyboard assertions.
 * The noted SR matrix lives in a11y-evidence/button.md (the third layer). Wired as the `a11y` ctl
 * verb and a phase-gate qa BLOCKER. Every assertion is weaken-to-confirm guarded against a vacuous
 * pass (axe must walk a real rule set; the token color must be a real, non-transparent value).
 */
import { test, expect } from '@playwright/test';
import { ensureAxe, runAxeFull, seriousOrCritical } from '../axe-helper.js';

// Read the resolved (cascade-computed) value of a CSS custom property via a probe element.
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

test.describe('Button — a11y evidence (axe + keyboard, Chromium & WebKit)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('button', { name: 'Primary action' })).toBeVisible();
  });

  test('Eden tokens are injected at/above the document (the token context axe reads)', async ({
    page,
  }) => {
    const css = await page.evaluate(() => window.__EDEN_CSS__);
    expect(css).toContain('--color-surface');
    expect(css).toContain('--color-on-surface');
    expect(css).toContain('--color-primary');
    expect(css).toMatch(/--color-surface:\s*oklch\(/);
  });

  test('axe: ZERO serious/critical violations across every Button variant', async ({
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

  test('axe: color-contrast rule specifically passes for the rendered buttons', async ({ page }) => {
    // Narrow the audit to the WCAG color-contrast rule — the design-correctness contrast gate, now
    // proven by the independent axe engine in a real browser (not just our own formula).
    await ensureAxe(page);
    const contrast = await page.evaluate(async () => {
      const w = window as unknown as {
        axe: { run: (ctx: unknown, opt: unknown) => Promise<{ violations: { id: string }[] }> };
      };
      const r = await w.axe.run(document.querySelectorAll('.eden-button'), {
        runOnly: { type: 'rule', values: ['color-contrast'] },
      });
      return r.violations.map((x) => x.id);
    });
    expect(contrast).toEqual([]);
  });

  test('keyboard: every enabled Button is reachable by Tab and participates in the tab order', async ({
    page,
  }) => {
    // Start from the "before" anchor, then Tab through; the three enabled buttons must each receive
    // focus in order. The DISABLED button must NOT receive focus (it is removed from the tab order).
    await page.getByTestId('before').focus();
    const labels: string[] = [];
    for (let i = 0; i < 5; i++) {
      await page.keyboard.press('Tab');
      const mark = await page.evaluate(() => {
        const el = document.activeElement;
        return el?.tagName === 'BUTTON' ? (el.textContent?.trim() ?? '') : `<${el?.tagName}>`;
      });
      labels.push(mark);
    }
    // The three enabled buttons appear, in order; the disabled one never gets focus.
    expect(labels).toContain('Primary action');
    expect(labels).toContain('Secondary action');
    expect(labels).toContain('Ghost action');
    expect(labels).not.toContain('Disabled action');
    // …and they appear in DOM order (real tab traversal, not a coincidence).
    const enabledOrder = labels.filter((l) =>
      ['Primary action', 'Secondary action', 'Ghost action'].includes(l),
    );
    expect(enabledOrder).toEqual(['Primary action', 'Secondary action', 'Ghost action']);
  });

  test('keyboard: a focused Button activates on Enter and on Space', async ({ page }) => {
    // The native activation contract: a focused button fires `click` on Enter (keydown) and on Space
    // (keyup). We attach an in-page counter on the element and assert each key fires a click — read
    // back via expect.poll so the engine's event dispatch (Space activates on keyup) has settled.
    const primary = page.getByRole('button', { name: 'Primary action' });
    await primary.evaluate((el) => {
      (el as unknown as { __clicks: number }).__clicks = 0;
      el.addEventListener('click', () => {
        (el as unknown as { __clicks: number }).__clicks += 1;
      });
    });
    const clicks = (): Promise<number> =>
      primary.evaluate((el) => (el as unknown as { __clicks: number }).__clicks);

    await primary.focus();
    await expect(primary).toBeFocused();

    await page.keyboard.press('Enter');
    await expect.poll(clicks, { message: 'Enter must fire a click' }).toBeGreaterThanOrEqual(1);

    await primary.focus();
    await page.keyboard.press('Space');
    await expect
      .poll(clicks, { message: 'Space must fire a second click' })
      .toBeGreaterThanOrEqual(2);
  });

  test('focus ring: a keyboard-focused Button shows a visible (non-none) outline', async ({
    page,
  }) => {
    const primary = page.getByRole('button', { name: 'Primary action' });
    await page.getByTestId('before').focus();
    await page.keyboard.press('Tab'); // moves to the first button
    await expect(primary).toBeFocused();
    const outlineStyle = await primary.evaluate((el) => getComputedStyle(el).outlineStyle);
    expect(outlineStyle, 'focus-visible must render a visible outline').not.toBe('none');
  });

  test('token-driven color: the primary Button paints the resolved on-primary / primary tokens', async ({
    page,
  }) => {
    const primary = page.getByRole('button', { name: 'Primary action' });
    const fg = await primary.evaluate((el) => getComputedStyle(el).color);
    const bg = await primary.evaluate((el) => getComputedStyle(el).backgroundColor);

    const expectedFg = await resolvedToken(page, '--color-on-primary', 'color');
    const expectedBg = await resolvedToken(page, '--color-primary', 'bg');

    expect(fg).toBe(expectedFg);
    expect(bg).toBe(expectedBg);
    // weaken-to-confirm: the tokens are real, distinct colors (a genuine fg/bg pair, not transparent).
    expect(bg).not.toBe('rgba(0, 0, 0, 0)');
    expect(bg).toMatch(/(rgb|oklch|color)/i);
    expect(fg).not.toBe(bg);
  });

  test('hit target: every enabled Button meets the 44px AAA tap floor in the real browser', async ({
    page,
  }) => {
    for (const name of ['Primary action', 'Secondary action', 'Ghost action']) {
      const box = await page.getByRole('button', { name }).boundingBox();
      expect(box, `${name} has no box`).not.toBeNull();
      expect(box!.height, `${name} height ${box!.height} < 44`).toBeGreaterThanOrEqual(44);
      expect(box!.width, `${name} width ${box!.width} < 44`).toBeGreaterThanOrEqual(44);
    }
  });

  test('disabled: the disabled Button is not operable and is excluded from the tab order', async ({
    page,
  }) => {
    const disabled = page.getByRole('button', { name: 'Disabled action' });
    await expect(disabled).toBeDisabled();
    // It cannot be focused programmatically into the tab sequence: focusing it leaves activeElement
    // off the disabled control in every engine.
    await disabled.evaluate((el) => (el as HTMLButtonElement).focus());
    const focusedDisabled = await page.evaluate(
      () => document.activeElement?.textContent?.trim() === 'Disabled action',
    );
    expect(focusedDisabled).toBe(false);
  });
});
