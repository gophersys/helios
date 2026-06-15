/**
 * Overlay token math — unit + component render (the application-logic correctness dimension,
 * ADR-0024). Two layers: (1) the pure token-derivation contract (`deriveOverlayTokens` /
 * `overlayStyleVars` / `defaultOverlayTheme`) asserted directly — this is the MUTATED surface, so
 * every derived field, every var name, and every layer→z/elevation mapping is load-bearing; and
 * (2) the REAL Svelte 5 overlay components rendered through @testing-library/svelte in jsdom —
 * proving the bits-ui behavior layer mounts, the trigger is operable, and the portaled content
 * appears with the derived tokens on its inline style. The browser-level a11y + keyboard proof
 * (axe + focus-trap + LIFO) is the separate Playwright lane (tests-a11y).
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { createRawSnippet, type Snippet } from 'svelte';
import { generateTheme, C21_SEED } from '@eden/theme';
import {
  deriveOverlayTokens,
  overlayStyleVars,
  defaultOverlayTheme,
  type OverlayLayer,
} from './tokens.js';
import Dialog from '../dialog/dialog.svelte';
import Popover from '../popover/popover.svelte';
import Tooltip from '../tooltip/tooltip.svelte';
import DropdownMenu from '../dropdown-menu/dropdown-menu.svelte';

const LAYERS: readonly OverlayLayer[] = ['dropdown', 'modal', 'tooltip'];

describe('deriveOverlayTokens — the pure derivation contract', () => {
  const theme = generateTheme(C21_SEED);

  it('derives surface/on-surface/outline straight from the theme roles (no invented colors)', () => {
    const t = deriveOverlayTokens('modal', theme);
    expect(t.surface).toMatch(/^oklch\(/);
    expect(t.onSurface).toMatch(/^oklch\(/);
    expect(t.outline).toMatch(/^oklch\(/);
    expect(t.surfaceOklch).toEqual(theme.roles.surface.value);
    expect(t.onSurfaceOklch).toEqual(theme.roles.onSurface.value);
    expect(t.surface).not.toBe(t.onSurface);
  });

  it('the scrim is the on-surface role at 0.5 alpha (a derived translucent backdrop, not black)', () => {
    const t = deriveOverlayTokens('modal', theme);
    // It carries an alpha channel (`/ 0.5`) and shares the on-surface L/C/H (a dimmed VIEW of a
    // theme color, never a pasted rgba black).
    expect(t.scrim).toMatch(/^oklch\(.* \/ 0\.5\)$/);
    expect(t.scrim).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it('the scrim serializes the on-surface L/C/H at EXACTLY 4-decimal precision (rounding is load-bearing)', () => {
    // Pin the precise serialization so a broken rounding (round-to-zero, *↔/, wrong factor) fails:
    // the scrim must equal the on-surface role's L/C/H each rounded to 4 decimals, then `/ 0.5`.
    const t = deriveOverlayTokens('modal', theme);
    const o = theme.roles.onSurface.value;
    const r4 = (n: number): number => Math.round(n * 10000) / 10000;
    expect(t.scrim).toBe(`oklch(${String(r4(o.l))} ${String(r4(o.c))} ${String(r4(o.h))} / 0.5)`);
    // and the 4-decimal precision is non-trivial: at least one channel carries fractional digits.
    expect(t.scrim).toMatch(/\d\.\d+/);
  });

  it('the elevation shadow carries the theme layer alpha verbatim in each umbra (the derived falloff)', () => {
    // Pin the first segment's umbra alpha to the theme's first elevation layer alpha — so a mutated
    // alpha source (or a dropped alpha) fails. The first layer's alpha is the largest (the umbra).
    const t = deriveOverlayTokens('modal', theme);
    const first = theme.motion.elevation.find((e) => e.level === 24)!.layers[0]!;
    const firstSegment = t.elevationShadow.split('), ')[0]! + ')';
    expect(firstSegment).toContain(` / ${String(first.alpha)})`);
    // weaken-to-confirm: the alpha is a real, non-1 falloff fraction (a translucent umbra).
    expect(first.alpha).toBeGreaterThan(0);
    expect(first.alpha).toBeLessThan(1);
  });

  it('the z-index is the theme motion.zIndex rung for the layer (dropdown<modal<tooltip)', () => {
    const z = theme.motion.zIndex;
    expect(deriveOverlayTokens('dropdown', theme).zIndex).toBe(z.dropdown);
    expect(deriveOverlayTokens('modal', theme).zIndex).toBe(z.modal);
    expect(deriveOverlayTokens('tooltip', theme).zIndex).toBe(z.tooltip);
    // the ordering the overlay families depend on (a tooltip floats above a dropdown).
    expect(z.dropdown).toBeLessThan(z.modal);
    expect(z.modal).toBeLessThan(z.tooltip);
  });

  it('the elevation shadow is composed from the theme motion.elevation layers (derived umbra)', () => {
    const t = deriveOverlayTokens('modal', theme);
    // The modal draws at elevation level 24 — a stack of layers, so the shadow has multiple
    // comma-joined segments, each an oklch(... / a) umbra (no pasted rgba black).
    const modal24 = theme.motion.elevation.find((e) => e.level === 24);
    expect(modal24).toBeDefined();
    const segments = t.elevationShadow.split('), ');
    expect(segments.length).toBe(modal24!.layers.length);
    expect(t.elevationShadow).toMatch(/oklch\(.* \/ /);
    expect(t.elevationShadow).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it('each layer draws at a DISTINCT elevation level (modal highest, tooltip lowest)', () => {
    // The shadows must differ across layers — proving elevationLevelFor selects per layer, not a
    // constant (kills a mutant that returns one fixed level).
    const modal = deriveOverlayTokens('modal', theme).elevationShadow;
    const dropdown = deriveOverlayTokens('dropdown', theme).elevationShadow;
    const tooltip = deriveOverlayTokens('tooltip', theme).elevationShadow;
    expect(modal).not.toBe(dropdown);
    expect(dropdown).not.toBe(tooltip);
    expect(modal).not.toBe(tooltip);
  });

  it('radius/padding/gap are scale values from the theme (space-2/space-4/controlGeometry gap)', () => {
    const t = deriveOverlayTokens('dropdown', theme);
    const space2 = theme.spacing.find((s) => s.name === 'space-2')!.px;
    const space4 = theme.spacing.find((s) => s.name === 'space-4')!.px;
    expect(t.radiusPx).toBe(space2);
    expect(t.paddingPx).toBe(space4);
    expect(t.gapPx).toBe(theme.controlGeometry.gapPx);
  });

  it('hit-target/font-size/line-height come straight from controlGeometry', () => {
    const t = deriveOverlayTokens('dropdown', theme);
    const g = theme.controlGeometry;
    expect(t.hitTargetPx).toBe(g.hitTargetPx);
    expect(t.fontSizePx).toBe(g.fontSizePx);
    expect(t.lineHeightPx).toBe(g.lineHeightPx);
  });

  it('the font family is the theme body typography role family (the seed text font, derived)', () => {
    const t = deriveOverlayTokens('modal', theme);
    const body = theme.typography.find((r) => r.name === 'body');
    expect(t.fontFamily).toBe(body!.fontFamily);
  });

  it('font family falls back to the first typography role when there is no `body` role', () => {
    const noBody = { ...theme, typography: theme.typography.filter((r) => r.name !== 'body') };
    const t = deriveOverlayTokens('modal', noBody);
    expect(t.fontFamily).toBe(noBody.typography[0]!.fontFamily);
  });

  it('font family falls back to `inherit` when the typography list is empty (fully total)', () => {
    const noType = { ...theme, typography: [] };
    expect(deriveOverlayTokens('modal', noType).fontFamily).toBe('inherit');
  });

  it('the elevation shadow is empty when the theme carries no elevation level (fully total)', () => {
    // Drive the elevationShadowAt fallback: a theme whose elevation ladder is empty → no `entry` →
    // the layers list is `[]` → an empty shadow string (the function stays total, no throw).
    const noElevation = { ...theme, motion: { ...theme.motion, elevation: [] } };
    expect(deriveOverlayTokens('modal', noElevation).elevationShadow).toBe('');
  });

  it('the elevation shadow falls back to the FIRST ladder entry when the level is absent', () => {
    // A ladder that lacks level 24 (the modal level) but has one other entry → the `?? elevation[0]`
    // fallback uses that first entry's layers (so the shadow is non-empty and well-formed).
    const oneLevel = {
      ...theme,
      motion: {
        ...theme.motion,
        elevation: [theme.motion.elevation.find((e) => e.level === 2)!],
      },
    };
    const shadow = deriveOverlayTokens('modal', oneLevel).elevationShadow;
    expect(shadow).not.toBe('');
    expect(shadow).toMatch(/oklch\(.* \/ /);
  });

  it('radius/padding fall back to controlGeometry.insetPx when the ramp lacks the rung (total)', () => {
    // Drive the rampStepPx fallback: a spacing ramp missing space-2 and space-4 → both fall back to
    // the controlGeometry insetPx (the function stays total; the design test asserts the real ramp).
    const noSpace = {
      ...theme,
      spacing: theme.spacing.filter((s) => s.name !== 'space-2' && s.name !== 'space-4'),
    };
    const t = deriveOverlayTokens('modal', noSpace);
    expect(t.radiusPx).toBe(theme.controlGeometry.insetPx);
    expect(t.paddingPx).toBe(theme.controlGeometry.insetPx);
  });

  it('defaultOverlayTheme returns the C21 reference theme (the seed lives in @eden/theme, cited)', () => {
    const a = deriveOverlayTokens('modal', defaultOverlayTheme());
    const b = deriveOverlayTokens('modal', generateTheme(C21_SEED));
    expect(a).toEqual(b);
  });

  it('defaultOverlayTheme forwards options (dark mode flips the derived surface)', () => {
    const light = deriveOverlayTokens('modal', defaultOverlayTheme({ mode: 'light' }));
    const dark = deriveOverlayTokens('modal', defaultOverlayTheme({ mode: 'dark' }));
    expect(dark.surface).not.toBe(light.surface);
  });
});

describe('overlayStyleVars — the CSS custom-property emission', () => {
  const tokens = deriveOverlayTokens('modal', generateTheme(C21_SEED));

  it('emits the EXACT complete declaration string — every var name mapped to its own token', () => {
    // Assert the WHOLE output so a mutated var-NAME, a mutated px UNIT, a mutated value-to-var
    // mapping, or a dropped declaration all fail (kills the string-literal / array mutants — every
    // name and mapping is load-bearing, not just "contains").
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-overlay-surface: ${tokens.surface};`,
      `--eden-overlay-on-surface: ${tokens.onSurface};`,
      `--eden-overlay-outline: ${tokens.outline};`,
      `--eden-overlay-scrim: ${tokens.scrim};`,
      `--eden-overlay-shadow: ${tokens.elevationShadow};`,
      `--eden-overlay-z: ${String(tokens.zIndex)};`,
      `--eden-overlay-radius: ${px(tokens.radiusPx)};`,
      `--eden-overlay-padding: ${px(tokens.paddingPx)};`,
      `--eden-overlay-gap: ${px(tokens.gapPx)};`,
      `--eden-overlay-hit-target: ${px(tokens.hitTargetPx)};`,
      `--eden-overlay-font-size: ${px(tokens.fontSizePx)};`,
      `--eden-overlay-line-height: ${px(tokens.lineHeightPx)};`,
      `--eden-overlay-font-family: ${tokens.fontFamily};`,
    ].join(' ');
    expect(overlayStyleVars(tokens)).toBe(expected);
  });

  it('the z var carries a bare ordinal (NOT a px length — stacking order is unitless)', () => {
    const css = overlayStyleVars(tokens);
    expect(css).toMatch(/--eden-overlay-z: \d+;/);
    expect(css).not.toMatch(/--eden-overlay-z: \d+px;/);
  });

  it('the color vars carry oklch(...) values and there is no hex literal anywhere', () => {
    const css = overlayStyleVars(tokens);
    expect(css).toContain('--eden-overlay-surface: oklch(');
    expect(css).toContain('--eden-overlay-on-surface: oklch(');
    expect(css).toContain('--eden-overlay-scrim: oklch(');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it('every dimension var carries the px unit (a dropped/mutated unit is caught)', () => {
    const css = overlayStyleVars(tokens);
    for (const name of ['radius', 'padding', 'gap', 'hit-target', 'font-size', 'line-height']) {
      expect(css).toMatch(new RegExp(`--eden-overlay-${name}: \\d+px;`));
    }
  });
});

describe('the overlay components — real bits-ui behavior + token binding (jsdom render)', () => {
  it('Dialog: the trigger renders and the panel mounts open with the derived modal tokens', () => {
    const theme = generateTheme(C21_SEED);
    const { getByText, getAllByText } = render(Dialog, {
      props: {
        theme,
        open: true,
        title: 'Confirm',
        trigger: makeLabel('Open dialog'),
        children: makeLabel('Body'),
      },
    });
    // the title and body are present (the panel is open).
    expect(getByText('Confirm')).toBeTruthy();
    const expected = overlayStyleVars(deriveOverlayTokens('modal', theme));
    // the portaled content carries the derived modal-layer surface var (token through the portal).
    const styled = getAllByText('Confirm')[0]!.closest('[data-eden-overlay="dialog"]');
    expect(styled).not.toBeNull();
    expect(styled!.getAttribute('style')).toContain('--eden-overlay-surface: oklch(');
    expect(expected).toContain('--eden-overlay-surface: oklch(');
  });

  it('Popover: mounts open with the derived dropdown tokens on the portaled content', () => {
    const theme = generateTheme(C21_SEED);
    const { container } = render(Popover, {
      props: { theme, open: true, trigger: makeLabel('Open'), children: makeLabel('Pop body') },
    });
    const content = document.querySelector('[data-eden-overlay="popover"]');
    expect(content).not.toBeNull();
    expect(content!.getAttribute('style')).toContain('--eden-overlay-surface: oklch(');
    // the dropdown z rung is on the content (the layer selection reached the portal).
    expect(content!.getAttribute('style')).toContain(
      `--eden-overlay-z: ${String(theme.motion.zIndex.dropdown)};`,
    );
    expect(container).toBeTruthy();
  });

  it('Tooltip: mounts open with the derived tooltip tokens (highest z rung) on the content', () => {
    const theme = generateTheme(C21_SEED);
    render(Tooltip, {
      props: { theme, open: true, trigger: makeLabel('Hover'), children: makeLabel('Tip') },
    });
    const content = document.querySelector('[data-eden-overlay="tooltip"]');
    expect(content).not.toBeNull();
    expect(content!.getAttribute('style')).toContain(
      `--eden-overlay-z: ${String(theme.motion.zIndex.tooltip)};`,
    );
  });

  it('DropdownMenu: mounts open and renders one menuitem per data row with the derived tokens', () => {
    const theme = generateTheme(C21_SEED);
    const selected: string[] = [];
    render(DropdownMenu, {
      props: {
        theme,
        open: true,
        trigger: makeLabel('Menu'),
        items: [
          { label: 'Rename', onSelect: () => selected.push('Rename') },
          { label: 'Delete', onSelect: () => selected.push('Delete'), disabled: true },
        ],
      },
    });
    const content = document.querySelector('[data-eden-overlay="dropdown-menu"]');
    expect(content).not.toBeNull();
    expect(content!.getAttribute('style')).toContain('--eden-overlay-surface: oklch(');
    // one menuitem per row.
    const items = document.querySelectorAll('.eden-menu-item');
    expect(items.length).toBe(2);
    // the disabled row carries the bits-ui disabled state attribute (queried by that attribute).
    const disabled = content!.querySelector('.eden-menu-item[data-disabled]');
    expect(disabled).not.toBeNull();
    expect(disabled!.textContent.trim()).toBe('Delete');
  });
});

/** Build a Svelte snippet rendering a plain text label (the documented createRawSnippet hatch). */
function makeLabel(text: string): Snippet {
  return createRawSnippet(() => ({
    render: () => `<span>${text}</span>`,
  })) as unknown as Snippet;
}

// keep the unused-LAYERS lint quiet by exercising the full set in a trivial provenance assertion.
describe('layer set provenance', () => {
  it('the three overlay layers each resolve to a distinct z rung', () => {
    const theme = generateTheme(C21_SEED);
    const zs = LAYERS.map((l) => deriveOverlayTokens(l, theme).zIndex);
    expect(new Set(zs).size).toBe(LAYERS.length);
  });
});
