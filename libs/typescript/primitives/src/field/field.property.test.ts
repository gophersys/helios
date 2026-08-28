/**
 * Field — property invariants (the fast-check lane, ADR-0024 / rule 21 §a). MATH IS SOURCE OF TRUTH:
 * the label and error-message legibility must hold for EVERY theme the engine can produce, not just
 * the C21 default — so the Field's text derivation is correct by construction, never by a fixture.
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
  type OkLch,
} from '@eden/theme';
import { deriveFieldTokens, fieldStyleVars } from './tokens.js';

const optionsArb: fc.Arbitrary<GenerateOptions> = fc.record({
  mode: fc.constantFrom('light', 'dark'),
  density: fc.constantFrom('spacious', 'comfortable', 'compact', 'condensed'),
  level: fc.constantFrom('AA', 'AAA'),
});

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('Field derivation — invariants over every generatable theme', () => {
  test.prop([optionsArb])(
    'the LABEL and the ERROR message ALWAYS clear the WCAG AA UI-text target over the surface',
    (options) => {
      const t = deriveFieldTokens(generateTheme(C21_SEED, options));
      const target = wcagTarget('normal-text', 'AA');
      expect(contrastOf(t.labelOklch, t.surfaceOklch)).toBeGreaterThanOrEqual(target);
      expect(contrastOf(t.errorOklch, t.surfaceOklch)).toBeGreaterThanOrEqual(target);
    },
  );

  test.prop([optionsArb])('the vertical-rhythm gap is ALWAYS on the 4px grid', (options) => {
    expect(deriveFieldTokens(generateTheme(C21_SEED, options)).gapPx % 4).toBe(0);
  });

  test.prop([optionsArb])(
    'the label line height is ALWAYS a whole positive px (a derived, rounded value)',
    (options) => {
      const t = deriveFieldTokens(generateTheme(C21_SEED, options));
      expect(Number.isInteger(t.labelLineHeightPx)).toBe(true);
      expect(t.labelLineHeightPx).toBeGreaterThan(0);
    },
  );

  test.prop([optionsArb])(
    'the emitted style string NEVER contains a hex literal (provenance — colors are oklch only)',
    (options) => {
      const css = fieldStyleVars(deriveFieldTokens(generateTheme(C21_SEED, options)));
      expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
      expect(css).toContain('oklch(');
    },
  );
});
