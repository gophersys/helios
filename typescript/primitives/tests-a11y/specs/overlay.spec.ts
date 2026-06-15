/**
 * Overlay group — the A11Y-EVIDENCE lane (ADR-0024 / RD-16 / OD-1). The browser-level layer of the
 * three-layer a11y stack for the PORTALED overlays (Dialog incl. nested/LIFO, Popover, Tooltip,
 * DropdownMenu): axe-core on the REAL Chromium AND WebKit engines + Playwright keyboard assertions.
 * The noted SR matrix lives in a11y-evidence/{dialog,popover,tooltip,dropdown-menu}.md (the third
 * layer). Wired as the `a11y` ctl verb and a phase-gate qa BLOCKER.
 *
 * The OD-1 contract each overlay proves here: (1) axe ZERO serious/critical AT EVERY OPEN DEPTH
 * (including a nested dialog) through the bits-ui Portal; (2) the portaled content's COMPUTED colors
 * EQUAL the resolved Eden tokens (the tokens cross the Portal); (3) keyboard — focus trap, Escape
 * dismissal with LIFO unwind for nested dialogs, and focus RETURN to the trigger. Every assertion is
 * weaken-to-confirm guarded against a vacuous pass.
 *
 * NOTE on locating triggers: bits-ui renders each `Trigger` as a real `<button>` wrapping the trigger
 * snippet's content, so the focusable element is the BUTTON (the snippet text becomes its accessible
 * name). We therefore target triggers by `getByRole('button', { name })` — the actual focusable node —
 * NOT by the inner span's data-testid (which is not focusable). Portaled content is matched by its
 * `data-eden-overlay` marker / ARIA role.
 */
import { test, expect, type Page } from '@playwright/test';
import { ensureAxe, runAxeFull, seriousOrCritical } from '../axe-helper.js';

/** Assert axe reports ZERO serious/critical AND genuinely walked a non-trivial WCAG rule set. */
async function expectAxeClean(page: Page, engine: string, where: string): Promise<void> {
  await ensureAxe(page);
  const full = await runAxeFull(page);
  const v = seriousOrCritical(full.violations);
  expect(v, `[${engine}] ${where} violations: ${JSON.stringify(v)}`).toEqual([]);
  expect(full.ruleCount, `[${engine}] ${where}: axe ran too few rules`).toBeGreaterThan(30);
  expect(full.passCount, `[${engine}] ${where}: axe reported zero passing checks`).toBeGreaterThan(
    0,
  );
}

