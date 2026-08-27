/**
 * EmptyState — the DESIGN-CORRECTNESS lane (ADR-0024 §3). BOTH the headline and the body clear the
 * contrast gate over the surface in BOTH modes; the headline is the SERIF DISPLAY voice (its family
 * equals a display role's family — the seed display font — not the body/text font); the measure is a
 * generated breakpoint. Weaken-to-confirm guarded.
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
import { deriveEmptyStateTokens } from './tokens.js';

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): headline + body clear the contrast gate over the surface', () => {
  for (const mode of ['light', 'dark'] as const) {
    it(`${mode}: the headline (onSurface) and body (outline) both clear AA 4.5`, () => {
      const t = deriveEmptyStateTokens(generateTheme(C21_SEED, { mode, level: 'AA' }));
      expect(contrastOf(t.headlineOklch, t.surfaceOklch)).toBeGreaterThanOrEqual(
        wcagTarget('normal-text', 'AA'),
      );
      expect(contrastOf(t.bodyOklch, t.surfaceOklch)).toBeGreaterThanOrEqual(
        wcagTarget('normal-text', 'AA'),
      );
    });
  }

  it('WEAKEN-TO-CONFIRM: a grey headline near the surface lightness fails the gate', () => {
    const t = deriveEmptyStateTokens(generateTheme(C21_SEED));
    const grey: OkLch = { l: t.surfaceOklch.l, c: 0, h: 0 };
    expect(contrastOf(grey, t.surfaceOklch)).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): the headline is the SERIF display voice (a checked property)', () => {
  const theme = generateTheme(C21_SEED);
  it('the headline family equals a DISPLAY role family, distinct from the body/text family', () => {
    const t = deriveEmptyStateTokens(theme);
    const displayRoles = theme.typography.filter((r) => r.name.startsWith('display'));
    const displayFamilies = new Set(displayRoles.map((r) => r.fontFamily));
    expect(displayFamilies.has(t.headlineFontFamily)).toBe(true);
    // the interface body voice is a DIFFERENT family (P-D4: never mixed within one block)
    expect(t.headlineFontFamily).not.toBe(t.bodyFontFamily);
  });

  it('the headline is larger than the body (an identity-moment hierarchy)', () => {
    const t = deriveEmptyStateTokens(theme);
    expect(t.headlineFontSizePx).toBeGreaterThan(t.bodyFontSizePx);
  });

  it('the reading measure is a generated breakpoint (the anti-void cap, not eyeballed)', () => {
    const t = deriveEmptyStateTokens(theme);
    expect(theme.breakpoints.map((b) => b.minWidthPx)).toContain(t.maxWidthPx);
  });
});
