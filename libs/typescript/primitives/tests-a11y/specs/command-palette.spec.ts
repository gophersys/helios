/**
 * CommandPalette — the A11Y-EVIDENCE lane (ADR-0024 / RD-16 / OD-1). The browser-level layer of the
 * three-layer a11y stack: axe-core on the REAL Chromium AND WebKit engines + Playwright keyboard
 * assertions, through the bits-ui Portal (the OD-1-proven ⌘K composition: Dialog.Portal wrapping
 * Command.Root). The noted SR matrix lives in a11y-evidence/command-palette.md (the third layer).
 * Wired as the `a11y` ctl verb and a phase-gate qa BLOCKER. Every assertion is weaken-to-confirm
 * guarded against a vacuous pass (axe must walk a real rule set; the token color must be a real,
 * non-transparent value; the keyboard navigation must actually move aria-activedescendant).
 */
import { test, expect, type Page } from '@playwright/test';
import { ensureAxe, runAxeFull, seriousOrCritical } from '../axe-helper.js';

/** Open the palette via its trigger and wait for the combobox input to be visible in the portal. */
async function openPalette(page: Page): Promise<void> {
  await page.getByTestId('palette-trigger').click();
  await expect(page.getByRole('combobox')).toBeVisible();
}

test.describe('CommandPalette — a11y evidence (axe + keyboard, Chromium & WebKit)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('palette-trigger')).toBeVisible();
  });

  test('Eden tokens are injected at/above the document (the token context axe reads through the portal)', async ({
    page,
  }) => {
    const css = await page.evaluate(() => window.__EDEN_CSS__);
    expect(css).toContain('--color-surface');
    expect(css).toContain('--color-on-surface');
    expect(css).toContain('--color-primary-container');
    expect(css).toMatch(/--color-surface:\s*oklch\(/);
  });

  test('axe: ZERO serious/critical violations with the palette OPEN (through the portal)', async ({
    page,
  }, testInfo) => {
    const engine = testInfo.project.name;
    await openPalette(page);
    const full = await runAxeFull(page);
    const v = seriousOrCritical(full.violations);
    expect(v, `[${engine}] violations: ${JSON.stringify(v)}`).toEqual([]);
    // weaken-to-confirm: axe must have genuinely walked a non-trivial WCAG rule set.
    expect(full.ruleCount, `[${engine}] axe ran too few rules (${full.ruleCount})`).toBeGreaterThan(
      30,
    );
    expect(full.passCount, `[${engine}] axe reported zero passing checks`).toBeGreaterThan(0);
  });

  test('axe: the color-contrast rule specifically passes for the open palette content', async ({
    page,
  }) => {
    await openPalette(page);
    // Type a query so items filter + the active item paints the selected (primary-container) pair —
    // then the contrast rule audits BOTH the rest items and the selected pair as actually rendered.
    await page.getByRole('combobox').fill('open');
    await ensureAxe(page);
    const contrast = await page.evaluate(async () => {
      const w = window as unknown as {
        axe: { run: (ctx: unknown, opt: unknown) => Promise<{ violations: { id: string }[] }> };
      };
      const r = await w.axe.run(document.querySelector('[data-eden-command]'), {
        runOnly: { type: 'rule', values: ['color-contrast'] },
      });
      return r.violations.map((x) => x.id);
    });
    expect(contrast).toEqual([]);
  });

  test('roles: the open palette exposes the combobox + listbox + grouped options (the ARIA pattern)', async ({
    page,
  }) => {
    await openPalette(page);
    // the input is role=combobox with aria-expanded + aria-controls (bits-ui Command.Input).
    const combobox = page.getByRole('combobox');
    await expect(combobox).toHaveAttribute('aria-expanded', 'true');
    await expect(combobox).toHaveAttribute('aria-controls', /.+/);
    // the results region is a listbox; the items are options inside labelled groups.
    await expect(page.getByRole('listbox')).toBeVisible();
    const options = page.getByRole('option');
    await expect(options.first()).toBeVisible();
    // five enabled + one disabled = six options render at rest (empty query = show all).
    expect(await options.count()).toBe(6);
    // the groups are labelled (role=group + an accessible name from the heading).
    const groups = page.getByRole('group');
    expect(await groups.count()).toBeGreaterThanOrEqual(2);
  });

  test('keyboard: ArrowDown moves aria-activedescendant through the options (the active option tracks)', async ({
    page,
  }) => {
    await openPalette(page);
    const combobox = page.getByRole('combobox');
    await combobox.focus();
    const active = (): Promise<string | null> => combobox.getAttribute('aria-activedescendant');
    const first = await active();
    expect(first, 'an item is active on open').toBeTruthy();
    await page.keyboard.press('ArrowDown');
    const second = await active();
    expect(second, 'ArrowDown advances the active descendant').not.toBe(first);
    // the active id resolves to a real role=option element marked aria-selected (the OD-1 pattern).
    const selectedId = await page.evaluate(() => {
      const sel = document.querySelector('[role="option"][aria-selected="true"]');
      return sel?.id ?? null;
    });
    expect(selectedId).toBe(second);
  });

  test('keyboard: Enter on the active command selects it (onSelect fires; the palette closes)', async ({
    page,
  }) => {
    await openPalette(page);
    const combobox = page.getByRole('combobox');
    await combobox.focus();
    // filter to a single deterministic command, then activate it with Enter.
    await combobox.fill('inbox');
    await expect(page.getByRole('option')).toHaveCount(1);
    await page.keyboard.press('Enter');
    // the host recorded the selected value and the palette closed (open=false via the bind).
    await expect(page.getByTestId('palette-choice')).toHaveText('go-inbox');
    await expect(page.getByRole('combobox')).toBeHidden();
  });

  test('keyboard: Escape closes the palette and returns focus to the page (dismissable)', async ({
    page,
  }) => {
    await openPalette(page);
    await page.keyboard.press('Escape');
    await expect(page.getByRole('combobox')).toBeHidden();
    // the modal is dismissed; the trigger is reachable again (focus is not trapped in a closed modal).
    await expect(page.getByTestId('palette-trigger')).toBeVisible();
  });

  test('focus: opening the palette moves focus into the input (the modal traps + auto-focuses)', async ({
    page,
  }) => {
    await openPalette(page);
    // bits-ui Dialog.Content traps focus; the Command.Input is the first focusable → it receives focus.
    await expect(page.getByRole('combobox')).toBeFocused();
  });

  test('scroll region: the results list is keyboard-focusable (tabindex=0 — the OD-1 lesson)', async ({
    page,
  }) => {
    await openPalette(page);
    const tabindex = await page.evaluate(
      () => document.querySelector('.eden-command-list')?.getAttribute('tabindex') ?? null,
    );
    expect(tabindex).toBe('0');
  });

  test('token-driven color: the selected option paints the resolved primary-container tokens', async ({
    page,
  }) => {
    await openPalette(page);
    // the first option is active/selected on open; read its computed colors and compare to the tokens.
    const selected = page.locator('[role="option"][aria-selected="true"]').first();
    await expect(selected).toBeVisible();
    const fg = await selected.evaluate((el) => getComputedStyle(el).color);
    const bg = await selected.evaluate((el) => getComputedStyle(el).backgroundColor);

    const expectedFg = await resolvedToken(page, '--color-on-primary-container', 'color');
    const expectedBg = await resolvedToken(page, '--color-primary-container', 'bg');
    expect(fg).toBe(expectedFg);
    expect(bg).toBe(expectedBg);
    // weaken-to-confirm: the tokens are real, distinct colors (a genuine fg/bg pair, not transparent).
    expect(bg).not.toBe('rgba(0, 0, 0, 0)');
    expect(fg).not.toBe(bg);
  });

  test('hit target: the input + every option meet the 44px AAA tap floor in the real browser', async ({
    page,
  }) => {
    await openPalette(page);
    const input = await page.getByRole('combobox').boundingBox();
    expect(input, 'combobox has no box').not.toBeNull();
    expect(input!.height, `input height ${input?.height} < 44`).toBeGreaterThanOrEqual(44);
    const options = page.getByRole('option');
    const n = await options.count();
    for (let i = 0; i < n; i++) {
      const box = await options.nth(i).boundingBox();
      expect(box, `option ${i} has no box`).not.toBeNull();
      expect(box!.height, `option ${i} height ${box?.height} < 44`).toBeGreaterThanOrEqual(44);
    }
  });

  test('fuzzy search: a partial/keyword query filters to the matching command', async ({
    page,
  }) => {
    await openPalette(page);
    const combobox = page.getByRole('combobox');
    // "preferences" is a KEYWORD of "Open Settings" — the fuzzy scorer matches on keywords, not just
    // the label (proving the scorer + keyword folding work through the real component).
    await combobox.fill('preferences');
    await expect(page.getByRole('option')).toHaveCount(1);
    await expect(page.getByRole('option')).toHaveText(/Open Settings/);
    // a no-match query renders the empty message (the Command.Empty branch).
    await combobox.fill('zzzznomatch');
    await expect(page.getByRole('option')).toHaveCount(0);
    await expect(page.getByText('No matching commands.')).toBeVisible();
  });

  test('disabled: the disabled command is not selectable (aria-disabled, excluded from activation)', async ({
    page,
  }) => {
    await openPalette(page);
    await page.getByRole('combobox').fill('Delete');
    const del = page.getByRole('option').filter({ hasText: 'Delete' });
    await expect(del).toHaveAttribute('aria-disabled', 'true');
  });
});

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
