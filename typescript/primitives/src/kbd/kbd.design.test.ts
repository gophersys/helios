/**
 * Kbd — the DESIGN-CORRECTNESS lane (ADR-0024 §3). The key-cap label MEETS the contrast gate over
 * the cap fill in BOTH modes; every size is a generated scale step. Weaken-to-confirm guarded.
 */
import { describe, expect, it } from 'vitest';
import {
  generateTheme,
  C21_SEED,
  wcagContrastRatio,
  wcagTarget,
  okLchToSrgb,
  srgbTo8,
  type OkLch,
} from '@eden/theme';
import { deriveKbdTokens } from './tokens.js';

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): the key label clears the contrast gate over the cap', () => {
  for (const mode of ['light', 'dark'] as const) {
    it(`${mode}: the label over the cap fill clears AA 4.5`, () => {
      const t = deriveKbdTokens(generateTheme(C21_SEED, { mode, level: 'AA' }));
      expect(contrastOf(t.foregroundOklch, t.backgroundOklch)).toBeGreaterThanOrEqual(
        wcagTarget('normal-text', 'AA'),
      );
    });
  }

  it('WEAKEN-TO-CONFIRM: a grey near the cap lightness FAILS the gate', () => {
    const t = deriveKbdTokens(generateTheme(C21_SEED));
    const grey: OkLch = { l: t.backgroundOklch.l, c: 0, h: 0 };
    expect(contrastOf(grey, t.backgroundOklch)).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): every size is a generated scale step', () => {
  const theme = generateTheme(C21_SEED);
  it('radius = control ramp step; paddings on the ramp; size = caption role', () => {
    const t = deriveKbdTokens(theme);
    const ramp = theme.spacing.map((s) => s.px);
    expect(t.radiusPx).toBe(theme.spacing.find((s) => s.name === 'space-1')!.px);
    expect(ramp).toContain(t.paddingInlinePx);
    expect(ramp).toContain(t.paddingBlockPx);
    expect(t.fontSizePx).toBe(theme.typography.find((r) => r.name === 'caption')!.fontSizePx);
  });

  it('WEAKEN-TO-CONFIRM: an off-ramp px (13) is not on the generated ramp', () => {
    expect(theme.spacing.map((s) => s.px)).not.toContain(13);
  });
});
