/**
 * Badge — property invariants (the fast-check lane, ADR-0024 / rule 21 §a). These invariants hold for
 * EVERY theme the engine can produce (mode × density × level), so the derivation is correct by
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
import { deriveBadgeTokens, badgeStyleVars, type BadgeVariant } from './tokens.js';

const VARIANTS: readonly BadgeVariant[] = [
  'healthy',
  'updating',
  'degraded',
  'down',
  'unknown',
  'neutral',
  'accent',
];

const optionsArb: fc.Arbitrary<GenerateOptions> = fc.record({
  mode: fc.constantFrom('light', 'dark'),
  density: fc.constantFrom('spacious', 'comfortable', 'compact', 'condensed'),
  level: fc.constantFrom('AA', 'AAA'),
});
const variantArb: fc.Arbitrary<BadgeVariant> = fc.constantFrom(...VARIANTS);

describe('Badge derivation — invariants over every generatable theme', () => {
  test.prop([variantArb, optionsArb])(
    'the status foreground ALWAYS clears AA over the badge surface',
    (variant, options) => {
      const t = deriveBadgeTokens(variant, generateTheme(C21_SEED, options));
      const ratio = wcagContrastRatio(
        srgbTo8(okLchToSrgb(t.foregroundOklch)),
        srgbTo8(okLchToSrgb(t.surfaceOklch)),
      );
      expect(ratio).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
    },
  );

  test.prop([variantArb, optionsArb])(
    'every size/space is on the generated spacing ramp',
    (variant, options) => {
      const theme = generateTheme(C21_SEED, options);
      const t = deriveBadgeTokens(variant, theme);
      const ramp = theme.spacing.map((s) => s.px);
      expect(ramp).toContain(t.paddingInlinePx);
      expect(ramp).toContain(t.paddingBlockPx);
      expect(ramp).toContain(t.gapPx);
      expect(ramp).toContain(t.radiusPx);
    },
  );

  test.prop([variantArb, optionsArb])(
    'the emitted style NEVER contains a hex literal (provenance)',
    (variant, options) => {
      const css = badgeStyleVars(deriveBadgeTokens(variant, generateTheme(C21_SEED, options)));
      expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
      expect(css).toContain('oklch(');
    },
  );
});
