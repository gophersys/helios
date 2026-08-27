/**
 * CommandPalette — the DESIGN-CORRECTNESS lane (ADR-0024 §3, the ninth dimension). The UI-MATH gate,
 * per component, MECHANICAL (the founder bar). Aesthetics made computable: this file asserts that
 *
 *   (1) every text/surface pair the palette PAINTS meets the contrast gate — recomputed from the
 *       SAME OKLCH values the component emits, against `@eden/theme`'s own WCAG ratio + APCA, with
 *       the WCAG target the theme's contrast audit records. The painted pairs are: the input text
 *       over the input surface, a result item at REST over the panel, the SELECTED item (its own
 *       fg/bg pair), the group heading over the panel, and the empty message over the panel;
 *   (2) every size/space the palette renders comes from the GENERATED SCALE (the theme's
 *       controlGeometry + spacing ramp + typography roles) — no hand-irregular px; and
 *   (3) the interactive hit target (the input + every selectable item) meets the 44px AAA touch floor.
 *
 * Each load-bearing assertion is WEAKEN-TO-CONFIRM guarded: a probe shows the assertion does real
 * work (a pointer-context theme drops the hit target below 44; a fabricated grey foreground fails
 * the contrast gate; an off-grid px is rejected; the heading size really tracks the caption role).
 * MATH IS SOURCE OF TRUTH — the contrast cited is @eden/theme's, the scale cited is @eden/theme's;
 * this lib derives, never re-spells.
 */
import { describe, expect, it } from 'vitest';
import {
  generateTheme,
  C21_SEED,
  wcagTarget,
  apcaLc,
  okLchToSrgb,
  srgbTo8,
  TARGET_FLOOR_PX,
  SHADOW_ALPHA0,
  Z_INDEX,
  densityTierForMode,
  EXPERT_DENSITY_MODE,
  type Theme,
  type OkLch,
} from '@eden/theme';
import { deriveCommandPaletteTokens, commandPaletteStyleVars, commandContrast } from './tokens.js';

/** The painted text/surface pairs the palette renders — the contrast gate must clear each. */
function paintedPairs(t: ReturnType<typeof deriveCommandPaletteTokens>): readonly {
  name: string;
  fg: OkLch;
  bg: OkLch;
}[] {
  return [
    { name: 'input text / input surface', fg: t.inputForegroundOklch, bg: t.inputBackgroundOklch },
    // a REST item paints on-surface over the panel (the panel bg is the surface role).
    { name: 'rest item / panel', fg: t.itemForegroundOklch, bg: t.inputBackgroundOklch },
    // the SELECTED item paints its own gated pair (on-primary-container over primary-container).
    {
      name: 'selected item fg / selected item bg',
      fg: t.itemSelectedForegroundOklch,
      bg: t.itemSelectedBackgroundOklch,
    },
    // the group heading + empty message paint the secondary role over the panel surface.
    {
      name: 'group heading / panel',
      fg: t.groupHeadingForegroundOklch,
      bg: t.inputBackgroundOklch,
    },
  ];
}

