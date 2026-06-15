/**
 * PermissionRequest — the DESIGN-CORRECTNESS lane (ADR-0024 §3). MECHANICAL: (1) the card prose pair,
 * the code-block pair, AND the warning heading-over-card pair MEET the contrast gate in both modes —
 * recomputed from the SAME OKLCH the component emits; (2) the heading/body/code proportions are
 * generated typography roles (title/body/caption, no hand px); (3) padding/gap/radius land on the
 * spacing ramp; (4) the interactive hit target meets the 44px AAA floor in every density. Each
 * load-bearing assertion is WEAKEN-TO-CONFIRM guarded. MATH IS SOURCE OF TRUTH — cited from @eden/theme.
 */
import { describe, expect, it } from 'vitest';
import {
  generateTheme,
  C21_SEED,
  wcagContrastRatio,
  wcagTarget,
  okLchToSrgb,
  srgbTo8,
  TARGET_FLOOR_PX,
  type Theme,
  type OkLch,
} from '@eden/theme';
import {
  derivePermissionRequestTokens,
  permissionRequestStyleVars,
  permissionHeadingPairOklch,
} from './tokens.js';

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): card prose, code, and warning heading meet the contrast gate', () => {
  for (const mode of ['light', 'dark'] as const) {
    const theme = generateTheme(C21_SEED, { mode, level: 'AA' });
    const target = wcagTarget('normal-text', 'AA');

    it(`${mode}: card text over card fill clears AA (4.5) — prose AND the code block`, () => {
      const t = derivePermissionRequestTokens(theme);
      expect(target).toBe(4.5);
      expect(contrastOf(t.foregroundOklch, t.backgroundOklch)).toBeGreaterThanOrEqual(target);
    });

    it(`${mode}: the warning heading over the card fill clears AA (4.5)`, () => {
      const pair = permissionHeadingPairOklch(theme);
      const t = derivePermissionRequestTokens(theme);
      // the heading-pair helper and the emitted token agree on the same OKLCH (no drift).
      expect(pair.fg).toEqual(t.headingOklch);
      expect(pair.bg).toEqual(t.backgroundOklch);
      expect(contrastOf(pair.fg, pair.bg)).toBeGreaterThanOrEqual(target);
    });
  }

  it('WEAKEN-TO-CONFIRM: a grey heading fails the same gate', () => {
    const theme = generateTheme(C21_SEED);
    const pair = permissionHeadingPairOklch(theme);
    const grey: OkLch = { l: pair.bg.l, c: 0, h: 0 };
    expect(contrastOf(grey, pair.bg)).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): proportions are generated typography roles (no hand px)', () => {
  const theme: Theme = generateTheme(C21_SEED);
  it('heading=title, body=body, code=caption; the code family is the monospace keyword', () => {
    const t = derivePermissionRequestTokens(theme);
    const title = theme.typography.find((r) => r.name === 'title')!;
    const body = theme.typography.find((r) => r.name === 'body')!;
    const caption = theme.typography.find((r) => r.name === 'caption')!;
    expect(t.headingSizePx).toBe(title.fontSizePx);
    expect(t.bodySizePx).toBe(body.fontSizePx);
    expect(t.codeSizePx).toBe(caption.fontSizePx);
    expect(t.codeFontFamily).toBe('monospace');
    // the heading reads LARGER than the body (a real proportional hierarchy from the type scale).
    expect(t.headingSizePx).toBeGreaterThan(t.bodySizePx);
  });
  it('WEAKEN-TO-CONFIRM: 15px is on NO typography role', () => {
    expect(theme.typography.map((r) => r.fontSizePx)).not.toContain(15);
  });
});

describe('design-correctness (3): padding/gap/action-gap/radius land on the spacing ramp', () => {
  const theme = generateTheme(C21_SEED);
  it('every space is a ramp step (20/16/8/12 default)', () => {
    const t = derivePermissionRequestTokens(theme);
    const ramp = theme.spacing.map((s) => s.px);
    for (const v of [t.paddingPx, t.gapPx, t.actionGapPx, t.radiusPx]) expect(ramp).toContain(v);
    expect([t.paddingPx, t.gapPx, t.actionGapPx, t.radiusPx]).toEqual([20, 16, 8, 12]);
  });
  it('WEAKEN-TO-CONFIRM: 13px is not on the ramp', () => {
    expect(theme.spacing.map((s) => s.px)).not.toContain(13);
  });
});

describe('design-correctness (4): the 44px AAA hit-target floor holds in every density', () => {
  it('every density keeps the action hit target >= 44px', () => {
    for (const density of ['spacious', 'comfortable', 'compact', 'condensed'] as const) {
      const t = derivePermissionRequestTokens(generateTheme(C21_SEED, { density }));
      expect(t.hitTargetPx, density).toBeGreaterThanOrEqual(TARGET_FLOOR_PX.wcagAaa);
      expect(TARGET_FLOOR_PX.wcagAaa).toBe(44); // cited floor value (provenance pin)
    }
  });
  it('WEAKEN-TO-CONFIRM: a pointer-context theme drops the hit target below 44', () => {
    const pointer = generateTheme(C21_SEED, { density: 'condensed', targetContext: 'pointer' });
    expect(derivePermissionRequestTokens(pointer).hitTargetPx).toBeLessThan(44);
  });
});

describe('design-correctness (provenance): the emitted CSS carries only derived tokens', () => {
  it('permissionRequestStyleVars emits oklch() + px + monospace keyword, no hex', () => {
    const css = permissionRequestStyleVars(derivePermissionRequestTokens(generateTheme(C21_SEED)));
    expect(css).toContain('--eden-permission-request-heading: oklch(');
    expect(css).toContain('--eden-permission-request-padding: 20px;');
    expect(css).toContain('--eden-permission-request-hit-target: 44px;');
    expect(css).toContain('--eden-permission-request-code-family: monospace;');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
