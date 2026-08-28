/**
 * Divider — the DESIGN-CORRECTNESS lane (ADR-0024 §3). The rule is a perceivable separator over the
 * surface (the 3:1 UI-component floor) in BOTH modes; the inset is a generated ramp step (the
 * anti-full-bleed). Weaken-to-confirm guarded.
 */
import { describe, expect, it } from 'vitest';
import {
  generateTheme,
  C21_SEED,
  wcagContrastRatio,
  okLchToSrgb,
  srgbTo8,
  type OkLch,
} from '@eden/theme';
import { deriveDividerTokens } from './tokens.js';

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): the rule is a perceivable separator over the surface', () => {
  for (const mode of ['light', 'dark'] as const) {
    it(`${mode}: the outline rule clears the 3:1 UI-component floor over the surface`, () => {
      const t = deriveDividerTokens(generateTheme(C21_SEED, { mode }));
      expect(contrastOf(t.lineOklch, t.surfaceOklch)).toBeGreaterThanOrEqual(3);
    });
  }

  it('WEAKEN-TO-CONFIRM: a rule equal to the surface fails the 3:1 floor', () => {
    const t = deriveDividerTokens(generateTheme(C21_SEED));
    expect(contrastOf(t.surfaceOklch, t.surfaceOklch)).toBeLessThan(3);
  });
});

describe('design-correctness (2): the inset is a generated ramp step (the anti-full-bleed)', () => {
  const theme = generateTheme(C21_SEED);
  it('the inset is the space-4 ramp step and is on the generated ramp', () => {
    const t = deriveDividerTokens(theme);
    expect(t.insetPx).toBe(theme.spacing.find((s) => s.name === 'space-4')!.px);
    expect(theme.spacing.map((s) => s.px)).toContain(t.insetPx);
  });

  it('WEAKEN-TO-CONFIRM: a full-bleed 0 inset is NOT the derived default (the default is non-zero)', () => {
    expect(deriveDividerTokens(theme).insetPx).toBeGreaterThan(0);
  });
});