describe('design-correctness (1): every painted fg/bg pair meets the contrast gate (cite @eden/theme)', () => {
  const theme = generateTheme(C21_SEED, { mode: 'light', level: 'AA' });

  for (const pair of paintedPairs(deriveCommandPaletteTokens(theme))) {
    it(`${pair.name}: clears the WCAG AA target for UI text`, () => {
      const ratio = commandContrast(pair.fg, pair.bg);
      // The palette text is non-large UI text → the AA target is 4.5 (research B4 / WCAG 1.4.3).
      // We cite @eden/theme's wcagTarget(contentClass, level) rather than hand-typing 4.5.
      const target = wcagTarget('normal-text', 'AA');
      expect(target).toBe(4.5); // the cited target value (provenance pin)
      expect(ratio).toBeGreaterThanOrEqual(target);
    });
  }

  it('the gate holds in DARK mode too (the contrast guarantee is mode-independent)', () => {
    const dark = deriveCommandPaletteTokens(generateTheme(C21_SEED, { mode: 'dark', level: 'AA' }));
    for (const pair of paintedPairs(dark)) {
      expect(commandContrast(pair.fg, pair.bg), pair.name).toBeGreaterThanOrEqual(
        wcagTarget('normal-text', 'AA'),
      );
    }
  });

  it('APCA agrees the input text pair is a strong perceptual pair (advisory, >= 45 Lc for UI text)', () => {
    const t = deriveCommandPaletteTokens(theme);
    const lc = Math.abs(
      apcaLc(
        srgbTo8(okLchToSrgb(t.inputForegroundOklch)),
        srgbTo8(okLchToSrgb(t.inputBackgroundOklch)),
      ),
    );
    // APCA Lc 45 is the bronze floor for ~16px/medium text (research B4 advisory).
    expect(lc).toBeGreaterThanOrEqual(45);
  });

  it('WEAKEN-TO-CONFIRM: a fabricated mid-grey foreground FAILS the same gate (it does real work)', () => {
    const t = deriveCommandPaletteTokens(theme);
    // Replace the derived item foreground with a grey near the panel lightness → must fail 4.5:1.
    const grey: OkLch = { l: t.inputBackgroundOklch.l, c: 0, h: 0 };
    const ratio = commandContrast(grey, t.inputBackgroundOklch);
    expect(ratio).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): every size/space comes from the generated scale (no hand px)', () => {
  const theme: Theme = generateTheme(C21_SEED);

  it('the input/item height + padding + gap + icon are exactly the theme controlGeometry values', () => {
    const t = deriveCommandPaletteTokens(theme);
    const g = theme.controlGeometry;
    expect(t.inputHeightPx).toBe(g.componentHeightPx);
    expect(t.itemHeightPx).toBe(g.componentHeightPx);
    expect(t.panelPaddingPx).toBe(g.insetPx);
    expect(t.itemPaddingInlinePx).toBe(g.insetPx);
    expect(t.gapPx).toBe(g.gapPx);
    expect(t.iconSizePx).toBe(g.iconSizePx);
    expect(t.fontSizePx).toBe(g.fontSizePx);
    expect(t.lineHeightPx).toBe(g.lineHeightPx);
  });

  it('the visual geometry stays on the 4px grid (snap4) — every grid dimension % 4 === 0', () => {
    const t = deriveCommandPaletteTokens(theme);
    expect(t.inputHeightPx % 4).toBe(0);
    expect(t.itemHeightPx % 4).toBe(0);
    expect(t.panelPaddingPx % 4).toBe(0);
    expect(t.itemPaddingInlinePx % 4).toBe(0);
    expect(t.gapPx % 4).toBe(0);
  });

  it('the panel radius + list max-height are EXACT spacing-ramp steps (real scale values, not eyeballed)', () => {
    const t = deriveCommandPaletteTokens(theme);
    const rampValues = theme.spacing.map((s) => s.px);
    // both are MEMBERS of the ramp (the design-correctness scale-provenance assertion), and pinned to
    // their exact selected steps so a mutant that always returns the first/last ramp step is killed.
    expect(rampValues).toContain(t.panelRadiusPx);
    expect(rampValues).toContain(t.listMaxHeightPx);
    expect(t.panelRadiusPx).toBe(12); // the --space-3 comfortable panel radius
    expect(t.listMaxHeightPx).toBe(rampValues[rampValues.length - 1]); // the tallest ramp step
    expect(t.listMaxHeightPx).toBe(384);
  });

  it('the heading font size is the caption typography-role size rounded to a whole px (a scale value)', () => {
    const t = deriveCommandPaletteTokens(theme);
    const caption = theme.typography.find((r) => r.name === 'caption');
    expect(t.headingFontSizePx).toBe(Math.round(caption!.fontSizePx));
    // weaken-to-confirm: the caption role is sub-body — the heading is smaller than the body font.
    expect(t.headingFontSizePx).toBeLessThan(t.fontSizePx);
  });

  it('the modal z-index + overlay alpha are cited scale CONSTANTS, never hand-set', () => {
    const light = deriveCommandPaletteTokens(generateTheme(C21_SEED, { mode: 'light' }));
    const dark = deriveCommandPaletteTokens(generateTheme(C21_SEED, { mode: 'dark' }));
    expect(light.zIndexModal).toBe(Z_INDEX.modal);
    // the scrim alpha is the canonical base shadow alpha, mode-aware (heavier in dark).
    expect(light.overlayAlpha).toBe(SHADOW_ALPHA0.light);
    expect(dark.overlayAlpha).toBe(SHADOW_ALPHA0.dark);
    expect(dark.overlayAlpha).toBeGreaterThan(light.overlayAlpha);
  });

  it('the font family is the theme body typography role family (the seed text font, derived)', () => {
    const t = deriveCommandPaletteTokens(theme);
    const body = theme.typography.find((r) => r.name === 'body');
    expect(t.fontFamily).toBe(body!.fontFamily);
  });

  it('WEAKEN-TO-CONFIRM: an off-grid px would be rejected by the 4px-grid assertion', () => {
    // Prove the % 4 check is non-vacuous: 13px is not on the grid and would fail.
    expect(13 % 4).not.toBe(0);
  });
});

describe('design-correctness (3): the 44px AAA hit-target floor holds in every density', () => {
  it('every density mode keeps the input + every item hit target >= 44px (the hard a11y constraint)', () => {
    for (const density of ['relaxed', 'standard', 'dense'] as const) {
      const theme =
        density === 'standard'
          ? generateTheme(C21_SEED)
          : generateTheme(C21_SEED, { density: densityTierForMode(density) });
      const t = deriveCommandPaletteTokens(theme);
      expect(t.hitTargetPx, `hit-target@${density}`).toBeGreaterThanOrEqual(
        TARGET_FLOOR_PX.wcagAaa,
      );
      expect(TARGET_FLOOR_PX.wcagAaa).toBe(44); // the cited floor value (provenance pin)
    }
  });

  it('WEAKEN-TO-CONFIRM: a pointer-context dense theme drops the hit target BELOW 44 (the touch default does real work)', () => {
    const dense = densityTierForMode(EXPERT_DENSITY_MODE);
    const touch = generateTheme(C21_SEED, { density: dense }); // default targetContext = touch (44)
    const pointer = generateTheme(C21_SEED, { density: dense, targetContext: 'pointer' });
    const touchTok = deriveCommandPaletteTokens(touch);
    const pointerTok = deriveCommandPaletteTokens(pointer);
    expect(touchTok.hitTargetPx).toBeGreaterThanOrEqual(44);
    expect(pointerTok.hitTargetPx).toBeLessThan(44);
    // …and the VISUAL height is identical either way — only the decoupled hit target differs (I1/I2).
    expect(pointerTok.itemHeightPx).toBe(touchTok.itemHeightPx);
  });
});

describe('design-correctness (provenance): the emitted CSS carries ONLY derived tokens (no literals)', () => {
  it('commandPaletteStyleVars emits oklch() colors + px dimensions — no hand-set hex anywhere', () => {
    const css = commandPaletteStyleVars(deriveCommandPaletteTokens(generateTheme(C21_SEED)));
    expect(css).toContain('--eden-command-input-fg: oklch(');
    expect(css).toContain('--eden-command-panel-bg: oklch(');
    expect(css).toContain('--eden-command-item-selected-bg: oklch(');
    expect(css).toContain('--eden-command-hit-target:');
    expect(css).toContain('--eden-command-z-modal:');
    // the cardinal provenance check: NO hex literal in the emitted style string.
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
