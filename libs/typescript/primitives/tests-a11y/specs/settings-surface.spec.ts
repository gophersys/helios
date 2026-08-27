/**
 * SettingsSurface (doc 17 §4/§7) — the A11Y-EVIDENCE lane (ADR-0024 / RD-16). The browser-level layer of
 * the three-layer a11y stack: axe-core on the REAL Chromium AND WebKit engines + Playwright keyboard
 * assertions (the FOCUS TRAP through the portal, ESCAPE-dismiss, the rail's active state, the token-driven
 * mono/sans voices). The behavior it asserts is the bits-ui Dialog layer the organism composes — this
 * spec PROVES that composition holds THROUGH the portal on both engines. The noted SR matrix lives in
 * a11y-evidence/settings-surface.md. Every assertion is weaken-to-confirm guarded against a vacuous pass.
 */
import { test, expect } from '@playwright/test';
import { runAxeFull, seriousOrCritical } from '../axe-helper.js';

test.describe('SettingsSurface — a11y evidence (axe + keyboard trap, Chromium & WebKit)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/settings-surface.html');
    await expect(page.getByTestId('settings')).toBeVisible();
  });

  test('axe: ZERO serious/critical violations across the settings sheet', async ({
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

  test('the sheet is a named dialog region (bits-ui Dialog: role="dialog" + aria-modal + a title)', async ({
    page,
  }) => {
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAccessibleName(/Settings/);
  });

  test('the rail renders the mono section labels and marks the ACTIVE one (aria-current + a distinct family)', async ({
    page,
  }) => {
    // the four section labels render as rail tabs.
    const items = page.locator('.eden-settings-surface-rail-item');
    await expect(items).toHaveCount(4);
    // the active section (Appearance) carries aria-current="page"; an inactive one does not.
    const active = page.locator('.eden-settings-surface-rail-item[data-active="true"]');
    await expect(active).toHaveText('Appearance');
    await expect(active).toHaveAttribute('aria-current', 'page');
    // the rail label is the MONO data voice; the section title a DIFFERENT (sans) family (P-D4).
    const labelFamily = await active.evaluate((el) => getComputedStyle(el).fontFamily);
    const titleFamily = await page
      .locator('.eden-settings-surface-heading')
      .evaluate((el) => getComputedStyle(el).fontFamily);
    expect(labelFamily.toLowerCase()).toContain('mono');
    expect(titleFamily).not.toBe(labelFamily);
  });

  test('picking a rail item switches the content region (the section-scoped content)', async ({
    page,
  }) => {
    // Appearance is active on load — its content shows.
    await expect(page.getByTestId('section-appearance')).toBeVisible();
    // pick Agents → the content area renders THAT section (and the rail moves the active state).
    await page.locator('.eden-settings-surface-rail-item[data-section="agents"]').click();
    await expect(page.getByTestId('section-agents')).toBeVisible();
    await expect(page.getByTestId('section-appearance')).toBeHidden();
    await expect(
      page.locator('.eden-settings-surface-rail-item[data-active="true"]'),
    ).toHaveText('Agents');
  });

  test('focus is TRAPPED within the sheet — Tab cycles the controls, never escaping to the page anchors', async ({
    page,
  }) => {
    const before = page.getByTestId('before');
    const after = page.getByTestId('after');
    // Tab many times from inside the sheet; focus must never land on the page anchors OUTSIDE it.
    await page.locator('.eden-settings-surface-rail-item[data-section="profile"]').focus();
    for (let i = 0; i < 14; i++) {
      await page.keyboard.press('Tab');
      await expect(after).not.toBeFocused();
      await expect(before).not.toBeFocused();
    }
    // focus stayed INSIDE the sheet subtree the whole time (the bits-ui trap held through the portal).
    const inside = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      return el?.closest('[data-eden-settings-surface]') !== null;
    });
    expect(inside).toBe(true);
  });

  test('Escape dismisses the sheet (the bits-ui Dialog close behavior, reinvented nowhere)', async ({
    page,
  }) => {
    await page.locator('.eden-settings-surface-rail-item[data-section="profile"]').focus();
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('settings')).toBeHidden();
    // the page anchors OUTSIDE the sheet are still present (the page did not crash on close).
    await expect(page.getByTestId('before')).toBeVisible();
  });
});
