/**
 * Badge — the DESIGN-CORRECTNESS lane (ADR-0024 §3, the ninth dimension). The UI-MATH gate:
 *   (1) every status foreground the Badge renders MEETS the contrast gate over the surface —
 *       recomputed from the SAME OKLCH the component emits, in BOTH light and dark;
 *   (2) every size/space comes from the generated scale (the control radius + spacing ramp);
 *   (3) the tint fill is a translucent VIEW of a theme role (no invented colour).
 * Each load-bearing assertion is weaken-to-confirm guarded. MATH IS SOURCE OF TRUTH.
 */
import { describe, expect, it } from 'vitest';
import {
  generateTheme,
  C21_SEED,
  wcagContrastRatio,
  wcagTarget,
  okLchToSrgb,
  srgbTo8,
  type OkLch,
} from '@eden/theme';
import { deriveBadgeTokens, type BadgeVariant } from './tokens.js';

const VARIANTS: readonly BadgeVariant[] = [
  'healthy',
  'updating',
  'degraded',
  'down',
  'unknown',
  'neutral',
  'accent',
];

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): the status text clears the contrast gate over the surface', () => {
  for (const mode of ['light', 'dark'] as const) {
    it(`${mode}: every variant's foreground clears AA 4.5 over the badge surface`, () => {
      const theme = generateTheme(C21_SEED, { mode, level: 'AA' });
      for (const variant of VARIANTS) {
        const t = deriveBadgeTokens(variant, theme);
        const ratio = contrastOf(t.foregroundOklch, t.surfaceOklch);
        expect(ratio, `${variant}@${mode}`).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
      }
      expect(wcagTarget('normal-text', 'AA')).toBe(4.5); // provenance pin
    });
  }

  it('WEAKEN-TO-CONFIRM: a mid-grey foreground near the surface lightness FAILS the same gate', () => {
    const theme = generateTheme(C21_SEED, { mode: 'light' });
    const t = deriveBadgeTokens('healthy', theme);
    const grey: OkLch = { l: t.surfaceOklch.l, c: 0, h: 0 };
    expect(contrastOf(grey, t.surfaceOklch)).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): every size/space comes from the generated scale (no hand px)', () => {
  const theme = generateTheme(C21_SEED);
  const ramp = theme.spacing.map((s) => s.px);

  it('the radius is the control ramp step and the paddings/gap are ramp steps', () => {
    const t = deriveBadgeTokens('neutral', theme);
    expect(t.radiusPx).toBe(theme.spacing.find((s) => s.name === 'space-1')!.px);
    expect(ramp).toContain(t.paddingInlinePx);
    expect(ramp).toContain(t.paddingBlockPx);
    expect(ramp).toContain(t.gapPx);
  });

  it('WEAKEN-TO-CONFIRM: an off-ramp px (13) is not on the generated ramp', () => {
    expect(ramp).not.toContain(13);
  });
});

describe('design-correctness (3): the tint is a translucent view of the role (no invented colour)', () => {
  const theme = generateTheme(C21_SEED);
  it('the fill + edge alphas are 0.12 / 0.35 and carry no hex', () => {
    const t = deriveBadgeTokens('down', theme);
    expect(t.background).toMatch(/\/ 0\.12\)$/);
    expect(t.border).toMatch(/\/ 0\.35\)$/);
    expect(t.background).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
