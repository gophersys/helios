/**
 * CommandPalette — property invariants (the fast-check lane, ADR-0024 / rule 21 §a). MATH IS SOURCE
 * OF TRUTH: these invariants must hold for EVERY theme the engine can produce (every mode × density ×
 * level × target-context), not just the C21 default — so the token derivation is correct by
 * construction, never by a lucky fixture.
 */
import { describe, expect } from 'vitest';
import { test, fc } from '@fast-check/vitest';
import { generateTheme, C21_SEED, wcagTarget, type GenerateOptions } from '@eden/theme';
import { deriveCommandPaletteTokens, commandPaletteStyleVars, commandContrast } from './tokens.js';

const optionsArb: fc.Arbitrary<GenerateOptions> = fc.record({
  mode: fc.constantFrom('light', 'dark'),
  density: fc.constantFrom('spacious', 'comfortable', 'compact', 'condensed'),
  level: fc.constantFrom('AA', 'AAA'),
  // targetContext defaults to `touch` (the 44px floor); we vary only mode/density/level so the 44px
  // invariant below is the default-context guarantee. (pointer is exercised in the design lane.)
});

describe('CommandPalette derivation — invariants over every generatable theme', () => {
  test.prop([optionsArb])(
    'EVERY painted fg/bg pair ALWAYS clears the WCAG AA UI-text contrast target',
    (options) => {
      const t = deriveCommandPaletteTokens(generateTheme(C21_SEED, options));
      const target = wcagTarget('normal-text', 'AA');
      // input text / input surface
      expect(
        commandContrast(t.inputForegroundOklch, t.inputBackgroundOklch),
      ).toBeGreaterThanOrEqual(target);
      // rest item over the panel (panel bg = the surface role = input bg)
      expect(commandContrast(t.itemForegroundOklch, t.inputBackgroundOklch)).toBeGreaterThanOrEqual(
        target,
      );
      // selected item pair (its own gated fg/bg)
      expect(
        commandContrast(t.itemSelectedForegroundOklch, t.itemSelectedBackgroundOklch),
      ).toBeGreaterThanOrEqual(target);
      // group heading over the panel
      expect(
        commandContrast(t.groupHeadingForegroundOklch, t.inputBackgroundOklch),
      ).toBeGreaterThanOrEqual(target);
    },
  );

  test.prop([optionsArb])(
    'the hit target is ALWAYS >= 44px (the AAA touch floor, default context)',
    (options) => {
      const t = deriveCommandPaletteTokens(generateTheme(C21_SEED, options));
      expect(t.hitTargetPx).toBeGreaterThanOrEqual(44);
    },
  );

  test.prop([optionsArb])(
    'the visual geometry is ALWAYS on the 4px grid (height/inset/gap % 4 === 0)',
    (options) => {
      const t = deriveCommandPaletteTokens(generateTheme(C21_SEED, options));
      expect(t.inputHeightPx % 4).toBe(0);
      expect(t.itemHeightPx % 4).toBe(0);
      expect(t.panelPaddingPx % 4).toBe(0);
      expect(t.itemPaddingInlinePx % 4).toBe(0);
      expect(t.gapPx % 4).toBe(0);
    },
  );

  test.prop([optionsArb])(
    'the panel radius + list max-height are ALWAYS members of the spacing ramp (scale provenance)',
    (options) => {
      const theme = generateTheme(C21_SEED, options);
      const t = deriveCommandPaletteTokens(theme);
      const ramp = theme.spacing.map((s) => s.px);
      expect(ramp).toContain(t.panelRadiusPx);
      expect(ramp).toContain(t.listMaxHeightPx);
    },
  );

  test.prop([optionsArb])(
    'the emitted style string NEVER contains a hex literal (provenance — colors are oklch only)',
    (options) => {
      const css = commandPaletteStyleVars(
        deriveCommandPaletteTokens(generateTheme(C21_SEED, options)),
      );
      expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
      expect(css).toContain('oklch(');
    },
  );

  test.prop([optionsArb])(
    'derivation is deterministic — same options yields an identical token set',
    (options) => {
      const a = deriveCommandPaletteTokens(generateTheme(C21_SEED, options));
      const b = deriveCommandPaletteTokens(generateTheme(C21_SEED, options));
      expect(a).toEqual(b);
    },
  );
});
