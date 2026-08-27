/**
 * StatRow — property invariants (the fast-check lane, ADR-0024 / rule 21 §a). Over every generatable
 * theme: both value and label clear AA, the value > label size hierarchy holds, no hex leaks.
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
import { deriveStatRowTokens, statRowStyleVars } from './tokens.js';

const optionsArb: fc.Arbitrary<GenerateOptions> = fc.record({
  mode: fc.constantFrom('light', 'dark'),
  density: fc.constantFrom('spacious', 'comfortable', 'compact', 'condensed'),
  level: fc.constantFrom('AA', 'AAA'),
});

describe('StatRow derivation — invariants over every generatable theme', () => {
  test.prop([optionsArb])('both value and label ALWAYS clear AA over the surface', (options) => {
    const t = deriveStatRowTokens(generateTheme(C21_SEED, options));
    const c = (fg: typeof t.valueOklch): number =>
      wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(t.surfaceOklch)));
    expect(c(t.valueOklch)).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
    expect(c(t.labelOklch)).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
  });

  test.prop([optionsArb])(
    'the value size is ALWAYS larger than the label; gaps on the ramp; no hex',
    (options) => {
      const theme = generateTheme(C21_SEED, options);
      const t = deriveStatRowTokens(theme);
      expect(t.valueFontSizePx).toBeGreaterThan(t.labelFontSizePx);
      expect(theme.spacing.map((s) => s.px)).toContain(t.gapPx);
      expect(statRowStyleVars(t)).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    },
  );
});
