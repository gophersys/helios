/**
 * Chip — the DESIGN-CORRECTNESS lane (ADR-0024 §3). The mono data chip's reading pair MEETS the
 * contrast gate in BOTH modes, every size is a generated scale step, the remove control clears the
 * 44px floor. Weaken-to-confirm guarded. MATH IS SOURCE OF TRUTH.
 */
import { describe, expect, it } from 'vitest';
import {
  generateTheme,
  C21_SEED,
  wcagContrastRatio,
  wcagTarget,
  TARGET_FLOOR_PX,
  okLchToSrgb,
  srgbTo8,
  type OkLch,
} from '@eden/theme';
import { deriveChipTokens } from './tokens.js';

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): the data text clears the contrast gate over the chip surface', () => {
  for (const mode of ['light', 'dark'] as const) {
    it(`${mode}: the onSurface data over the surface clears AA 4.5`, () => {
      const t = deriveChipTokens(generateTheme(C21_SEED, { mode, level: 'AA' }));
      expect(contrastOf(t.foregroundOklch, t.backgroundOklch)).toBeGreaterThanOrEqual(
        wcagTarget('normal-text', 'AA'),
      );
    });
  }

  it('WEAKEN-TO-CONFIRM: a grey near the surface lightness FAILS the gate', () => {
    const t = deriveChipTokens(generateTheme(C21_SEED));
    const grey: OkLch = { l: t.backgroundOklch.l, c: 0, h: 0 };
    expect(contrastOf(grey, t.backgroundOklch)).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): every size is a generated scale step', () => {
  const theme = generateTheme(C21_SEED);
  const ramp = theme.spacing.map((s) => s.px);
  it('radius = control ramp step; paddings/gap on the ramp; size = caption role', () => {
    const t = deriveChipTokens(theme);
    expect(t.radiusPx).toBe(theme.spacing.find((s) => s.name === 'space-1')!.px);
    expect(ramp).toContain(t.paddingInlinePx);
    expect(ramp).toContain(t.paddingBlockPx);
    expect(ramp).toContain(t.gapPx);
    expect(t.fontSizePx).toBe(theme.typography.find((r) => r.name === 'caption')!.fontSizePx);
  });
});

describe('design-correctness (3): the remove control meets the 44px AAA floor in every density', () => {
  it('every density keeps the hit target >= 44', () => {
    for (const density of ['spacious', 'comfortable', 'compact', 'condensed'] as const) {
      const t = deriveChipTokens(generateTheme(C21_SEED, { density }));
      expect(t.hitTargetPx, density).toBeGreaterThanOrEqual(TARGET_FLOOR_PX.wcagAaa);
    }
    expect(TARGET_FLOOR_PX.wcagAaa).toBe(44); // provenance pin
  });

  it('WEAKEN-TO-CONFIRM: a pointer-context theme drops the hit target below 44', () => {
    const t = deriveChipTokens(generateTheme(C21_SEED, { targetContext: 'pointer' }));
    expect(t.hitTargetPx).toBeLessThan(44);
  });
});
