/**
 * Tabs — the DESIGN-CORRECTNESS lane (ADR-0024 §3). The active + inactive + panel text all clear the
 * contrast gate over the surface in BOTH modes; each trigger clears the 44px floor; the sizes are
 * generated scale steps. Weaken-to-confirm guarded.
 */
import { describe, expect, it } from 'vitest';
import {
  generateTheme,
  C21_SEED,
  wcagContrastRatio,
  wcagTarget,
  TARGET_FLOOR_PX,
  okLchToSrgb,
  srgbTo8,
  type OkLch,
} from '@eden/theme';
import { deriveTabsTokens } from './tokens.js';

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): the active/inactive/panel text clear the contrast gate', () => {
  for (const mode of ['light', 'dark'] as const) {
    it(`${mode}: active, inactive, and panel foreground all clear AA 4.5 over the surface`, () => {
      const t = deriveTabsTokens(generateTheme(C21_SEED, { mode, level: 'AA' }));
      expect(contrastOf(t.activeOklch, t.surfaceOklch)).toBeGreaterThanOrEqual(
        wcagTarget('normal-text', 'AA'),
      );
      expect(contrastOf(t.inactiveOklch, t.surfaceOklch)).toBeGreaterThanOrEqual(
        wcagTarget('normal-text', 'AA'),
      );
      expect(contrastOf(t.foregroundOklch, t.surfaceOklch)).toBeGreaterThanOrEqual(
        wcagTarget('normal-text', 'AA'),
      );
    });
  }

  it('WEAKEN-TO-CONFIRM: a grey near the surface lightness fails the gate', () => {
    const t = deriveTabsTokens(generateTheme(C21_SEED));
    const grey: OkLch = { l: t.surfaceOklch.l, c: 0, h: 0 };
    expect(contrastOf(grey, t.surfaceOklch)).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): each trigger clears the 44px floor; sizes are scale steps', () => {
  it('every density keeps the trigger hit target >= 44', () => {
    for (const density of ['spacious', 'comfortable', 'compact', 'condensed'] as const) {
      const t = deriveTabsTokens(generateTheme(C21_SEED, { density }));
      expect(t.hitTargetPx, density).toBeGreaterThanOrEqual(TARGET_FLOOR_PX.wcagAaa);
    }
  });

  it('the paddings/gap are on the ramp; the label size is the label role', () => {
    const theme = generateTheme(C21_SEED);
    const t = deriveTabsTokens(theme);
    const ramp = theme.spacing.map((s) => s.px);
    expect(ramp).toContain(t.paddingInlinePx);
    expect(ramp).toContain(t.paddingBlockPx);
    expect(ramp).toContain(t.gapPx);
    expect(t.fontSizePx).toBe(theme.typography.find((r) => r.name === 'label')!.fontSizePx);
  });

  it('WEAKEN-TO-CONFIRM: a pointer-context theme drops the trigger hit target below 44', () => {
    expect(
      deriveTabsTokens(generateTheme(C21_SEED, { targetContext: 'pointer' })).hitTargetPx,
    ).toBeLessThan(44);
  });
});
