/**
 * Input/Textarea — property invariants (the fast-check lane, ADR-0024 / rule 21 §a). MATH IS SOURCE
 * OF TRUTH: these invariants must hold for EVERY theme the engine can produce, not just the C21
 * default — so the field derivation is correct by construction, never by a lucky fixture.
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
import { deriveInputTokens, inputStyleVars } from './tokens.js';

const optionsArb: fc.Arbitrary<GenerateOptions> = fc.record({
  mode: fc.constantFrom('light', 'dark'),
  density: fc.constantFrom('spacious', 'comfortable', 'compact', 'condensed'),
  level: fc.constantFrom('AA', 'AAA'),
});

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('Input derivation — invariants over every generatable theme', () => {
  test.prop([optionsArb])(
    'the TEXT over the field background ALWAYS clears the WCAG AA UI-text target',
    (options) => {
      const t = deriveInputTokens(generateTheme(C21_SEED, options));
      expect(contrastOf(t.foregroundOklch, t.backgroundOklch)).toBeGreaterThanOrEqual(
        wcagTarget('normal-text', 'AA'),
      );
    },
  );

  test.prop([optionsArb])(
    'the placeholder, the resting border, and the invalid border ALWAYS clear the 3:1 UI-component target',
    (options) => {
      const t = deriveInputTokens(generateTheme(C21_SEED, options));
      const floor = wcagTarget('ui-component', 'AA');
      expect(contrastOf(t.placeholderOklch, t.backgroundOklch)).toBeGreaterThanOrEqual(floor);
      expect(contrastOf(t.borderOklch, t.backgroundOklch)).toBeGreaterThanOrEqual(floor);
      expect(contrastOf(t.borderInvalidOklch, t.backgroundOklch)).toBeGreaterThanOrEqual(floor);
    },
  );

  test.prop([optionsArb])('the hit target is ALWAYS >= 44px (the AAA touch floor)', (options) => {
    expect(deriveInputTokens(generateTheme(C21_SEED, options)).hitTargetPx).toBeGreaterThanOrEqual(
      44,
    );
  });

  test.prop([optionsArb])(
    'the visual geometry is ALWAYS on the 4px grid (height/inset % 4 === 0)',
    (options) => {
      const t = deriveInputTokens(generateTheme(C21_SEED, options));
      expect(t.heightPx % 4).toBe(0);
      expect(t.paddingBlockPx % 4).toBe(0);
      expect(t.paddingInlinePx % 4).toBe(0);
    },
  );

  test.prop([optionsArb])(
    'the emitted style string NEVER contains a hex literal (provenance — colors are oklch only)',
    (options) => {
      const css = inputStyleVars(deriveInputTokens(generateTheme(C21_SEED, options)));
      expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
      expect(css).toContain('oklch(');
    },
  );
});
