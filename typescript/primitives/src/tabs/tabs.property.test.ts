/**
 * Tabs — property invariants (the fast-check lane, ADR-0024 / rule 21 §a). Over every generatable
 * theme: active/inactive/foreground clear AA, the trigger clears 44, no hex leaks.
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
import { deriveTabsTokens, tabsStyleVars } from './tokens.js';

const optionsArb: fc.Arbitrary<GenerateOptions> = fc.record({
  mode: fc.constantFrom('light', 'dark'),
  density: fc.constantFrom('spacious', 'comfortable', 'compact', 'condensed'),
  level: fc.constantFrom('AA', 'AAA'),
});

describe('Tabs derivation — invariants over every generatable theme', () => {
  test.prop([optionsArb])(
    'active/inactive/foreground ALWAYS clear AA over the surface',
    (options) => {
      const t = deriveTabsTokens(generateTheme(C21_SEED, options));
      const c = (fg: typeof t.activeOklch): number =>
        wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(t.surfaceOklch)));
      expect(c(t.activeOklch)).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
      expect(c(t.inactiveOklch)).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
      expect(c(t.foregroundOklch)).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
    },
  );

  test.prop([optionsArb])('the trigger hit target is ALWAYS >= 44; no hex leaks', (options) => {
    const t = deriveTabsTokens(generateTheme(C21_SEED, options));
    expect(t.hitTargetPx).toBeGreaterThanOrEqual(44);
    expect(tabsStyleVars(t)).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
