/**
 * Spinner — the DESIGN-CORRECTNESS lane (ADR-0024 §3). The arc colour is a real theme role over the
 * surface (a perceivable, non-transparent indicator) in BOTH modes; the diameter is the on-grid icon
 * size; the ROTATION is a MOTION token (a ladder rung + a theme easing), never a hand-typed duration.
 * Weaken-to-confirm guarded. MATH IS SOURCE OF TRUTH — the motion cited is @eden/theme's.
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
import { deriveSpinnerTokens, type SpinnerVariant } from './tokens.js';

const VARIANTS: readonly SpinnerVariant[] = ['accent', 'healthy', 'updating', 'degraded', 'down'];

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): the arc is a perceivable indicator over the surface', () => {
  for (const mode of ['light', 'dark'] as const) {
    it(`${mode}: every arc clears the 3:1 non-text/UI-component contrast over the surface`, () => {
      const theme = generateTheme(C21_SEED, { mode });
      for (const variant of VARIANTS) {
        const t = deriveSpinnerTokens(variant, theme);
        // a spinner arc is a non-text graphical indicator → the WCAG 1.4.11 3:1 UI-component floor.
        expect(contrastOf(t.arcOklch, t.surfaceOklch), `${variant}@${mode}`).toBeGreaterThanOrEqual(
          3,
        );
      }
    });
  }

  it('WEAKEN-TO-CONFIRM: an arc equal to the surface has ratio 1 (fails the 3:1 floor)', () => {
    const theme = generateTheme(C21_SEED);
    const t = deriveSpinnerTokens('accent', theme);
    expect(contrastOf(t.surfaceOklch, t.surfaceOklch)).toBeLessThan(3);
  });
});

describe('design-correctness (2): the geometry + motion are generated tokens (not hand values)', () => {
  const theme = generateTheme(C21_SEED);

  it('the diameter is the theme icon size; the stroke is a ramp step', () => {
    const t = deriveSpinnerTokens('accent', theme);
    expect(t.sizePx).toBe(theme.controlGeometry.iconSizePx);
    expect(theme.spacing.map((s) => s.px)).toContain(t.strokePx);
  });

  it('the rotation period is a real motion.durations ladder rung', () => {
    const t = deriveSpinnerTokens('accent', theme);
    expect(Object.values(theme.motion.durations)).toContain(t.durationMs);
  });

  it('WEAKEN-TO-CONFIRM: an off-ladder duration (999ms) is not on the generated duration ladder', () => {
    expect(Object.values(theme.motion.durations)).not.toContain(999);
  });
});