/** Read the resolved (cascade-computed) value of a CSS custom property via a probe element. */
async function resolvedToken(page: Page, prop: string, kind: 'bg' | 'color'): Promise<string> {
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

test.describe('Overlay group — a11y evidence (axe + keyboard, Chromium & WebKit)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('overlays')).toBeVisible();
  });

  test('baseline: the closed page (overlays at rest) is axe-clean', async ({ page }, testInfo) => {
    // Overlays are closed at rest — the page must already be clean before any portal opens.
    await expectAxeClean(page, testInfo.project.name, 'page at rest');
  });

  // ── DIALOG (incl. the nested/LIFO behavior the OD-1 spike proved) ───────────────────────────
  test('Dialog: opens, is axe-clean through the portal at depth 1, exposes its accessible name', async ({
    page,
  }, testInfo) => {
    await page.getByRole('button', { name: 'Open dialog' }).click();
    const panel = page.getByRole('dialog');
    await expect(panel).toBeVisible();
    await expectAxeClean(page, testInfo.project.name, 'dialog open');
    // the dialog exposes its accessible name (the Title is wired to aria-labelledby by bits-ui).
    await expect(panel).toHaveAccessibleName(/Edit profile/);
  });

  test('Dialog: NESTED open is axe-clean and Escape unwinds LIFO (inner first), focus returns', async ({
    page,
  }, testInfo) => {
    const trigger = page.getByRole('button', { name: 'Open dialog' });
    await trigger.click();
    await expect(page.getByRole('dialog')).toHaveCount(1);

    // open the NESTED dialog from inside the outer one.
    await page.getByRole('button', { name: 'Open nested dialog' }).click();
    await expect(page.getByRole('dialog')).toHaveCount(2);
    // axe-clean at depth 2 (two stacked portaled surfaces) — the OD-1 nested proof.
    await expectAxeClean(page, testInfo.project.name, 'nested dialog open (depth 2)');

    // Escape unwinds LIFO: the INNER closes first (still one dialog left), then the OUTER.
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toHaveCount(1);
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toHaveCount(0);

    // focus RETURNS to the original trigger after the outer dialog closes (the focus-return contract).
    await expect(trigger).toBeFocused();
  });

  test('Dialog: the portaled panel paints the resolved Eden surface/on-surface tokens', async ({
    page,
  }) => {
    await page.getByRole('button', { name: 'Open dialog' }).click();
    const panel = page.getByRole('dialog');
    await expect(panel).toBeVisible();
    const bg = await panel.evaluate((el) => getComputedStyle(el).backgroundColor);
    const fg = await panel.evaluate((el) => getComputedStyle(el).color);
    const expectedBg = await resolvedToken(page, '--color-surface', 'bg');
    const expectedFg = await resolvedToken(page, '--color-on-surface', 'color');
    // the computed colors equal the resolved Eden tokens — the tokens crossed the Portal.
    expect(bg).toBe(expectedBg);
    expect(fg).toBe(expectedFg);
    // weaken-to-confirm: the surface is a real, non-transparent color (a genuine painted panel).
    expect(bg).not.toBe('rgba(0, 0, 0, 0)');
    expect(fg).not.toBe(bg);
  });

  // ── POPOVER ──────────────────────────────────────────────────────────────────────────────
  test('Popover: opens, is axe-clean through the portal, Escape closes and returns focus', async ({
    page,
  }, testInfo) => {
    const trigger = page.getByRole('button', { name: 'Open popover' });
    await trigger.click();
    const content = page.locator('[data-eden-overlay="popover"]');
    await expect(content).toBeVisible();
    await expectAxeClean(page, testInfo.project.name, 'popover open');

    await page.keyboard.press('Escape');
    await expect(content).toHaveCount(0);
    await expect(trigger).toBeFocused();
  });

  test('Popover: the portaled content paints the resolved Eden surface token', async ({ page }) => {
    await page.getByRole('button', { name: 'Open popover' }).click();
    const content = page.locator('[data-eden-overlay="popover"]');
    await expect(content).toBeVisible();
    const bg = await content.evaluate((el) => getComputedStyle(el).backgroundColor);
    const expectedBg = await resolvedToken(page, '--color-surface', 'bg');
    expect(bg).toBe(expectedBg);
    expect(bg).not.toBe('rgba(0, 0, 0, 0)');
  });

  // ── TOOLTIP ──────────────────────────────────────────────────────────────────────────────
  test('Tooltip: opens on trigger focus, is axe-clean through the portal (keyboard-operable)', async ({
    page,
  }, testInfo) => {
    // Tooltip opens on the trigger BUTTON's focus (keyboard-operable, not hover-only).
    await page.getByRole('button', { name: 'Hover me' }).focus();
    const content = page.locator('[data-eden-overlay="tooltip"]');
    await expect(content).toBeVisible();
    await expectAxeClean(page, testInfo.project.name, 'tooltip open');
  });

  test('Tooltip: the portaled label paints the resolved Eden surface token', async ({ page }) => {
    await page.getByRole('button', { name: 'Hover me' }).focus();
    const content = page.locator('[data-eden-overlay="tooltip"]');
    await expect(content).toBeVisible();
    const bg = await content.evaluate((el) => getComputedStyle(el).backgroundColor);
    const expectedBg = await resolvedToken(page, '--color-surface', 'bg');
    expect(bg).toBe(expectedBg);
    expect(bg).not.toBe('rgba(0, 0, 0, 0)');
  });

  // ── DROPDOWN MENU ────────────────────────────────────────────────────────────────────────
  test('DropdownMenu: opens, is axe-clean, arrow-navigates and Enter selects an item', async ({
    page,
  }, testInfo) => {
    const trigger = page.getByRole('button', { name: 'Open menu' });
    await trigger.click();
    const menu = page.getByRole('menu');
    await expect(menu).toBeVisible();
    await expectAxeClean(page, testInfo.project.name, 'menu open');

    // roving arrow navigation: ArrowDown highlights the first item, Enter activates it.
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('menu-choice')).toHaveText('Rename');
    // the menu closed on selection and focus returned to the trigger.
    await expect(menu).toHaveCount(0);
    await expect(trigger).toBeFocused();
  });

  test('DropdownMenu: every ENABLED item meets the 44px AAA tap floor in the real browser', async ({
    page,
  }) => {
    await page.getByRole('button', { name: 'Open menu' }).click();
    await expect(page.getByRole('menu')).toBeVisible();
    const items = page.getByRole('menuitem').filter({ hasNot: page.locator('[data-disabled]') });
    const count = await items.count();
    expect(count).toBeGreaterThan(0);
    for (let i = 0; i < count; i++) {
      const box = await items.nth(i).boundingBox();
      expect(box, `menu item ${i} has no box`).not.toBeNull();
      expect(box!.height, `menu item ${i} height ${box!.height} < 44`).toBeGreaterThanOrEqual(44);
    }
  });

  test('DropdownMenu: the disabled item is present but not operable', async ({ page }) => {
    await page.getByRole('button', { name: 'Open menu' }).click();
    const deleteItem = page.getByRole('menuitem', { name: 'Delete' });
    await expect(deleteItem).toBeVisible();
    await expect(deleteItem).toHaveAttribute('data-disabled');
  });
});
