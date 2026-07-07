/**
 * WizardShell — property invariants (the fast-check lane, ADR-0024 / rule 21 §a). Over every
 * generatable theme: the title + lead clear AA over the surface, the title-over-lead-over-mono size
 * hierarchy holds, the title is a display voice distinct from the lead, no hex leaks. Over every step
 * position: the progress fraction is monotone, in [0, 1], anchored 0 at the first / 1 at the last, and
 * is EXACTLY `index / (count − 1)`.
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
import { deriveWizardShellTokens, wizardShellStyleVars, wizardProgressFraction } from './tokens.js';

const optionsArb: fc.Arbitrary<GenerateOptions> = fc.record({
  mode: fc.constantFrom('light', 'dark'),
  density: fc.constantFrom('spacious', 'comfortable', 'compact', 'condensed'),
  level: fc.constantFrom('AA', 'AAA'),
});

describe('WizardShell derivation — invariants over every generatable theme', () => {
  test.prop([optionsArb])('title + lead ALWAYS clear AA over the surface', (options) => {
    const t = deriveWizardShellTokens(generateTheme(C21_SEED, options));
    const c = (fg: typeof t.titleOklch): number =>
      wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(t.surfaceOklch)));
    expect(c(t.titleOklch)).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
    expect(c(t.leadOklch)).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
  });

  test.prop([optionsArb])(
    'the title is ALWAYS the largest, a distinct display voice; the hierarchy holds; no hex',
    (options) => {
      const theme = generateTheme(C21_SEED, options);
      const t = deriveWizardShellTokens(theme);
      // the title is the largest, above the lead, above the mono datum (the type hierarchy)
      expect(t.titleFontSizePx).toBeGreaterThan(t.leadFontSizePx);
      expect(t.leadFontSizePx).toBeGreaterThanOrEqual(t.monoFontSizePx);
      // the title is a display voice, distinct from the sans lead + the mono datum
      const displayFamilies = new Set(
        theme.typography.filter((r) => r.name.startsWith('display')).map((r) => r.fontFamily),
      );
      expect(displayFamilies.has(t.titleFontFamily)).toBe(true);
      expect(t.titleFontFamily).not.toBe(t.leadFontFamily);
      expect(t.monoFontFamily).toBe('monospace');
      expect(wizardShellStyleVars(t, 0.5)).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    },
  );
});

describe('wizardProgressFraction — invariants over every step position', () => {
  const stepArb = fc.integer({ min: 2, max: 12 });

  test.prop([stepArb])('the fraction is ALWAYS in [0, 1], anchored 0 first and 1 last', (count) => {
    for (let i = 0; i < count; i++) {
      const f = wizardProgressFraction(i, count);
      expect(f).toBeGreaterThanOrEqual(0);
      expect(f).toBeLessThanOrEqual(1);
    }
    expect(wizardProgressFraction(0, count)).toBe(0);
    expect(wizardProgressFraction(count - 1, count)).toBe(1);
  });

  test.prop([stepArb])('the fraction is STRICTLY monotone increasing across steps', (count) => {
    let prev = -1;
    for (let i = 0; i < count; i++) {
      const f = wizardProgressFraction(i, count);
      expect(f).toBeGreaterThan(prev);
      prev = f;
    }
  });

  test.prop([fc.integer({ min: 0, max: 11 }), stepArb])(
    'the fraction is EXACTLY index / (count − 1) for an in-range index',
    (rawIndex, count) => {
      const i = Math.min(rawIndex, count - 1);
      expect(wizardProgressFraction(i, count)).toBeCloseTo(i / (count - 1), 12);
    },
  );
});
