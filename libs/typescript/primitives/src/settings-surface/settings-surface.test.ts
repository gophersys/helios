/**
 * SettingsSurface — unit + component render (the application-logic correctness dimension, ADR-0024).
 * Two layers: (1) the pure token-derivation contract (`deriveSettingsSurfaceTokens` /
 * `settingsSurfaceStyleVars`) asserted assertion-richly — this is the MUTATED surface, so every derived
 * field, every var name, and every role/ramp mapping is load-bearing (mutation 75 kills a swapped role,
 * a dropped var, a mutated ramp index); and (2) the REAL Svelte 5 SettingsSurface rendered through
 * @testing-library/svelte in jsdom — proving the bits-ui Dialog behavior layer mounts the portaled sheet
 * open, the rail renders one mono tab per section with the ACTIVE one marked, and the per-section content
 * snippet renders the active section. The browser-level a11y + keyboard-trap proof (axe + Escape) is the
 * separate Playwright lane (tests-a11y/specs/settings-surface.spec.ts).
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { createRawSnippet, type Snippet } from 'svelte';
import { generateTheme, C21_SEED, oklchToCss } from '@eden/theme';
import { radiusPx, statusTint } from '../surface-tokens/tokens.js';
import { space, proportion } from '../chat-surface/tokens.js';
import { deriveOverlayTokens } from '../overlay/tokens.js';
import SettingsSurface from './settings-surface.svelte';
import {
  deriveSettingsSurfaceTokens,
  settingsSurfaceStyleVars,
  type SettingsSection,
} from './tokens.js';

const theme = generateTheme(C21_SEED);

describe('deriveSettingsSurfaceTokens — the pure derivation contract', () => {
  it('the sheet surface/on-surface/outline/scrim/elevation/z are the shared overlay MODAL tokens', () => {
    const t = deriveSettingsSurfaceTokens(theme);
    const overlay = deriveOverlayTokens('modal', theme);
    expect(t.surface).toBe(overlay.surface);
    expect(t.onSurface).toBe(overlay.onSurface);
    expect(t.outline).toBe(overlay.outline);
    expect(t.scrim).toBe(overlay.scrim);
    expect(t.elevationShadow).toBe(overlay.elevationShadow);
    expect(t.zIndex).toBe(overlay.zIndex);
    expect(t.hitTargetPx).toBe(overlay.hitTargetPx);
    // the sheet cites the overlay's surface OKLCH (the same background the contrast gate judges over)
    expect(t.surfaceOklch).toEqual(overlay.surfaceOklch);
  });

  it('the rail labels are outline (inactive) → primary (active); the title is onSurface', () => {
    const t = deriveSettingsSurfaceTokens(theme);
    expect(t.labelInactive).toBe(oklchToCss(theme.roles.outline.value));
    expect(t.labelActive).toBe(oklchToCss(theme.roles.primary.value));
    expect(t.title).toBe(oklchToCss(theme.roles.onSurface.value));
    expect(t.labelInactiveOklch).toEqual(theme.roles.outline.value);
    expect(t.labelActiveOklch).toEqual(theme.roles.primary.value);
    expect(t.titleOklch).toEqual(theme.roles.onSurface.value);
    // the inactive rail label is a DIFFERENT colour than the active one (the selection is visible)
    expect(t.labelInactive).not.toBe(t.labelActive);
  });

  it('the active tint is the accent role washed to 0.14 alpha (a translucent VIEW, cites statusTint)', () => {
    const t = deriveSettingsSurfaceTokens(theme);
    expect(t.activeTint).toBe(statusTint('accent', theme, 0.14));
    expect(t.activeTint).toMatch(/^oklch\(.* \/ 0\.14\)$/);
  });

  it('the label is the MONO `label` role; the title the SANS `title` role (distinct voices)', () => {
    const t = deriveSettingsSurfaceTokens(theme);
    const label = proportion(theme, 'label');
    const title = proportion(theme, 'title');
    expect(t.labelFontSizePx).toBe(label.fontSizePx);
    expect(t.labelLineHeightPx).toBe(label.lineHeightPx);
    expect(t.labelFontFamily).toBe('monospace');
    expect(t.titleFontSizePx).toBe(title.fontSizePx);
    expect(t.titleLineHeightPx).toBe(title.lineHeightPx);
    expect(t.titleFontFamily).toBe(title.fontFamily);
    // the two voices are never the same family (P-D4)
    expect(t.labelFontFamily).not.toBe(t.titleFontFamily);
  });

  it('the radii + spacing are the exact scale steps (sheet radius, control item radius, ramp gaps)', () => {
    const t = deriveSettingsSurfaceTokens(theme);
    expect(t.radiusPx).toBe(radiusPx(theme, 'sheet'));
    expect(t.itemRadiusPx).toBe(radiusPx(theme, 'control'));
    expect(t.paddingPx).toBe(space(theme, 6));
    expect(t.gapPx).toBe(space(theme, 3));
    expect(t.itemPaddingPx).toBe(space(theme, 3));
  });

  it('the rail width is 27% of the medium breakpoint, rounded (a real layout measure)', () => {
    const t = deriveSettingsSurfaceTokens(theme);
    const medium = theme.breakpoints.find((b) => b.name === 'medium')!;
    expect(t.railWidthPx).toBe(Math.round(medium.minWidthPx * 0.27));
  });

  it('dark mode flips the derived sheet surface (the theme is the single input)', () => {
    const light = deriveSettingsSurfaceTokens(generateTheme(C21_SEED, { mode: 'light' }));
    const dark = deriveSettingsSurfaceTokens(generateTheme(C21_SEED, { mode: 'dark' }));
    expect(dark.surface).not.toBe(light.surface);
  });
});

describe('settingsSurfaceStyleVars — the CSS custom-property emission', () => {
  const tokens = deriveSettingsSurfaceTokens(theme);

  it('emits the EXACT complete declaration string — every var name mapped to its own token', () => {
    // Assert the WHOLE output so a mutated var-NAME, a mutated px UNIT, a mutated value-to-var mapping,
    // or a dropped declaration all fail (kills the string-literal / array mutants).
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-settings-surface-surface: ${tokens.surface};`,
      `--eden-settings-surface-on-surface: ${tokens.onSurface};`,
      `--eden-settings-surface-outline: ${tokens.outline};`,
      `--eden-settings-surface-scrim: ${tokens.scrim};`,
      `--eden-settings-surface-label-inactive: ${tokens.labelInactive};`,
      `--eden-settings-surface-label-active: ${tokens.labelActive};`,
      `--eden-settings-surface-active-tint: ${tokens.activeTint};`,
      `--eden-settings-surface-title: ${tokens.title};`,
      `--eden-settings-surface-label-font-size: ${px(tokens.labelFontSizePx)};`,
      `--eden-settings-surface-label-line-height: ${px(tokens.labelLineHeightPx)};`,
      `--eden-settings-surface-label-font-family: ${tokens.labelFontFamily};`,
      `--eden-settings-surface-title-font-size: ${px(tokens.titleFontSizePx)};`,
      `--eden-settings-surface-title-line-height: ${px(tokens.titleLineHeightPx)};`,
      `--eden-settings-surface-title-font-family: ${tokens.titleFontFamily};`,
      `--eden-settings-surface-radius: ${px(tokens.radiusPx)};`,
      `--eden-settings-surface-item-radius: ${px(tokens.itemRadiusPx)};`,
      `--eden-settings-surface-rail-width: ${px(tokens.railWidthPx)};`,
      `--eden-settings-surface-padding: ${px(tokens.paddingPx)};`,
      `--eden-settings-surface-gap: ${px(tokens.gapPx)};`,
      `--eden-settings-surface-item-padding: ${px(tokens.itemPaddingPx)};`,
      `--eden-settings-surface-hit-target: ${px(tokens.hitTargetPx)};`,
      `--eden-settings-surface-shadow: ${tokens.elevationShadow};`,
      `--eden-settings-surface-z: ${String(tokens.zIndex)};`,
    ].join(' ');
    expect(settingsSurfaceStyleVars(tokens)).toBe(expected);
  });

  it('the z var carries a bare ordinal (NOT a px length — stacking order is unitless)', () => {
    const css = settingsSurfaceStyleVars(tokens);
    expect(css).toMatch(/--eden-settings-surface-z: \d+;/);
    expect(css).not.toMatch(/--eden-settings-surface-z: \d+px;/);
  });

  it('the colour vars carry oklch(...) values and there is no hex literal anywhere', () => {
    const css = settingsSurfaceStyleVars(tokens);
    expect(css).toContain('--eden-settings-surface-surface: oklch(');
    expect(css).toContain('--eden-settings-surface-label-active: oklch(');
    expect(css).toContain('--eden-settings-surface-active-tint: oklch(');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it('every dimension var carries the px unit (a dropped/mutated unit is caught)', () => {
    const css = settingsSurfaceStyleVars(tokens);
    // a font-size may carry a fractional px (the type ramp is not rounded), so allow decimals; the
    // radii/spacing steps are whole ramp values — the `\d+px` shape catches a dropped/mutated unit.
    for (const name of ['label-font-size', 'title-font-size']) {
      expect(css).toMatch(new RegExp(`--eden-settings-surface-${name}: \\d+(\\.\\d+)?px;`));
    }
    for (const name of [
      'label-line-height',
      'title-line-height',
      'radius',
      'item-radius',
      'rail-width',
      'padding',
      'gap',
      'item-padding',
      'hit-target',
    ]) {
      expect(css).toMatch(new RegExp(`--eden-settings-surface-${name}: \\d+px;`));
    }
  });
});

const SECTIONS: readonly SettingsSection[] = [
  { id: 'profile', label: 'Profile' },
  { id: 'appearance', label: 'Appearance' },
  { id: 'agents', label: 'Agents' },
];

describe('the SettingsSurface component — real bits-ui Dialog behavior + token binding (jsdom render)', () => {
  it('mounts the portaled sheet open with the derived sheet tokens on the portaled content', () => {
    render(SettingsSurface, {
      props: {
        theme,
        open: true,
        sections: SECTIONS,
        active: 'appearance',
        title: 'Settings',
        content: sectionSnippet(),
      },
    });
    const sheet = document.querySelector('[data-eden-settings-surface]');
    expect(sheet).not.toBeNull();
    // the derived sheet surface var reached the portaled content (token through the portal, OD-1 seam).
    expect(sheet!.getAttribute('style')).toContain('--eden-settings-surface-surface: oklch(');
    // the active section id is reflected on the sheet root (a load-bearing app-migration seam).
    expect(sheet!.getAttribute('data-active')).toBe('appearance');
  });

  it('renders one mono rail tab per section, with the ACTIVE one marked (aria-current + data-active)', () => {
    render(SettingsSurface, {
      props: {
        theme,
        open: true,
        sections: SECTIONS,
        active: 'appearance',
        content: sectionSnippet(),
      },
    });
    const items = document.querySelectorAll('.eden-settings-surface-rail-item');
    expect(items.length).toBe(SECTIONS.length);
    // the labels render verbatim (the mono section labels).
    expect(Array.from(items).map((el) => el.textContent.trim())).toEqual([
      'Profile',
      'Appearance',
      'Agents',
    ]);
    // exactly ONE item is active — the one matching `active`, carrying aria-current="page".
    const active = document.querySelectorAll(
      '.eden-settings-surface-rail-item[data-active="true"]',
    );
    expect(active.length).toBe(1);
    expect(active[0]!.textContent.trim()).toBe('Appearance');
    expect(active[0]!.getAttribute('aria-current')).toBe('page');
    // an INACTIVE item never claims aria-current.
    const profile = document.querySelector(
      '.eden-settings-surface-rail-item[data-section="profile"]',
    );
    expect(profile!.getAttribute('aria-current')).toBeNull();
  });

  it('renders the per-section content snippet for the ACTIVE section (the content area is section-scoped)', () => {
    const { getByTestId } = render(SettingsSurface, {
      props: {
        theme,
        open: true,
        sections: SECTIONS,
        active: 'agents',
        content: sectionSnippet(),
      },
    });
    // the content snippet received the active id and rendered THAT section's marker.
    expect(getByTestId('section-body').textContent).toContain('agents');
    // the content region is labelled by the active tab (the aria wiring).
    const region = document.querySelector('.eden-settings-surface-content');
    expect(region!.getAttribute('aria-labelledby')).toMatch(/-tab-agents$/);
  });

  it('does not render the sheet when closed (the portal is empty)', () => {
    render(SettingsSurface, {
      props: {
        theme,
        open: false,
        sections: SECTIONS,
        active: 'profile',
        content: sectionSnippet(),
      },
    });
    expect(document.querySelector('[data-eden-settings-surface]')).toBeNull();
  });
});

/** A content snippet that receives the active section id and renders a marker carrying it (so the test
 *  can assert the ACTIVE section drives the content). Uses the documented createRawSnippet hatch. */
function sectionSnippet(): Snippet<[string]> {
  return createRawSnippet((activeGetter: () => string) => ({
    render: () => `<div data-testid="section-body">section: ${activeGetter()}</div>`,
  })) as unknown as Snippet<[string]>;
}
