/**
 * Divider — property invariants (the fast-check lane, ADR-0024 / rule 21 §a). Over every generatable
 * theme: the rule clears 3:1 over the surface, the inset is on the ramp, no hex leaks.
 */
import { describe, expect } from 'vitest';
import { test, fc } from '@fast-check/vitest';
import {
  generateTheme,
  C21_SEED,
  wcagContrastRatio,
  okLchToSrgb,
  srgbTo8,
  type GenerateOptions,
} from '@eden/theme';
import { deriveDividerTokens, dividerStyleVars } from './tokens.js';

const optionsArb: fc.Arbitrary<GenerateOptions> = fc.record({
  mode: fc.constantFrom('light', 'dark'),
  density: fc.constantFrom('spacious', 'comfortable', 'compact', 'condensed'),
  level: fc.constantFrom('AA', 'AAA'),
});

describe('Divider derivation — invariants over every generatable theme', () => {
  test.prop([optionsArb])('the rule ALWAYS clears 3:1 over the surface', (options) => {
    const t = deriveDividerTokens(generateTheme(C21_SEED, options));
    const ratio = wcagContrastRatio(
      srgbTo8(okLchToSrgb(t.lineOklch)),
      srgbTo8(okLchToSrgb(t.surfaceOklch)),
    );
    expect(ratio).toBeGreaterThanOrEqual(3);
  });

  test.prop([optionsArb])('the inset is ALWAYS on the ramp; no hex leaks', (options) => {
    const theme = generateTheme(C21_SEED, options);
    const t = deriveDividerTokens(theme);
    expect(theme.spacing.map((s) => s.px)).toContain(t.insetPx);
    expect(dividerStyleVars(t)).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
