/**
 * Card — the DESIGN-CORRECTNESS lane (ADR-0024 §3). The body text clears the contrast gate over the
 * card surface in BOTH modes; the radius is EXACTLY the surface radius and the raised shadow EXACTLY
 * the raised elevation (doc 17 §4). Weaken-to-confirm guarded.
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
import { deriveCardTokens } from './tokens.js';
import { radiusPx, elevationShadow } from '../surface-tokens/tokens.js';

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): the card body text clears the contrast gate', () => {
  for (const mode of ['light', 'dark'] as const) {
    it(`${mode}: the onSurface body over the card surface clears AA 4.5`, () => {
      const t = deriveCardTokens('raised', generateTheme(C21_SEED, { mode, level: 'AA' }));
      expect(contrastOf(t.foregroundOklch, t.backgroundOklch)).toBeGreaterThanOrEqual(
        wcagTarget('normal-text', 'AA'),
      );
    });
  }

  it('WEAKEN-TO-CONFIRM: a grey near the surface lightness fails the gate', () => {
    const t = deriveCardTokens('raised', generateTheme(C21_SEED));
    const grey: OkLch = { l: t.backgroundOklch.l, c: 0, h: 0 };
    expect(contrastOf(grey, t.backgroundOklch)).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): the radius + shadow are EXACTLY the doc 17 §4 selections', () => {
  const theme = generateTheme(C21_SEED);

  it('the radius is EXACTLY the surface radius (a ramp step)', () => {
    const t = deriveCardTokens('raised', theme);
    expect(t.radiusPx).toBe(radiusPx(theme, 'surface'));
    expect(theme.spacing.map((s) => s.px)).toContain(t.radiusPx);
  });

  it('the raised shadow is EXACTLY the raised elevation recipe (a derived umbra, no hex)', () => {
    const t = deriveCardTokens('raised', theme);
    expect(t.shadow).toBe(elevationShadow(theme, 'raised'));
    expect(t.shadow).toMatch(/oklch\(/);
    expect(t.shadow).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it('WEAKEN-TO-CONFIRM: the flat variant paints no shadow (distinct from raised)', () => {
    expect(deriveCardTokens('flat', theme).shadow).toBe('none');
    expect(deriveCardTokens('flat', theme).shadow).not.toBe(
      deriveCardTokens('raised', theme).shadow,
    );
  });
});
