/**
 * Card — property invariants (the fast-check lane, ADR-0024 / rule 21 §a). Over every generatable
 * theme: the body pair clears AA, the radius is the surface ramp step, the raised shadow is the
 * raised recipe, no hex leaks.
 */
import { describe, expect } from 'vitest';
import { test, fc } from '@fast-check/vitest';
import {
  generateTheme,
  C21_SEED,
  wcagContrastRatio,
  wcagTarget,
  okLchToSrgb,
  srgbTo8,
  type GenerateOptions,
} from '@eden/theme';
import { deriveCardTokens, cardStyleVars, type CardVariant } from './tokens.js';
import { radiusPx, elevationShadow } from '../surface-tokens/tokens.js';

const VARIANTS: readonly CardVariant[] = ['raised', 'flat'];
const optionsArb: fc.Arbitrary<GenerateOptions> = fc.record({
  mode: fc.constantFrom('light', 'dark'),
  density: fc.constantFrom('spacious', 'comfortable', 'compact', 'condensed'),
  level: fc.constantFrom('AA', 'AAA'),
});
const variantArb: fc.Arbitrary<CardVariant> = fc.constantFrom(...VARIANTS);

describe('Card derivation — invariants over every generatable theme', () => {
  test.prop([variantArb, optionsArb])('the body pair ALWAYS clears AA', (variant, options) => {
    const t = deriveCardTokens(variant, generateTheme(C21_SEED, options));
    const ratio = wcagContrastRatio(
      srgbTo8(okLchToSrgb(t.foregroundOklch)),
      srgbTo8(okLchToSrgb(t.backgroundOklch)),
    );
    expect(ratio).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
  });

  test.prop([variantArb, optionsArb])(
    'the radius is ALWAYS the surface ramp step; the raised shadow the raised recipe; no hex',
    (variant, options) => {
      const theme = generateTheme(C21_SEED, options);
      const t = deriveCardTokens(variant, theme);
      expect(t.radiusPx).toBe(radiusPx(theme, 'surface'));
      expect(t.shadow).toBe(variant === 'raised' ? elevationShadow(theme, 'raised') : 'none');
      expect(cardStyleVars(t)).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    },
  );
});
