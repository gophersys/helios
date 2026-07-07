/**
 * Spinner — property invariants (the fast-check lane, ADR-0024 / rule 21 §a). Over every generatable
 * theme: the arc clears the 3:1 UI-component floor over the surface, the duration is a real ladder
 * rung, no hex leaks.
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
import { deriveSpinnerTokens, spinnerStyleVars, type SpinnerVariant } from './tokens.js';

const VARIANTS: readonly SpinnerVariant[] = ['accent', 'healthy', 'updating', 'degraded', 'down'];
const optionsArb: fc.Arbitrary<GenerateOptions> = fc.record({
  mode: fc.constantFrom('light', 'dark'),
  density: fc.constantFrom('spacious', 'comfortable', 'compact', 'condensed'),
  level: fc.constantFrom('AA', 'AAA'),
});
const variantArb: fc.Arbitrary<SpinnerVariant> = fc.constantFrom(...VARIANTS);

describe('Spinner derivation — invariants over every generatable theme', () => {
  test.prop([variantArb, optionsArb])(
    'the arc ALWAYS clears 3:1 over the surface',
    (variant, options) => {
      const t = deriveSpinnerTokens(variant, generateTheme(C21_SEED, options));
      const ratio = wcagContrastRatio(
        srgbTo8(okLchToSrgb(t.arcOklch)),
        srgbTo8(okLchToSrgb(t.surfaceOklch)),
      );
      expect(ratio).toBeGreaterThanOrEqual(3);
    },
  );

  test.prop([variantArb, optionsArb])(
    'the rotation period is ALWAYS a real motion-ladder rung; no hex leaks',
    (variant, options) => {
      const theme = generateTheme(C21_SEED, options);
      const t = deriveSpinnerTokens(variant, theme);
      expect(Object.values(theme.motion.durations)).toContain(t.durationMs);
      expect(spinnerStyleVars(t)).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    },
  );
});
