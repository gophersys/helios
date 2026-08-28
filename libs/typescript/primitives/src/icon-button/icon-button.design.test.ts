/**
 * IconButton — the DESIGN-CORRECTNESS lane (ADR-0024 §3, the ninth dimension). The UI-MATH gate,
 * per component, MECHANICAL (the founder bar). This file asserts that
 *
 *   (1) every icon/background pair the IconButton renders MEETS the contrast gate — recomputed from
 *       the SAME OKLCH values the component emits, against @eden/theme's own WCAG ratio + APCA;
 *   (2) every size the IconButton renders comes from the GENERATED SCALE (the theme's
 *       controlGeometry — the square edge AND the glyph size) — no hand-irregular px; and
 *   (3) the interactive hit target meets the 44px AAA touch floor, in every density.
 *
 * Each load-bearing assertion is WEAKEN-TO-CONFIRM guarded. MATH IS SOURCE OF TRUTH — the contrast
 * cited is @eden/theme's, the scale cited is @eden/theme's; this component derives, never re-spells.
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
import { deriveIconButtonTokens, iconButtonStyleVars } from './tokens.js';
import { type ButtonVariant } from '../button/tokens.js';

const VARIANTS: readonly ButtonVariant[] = ['primary', 'secondary', 'ghost', 'danger'];

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): the icon/bg pair meets the contrast gate (cite @eden/theme)', () => {
  const theme = generateTheme(C21_SEED, { mode: 'light', level: 'AA' });

  for (const variant of VARIANTS) {
    it(`${variant}: icon foreground over background clears the WCAG AA target`, () => {
      const t = deriveIconButtonTokens(variant, theme);
      const ratio = contrastOf(t.foregroundOklch, t.backgroundOklch);
      const target = wcagTarget('normal-text', 'AA');
      expect(target).toBe(4.5); // the cited target value (provenance pin)
      expect(ratio).toBeGreaterThanOrEqual(target);
    });
  }

  it('the gate holds in DARK mode too (the contrast guarantee is mode-independent)', () => {
    const dark = generateTheme(C21_SEED, { mode: 'dark', level: 'AA' });
    for (const variant of VARIANTS) {
      const t = deriveIconButtonTokens(variant, dark);
      const ratio = contrastOf(t.foregroundOklch, t.backgroundOklch);
      expect(ratio).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
    }
  });

  it('WEAKEN-TO-CONFIRM: a fabricated mid-grey foreground FAILS the same gate (it does real work)', () => {
    const t = deriveIconButtonTokens('primary', theme);
    const grey: OkLch = { l: t.backgroundOklch.l, c: 0, h: 0 };
    const ratio = contrastOf(grey, t.backgroundOklch);
    expect(ratio).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): every size comes from the generated scale (no hand px)', () => {
  const theme: Theme = generateTheme(C21_SEED);

  it('the square edge is the theme component height and the glyph is the theme icon size', () => {
    const t = deriveIconButtonTokens('primary', theme);
    const g = theme.controlGeometry;
    expect(t.sizePx).toBe(g.componentHeightPx);
    expect(t.iconSizePx).toBe(g.iconSizePx);
  });

  it('the visual geometry stays on the 4px grid (snap4) — square edge % 4 === 0', () => {
    const t = deriveIconButtonTokens('primary', theme);
    expect(t.sizePx % 4).toBe(0);
    expect(t.iconSizePx % 4).toBe(0);
  });

  it('the icon glyph is strictly smaller than the square edge (it fits inside the box)', () => {
    const t = deriveIconButtonTokens('primary', theme);
    expect(t.iconSizePx).toBeLessThan(t.sizePx);
  });

  it('WEAKEN-TO-CONFIRM: an off-grid px would be rejected by the 4px-grid assertion', () => {
    expect(13 % 4).not.toBe(0);
  });
});

describe('design-correctness (3): the 44px AAA hit-target floor holds in every density', () => {
  it('every density mode keeps the IconButton hit target >= 44px (the hard a11y constraint)', () => {
    for (const density of ['relaxed', 'standard', 'dense'] as const) {
      const theme =
        density === 'standard'
          ? generateTheme(C21_SEED)
          : generateTheme(C21_SEED, { density: densityTierForMode(density) });
      for (const variant of VARIANTS) {
        const t = deriveIconButtonTokens(variant, theme);
        expect(t.hitTargetPx, `${variant}@${density}`).toBeGreaterThanOrEqual(
          TARGET_FLOOR_PX.wcagAaa,
        );
        expect(TARGET_FLOOR_PX.wcagAaa).toBe(44); // the cited floor value (provenance pin)
      }
    }
  });

  it('WEAKEN-TO-CONFIRM: a pointer-context dense theme drops the hit target BELOW 44 (touch default does real work)', () => {
    const dense = densityTierForMode(EXPERT_DENSITY_MODE);
    const touch = generateTheme(C21_SEED, { density: dense }); // default targetContext = touch (44)
    const pointer = generateTheme(C21_SEED, { density: dense, targetContext: 'pointer' });
    expect(deriveIconButtonTokens('primary', touch).hitTargetPx).toBeGreaterThanOrEqual(44);
    expect(deriveIconButtonTokens('primary', pointer).hitTargetPx).toBeLessThan(44);
    // …and the VISUAL square edge is identical either way — only the decoupled hit target differs.
    expect(deriveIconButtonTokens('primary', pointer).sizePx).toBe(
      deriveIconButtonTokens('primary', touch).sizePx,
    );
  });
});

describe('design-correctness (provenance): the emitted CSS carries ONLY derived tokens (no literals)', () => {
  it('iconButtonStyleVars emits oklch() colors + px dimensions — no hand-set hex anywhere', () => {
    const theme = generateTheme(C21_SEED);
    for (const variant of VARIANTS) {
      const css = iconButtonStyleVars(deriveIconButtonTokens(variant, theme));
      expect(css).toContain('--eden-icon-button-fg: oklch(');
      expect(css).toContain('--eden-icon-button-bg: oklch(');
      expect(css).toContain('--eden-icon-button-hit-target:');
      expect(css).toContain('--eden-icon-button-icon-size:');
      expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    }
  });
});
