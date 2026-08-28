/**
 * EmptyState — property invariants (the fast-check lane, ADR-0024 / rule 21 §a). Over every
 * generatable theme: headline + body clear AA, the headline-over-body size hierarchy holds, the
 * headline is a display voice distinct from the body, no hex leaks.
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
import { deriveEmptyStateTokens, emptyStateStyleVars } from './tokens.js';

const optionsArb: fc.Arbitrary<GenerateOptions> = fc.record({
  mode: fc.constantFrom('light', 'dark'),
  density: fc.constantFrom('spacious', 'comfortable', 'compact', 'condensed'),
  level: fc.constantFrom('AA', 'AAA'),
});

describe('EmptyState derivation — invariants over every generatable theme', () => {
  test.prop([optionsArb])('headline + body ALWAYS clear AA over the surface', (options) => {
    const t = deriveEmptyStateTokens(generateTheme(C21_SEED, options));
    const c = (fg: typeof t.headlineOklch): number =>
      wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(t.surfaceOklch)));
    expect(c(t.headlineOklch)).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
    expect(c(t.bodyOklch)).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
  });

  test.prop([optionsArb])(
    'the headline is ALWAYS larger than the body, in a distinct display voice; no hex',
    (options) => {
      const theme = generateTheme(C21_SEED, options);
      const t = deriveEmptyStateTokens(theme);
      expect(t.headlineFontSizePx).toBeGreaterThan(t.bodyFontSizePx);
      const displayFamilies = new Set(
        theme.typography.filter((r) => r.name.startsWith('display')).map((r) => r.fontFamily),
      );
      expect(displayFamilies.has(t.headlineFontFamily)).toBe(true);
      expect(emptyStateStyleVars(t)).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    },
  );
});
