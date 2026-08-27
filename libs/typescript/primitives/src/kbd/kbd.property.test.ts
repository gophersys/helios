/**
 * Kbd — property invariants (the fast-check lane, ADR-0024 / rule 21 §a). Over every generatable
 * theme: the label pair clears AA, every size is on the ramp, no hex leaks.
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
import { deriveKbdTokens, kbdStyleVars } from './tokens.js';

const optionsArb: fc.Arbitrary<GenerateOptions> = fc.record({
  mode: fc.constantFrom('light', 'dark'),
  density: fc.constantFrom('spacious', 'comfortable', 'compact', 'condensed'),
  level: fc.constantFrom('AA', 'AAA'),
});

describe('Kbd derivation — invariants over every generatable theme', () => {
  test.prop([optionsArb])('the label pair ALWAYS clears AA', (options) => {
    const t = deriveKbdTokens(generateTheme(C21_SEED, options));
    const ratio = wcagContrastRatio(
      srgbTo8(okLchToSrgb(t.foregroundOklch)),
      srgbTo8(okLchToSrgb(t.backgroundOklch)),
    );
    expect(ratio).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
  });

  test.prop([optionsArb])('every size is on the ramp; no hex leaks', (options) => {
    const theme = generateTheme(C21_SEED, options);
    const t = deriveKbdTokens(theme);
    const ramp = theme.spacing.map((s) => s.px);
    expect(ramp).toContain(t.paddingInlinePx);
    expect(ramp).toContain(t.paddingBlockPx);
    expect(ramp).toContain(t.radiusPx);
    expect(kbdStyleVars(t)).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
