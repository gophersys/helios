/**
 * ThinkingBlock — the DESIGN-CORRECTNESS lane (ADR-0024 §3). MECHANICAL: (1) the block prose pair
 * (summary AND reasoning, both over the quiet container fill) MEETS the contrast gate in both modes;
 * (2) the summary/prose proportions are generated typography roles (label/body, no hand px); (3)
 * padding/gap/radius land on the spacing ramp; (4) the trigger hit target meets the 44px AAA floor in
 * every density. Each load-bearing assertion is WEAKEN-TO-CONFIRM guarded. MATH IS SOURCE OF TRUTH.
 */
import { describe, expect, it } from 'vitest';
import {
  generateTheme,
  C21_SEED,
  wcagContrastRatio,
  wcagTarget,
  apcaLc,
  okLchToSrgb,
  srgbTo8,
  TARGET_FLOOR_PX,
  type Theme,
  type OkLch,
} from '@eden/theme';
import { deriveThinkingBlockTokens, thinkingBlockStyleVars } from './tokens.js';

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): the block prose pair meets the contrast gate', () => {
  for (const mode of ['light', 'dark'] as const) {
    const theme = generateTheme(C21_SEED, { mode, level: 'AA' });
    it(`${mode}: block text over the quiet fill clears AA (4.5) — summary AND reasoning`, () => {
      const t = deriveThinkingBlockTokens(theme);
      const target = wcagTarget('normal-text', 'AA');
      expect(target).toBe(4.5);
      // summary and prose share the same fg/bg pair, so one assertion covers both.
      expect(contrastOf(t.foregroundOklch, t.backgroundOklch)).toBeGreaterThanOrEqual(target);
    });
  }

  it('APCA agrees the aside pair is a strong perceptual pair (>= 45 Lc advisory)', () => {
    const t = deriveThinkingBlockTokens(generateTheme(C21_SEED));
    const lc = Math.abs(
      apcaLc(srgbTo8(okLchToSrgb(t.foregroundOklch)), srgbTo8(okLchToSrgb(t.backgroundOklch))),
    );
    expect(lc).toBeGreaterThanOrEqual(45);
  });

  it('WEAKEN-TO-CONFIRM: a grey foreground fails the same gate', () => {
    const t = deriveThinkingBlockTokens(generateTheme(C21_SEED));
    const grey: OkLch = { l: t.backgroundOklch.l, c: 0, h: 0 };
    expect(contrastOf(grey, t.backgroundOklch)).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): proportions are generated typography roles (no hand px)', () => {
  const theme: Theme = generateTheme(C21_SEED);
  it('summary=label, prose=body', () => {
    const t = deriveThinkingBlockTokens(theme);
    const label = theme.typography.find((r) => r.name === 'label')!;
    const body = theme.typography.find((r) => r.name === 'body')!;
    expect(t.summarySizePx).toBe(label.fontSizePx);
    expect(t.proseSizePx).toBe(body.fontSizePx);
    // the reasoning prose reads LARGER than the summary label (a real proportional relationship).
    expect(t.proseSizePx).toBeGreaterThan(t.summarySizePx);
  });
  it('WEAKEN-TO-CONFIRM: 15px is on NO typography role', () => {
    expect(theme.typography.map((r) => r.fontSizePx)).not.toContain(15);
  });
});

describe('design-correctness (3): padding/gap/radius land on the spacing ramp', () => {
  const theme = generateTheme(C21_SEED);
  it('every space is a ramp step (16/8/12 default)', () => {
    const t = deriveThinkingBlockTokens(theme);
    const ramp = theme.spacing.map((s) => s.px);
    for (const v of [t.paddingPx, t.gapPx, t.radiusPx]) expect(ramp).toContain(v);
    expect([t.paddingPx, t.gapPx, t.radiusPx]).toEqual([16, 8, 12]);
  });
  it('WEAKEN-TO-CONFIRM: 13px is not on the ramp', () => {
    expect(theme.spacing.map((s) => s.px)).not.toContain(13);
  });
});

describe('design-correctness (4): the 44px AAA hit-target floor holds in every density', () => {
  it('every density keeps the trigger hit target >= 44px', () => {
    for (const density of ['spacious', 'comfortable', 'compact', 'condensed'] as const) {
      const t = deriveThinkingBlockTokens(generateTheme(C21_SEED, { density }));
      expect(t.hitTargetPx, density).toBeGreaterThanOrEqual(TARGET_FLOOR_PX.wcagAaa);
      expect(TARGET_FLOOR_PX.wcagAaa).toBe(44); // cited floor value (provenance pin)
    }
  });
  it('WEAKEN-TO-CONFIRM: a pointer-context theme drops the hit target below 44', () => {
    const pointer = generateTheme(C21_SEED, { density: 'condensed', targetContext: 'pointer' });
    expect(deriveThinkingBlockTokens(pointer).hitTargetPx).toBeLessThan(44);
  });
});

describe('design-correctness (provenance): the emitted CSS carries only derived tokens', () => {
  it('thinkingBlockStyleVars emits oklch() + px, no hex', () => {
    const css = thinkingBlockStyleVars(deriveThinkingBlockTokens(generateTheme(C21_SEED)));
    expect(css).toContain('--eden-thinking-block-fg: oklch(');
    expect(css).toContain('--eden-thinking-block-hit-target: 44px;');
    expect(css).toContain('--eden-thinking-block-padding: 16px;');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
