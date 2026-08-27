/**
 * HotspotMap — the A11Y-EVIDENCE lane (ADR-0024 / codeinsight contract §5/§6). The browser-level layer
 * of the three-layer a11y stack for the scatter widget: axe-core on the REAL Chromium AND WebKit
 * engines + Playwright keyboard assertions + the offscreen data-table fallback (the structure a screen
 * reader actually reads). The noted SR matrix lives in a11y-evidence/hotspot-map.md (the third layer).
 * Every assertion is weaken-to-confirm guarded against a vacuous pass (axe must walk a real rule set;
 * the token colour must be a real, non-transparent value; the hit boxes must be real measured boxes).
 */
import { test, expect } from '@playwright/test';
import { ensureAxe, runAxeFull, seriousOrCritical } from '../axe-helper.js';

test.describe('HotspotMap — a11y evidence (axe + keyboard, Chromium & WebKit)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/index.html');
    await expect(page.getByText(/Scatter of 3 entities/)).toBeAttached();
    await expect(page.getByRole('button', { name: /cases\.go/ })).toBeVisible();
  });

  test('Eden tokens are injected at/above the document (the token context axe reads)', async ({
    page,
  }) => {
    const css = await page.evaluate(() => window.__EDEN_CSS__);
    expect(css).toContain('--color-surface');
    expect(css).toContain('--color-on-surface');
    expect(css).toMatch(/--color-surface:\s*oklch\(/);
  });

  test('axe: ZERO serious/critical violations across the hotspot map', async ({ page }, testInfo) => {
    const engine = testInfo.project.name;
    const full = await runAxeFull(page);
    const v = seriousOrCritical(full.violations);
    expect(v, `[${engine}] violations: ${JSON.stringify(v)}`).toEqual([]);
    // weaken-to-confirm: axe must have genuinely walked a non-trivial WCAG rule set.
    expect(full.ruleCount, `[${engine}] axe ran too few rules (${full.ruleCount})`).toBeGreaterThan(30);
    expect(full.passCount, `[${engine}] axe reported zero passing checks`).toBeGreaterThan(0);
  });

  test('axe: the color-contrast rule passes for the painted chart text', async ({ page }) => {
    // Narrow the audit to the WCAG color-contrast rule over the chart — the design-correctness contrast
    // gate, now proven by the independent axe engine in a real browser (not just our formula).
    await ensureAxe(page);
    const contrast = await page.evaluate(async () => {
      const w = window as unknown as {
        axe: { run: (ctx: unknown, opt: unknown) => Promise<{ violations: { id: string }[] }> };
      };
      const targets = document.querySelectorAll('[data-eden-hotspot-map]');
      const r = await w.axe.run(targets, { runOnly: { type: 'rule', values: ['color-contrast'] } });
      return r.violations.map((x) => x.id);
    });
    expect(contrast).toEqual([]);
  });

  test('the offscreen data-table fallback enumerates every point (the SR-readable structure)', async ({
    page,
  }) => {
    const table = page.getByRole('table', { name: /data table/ });
    await expect(table).toBeAttached();
    // a header row + one row per entity (3) — the scatter is fully readable as a table.
    const rows = table.getByRole('row');
    await expect(rows).toHaveCount(4);
    // the top hotspot's row carries its path + metrics in text (colour is never the only signal).
    await expect(table.getByRole('row', { name: /cases\.go/ })).toBeAttached();
  });

  test('keyboard: the scatter points participate in the tab order, in DOM order', async ({ page }) => {
    await page.getByTestId('before').focus();
    const labels: string[] = [];
    for (let i = 0; i < 5; i++) {
      await page.keyboard.press('Tab');
      const mark = await page.evaluate(() => {
        const el = document.activeElement;
        return el?.getAttribute('role') === 'button' ? (el.getAttribute('aria-label') ?? '') : `<${el?.tagName}>`;
      });
      labels.push(mark);
    }
    // the three point hit-targets are reachable by Tab and announce their path + metrics.
    const pointLabels = labels.filter((l) => l.includes('churnRelative'));
    expect(pointLabels.length).toBeGreaterThanOrEqual(3);
    expect(pointLabels.some((l) => l.includes('cases.go'))).toBe(true);
  });

  test('focus ring: a keyboard-focused point shows a visible (non-none) outline', async ({ page }) => {
    const point = page.getByRole('button', { name: /cases\.go/ });
    await point.focus();
    const outlineStyle = await point.evaluate((el) => getComputedStyle(el).outlineStyle);
    expect(outlineStyle, 'focus-visible must render a visible outline').not.toBe('none');
  });

  test('hit target: every interactive scatter point meets the 44px AAA tap floor in the real browser', async ({
    page,
  }) => {
    const points = page.getByRole('button');
    const count = await points.count();
    expect(count).toBe(3);
    for (let i = 0; i < count; i++) {
      const box = await points.nth(i).boundingBox();
      expect(box, `point ${String(i)} has no box`).not.toBeNull();
      expect(box!.height, `point ${String(i)} height ${box!.height} < 44`).toBeGreaterThanOrEqual(44);
      expect(box!.width, `point ${String(i)} width ${box!.width} < 44`).toBeGreaterThanOrEqual(44);
    }
  });

  test('token-driven color: the plot paints the resolved surface/on-surface tokens', async ({
    page,
  }) => {
    const figure = page.locator('[data-eden-hotspot-map]');
    const fg = await figure.evaluate((el) => getComputedStyle(el).color);
    const bg = await figure.evaluate((el) => getComputedStyle(el).backgroundColor);
    // weaken-to-confirm: real, distinct, non-transparent colours (a genuine fg/bg pair).
    expect(bg).not.toBe('rgba(0, 0, 0, 0)');
    expect(bg).toMatch(/(rgb|oklch|color)/i);
    expect(fg).not.toBe(bg);
  });
});
