/**
 * UsageMeter — the DESIGN-CORRECTNESS lane (ADR-0024 §3). MECHANICAL: (1) the readout pair and every
 * TIER fill-over-card pair MEET the contrast gate in both modes; (2) the readout/caption proportions
 * are generated typography roles (label/caption, no hand px); (3) padding/gap/track/radius land on
 * the spacing ramp. Plus the meter MATH is asserted (fraction clamps, tier boundaries, bar percent).
 * Each load-bearing assertion is WEAKEN-TO-CONFIRM guarded. MATH IS SOURCE OF TRUTH — cited from theme.
 */
import { describe, expect, it } from 'vitest';
import {
  generateTheme,
  C21_SEED,
  wcagContrastRatio,
  wcagTarget,
  okLchToSrgb,
  srgbTo8,
  type Theme,
  type OkLch,
} from '@eden/theme';
import {
  deriveUsageMeterTokens,
  usageMeterStyleVars,
  usageFraction,
  usageTier,
  barWidthPercent,
  type UsageTier,
} from './tokens.js';

const TIERS: readonly UsageTier[] = ['under', 'near', 'over'];

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): the readout + every tier fill meet the contrast gate', () => {
  for (const mode of ['light', 'dark'] as const) {
    const theme = generateTheme(C21_SEED, { mode, level: 'AA' });
    const target = wcagTarget('normal-text', 'AA');

    it(`${mode}: readout text over card fill clears AA (4.5)`, () => {
      const t = deriveUsageMeterTokens('under', theme);
      expect(target).toBe(4.5);
      expect(contrastOf(t.foregroundOklch, t.backgroundOklch)).toBeGreaterThanOrEqual(target);
    });

    for (const tier of TIERS) {
      it(`${mode}: the ${tier} fill/tier-word over the card fill clears AA (4.5)`, () => {
        const t = deriveUsageMeterTokens(tier, theme);
        expect(contrastOf(t.fillOklch, t.backgroundOklch)).toBeGreaterThanOrEqual(target);
      });
    }
  }

  it('the three tiers render DISTINCT fills (info / warning / error)', () => {
    const theme = generateTheme(C21_SEED);
    expect(new Set(TIERS.map((t) => deriveUsageMeterTokens(t, theme).fill)).size).toBe(3);
  });

  it('WEAKEN-TO-CONFIRM: a grey fill fails the same gate', () => {
    const theme = generateTheme(C21_SEED);
    const t = deriveUsageMeterTokens('over', theme);
    const grey: OkLch = { l: t.backgroundOklch.l, c: 0, h: 0 };
    expect(contrastOf(grey, t.backgroundOklch)).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): proportions are generated typography roles (no hand px)', () => {
  const theme: Theme = generateTheme(C21_SEED);
  it('readout=label, caption=caption', () => {
    const t = deriveUsageMeterTokens('under', theme);
    const label = theme.typography.find((r) => r.name === 'label')!;
    const caption = theme.typography.find((r) => r.name === 'caption')!;
    expect(t.readoutSizePx).toBe(label.fontSizePx);
    expect(t.captionSizePx).toBe(caption.fontSizePx);
  });
  it('WEAKEN-TO-CONFIRM: 15px is on NO typography role', () => {
    expect(theme.typography.map((r) => r.fontSizePx)).not.toContain(15);
  });
});

describe('design-correctness (3): padding/gap/track/radius land on the spacing ramp', () => {
  const theme = generateTheme(C21_SEED);
  it('every space is a ramp step (16/8/8/12 default)', () => {
    const t = deriveUsageMeterTokens('under', theme);
    const ramp = theme.spacing.map((s) => s.px);
    for (const v of [t.paddingPx, t.gapPx, t.trackHeightPx, t.radiusPx]) expect(ramp).toContain(v);
    expect([t.paddingPx, t.gapPx, t.trackHeightPx, t.radiusPx]).toEqual([16, 8, 8, 12]);
  });
  it('WEAKEN-TO-CONFIRM: 13px is not on the ramp', () => {
    expect(theme.spacing.map((s) => s.px)).not.toContain(13);
  });
});

describe('the meter MATH (fraction / tier boundaries / bar percent)', () => {
  it('usageFraction clamps to [0,1]; an unknown (<=0) budget is 0 (indeterminate)', () => {
    expect(usageFraction(50, 100)).toBe(0.5);
    expect(usageFraction(150, 100)).toBe(1); // clamped
    expect(usageFraction(-5, 100)).toBe(0); // clamped
    expect(usageFraction(50, 0)).toBe(0); // unknown budget
  });

  it('usageTier classifies at the exact boundaries (0.8 near, 1.0 over)', () => {
    expect(usageTier(0.0)).toBe('under');
    expect(usageTier(0.79)).toBe('under');
    expect(usageTier(0.8)).toBe('near'); // boundary INCLUSIVE
    expect(usageTier(0.99)).toBe('near');
    expect(usageTier(1.0)).toBe('over'); // boundary INCLUSIVE
  });

  it('WEAKEN-TO-CONFIRM: just below each boundary is the lower tier (the >= is load-bearing)', () => {
    expect(usageTier(0.7999)).toBe('under');
    expect(usageTier(0.9999)).toBe('near');
  });

  it('barWidthPercent renders the clamped fraction as a CSS percentage', () => {
    expect(barWidthPercent(0)).toBe('0%');
    expect(barWidthPercent(0.5)).toBe('50%');
    expect(barWidthPercent(1)).toBe('100%');
    expect(barWidthPercent(1.5)).toBe('100%'); // clamped
  });
});

describe('design-correctness (provenance): the emitted CSS carries only derived tokens', () => {
  it('usageMeterStyleVars emits oklch() + px, no hex', () => {
    const css = usageMeterStyleVars(deriveUsageMeterTokens('near', generateTheme(C21_SEED)));
    expect(css).toContain('--eden-usage-meter-fill: oklch(');
    expect(css).toContain('--eden-usage-meter-track-height: 8px;');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
