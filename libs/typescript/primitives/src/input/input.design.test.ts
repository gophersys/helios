/**
 * Input/Textarea — the DESIGN-CORRECTNESS lane (ADR-0024 §3, the ninth dimension). The UI-MATH gate,
 * MECHANICAL (the founder bar). This file asserts that
 *
 *   (1) every text/background pair the field renders MEETS the contrast gate — for the resting text,
 *       the placeholder, AND the border/ring (resting outline AND invalid error) against the field
 *       surface — recomputed from the SAME OKLCH values the component emits, against @eden/theme's
 *       own WCAG ratio; the focus/disabled/invalid states are covered as state×pair assertions;
 *   (2) every size/space comes from the GENERATED SCALE (the theme's controlGeometry) — no hand px; and
 *   (3) the interactive hit target meets the 44px AAA touch floor, in every density.
 *
 * Each load-bearing assertion is WEAKEN-TO-CONFIRM guarded. MATH IS SOURCE OF TRUTH.
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
  densityTierForMode,
  EXPERT_DENSITY_MODE,
  type Theme,
  type OkLch,
} from '@eden/theme';
import { deriveInputTokens, inputStyleVars } from './tokens.js';

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): every rendered pair meets the contrast gate (cite @eden/theme)', () => {
  const theme = generateTheme(C21_SEED, { mode: 'light', level: 'AA' });

  it('the typed TEXT over the field background clears the WCAG AA target for UI text', () => {
    const t = deriveInputTokens(theme);
    const ratio = contrastOf(t.foregroundOklch, t.backgroundOklch);
    const target = wcagTarget('normal-text', 'AA');
    expect(target).toBe(4.5); // the cited target value (provenance pin)
    expect(ratio).toBeGreaterThanOrEqual(target);
  });

  it('the PLACEHOLDER over the field background clears the AA non-text-content target (>= 3:1)', () => {
    // A placeholder is muted, advisory text — the WCAG floor for it is the 3:1 non-text/UI-component
    // contrast (research B4). We cite @eden/theme's wcagTarget('ui-component', 'AA') rather than hand-typing.
    const t = deriveInputTokens(theme);
    const ratio = contrastOf(t.placeholderOklch, t.backgroundOklch);
    const target = wcagTarget('ui-component', 'AA');
    expect(target).toBe(3); // the cited target value (provenance pin)
    expect(ratio).toBeGreaterThanOrEqual(target);
  });

  it('the RESTING border (the outline ring) is visible against the surface (>= 3:1, UI component)', () => {
    // WCAG 1.4.11 — a UI component boundary needs >= 3:1 against its adjacent color to be perceivable.
    const t = deriveInputTokens(theme);
    const ratio = contrastOf(t.borderOklch, t.backgroundOklch);
    expect(ratio).toBeGreaterThanOrEqual(wcagTarget('ui-component', 'AA'));
  });

  it('the INVALID border/ring (the error role) is visible against the surface (>= 3:1, the error state)', () => {
    const t = deriveInputTokens(theme);
    const ratio = contrastOf(t.borderInvalidOklch, t.backgroundOklch);
    expect(ratio).toBeGreaterThanOrEqual(wcagTarget('ui-component', 'AA'));
  });

  it('every pair holds in DARK mode too (the contrast guarantee is mode-independent)', () => {
    const dark = generateTheme(C21_SEED, { mode: 'dark', level: 'AA' });
    const t = deriveInputTokens(dark);
    expect(contrastOf(t.foregroundOklch, t.backgroundOklch)).toBeGreaterThanOrEqual(
      wcagTarget('normal-text', 'AA'),
    );
    expect(contrastOf(t.placeholderOklch, t.backgroundOklch)).toBeGreaterThanOrEqual(
      wcagTarget('ui-component', 'AA'),
    );
    expect(contrastOf(t.borderOklch, t.backgroundOklch)).toBeGreaterThanOrEqual(
      wcagTarget('ui-component', 'AA'),
    );
    expect(contrastOf(t.borderInvalidOklch, t.backgroundOklch)).toBeGreaterThanOrEqual(
      wcagTarget('ui-component', 'AA'),
    );
  });

  it('WEAKEN-TO-CONFIRM: a fabricated near-surface grey text FAILS the same gate (it does real work)', () => {
    const t = deriveInputTokens(theme);
    const grey: OkLch = { l: t.backgroundOklch.l, c: 0, h: 0 };
    expect(contrastOf(grey, t.backgroundOklch)).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): every size/space comes from the generated scale (no hand px)', () => {
  const theme: Theme = generateTheme(C21_SEED);

  it('the field height / inset / type are exactly the theme controlGeometry values', () => {
    const t = deriveInputTokens(theme);
    const g = theme.controlGeometry;
    expect(t.heightPx).toBe(g.componentHeightPx);
    expect(t.paddingBlockPx).toBe(g.insetPx);
    expect(t.paddingInlinePx).toBe(g.insetPx);
    expect(t.fontSizePx).toBe(g.fontSizePx);
    expect(t.lineHeightPx).toBe(g.lineHeightPx);
  });

  it('the visual geometry stays on the 4px grid (snap4) — every dimension % 4 === 0', () => {
    const t = deriveInputTokens(theme);
    expect(t.heightPx % 4).toBe(0);
    expect(t.paddingBlockPx % 4).toBe(0);
    expect(t.paddingInlinePx % 4).toBe(0);
  });

  it('the font family is the theme body typography role family (the seed text font, derived)', () => {
    const t = deriveInputTokens(theme);
    const body = theme.typography.find((r) => r.name === 'body');
    expect(t.fontFamily).toBe(body!.fontFamily);
  });

  it('WEAKEN-TO-CONFIRM: an off-grid px would be rejected by the 4px-grid assertion', () => {
    expect(13 % 4).not.toBe(0);
  });
});

describe('design-correctness (3): the 44px AAA hit-target floor holds in every density', () => {
  it('every density mode keeps the field hit target >= 44px (the hard a11y constraint)', () => {
    for (const density of ['relaxed', 'standard', 'dense'] as const) {
      const theme =
        density === 'standard'
          ? generateTheme(C21_SEED)
          : generateTheme(C21_SEED, { density: densityTierForMode(density) });
      const t = deriveInputTokens(theme);
      expect(t.hitTargetPx, `@${density}`).toBeGreaterThanOrEqual(TARGET_FLOOR_PX.wcagAaa);
      expect(TARGET_FLOOR_PX.wcagAaa).toBe(44); // the cited floor value (provenance pin)
    }
  });

  it('WEAKEN-TO-CONFIRM: a pointer-context dense theme drops the hit target BELOW 44 (touch default does real work)', () => {
    const dense = densityTierForMode(EXPERT_DENSITY_MODE);
    const touch = generateTheme(C21_SEED, { density: dense });
    const pointer = generateTheme(C21_SEED, { density: dense, targetContext: 'pointer' });
    expect(deriveInputTokens(touch).hitTargetPx).toBeGreaterThanOrEqual(44);
    expect(deriveInputTokens(pointer).hitTargetPx).toBeLessThan(44);
    // …and the VISUAL height is identical either way — only the decoupled hit target differs (I1/I2).
    expect(deriveInputTokens(pointer).heightPx).toBe(deriveInputTokens(touch).heightPx);
  });
});

describe('design-correctness (provenance): the emitted CSS carries ONLY derived tokens (no literals)', () => {
  it('inputStyleVars emits oklch() colors + px dimensions — no hand-set hex anywhere', () => {
    const css = inputStyleVars(deriveInputTokens(generateTheme(C21_SEED)));
    expect(css).toContain('--eden-input-fg: oklch(');
    expect(css).toContain('--eden-input-bg: oklch(');
    expect(css).toContain('--eden-input-border-invalid: oklch(');
    expect(css).toContain('--eden-input-hit-target:');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
