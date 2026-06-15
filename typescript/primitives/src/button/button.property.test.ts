/**
 * Button — property invariants (the fast-check lane, ADR-0024 / rule 21 §a). MATH IS SOURCE OF
 * TRUTH: these invariants must hold for EVERY theme the engine can produce (every mode × density ×
 * level × target-context), not just the C21 default — so the token derivation is correct by
 * construction, never by a lucky fixture.
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
import { deriveButtonTokens, buttonStyleVars, type ButtonVariant } from './tokens.js';

const VARIANTS: readonly ButtonVariant[] = ['primary', 'secondary', 'ghost', 'danger'];

const optionsArb: fc.Arbitrary<GenerateOptions> = fc.record({
  mode: fc.constantFrom('light', 'dark'),
  density: fc.constantFrom('spacious', 'comfortable', 'compact', 'condensed'),
  level: fc.constantFrom('AA', 'AAA'),
  // targetContext defaults to `touch` (the 44px floor); we only vary mode/density/level so the
  // 44px invariant below is the default-context guarantee. (pointer is exercised in the design lane.)
});

const variantArb: fc.Arbitrary<ButtonVariant> = fc.constantFrom(...VARIANTS);

describe('Button derivation — invariants over every generatable theme', () => {
  test.prop([variantArb, optionsArb])(
    'the fg/bg pair ALWAYS clears the WCAG AA UI-text contrast target',
    (variant, options) => {
      const t = deriveButtonTokens(variant, generateTheme(C21_SEED, options));
      const ratio = wcagContrastRatio(
        srgbTo8(okLchToSrgb(t.foregroundOklch)),
        srgbTo8(okLchToSrgb(t.backgroundOklch)),
      );
      expect(ratio).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
    },
  );

  test.prop([variantArb, optionsArb])(
    'the hit target is ALWAYS >= 44px (the AAA touch floor, default context)',
    (variant, options) => {
      const t = deriveButtonTokens(variant, generateTheme(C21_SEED, options));
      expect(t.hitTargetPx).toBeGreaterThanOrEqual(44);
    },
  );

  test.prop([variantArb, optionsArb])(
    'the visual geometry is ALWAYS on the 4px grid (height/inset/gap/inline-padding % 4 === 0)',
    (variant, options) => {
      const t = deriveButtonTokens(variant, generateTheme(C21_SEED, options));
      expect(t.heightPx % 4).toBe(0);
      expect(t.paddingBlockPx % 4).toBe(0);
      expect(t.gapPx % 4).toBe(0);
      expect(t.paddingInlinePx % 4).toBe(0);
    },
  );

  test.prop([variantArb, optionsArb])(
    'the emitted style string NEVER contains a hex literal (provenance — colors are oklch only)',
    (variant, options) => {
      const css = buttonStyleVars(deriveButtonTokens(variant, generateTheme(C21_SEED, options)));
      expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
      expect(css).toContain('oklch(');
    },
  );

  test.prop([variantArb, optionsArb])(
    'derivation is deterministic — same variant+options yields an identical token set',
    (variant, options) => {
      const a = deriveButtonTokens(variant, generateTheme(C21_SEED, options));
      const b = deriveButtonTokens(variant, generateTheme(C21_SEED, options));
      expect(a).toEqual(b);
    },
  );
});
