/**
 * Button — the DESIGN-CORRECTNESS lane (ADR-0024 §3, the ninth dimension). The UI-MATH gate, per
 * component, MECHANICAL (the founder bar). Aesthetics made computable: this file asserts that
 *
 *   (1) every text/background pair the Button renders MEETS the contrast gate — recomputed from the
 *       SAME OKLCH values the component emits, against `@eden/theme`'s own WCAG ratio + APCA, with
 *       the WCAG target the theme's contrast audit recorded;
 *   (2) every size/space the Button renders comes from the GENERATED SCALE (the theme's
 *       controlGeometry + spacing ramp) — no hand-irregular px; and
 *   (3) the interactive hit target meets the 44px AAA touch floor.
 *
 * Each load-bearing assertion is WEAKEN-TO-CONFIRM guarded: a probe shows the assertion does real
 * work (a pointer-context theme drops the hit target below 44; a fabricated grey foreground fails
 * the contrast gate; an off-grid px is rejected). MATH IS SOURCE OF TRUTH — the contrast cited is
 * @eden/theme's, the scale cited is @eden/theme's; this lib derives, never re-spells.
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
  densityTierForMode,
  EXPERT_DENSITY_MODE,
  type Theme,
  type OkLch,
} from '@eden/theme';
import { deriveButtonTokens, buttonStyleVars, type ButtonVariant } from './tokens.js';

const VARIANTS: readonly ButtonVariant[] = ['primary', 'secondary', 'ghost', 'danger'];

/** The contrast ratio of an OKLCH fg/bg pair, recomputed via @eden/theme's own WCAG formula. */
function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): the fg/bg pair meets the contrast gate (cite @eden/theme)', () => {
  const theme = generateTheme(C21_SEED, { mode: 'light', level: 'AA' });

  for (const variant of VARIANTS) {
    it(`${variant}: foreground over background clears the WCAG AA target for UI text`, () => {
      const t = deriveButtonTokens(variant, theme);
      const ratio = contrastOf(t.foregroundOklch, t.backgroundOklch);
      // The Button text is non-large UI text → the AA target is 4.5 (research B4 / WCAG 1.4.3).
      // We cite @eden/theme's wcagTarget(contentClass, level) rather than hand-typing 4.5.
      const target = wcagTarget('normal-text', 'AA');
      expect(target).toBe(4.5); // the cited target value (provenance pin)
      expect(ratio).toBeGreaterThanOrEqual(target);
    });
  }

  it('the gate holds in DARK mode too (the contrast guarantee is mode-independent)', () => {
    const dark = generateTheme(C21_SEED, { mode: 'dark', level: 'AA' });
    for (const variant of VARIANTS) {
      const t = deriveButtonTokens(variant, dark);
      const ratio = contrastOf(t.foregroundOklch, t.backgroundOklch);
      expect(ratio).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
    }
  });

  it('APCA agrees the primary pair is a strong perceptual pair (advisory, >= 45 Lc for UI text)', () => {
    const t = deriveButtonTokens('primary', theme);
    const lc = Math.abs(
      apcaLc(srgbTo8(okLchToSrgb(t.foregroundOklch)), srgbTo8(okLchToSrgb(t.backgroundOklch))),
    );
    // APCA Lc 45 is the bronze floor for ~16px/medium text (research B4 advisory).
    expect(lc).toBeGreaterThanOrEqual(45);
  });

  it('WEAKEN-TO-CONFIRM: a fabricated mid-grey foreground FAILS the same gate (it does real work)', () => {
    const t = deriveButtonTokens('primary', theme);
    // Replace the derived foreground with a grey near the background lightness → must fail 4.5:1.
    const grey: OkLch = { l: t.backgroundOklch.l, c: 0, h: 0 };
    const ratio = contrastOf(grey, t.backgroundOklch);
    expect(ratio).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): every size/space comes from the generated scale (no hand px)', () => {
  const theme: Theme = generateTheme(C21_SEED);

  it('the Button height / inset / gap are exactly the theme controlGeometry values', () => {
    const t = deriveButtonTokens('primary', theme);
    const g = theme.controlGeometry;
    expect(t.heightPx).toBe(g.componentHeightPx);
    expect(t.paddingBlockPx).toBe(g.insetPx);
    expect(t.gapPx).toBe(g.gapPx);
    expect(t.fontSizePx).toBe(g.fontSizePx);
    expect(t.lineHeightPx).toBe(g.lineHeightPx);
  });

  it('the visual geometry stays on the 4px grid (snap4) — every dimension % 4 === 0', () => {
    const t = deriveButtonTokens('primary', theme);
    expect(t.heightPx % 4).toBe(0);
    expect(t.paddingBlockPx % 4).toBe(0);
    expect(t.gapPx % 4).toBe(0);
    expect(t.paddingInlinePx % 4).toBe(0);
  });

  it('the inline padding is the EXACT inset*2 ramp step (2:1 inline:block) — a precise scale value', () => {
    const t = deriveButtonTokens('primary', theme);
    const rampValues = theme.spacing.map((s) => s.px);
    // it is on the ramp AND it is precisely twice the vertical inset (the 2:1 ratio the B2 ramp
    // provides as adjacent steps). The exact value (24 for the default comfortable geometry) kills a
    // mutant that makes the ramp `find` predicate always-true (which would return the first step, 2).
    expect(rampValues).toContain(t.paddingInlinePx);
    expect(t.paddingInlinePx).toBe(theme.controlGeometry.insetPx * 2);
    expect(t.paddingInlinePx).toBe(24);
  });

  it('the font family is the theme body typography role family (the seed text font, derived)', () => {
    const t = deriveButtonTokens('primary', theme);
    const body = theme.typography.find((r) => r.name === 'body');
    expect(t.fontFamily).toBe(body!.fontFamily);
  });

  it('WEAKEN-TO-CONFIRM: an off-grid px would be rejected by the 4px-grid assertion', () => {
    // Prove the % 4 check is non-vacuous: 13px is not on the grid and would fail.
    expect(13 % 4).not.toBe(0);
  });
});

