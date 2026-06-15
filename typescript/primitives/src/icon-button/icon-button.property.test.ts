/**
 * IconButton — property invariants (the fast-check lane, ADR-0024 / rule 21 §a). MATH IS SOURCE OF
 * TRUTH: these invariants must hold for EVERY theme the engine can produce, not just the C21
 * default — so the square-control derivation is correct by construction, never by a lucky fixture.
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
import { deriveIconButtonTokens, iconButtonStyleVars } from './tokens.js';
import { type ButtonVariant } from '../button/tokens.js';

const VARIANTS: readonly ButtonVariant[] = ['primary', 'secondary', 'ghost', 'danger'];

const optionsArb: fc.Arbitrary<GenerateOptions> = fc.record({
  mode: fc.constantFrom('light', 'dark'),
  density: fc.constantFrom('spacious', 'comfortable', 'compact', 'condensed'),
  level: fc.constantFrom('AA', 'AAA'),
});

const variantArb: fc.Arbitrary<ButtonVariant> = fc.constantFrom(...VARIANTS);

describe('IconButton derivation — invariants over every generatable theme', () => {
  test.prop([variantArb, optionsArb])(
    'the icon/bg pair ALWAYS clears the WCAG AA contrast target',
    (variant, options) => {
      const t = deriveIconButtonTokens(variant, generateTheme(C21_SEED, options));
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
      const t = deriveIconButtonTokens(variant, generateTheme(C21_SEED, options));
      expect(t.hitTargetPx).toBeGreaterThanOrEqual(44);
    },
  );

  test.prop([variantArb, optionsArb])(
    'the square edge is ALWAYS on the 4px grid and the glyph ALWAYS fits inside it',
    (variant, options) => {
      const t = deriveIconButtonTokens(variant, generateTheme(C21_SEED, options));
      expect(t.sizePx % 4).toBe(0);
      expect(t.iconSizePx % 4).toBe(0);
      expect(t.iconSizePx).toBeLessThan(t.sizePx);
    },
  );

  test.prop([variantArb, optionsArb])(
    'the emitted style string NEVER contains a hex literal (provenance — colors are oklch only)',
    (variant, options) => {
      const css = iconButtonStyleVars(
        deriveIconButtonTokens(variant, generateTheme(C21_SEED, options)),
      );
      expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
      expect(css).toContain('oklch(');
    },
  );
});
