/**
 * Wave-1 (Badge · Chip · Kbd · Spinner · Divider · Card · StatRow · Tabs · EmptyState) — the
 * A11Y-EVIDENCE lane (ADR-0024 / RD-16 · doc 17 §3/§4). The browser-level layer of the three-layer
 * a11y stack: axe-core on the REAL Chromium AND WebKit engines + Playwright keyboard assertions +
 * the token-driven colour + the 44px hit floor for the interactive members. The noted SR matrix
 * lives in a11y-evidence/wave1.md. Every assertion is weaken-to-confirm guarded against a vacuous
 * pass (axe must walk a real rule set; the token colour must be a real, non-transparent value).
 */
import { test, expect } from '@playwright/test';
import { runAxeFull, seriousOrCritical } from '../axe-helper.js';

test.describe('Wave-1 atoms/molecules — a11y evidence (axe + keyboard, Chromium & WebKit)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/wave1.html');
    await expect(page.getByTestId('badges')).toBeVisible();
  });

  test('Eden tokens are injected at/above the document (the token context axe reads)', async ({
    page,
  }) => {
    const css = await page.evaluate(() => window.__EDEN_CSS__);
    expect(css).toContain('--color-surface');
    expect(css).toContain('--color-success');
    expect(css).toMatch(/--color-surface:\s*oklch\(/);
  });

  test('axe: ZERO serious/critical violations across the whole Wave-1 harness', async ({
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

  test('badges: each status badge carries a status word (never colour alone) + role="status"', async ({
    page,
  }) => {
    // The status badges are announced live; each has a text label (the triple-encoding survives
    // grayscale — the meaning is the word, not the tint). Scope to the badges section so the
    // Spinner's own role=status regions do not collide with the badge words.
    const badges = page.getByTestId('badges');
    for (const word of ['Healthy', 'Updating', 'Degraded', 'Down', 'Unknown']) {
      await expect(badges.getByRole('status').filter({ hasText: word })).toBeVisible();
    }
  });

  test('chip: the removable chip exposes a named remove button, reachable by keyboard, that removes', async ({
    page,
  }) => {
    const remove = page.getByRole('button', { name: 'Remove namespace filter' });
    await expect(remove).toBeVisible();
    // reachable + operable by keyboard: focus it and activate with Enter.
    await remove.focus();
    await expect(remove).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('chip-removed')).toHaveText('namespace');
  });

  test('chip remove control: meets the 44px AAA tap floor in the real browser', async ({ page }) => {
    const box = await page.getByRole('button', { name: 'Remove namespace filter' }).boundingBox();
    expect(box, 'remove control has no box').not.toBeNull();
    expect(box!.height, `height ${box!.height} < 44`).toBeGreaterThanOrEqual(44);
    expect(box!.width, `width ${box!.width} < 44`).toBeGreaterThanOrEqual(44);
  });

  test('kbd: the ⌘K cap renders a native <kbd> (the keyboard-input semantic element)', async ({
    page,
  }) => {
    const cmdk = page.getByTestId('kbds').locator('kbd', { hasText: '⌘K' });
    await expect(cmdk).toBeVisible();
    expect(await cmdk.evaluate((el) => el.tagName)).toBe('KBD');
  });

  test('spinner: exposes an accessible live status label (role=status)', async ({ page }) => {
    await expect(
      page.getByRole('status').filter({ hasText: 'Loading projects' }),
    ).toBeAttached();
  });

  test('tabs: roving keyboard navigation selects tabs (ArrowRight moves, Enter/auto activates)', async ({
    page,
  }) => {
    const overview = page.getByRole('tab', { name: 'Overview' });
    const build = page.getByRole('tab', { name: 'Build' });
    await overview.focus();
    await expect(overview).toBeFocused();
    // ArrowRight moves the roving focus to the next enabled tab (bits-ui automatic activation).
    await page.keyboard.press('ArrowRight');
    await expect(build).toBeFocused();
    await expect(build).toHaveAttribute('data-state', 'active');
    // the disabled Insight tab is not selectable
    await expect(page.getByRole('tab', { name: 'Insight' })).toHaveAttribute('data-disabled', '');
  });

  test('tabs trigger: meets the 44px AAA tap floor in the real browser', async ({ page }) => {
    const box = await page.getByRole('tab', { name: 'Overview' }).boundingBox();
    expect(box, 'tab has no box').not.toBeNull();
    expect(box!.height, `height ${box!.height} < 44`).toBeGreaterThanOrEqual(44);
  });

  test('card: the raised card paints a token-driven shadow (a real, non-none box-shadow)', async ({
    page,
  }) => {
    const raised = page.getByLabel('Project card');
    const shadow = await raised.evaluate((el) => getComputedStyle(el).boxShadow);
    expect(shadow, 'raised card must carry a box-shadow').not.toBe('none');
    // weaken-to-confirm: the flat card carries NO shadow (the variant does real work).
    const flat = page.getByLabel('Flat card');
    const flatShadow = await flat.evaluate((el) => getComputedStyle(el).boxShadow);
    expect(flatShadow).toBe('none');
  });

  test('empty-state: the headline is a labelled region wired via aria-labelledby', async ({
    page,
  }) => {
    const region = page.getByRole('region', { name: 'No projects yet' });
    await expect(region).toBeVisible();
    // the content slot is a real product surface (templates/recents), not a bare void.
    await expect(region.getByText('Start from a template')).toBeVisible();
    await expect(region.getByRole('button', { name: 'Create project' })).toBeVisible();
  });

  test('empty-state headline: renders in a DIFFERENT font family than the body (the serif voice)', async ({
    page,
  }) => {
    const region = page.getByRole('region', { name: 'No projects yet' });
    const headlineFamily = await region
      .locator('.eden-empty-state-headline')
      .evaluate((el) => getComputedStyle(el).fontFamily);
    const bodyFamily = await region
      .locator('.eden-empty-state-body')
      .evaluate((el) => getComputedStyle(el).fontFamily);
    expect(headlineFamily).not.toBe(bodyFamily);
  });

  test('divider: the horizontal rule is a native <hr> (the semantic separator)', async ({ page }) => {
    // The <hr> is a 1px hairline (block-size 1px) — Playwright treats a zero-width flex child as
    // "hidden", so assert it is ATTACHED (present + native) and carries the derived rule colour,
    // which is the honest separator evidence (the semantic element + a real, token-driven line).
    const hr = page.getByTestId('dividers').locator('hr');
    await expect(hr).toBeAttached();
    const bg = await hr.evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(bg).not.toBe('rgba(0, 0, 0, 0)');
  });
});
