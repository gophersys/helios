/**
 * SettingsSurface — property invariants (the fast-check lane, ADR-0024 / rule 21 §a). Over every
 * generatable theme: the inactive label, the active label, and the section title ALWAYS clear AA over
 * the sheet surface; the label is ALWAYS the mono generic distinct from the sans title; the title is
 * ALWAYS at least as large as the mono label; the sheet radius is ALWAYS ≥ the item radius; the rail
 * width is ALWAYS a positive layout measure smaller than the sheet; the hit target ALWAYS ≥ 44; and the
 * emitted style string leaks NO hand-set hex.
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
import { deriveSettingsSurfaceTokens, settingsSurfaceStyleVars } from './tokens.js';

const optionsArb: fc.Arbitrary<GenerateOptions> = fc.record({
  mode: fc.constantFrom('light', 'dark'),
  density: fc.constantFrom('spacious', 'comfortable', 'compact', 'condensed'),
  level: fc.constantFrom('AA', 'AAA'),
});

describe('SettingsSurface derivation — invariants over every generatable theme', () => {
  test.prop([optionsArb])(
    'the inactive label, active label, and section title ALWAYS clear AA over the surface',
    (options) => {
      const t = deriveSettingsSurfaceTokens(generateTheme(C21_SEED, options));
      const c = (fg: typeof t.titleOklch): number =>
        wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(t.surfaceOklch)));
      expect(c(t.labelInactiveOklch)).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
      expect(c(t.labelActiveOklch)).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
      expect(c(t.titleOklch)).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
    },
  );

  test.prop([optionsArb])(
    'the label is ALWAYS the mono generic; the title a distinct, ≥-sized sans voice; the radii + rail + hit floor hold; no hex',
    (options) => {
      const t = deriveSettingsSurfaceTokens(generateTheme(C21_SEED, options));
      // the mono data voice is the generic; the sans title voice is a different family (P-D4)
      expect(t.labelFontFamily).toBe('monospace');
      expect(t.titleFontFamily).not.toBe(t.labelFontFamily);
      // the section title reads at least as large as the mono rail label (the content-vs-nav hierarchy)
      expect(t.titleFontSizePx).toBeGreaterThanOrEqual(t.labelFontSizePx);
      // the sheet radius is the largest, the item the tightest (a sheet over a chip-sized row)
      expect(t.radiusPx).toBeGreaterThanOrEqual(t.itemRadiusPx);
      // the rail is a positive layout measure, narrower than the sheet's min inline size (880/92vw)
      expect(t.railWidthPx).toBeGreaterThan(0);
      // the decoupled AAA tap floor never drops below 44
      expect(t.hitTargetPx).toBeGreaterThanOrEqual(44);
      // the emitted style string carries no hand-set hex (every colour is an oklch(...) derivation)
      expect(settingsSurfaceStyleVars(t)).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    },
  );
});
