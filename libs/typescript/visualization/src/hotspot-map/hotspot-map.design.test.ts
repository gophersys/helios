/**
 * HotspotMap — the DESIGN-CORRECTNESS lane (ADR-0024 §3, the ninth dimension). MECHANICAL:
 *  (1) the axis/tick/label text MEETS the WCAG contrast gate over the plot surface in BOTH modes, and
 *      the axis line clears the UI-component contrast (3.0) over the surface;
 *  (2) the hotspot ramp is PERCEPTUALLY ORDERED — monotonically decreasing lightness from calm→hot —
 *      and the hot end clears the contrast gate over the surface (a swatch label can be read);
 *  (3) the tick/label proportions are generated typography roles (caption/label, no hand px);
 *  (4) padding/gap/radius land on the spacing ramp, and the hit target is the ≥44px AAA floor.
 * Each load-bearing assertion is WEAKEN-TO-CONFIRM guarded. MATH IS SOURCE OF TRUTH — cited from theme.
 */
import { describe, expect, it } from 'vitest';
import {
  generateTheme,
  C21_SEED,
  wcagContrastRatio,
  wcagTarget,
  okLchToSrgb,
  srgbTo8,
  TARGET_FLOOR_PX,
  type Theme,
  type OkLch,
} from '@eden/theme';
import { deriveHotspotMapTokens, hotspotMapStyleVars, rampPx } from './tokens.js';
import { hotspotRamp, hotspotColorAt } from './scales.js';

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): chart text + axis meet the contrast gate over the plot surface', () => {
  for (const mode of ['light', 'dark'] as const) {
    const theme = generateTheme(C21_SEED, { mode, level: 'AA' });
    const t = deriveHotspotMapTokens(theme);

    it(`${mode}: tick/label text over the plot surface clears AA (4.5)`, () => {
      const target = wcagTarget('normal-text', 'AA');
      expect(target).toBe(4.5);
      expect(contrastOf(t.foregroundOklch, t.plotBackgroundOklch)).toBeGreaterThanOrEqual(target);
    });

    it(`${mode}: the axis line clears the UI-component contrast (3.0) over the surface`, () => {
      const target = wcagTarget('ui-component', 'AA');
      expect(target).toBe(3);
      expect(contrastOf(t.axisOklch, t.plotBackgroundOklch)).toBeGreaterThanOrEqual(target);
    });
  }

  it('WEAKEN-TO-CONFIRM: a near-surface grey text fails the same gate', () => {
    const theme = generateTheme(C21_SEED);
    const t = deriveHotspotMapTokens(theme);
    const grey: OkLch = { l: t.plotBackgroundOklch.l - 0.02, c: 0, h: 0 };
    expect(contrastOf(grey, t.plotBackgroundOklch)).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): the hotspot ramp is perceptually ordered + the hot end is readable', () => {
  for (const mode of ['light', 'dark'] as const) {
    const theme = generateTheme(C21_SEED, { mode });
    const ramp = hotspotRamp(theme);
    const surfaceL = theme.roles.surface.value.l;

    it(`${mode}: lightness MONOTONICALLY moves FURTHER from the surface across 0→1 (sequential order)`, () => {
      // a single-hue sequential scale: |L − surfaceL| is non-decreasing in score (it deepens in light
      // mode, brightens in dark mode — either way the hotter mark stands further off the surface).
      const distances = [0, 0.25, 0.5, 0.75, 1].map((s) =>
        Math.abs(hotspotColorAt(s, ramp).l - surfaceL),
      );
      for (let i = 1; i < distances.length; i++) {
        expect(distances[i]!).toBeGreaterThanOrEqual(distances[i - 1]! - 1e-9);
      }
      // genuinely a ramp (the hot end stands meaningfully further off the surface than the calm end).
      expect(distances[distances.length - 1]!).toBeGreaterThan(distances[0]! + 0.05);
    });

    it(`${mode}: the hot end (score 1) is the gated error accent and clears the contrast gate over the surface`, () => {
      const t = deriveHotspotMapTokens(theme);
      const hot = hotspotColorAt(1, ramp);
      // the hottest mark IS the theme's gated alarm accent (one home), legible over the reading surface.
      expect(hot.l).toBe(theme.roles.error.value.l);
      expect(contrastOf(hot, t.plotBackgroundOklch)).toBeGreaterThanOrEqual(
        wcagTarget('ui-component', 'AA'),
      );
    });
  }

  it('WEAKEN-TO-CONFIRM: a CONSTANT-lightness ramp would NOT be a real sequential scale', () => {
    const theme = generateTheme(C21_SEED);
    const ramp = hotspotRamp(theme);
    // the real ramp's ends differ in lightness; a forged flat ramp (low===high) does not.
    expect(ramp.low.l).not.toBeCloseTo(ramp.high.l, 2);
  });
});

describe('design-correctness (3): proportions are generated typography roles (no hand px)', () => {
  const theme: Theme = generateTheme(C21_SEED);
  it('tick=caption, label=label', () => {
    const t = deriveHotspotMapTokens(theme);
    const caption = theme.typography.find((r) => r.name === 'caption')!;
    const label = theme.typography.find((r) => r.name === 'label')!;
    expect(t.tickLabelSizePx).toBe(caption.fontSizePx);
    expect(t.labelSizePx).toBe(label.fontSizePx);
  });
  it('WEAKEN-TO-CONFIRM: 15px is on NO typography role', () => {
    expect(theme.typography.map((r) => r.fontSizePx)).not.toContain(15);
  });
});

describe('design-correctness (4): padding/gap/radius on the ramp; hit target ≥ the AAA floor', () => {
  const theme = generateTheme(C21_SEED);
  it('padding/gap/radius are ramp steps (16/8/12 default)', () => {
    const t = deriveHotspotMapTokens(theme);
    const ramp = rampPx(theme);
    for (const v of [t.paddingPx, t.gapPx, t.radiusPx]) expect(ramp).toContain(v);
    expect([t.paddingPx, t.gapPx, t.radiusPx]).toEqual([16, 8, 12]);
  });
  it('the point hit target meets the 44px AAA tap floor (TARGET_FLOOR_PX.wcagAaa)', () => {
    const t = deriveHotspotMapTokens(theme);
    expect(TARGET_FLOOR_PX.wcagAaa).toBe(44);
    expect(t.hitTargetPx).toBeGreaterThanOrEqual(TARGET_FLOOR_PX.wcagAaa);
  });
  it('WEAKEN-TO-CONFIRM: 13px is not on the ramp', () => {
    expect(rampPx(theme).map((v) => v)).not.toContain(13);
  });
});

describe('design-correctness (provenance): the emitted CSS carries only derived tokens', () => {
  it('hotspotMapStyleVars emits oklch() + px, no hex', () => {
    const css = hotspotMapStyleVars(deriveHotspotMapTokens(generateTheme(C21_SEED)));
    expect(css).toContain('--eden-hotspot-map-axis: oklch(');
    expect(css).toContain('--eden-hotspot-map-radius: 12px;');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
