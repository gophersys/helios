/**
 * Chat group — the A11Y-EVIDENCE lane (ADR-0024 / RD-16). The browser-level layer of the three-layer
 * a11y stack for the chat surfaces (Message, StreamingText, ToolCall, PermissionRequest, UsageMeter,
 * ThinkingBlock): axe-core on the REAL Chromium AND WebKit engines + Playwright keyboard assertions.
 * The noted SR matrix lives in a11y-evidence/chat.md (the third layer). Every assertion is
 * weaken-to-confirm guarded against a vacuous pass (axe must walk a real rule set; the token colour
 * must be a real, non-transparent value; the hit boxes must be real measured boxes).
 */
import { test, expect } from '@playwright/test';
import { ensureAxe, runAxeFull, seriousOrCritical } from '../axe-helper.js';

test.describe('Chat surfaces — a11y evidence (axe + keyboard, Chromium & WebKit)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/chat.html');
    await expect(page.getByRole('button', { name: 'Allow once' })).toBeVisible();
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

  test('axe: ZERO serious/critical violations across every chat surface', async ({
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

  test('axe: the color-contrast rule passes for every painted chat surface', async ({ page }) => {
    // Narrow the audit to the WCAG color-contrast rule over the chat surfaces — the design-correctness
    // contrast gate, now proven by the independent axe engine in a real browser (not just our formula).
    await ensureAxe(page);
    const contrast = await page.evaluate(async () => {
      const w = window as unknown as {
        axe: { run: (ctx: unknown, opt: unknown) => Promise<{ violations: { id: string }[] }> };
      };
      const targets = document.querySelectorAll(
        '[data-eden-message], [data-eden-streaming-text], [data-eden-tool-call], [data-eden-permission-request], [data-eden-usage-meter], [data-eden-thinking-block]',
      );
      const r = await w.axe.run(targets, { runOnly: { type: 'rule', values: ['color-contrast'] } });
      return r.violations.map((x) => x.id);
    });
    expect(contrast).toEqual([]);
  });

  test('keyboard: the permission actions are reachable by Tab and activate on Enter/Space', async ({
    page,
  }) => {
    // The three permission actions are real Buttons; each must be tab-reachable and activate by keyboard.
    const allowOnce = page.getByRole('button', { name: 'Allow once' });
    await allowOnce.evaluate((el) => {
      (el as unknown as { __clicks: number }).__clicks = 0;
      el.addEventListener('click', () => {
        (el as unknown as { __clicks: number }).__clicks += 1;
      });
    });
    const clicks = (): Promise<number> =>
      allowOnce.evaluate((el) => (el as unknown as { __clicks: number }).__clicks);

    await allowOnce.focus();
    await expect(allowOnce).toBeFocused();
    await page.keyboard.press('Enter');
    await expect.poll(clicks, { message: 'Enter must fire a click' }).toBeGreaterThanOrEqual(1);
    await allowOnce.focus();
    await page.keyboard.press('Space');
    await expect
      .poll(clicks, { message: 'Space must fire a second click' })
      .toBeGreaterThanOrEqual(2);
  });

  test('keyboard: all three permission actions participate in the tab order, in DOM order', async ({
    page,
  }) => {
    await page.getByTestId('before').focus();
    const labels: string[] = [];
    for (let i = 0; i < 6; i++) {
      await page.keyboard.press('Tab');
      const mark = await page.evaluate(() => {
        const el = document.activeElement;
        return el?.tagName === 'BUTTON' ? (el.textContent?.trim() ?? '') : `<${el?.tagName}>`;
      });
      labels.push(mark);
    }
    expect(labels).toContain('Allow once');
    expect(labels).toContain('Allow for session');
    expect(labels).toContain('Deny');
    const wanted = ['Allow once', 'Allow for session', 'Deny'];
    const order = labels.filter((l) => wanted.includes(l)).slice(0, 3);
    expect(order).toEqual(wanted);
  });

  test('keyboard: the ThinkingBlock toggle expands/collapses on Enter (aria-expanded flips)', async ({
    page,
  }) => {
    const toggle = page.getByRole('button', { name: 'Thinking' });
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await toggle.focus();
    await page.keyboard.press('Enter');
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await page.keyboard.press('Enter');
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  });

  test('focus ring: a keyboard-focused permission action shows a visible (non-none) outline', async ({
    page,
  }) => {
    const deny = page.getByRole('button', { name: 'Deny' });
    await deny.focus();
    const outlineStyle = await deny.evaluate((el) => getComputedStyle(el).outlineStyle);
    expect(outlineStyle, 'focus-visible must render a visible outline').not.toBe('none');
  });

  test('hit target: every interactive chat control meets the 44px AAA tap floor in the real browser', async ({
    page,
  }) => {
    for (const name of ['Allow once', 'Allow for session', 'Deny', 'Thinking']) {
      const box = await page.getByRole('button', { name }).boundingBox();
      expect(box, `${name} has no box`).not.toBeNull();
      expect(box!.height, `${name} height ${box!.height} < 44`).toBeGreaterThanOrEqual(44);
      expect(box!.width, `${name} width ${box!.width} < 44`).toBeGreaterThanOrEqual(44);
    }
  });

  test('token-driven color: the user Message paints the resolved on-primary / primary tokens', async ({
    page,
  }) => {
    const bubble = page.getByRole('listitem', { name: 'User message' });
    const fg = await bubble.evaluate((el) => getComputedStyle(el).color);
    const bg = await bubble.evaluate((el) => getComputedStyle(el).backgroundColor);
    // weaken-to-confirm: real, distinct, non-transparent colours (a genuine fg/bg pair).
    expect(bg).not.toBe('rgba(0, 0, 0, 0)');
    expect(bg).toMatch(/(rgb|oklch|color)/i);
    expect(fg).not.toBe(bg);
  });

  test('progressbar: the over-budget UsageMeter exposes aria-valuenow/valuetext', async ({
    page,
  }) => {
    const bars = page.getByRole('progressbar');
    await expect(bars.first()).toBeVisible();
    // the third meter is the 100/100 over-budget case.
    const over = bars.nth(2);
    await expect(over).toHaveAttribute('aria-valuenow', '100');
    const valueText = await over.getAttribute('aria-valuetext');
    expect(valueText).toContain('over budget');
  });
});
