/**
 * CommandPalette — unit + component render (the application-logic correctness dimension, ADR-0024).
 *
 * Two layers: (1) the pure token-derivation contract (deriveCommandPaletteTokens /
 * commandPaletteStyleVars / defaultCommandPaletteTheme / commandContrast) asserted directly — this
 * is the MUTATED surface (tokens.ts), so the assertions are exact enough to kill the value/mapping
 * mutants; and (2) the REAL Svelte 5 component rendered through @testing-library/svelte in jsdom,
 * proving the bits-ui Dialog+Command behavior layer mounts, the modal opens, the combobox/listbox
 * roles are present, the items render in their groups, and the derived `--eden-command-*` vars reach
 * the portalled content. The browser-level a11y + keyboard proof is the separate Playwright lane.
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { tick } from 'svelte';
import {
  generateTheme,
  C21_SEED,
  oklchToCss,
  wcagContrastRatio,
  okLchToSrgb,
  srgbTo8,
} from '@eden/theme';
import CommandPalette from './command-palette.svelte';
import type { CommandPaletteGroup } from './model.js';
import {
  deriveCommandPaletteTokens,
  commandPaletteStyleVars,
  defaultCommandPaletteTheme,
  commandContrast,
} from './tokens.js';

const GROUPS: readonly CommandPaletteGroup[] = [
  {
    value: 'navigation',
    heading: 'Navigation',
    items: [
      { value: 'go-home', label: 'Go to Home' },
      { value: 'go-settings', label: 'Open Settings', keywords: ['preferences'] },
    ],
  },
  {
    value: 'actions',
    heading: 'Actions',
    items: [
      { value: 'new-file', label: 'Create file', keywords: ['new', 'document'] },
      { value: 'delete', label: 'Delete', disabled: true },
    ],
  },
];

describe('deriveCommandPaletteTokens — the pure derivation contract', () => {
  const theme = generateTheme(C21_SEED);

  it('the input/rest item paint on-surface over surface (the gated reading pair)', () => {
    const t = deriveCommandPaletteTokens(theme);
    expect(t.inputForeground).toMatch(/^oklch\(/);
    expect(t.inputBackground).toMatch(/^oklch\(/);
    expect(t.inputForegroundOklch).toEqual(theme.roles.onSurface.value);
    expect(t.inputBackgroundOklch).toEqual(theme.roles.surface.value);
    // the rest item fg is the same on-surface ink; the panel bg is the surface.
    expect(t.itemForegroundOklch).toEqual(theme.roles.onSurface.value);
    expect(t.panelBackground).toBe(t.inputBackground);
  });

  it('the SELECTED item paints the primary-container gated pair (on-primary-container over container)', () => {
    const t = deriveCommandPaletteTokens(theme);
    expect(t.itemSelectedForegroundOklch).toEqual(theme.roles.onPrimaryContainer.value);
    expect(t.itemSelectedBackgroundOklch).toEqual(theme.roles.primaryContainer.value);
    // the selected pair is a DISTINCT surface from the rest panel (a real highlight, not aliased).
    expect(t.itemSelectedBackground).not.toBe(t.panelBackground);
  });

  it('the group heading is the secondary role; the placeholder + border + separator are the outline role', () => {
    const t = deriveCommandPaletteTokens(theme);
    expect(t.groupHeadingForegroundOklch).toEqual(theme.roles.secondary.value);
    // the outline role is the SINGLE home of the border, the input placeholder, and the separator —
    // all three are the same derived string (one role, three uses).
    expect(t.inputPlaceholder).toBe(t.panelBorder);
    expect(t.separator).toBe(t.panelBorder);
    // and that string is the outline role rendered through @eden/theme's oklchToCss (cited, not
    // re-spelled): the border equals the surface-bordering outline role, distinct from the surface.
    expect(t.panelBorder).toBe(oklchToCss(theme.roles.outline.value));
    expect(t.panelBorder).not.toBe(t.panelBackground);
  });

  it('the contrast helper recomputes @eden/theme WCAG ratio (one concept, one home — never re-spelled)', () => {
    const t = deriveCommandPaletteTokens(theme);
    const viaHelper = commandContrast(t.inputForegroundOklch, t.inputBackgroundOklch);
    const viaTheme = wcagContrastRatio(
      srgbTo8(okLchToSrgb(t.inputForegroundOklch)),
      srgbTo8(okLchToSrgb(t.inputBackgroundOklch)),
    );
    expect(viaHelper).toBe(viaTheme);
  });

  it('defaultCommandPaletteTheme returns the C21 reference theme (the seed lives in @eden/theme, cited)', () => {
    const a = deriveCommandPaletteTokens(defaultCommandPaletteTheme());
    const b = deriveCommandPaletteTokens(generateTheme(C21_SEED));
    expect(a).toEqual(b);
  });

  it('defaultCommandPaletteTheme forwards options (dark mode flips the derived input foreground)', () => {
    const light = deriveCommandPaletteTokens(defaultCommandPaletteTheme({ mode: 'light' }));
    const dark = deriveCommandPaletteTokens(defaultCommandPaletteTheme({ mode: 'dark' }));
    expect(dark.inputForeground).not.toBe(light.inputForeground);
  });
});

describe('deriveCommandPaletteTokens — derivation totality over a host-injected theme', () => {
  const base = generateTheme(C21_SEED);

  it('the heading font size falls back to body when there is no `caption` role', () => {
    const noCaption = { ...base, typography: base.typography.filter((r) => r.name !== 'caption') };
    const body = noCaption.typography.find((r) => r.name === 'body');
    const t = deriveCommandPaletteTokens(noCaption);
    expect(t.headingFontSizePx).toBe(Math.round(body!.fontSizePx));
  });

  it('the heading font size falls back to 12 when the typography list is empty (fully total)', () => {
    const noType = { ...base, typography: [] };
    const t = deriveCommandPaletteTokens(noType);
    expect(t.headingFontSizePx).toBe(12);
  });

  it('the font family falls back to `inherit` when the typography list is empty (fully total)', () => {
    const noType = { ...base, typography: [] };
    expect(deriveCommandPaletteTokens(noType).fontFamily).toBe('inherit');
  });
});

describe('commandPaletteStyleVars — the CSS custom-property emission', () => {
  const tokens = deriveCommandPaletteTokens(generateTheme(C21_SEED));

  it('emits the EXACT complete declaration string — every var name mapped to its own token', () => {
    // Assert the WHOLE output, built from the tokens, so a mutated var-NAME, a mutated px UNIT, a
    // mutated VALUE-to-var mapping, or a dropped declaration all fail (kills the string-literal /
    // array-declaration mutants — every name and mapping is load-bearing, not just "contains").
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-command-overlay: ${tokens.overlay};`,
      `--eden-command-overlay-alpha: ${String(tokens.overlayAlpha)};`,
      `--eden-command-panel-bg: ${tokens.panelBackground};`,
      `--eden-command-panel-border: ${tokens.panelBorder};`,
      `--eden-command-panel-radius: ${px(tokens.panelRadiusPx)};`,
      `--eden-command-panel-padding: ${px(tokens.panelPaddingPx)};`,
      `--eden-command-z-modal: ${String(tokens.zIndexModal)};`,
      `--eden-command-input-fg: ${tokens.inputForeground};`,
      `--eden-command-input-bg: ${tokens.inputBackground};`,
      `--eden-command-input-placeholder: ${tokens.inputPlaceholder};`,
      `--eden-command-item-fg: ${tokens.itemForeground};`,
      `--eden-command-item-selected-fg: ${tokens.itemSelectedForeground};`,
      `--eden-command-item-selected-bg: ${tokens.itemSelectedBackground};`,
      `--eden-command-heading-fg: ${tokens.groupHeadingForeground};`,
      `--eden-command-separator: ${tokens.separator};`,
      `--eden-command-hit-target: ${px(tokens.hitTargetPx)};`,
      `--eden-command-input-height: ${px(tokens.inputHeightPx)};`,
      `--eden-command-item-height: ${px(tokens.itemHeightPx)};`,
      `--eden-command-item-padding-inline: ${px(tokens.itemPaddingInlinePx)};`,
      `--eden-command-gap: ${px(tokens.gapPx)};`,
      `--eden-command-icon-size: ${px(tokens.iconSizePx)};`,
      `--eden-command-font-size: ${px(tokens.fontSizePx)};`,
      `--eden-command-heading-font-size: ${px(tokens.headingFontSizePx)};`,
      `--eden-command-line-height: ${px(tokens.lineHeightPx)};`,
      `--eden-command-list-max-height: ${px(tokens.listMaxHeightPx)};`,
      `--eden-command-font-family: ${tokens.fontFamily};`,
    ].join(' ');
    expect(commandPaletteStyleVars(tokens)).toBe(expected);
  });

  it('every dimension var carries the px unit (a dropped/mutated unit is caught)', () => {
    const css = commandPaletteStyleVars(tokens);
    for (const name of [
      'panel-radius',
      'panel-padding',
      'hit-target',
      'input-height',
      'item-height',
      'item-padding-inline',
      'gap',
      'icon-size',
      'font-size',
      'heading-font-size',
      'line-height',
      'list-max-height',
    ]) {
      expect(css).toMatch(new RegExp(`--eden-command-${name}: \\d+px;`));
    }
  });

  it('the color vars carry oklch(...) values and there is no hex literal anywhere', () => {
    const css = commandPaletteStyleVars(tokens);
    expect(css).toContain('--eden-command-input-fg: oklch(');
    expect(css).toContain('--eden-command-panel-bg: oklch(');
    expect(css).toContain('--eden-command-item-selected-bg: oklch(');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it('the non-px scalar vars (alpha, z-index) are emitted WITHOUT a px unit', () => {
    const css = commandPaletteStyleVars(tokens);
    expect(css).toContain(`--eden-command-overlay-alpha: ${String(tokens.overlayAlpha)};`);
    expect(css).toContain(`--eden-command-z-modal: ${String(tokens.zIndexModal)};`);
    expect(css).not.toMatch(/--eden-command-z-modal: \d+px/);
  });
});

describe('CommandPalette.svelte — the real component (bits-ui Dialog + Command behavior)', () => {
  it('mounts closed: no combobox/listbox in the document until opened', () => {
    const { queryByRole } = render(CommandPalette, { props: { groups: GROUPS } });
    expect(queryByRole('combobox')).toBeNull();
    expect(queryByRole('listbox')).toBeNull();
  });

  it('opens into the portal: the combobox input + the listbox results region render', async () => {
    const { getByRole } = render(CommandPalette, {
      props: { groups: GROUPS, open: true, label: 'Commands' },
    });
    await tick();
    // the input is the ARIA combobox (bits-ui Command.Input); the viewport is the listbox.
    expect(getByRole('combobox')).toBeTruthy();
    expect(getByRole('listbox')).toBeTruthy();
  });

  it('renders every enabled command as a role=option inside its labelled group', async () => {
    const { getAllByRole, getByText } = render(CommandPalette, {
      props: { groups: GROUPS, open: true },
    });
    await tick();
    const options = getAllByRole('option');
    // four items in the model; all render (filtering is empty-query = show-all).
    expect(options.length).toBe(4);
    expect(getByText('Go to Home')).toBeTruthy();
    expect(getByText('Create file')).toBeTruthy();
    // the group headings render as labelled groups.
    expect(getByText('Navigation')).toBeTruthy();
    expect(getByText('Actions')).toBeTruthy();
  });

  it('binds the derived --eden-command-* vars into the portalled content inline style', async () => {
    const theme = generateTheme(C21_SEED);
    const { baseElement } = render(CommandPalette, {
      props: { groups: GROUPS, open: true, theme },
    });
    await tick();
    const content = baseElement.querySelector('[data-eden-command]');
    expect(content).not.toBeNull();
    const tokens = deriveCommandPaletteTokens(theme);
    const style = content!.getAttribute('style') ?? '';
    expect(style).toContain(`--eden-command-input-fg: ${tokens.inputForeground}`);
    expect(style).toContain(`--eden-command-panel-bg: ${tokens.panelBackground}`);
    expect(style).toContain(`--eden-command-z-modal: ${String(tokens.zIndexModal)}`);
  });

  it('the scrollable results region (Command.List) is keyboard-focusable (tabindex=0 — the OD-1 lesson)', async () => {
    const { getByRole } = render(CommandPalette, { props: { groups: GROUPS, open: true } });
    await tick();
    const list = getByRole('listbox');
    // the listbox viewport sits inside the focusable List; assert a tabindex=0 element wraps it.
    const focusable =
      list.closest('[tabindex="0"]') ?? document.querySelector('.eden-command-list[tabindex="0"]');
    expect(focusable).not.toBeNull();
  });

  it('the disabled command renders aria-disabled (non-selectable; bits-ui Command.Item disabled)', async () => {
    const { getByText } = render(CommandPalette, { props: { groups: GROUPS, open: true } });
    await tick();
    const del = getByText('Delete').closest('[role="option"]');
    expect(del).not.toBeNull();
    expect(del!.getAttribute('aria-disabled')).toBe('true');
  });

  it('the contrast of the rendered selected pair clears AA (the math holds for the real component)', () => {
    const theme = generateTheme(C21_SEED);
    const t = deriveCommandPaletteTokens(theme);
    // the component paints data-selected with the selected pair; verify that pair clears AA (the
    // same math the design lane asserts, pinned here against the model the component renders).
    expect(
      commandContrast(t.itemSelectedForegroundOklch, t.itemSelectedBackgroundOklch),
    ).toBeGreaterThanOrEqual(4.5);
  });
});
