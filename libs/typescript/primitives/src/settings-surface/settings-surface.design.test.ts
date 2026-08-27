/**
 * SettingsSurface — the DESIGN-CORRECTNESS lane (ADR-0024 §3). The rail's INACTIVE label, its ACTIVE
 * label, and the section TITLE all clear the contrast gate over the sheet surface in BOTH modes; the
 * label voice is the MONO generic (the data voice, P-D4) and the title voice is the SANS interface
 * font (distinct families); the rail width is a real layout measure; the sheet radius is the LARGEST
 * (`sheet`) radius and the item radius the TIGHTEST (`control`); the active tint is a translucent VIEW
 * of the primary role (an alpha channel on the SAME accent OKLCH). Weaken-to-confirm guarded.
 */
import { describe, expect, it } from 'vitest';
import {
  generateTheme,
  C21_SEED,
  wcagContrastRatio,
  wcagTarget,
  okLchToSrgb,
  srgbTo8,
  oklchToCss,
  type OkLch,
} from '@eden/theme';
import { radiusPx } from '../surface-tokens/tokens.js';
import { deriveSettingsSurfaceTokens } from './tokens.js';

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): the rail labels + the section title clear the gate over the surface', () => {
  for (const mode of ['light', 'dark'] as const) {
    it(`${mode}: the inactive label (outline), active label (primary), and title (onSurface) all clear AA 4.5`, () => {
      const t = deriveSettingsSurfaceTokens(generateTheme(C21_SEED, { mode, level: 'AA' }));
      expect(contrastOf(t.labelInactiveOklch, t.surfaceOklch)).toBeGreaterThanOrEqual(
        wcagTarget('normal-text', 'AA'),
      );
      expect(contrastOf(t.labelActiveOklch, t.surfaceOklch)).toBeGreaterThanOrEqual(
        wcagTarget('normal-text', 'AA'),
      );
      expect(contrastOf(t.titleOklch, t.surfaceOklch)).toBeGreaterThanOrEqual(
        wcagTarget('normal-text', 'AA'),
      );
    });
  }

  it('WEAKEN-TO-CONFIRM: a grey label near the surface lightness fails the gate', () => {
    const t = deriveSettingsSurfaceTokens(generateTheme(C21_SEED));
    const grey: OkLch = { l: t.surfaceOklch.l, c: 0, h: 0 };
    expect(contrastOf(grey, t.surfaceOklch)).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): the label is the MONO data voice, the title the SANS interface voice', () => {
  const theme = generateTheme(C21_SEED);

  it('the rail label family is the MONO generic; the section title is a real (non-mono) role family', () => {
    const t = deriveSettingsSurfaceTokens(theme);
    expect(t.labelFontFamily).toBe('monospace');
    // the section title is the `title` role's family — the sans interface voice, NOT the mono generic
    const titleRole = theme.typography.find((r) => r.name === 'title')!;
    expect(t.titleFontFamily).toBe(titleRole.fontFamily);
    expect(t.titleFontFamily).not.toBe(t.labelFontFamily);
  });

  it('the label size is the `label` role step; the title size the `title` role step (on the scale)', () => {
    const t = deriveSettingsSurfaceTokens(theme);
    expect(t.labelFontSizePx).toBe(theme.typography.find((r) => r.name === 'label')!.fontSizePx);
    expect(t.titleFontSizePx).toBe(theme.typography.find((r) => r.name === 'title')!.fontSizePx);
    // WEAKEN-TO-CONFIRM: the section title reads LARGER than the mono rail label (a real hierarchy)
    expect(t.titleFontSizePx).toBeGreaterThan(t.labelFontSizePx);
  });
});

describe('design-correctness (3): the radii + rail width are scale/layout derivations', () => {
  const theme = generateTheme(C21_SEED);

  it('the sheet radius is the LARGEST (`sheet`) radius, the item radius the TIGHTEST (`control`)', () => {
    const t = deriveSettingsSurfaceTokens(theme);
    expect(t.radiusPx).toBe(radiusPx(theme, 'sheet'));
    expect(t.itemRadiusPx).toBe(radiusPx(theme, 'control'));
    // WEAKEN-TO-CONFIRM: the sheet is a strictly larger radius than the rail row (a sheet, not a chip)
    expect(t.radiusPx).toBeGreaterThan(t.itemRadiusPx);
  });

  it('the rail width is a real fraction of a generated breakpoint (a layout measure, not eyeballed)', () => {
    const t = deriveSettingsSurfaceTokens(theme);
    const medium = theme.breakpoints.find((b) => b.name === 'medium')!;
    expect(t.railWidthPx).toBe(Math.round(medium.minWidthPx * 0.27));
    // the rail is a positive measure narrower than the breakpoint (a rail, not a second content column)
    expect(t.railWidthPx).toBeGreaterThan(0);
    expect(t.railWidthPx).toBeLessThan(medium.minWidthPx);
  });

  it('the interior padding, gap, hit-target are ramp/geometry values (44px floor honored)', () => {
    const t = deriveSettingsSurfaceTokens(theme);
    const ramp = theme.spacing.map((s) => s.px);
    expect(ramp).toContain(t.paddingPx);
    expect(ramp).toContain(t.gapPx);
    expect(ramp).toContain(t.itemPaddingPx);
    // the decoupled AAA tap floor for the rail rows never drops below 44
    expect(t.hitTargetPx).toBeGreaterThanOrEqual(44);
  });
});

describe('design-correctness (4): the active tint is a translucent VIEW of the accent (not a new colour)', () => {
  const theme = generateTheme(C21_SEED);

  it('the active tint carries the SAME L/C/H as the accent role, only an alpha < 1', () => {
    const t = deriveSettingsSurfaceTokens(theme);
    const accent = theme.roles.primary.value;
    // the tint string is oklch(L C H / a) — its L/C/H prefix equals the opaque accent serialization.
    const opaque = oklchToCss(accent); // e.g. "oklch(0.5 0.1 150)"
    const lch = opaque
      .replace(/^oklch\(/, '')
      .replace(/\)$/, '')
      .trim();
    expect(t.activeTint.startsWith('oklch(')).toBe(true);
    expect(t.activeTint).toContain(lch);
    expect(t.activeTint).toContain('/ 0.14');
    // WEAKEN-TO-CONFIRM: the tint is NOT the opaque accent (it is a wash, an alpha < 1)
    expect(t.activeTint).not.toBe(opaque);
  });
});