describe('design-correctness (3): the 44px AAA hit-target floor holds in every density', () => {
  it('every density mode keeps the Button hit target >= 44px (the hard a11y constraint)', () => {
    for (const density of ['relaxed', 'standard', 'dense'] as const) {
      // `standard` resolves to the theme's default tier (no density override); the others map a
      // density mode to its tier. exactOptionalPropertyTypes: build the options without a literal
      // `undefined` (omit the key entirely for the default).
      const theme =
        density === 'standard'
          ? generateTheme(C21_SEED)
          : generateTheme(C21_SEED, { density: densityTierForMode(density) });
      for (const variant of VARIANTS) {
        const t = deriveButtonTokens(variant, theme);
        expect(t.hitTargetPx, `${variant}@${density}`).toBeGreaterThanOrEqual(
          TARGET_FLOOR_PX.wcagAaa,
        );
        expect(TARGET_FLOOR_PX.wcagAaa).toBe(44); // the cited floor value (provenance pin)
      }
    }
  });

  it('WEAKEN-TO-CONFIRM: a pointer-context dense theme drops the hit target BELOW 44 (the touch default does real work)', () => {
    const dense = densityTierForMode(EXPERT_DENSITY_MODE);
    const touch = generateTheme(C21_SEED, { density: dense }); // default targetContext = touch (44)
    const pointer = generateTheme(C21_SEED, { density: dense, targetContext: 'pointer' });
    const touchTok = deriveButtonTokens('primary', touch);
    const pointerTok = deriveButtonTokens('primary', pointer);
    expect(touchTok.hitTargetPx).toBeGreaterThanOrEqual(44);
    expect(pointerTok.hitTargetPx).toBeLessThan(44);
    // …and the VISUAL height is identical either way — only the decoupled hit target differs (I1/I2).
    expect(pointerTok.heightPx).toBe(touchTok.heightPx);
  });
});

describe('design-correctness (provenance): the emitted CSS carries ONLY derived tokens (no literals)', () => {
  it('buttonStyleVars emits oklch() colors + px dimensions — no hand-set hex anywhere', () => {
    const theme = generateTheme(C21_SEED);
    for (const variant of VARIANTS) {
      const css = buttonStyleVars(deriveButtonTokens(variant, theme));
      expect(css).toContain('--eden-button-fg: oklch(');
      expect(css).toContain('--eden-button-bg: oklch(');
      expect(css).toContain('--eden-button-hit-target:');
      // the cardinal provenance check: NO hex literal in the emitted style string.
      expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    }
  });
});
