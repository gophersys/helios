/**
 * StatRow — the DESIGN-CORRECTNESS lane (ADR-0024 §3). BOTH the value and the label clear the
 * contrast gate over the surface in BOTH modes; the value/label sizes are generated scale steps and
 * the value is larger (a real hierarchy). Weaken-to-confirm guarded.
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
import { deriveStatRowTokens } from './tokens.js';

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): both value and label clear the contrast gate over the surface', () => {
  for (const mode of ['light', 'dark'] as const) {
    it(`${mode}: the value (onSurface) and the label (outline) both clear AA 4.5`, () => {
      const t = deriveStatRowTokens(generateTheme(C21_SEED, { mode, level: 'AA' }));
      expect(contrastOf(t.valueOklch, t.surfaceOklch)).toBeGreaterThanOrEqual(
        wcagTarget('normal-text', 'AA'),
      );
      expect(contrastOf(t.labelOklch, t.surfaceOklch)).toBeGreaterThanOrEqual(
        wcagTarget('normal-text', 'AA'),
      );
    });
  }

  it('WEAKEN-TO-CONFIRM: a grey label near the surface lightness fails the gate', () => {
    const t = deriveStatRowTokens(generateTheme(C21_SEED));
    const grey: OkLch = { l: t.surfaceOklch.l, c: 0, h: 0 };
    expect(contrastOf(grey, t.surfaceOklch)).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): value/label sizes are generated scale steps with a real hierarchy', () => {
  const theme = generateTheme(C21_SEED);
  it('the value is the title role, the label the caption role, value > label', () => {
    const t = deriveStatRowTokens(theme);
    expect(t.valueFontSizePx).toBe(theme.typography.find((r) => r.name === 'title')!.fontSizePx);
    expect(t.labelFontSizePx).toBe(theme.typography.find((r) => r.name === 'caption')!.fontSizePx);
    expect(t.valueFontSizePx).toBeGreaterThan(t.labelFontSizePx);
  });

  it('WEAKEN-TO-CONFIRM: the gaps are on the ramp (an off-ramp 13 is not)', () => {
    const t = deriveStatRowTokens(theme);
    const ramp = theme.spacing.map((s) => s.px);
    expect(ramp).toContain(t.gapPx);
    expect(ramp).not.toContain(13);
  });
});
