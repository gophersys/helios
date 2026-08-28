/**
 * Overlay group — the DESIGN-CORRECTNESS lane (ADR-0024 §3, the ninth dimension). The UI-MATH gate,
 * per component, MECHANICAL (the founder bar). Aesthetics made computable for the PORTALED surfaces
 * (Dialog, Popover, Tooltip, DropdownMenu — they share `deriveOverlayTokens`): this file asserts that
 *
 *   (1) every text/background pair the overlay renders MEETS the contrast gate — recomputed from the
 *       SAME OKLCH values the component emits, against `@eden/theme`'s own WCAG ratio + APCA;
 *   (2) every size/space the overlay renders comes from the GENERATED SCALE (the theme's spacing
 *       ramp + controlGeometry) — no hand-irregular px; and
 *   (3) the interactive hit targets (dialog close, menu items) meet the 44px AAA touch floor.
 *
 * Each load-bearing assertion is WEAKEN-TO-CONFIRM guarded: a fabricated grey foreground fails the
 * contrast gate; an off-grid px is rejected; a pointer-context theme drops the hit target below 44.
 * MATH IS SOURCE OF TRUTH — the contrast cited is @eden/theme's, the scale cited is @eden/theme's;
 * this lib derives, never re-spells. (The portaled computed-color == resolved-token proof in a REAL
 * browser is the a11y lane, tests-a11y/specs/overlay.spec.ts — the third leg of the same gate.)
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
import { deriveOverlayTokens, overlayStyleVars, type OverlayLayer } from './tokens.js';

const LAYERS: readonly OverlayLayer[] = ['dropdown', 'modal', 'tooltip'];

/** The contrast ratio of an OKLCH fg/bg pair, recomputed via @eden/theme's own WCAG formula. */
function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): the on-surface/surface pair meets the contrast gate (cite @eden/theme)', () => {
  const theme = generateTheme(C21_SEED, { mode: 'light', level: 'AA' });

  for (const layer of LAYERS) {
    it(`${layer}: the panel text (on-surface) over the panel (surface) clears the WCAG AA target`, () => {
      const t = deriveOverlayTokens(layer, theme);
      const ratio = contrastOf(t.onSurfaceOklch, t.surfaceOklch);
      // Overlay body text is non-large UI text → the AA target is 4.5 (research B4 / WCAG 1.4.3). We
      // cite @eden/theme's wcagTarget(contentClass, level) rather than hand-typing 4.5.
      const target = wcagTarget('normal-text', 'AA');
      expect(target).toBe(4.5); // the cited target value (provenance pin)
      expect(ratio).toBeGreaterThanOrEqual(target);
    });
  }

  it('the gate holds in DARK mode too (the contrast guarantee is mode-independent)', () => {
    const dark = generateTheme(C21_SEED, { mode: 'dark', level: 'AA' });
    for (const layer of LAYERS) {
      const t = deriveOverlayTokens(layer, dark);
      const ratio = contrastOf(t.onSurfaceOklch, t.surfaceOklch);
      expect(ratio).toBeGreaterThanOrEqual(wcagTarget('normal-text', 'AA'));
    }
  });

  it('APCA agrees the panel pair is a strong perceptual pair (advisory, >= 45 Lc for UI text)', () => {
    const t = deriveOverlayTokens('modal', theme);
    const lc = Math.abs(
      apcaLc(srgbTo8(okLchToSrgb(t.onSurfaceOklch)), srgbTo8(okLchToSrgb(t.surfaceOklch))),
    );
    expect(lc).toBeGreaterThanOrEqual(45);
  });

  it('WEAKEN-TO-CONFIRM: a fabricated mid-grey foreground FAILS the same gate (it does real work)', () => {
    const t = deriveOverlayTokens('modal', theme);
    // Replace the derived on-surface with a grey near the surface lightness → must fail 4.5:1.
    const grey: OkLch = { l: t.surfaceOklch.l, c: 0, h: 0 };
    const ratio = contrastOf(grey, t.surfaceOklch);
    expect(ratio).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): every size/space comes from the generated scale (no hand px)', () => {
  const theme: Theme = generateTheme(C21_SEED);

  it('the radius/padding are EXACT spacing-ramp steps (space-2 / space-4 — precise scale values)', () => {
    const t = deriveOverlayTokens('modal', theme);
    const ramp = theme.spacing.map((s) => s.px);
    const space2 = theme.spacing.find((s) => s.name === 'space-2')!.px;
    const space4 = theme.spacing.find((s) => s.name === 'space-4')!.px;
    // on the ramp AND exactly the named rung (kills a mutant that returns the first/any step).
    expect(ramp).toContain(t.radiusPx);
    expect(ramp).toContain(t.paddingPx);
    expect(t.radiusPx).toBe(space2);
    expect(t.paddingPx).toBe(space4);
    expect(t.radiusPx).toBe(8); // the default-base concrete value (provenance pin)
    expect(t.paddingPx).toBe(16);
  });

  it('the gap / font-size / line-height are exactly the theme controlGeometry values', () => {
    const t = deriveOverlayTokens('dropdown', theme);
    const g = theme.controlGeometry;
    expect(t.gapPx).toBe(g.gapPx);
    expect(t.fontSizePx).toBe(g.fontSizePx);
    expect(t.lineHeightPx).toBe(g.lineHeightPx);
  });

  it('the radius / padding / gap stay on the 4px grid (snap4) — every dimension % 4 === 0', () => {
    const t = deriveOverlayTokens('modal', theme);
    expect(t.radiusPx % 4).toBe(0);
    expect(t.paddingPx % 4).toBe(0);
    expect(t.gapPx % 4).toBe(0);
  });

  it('the z-index is the cited motion.zIndex ladder rung per layer (stacking order from the scale)', () => {
    const z = theme.motion.zIndex;
    expect(deriveOverlayTokens('dropdown', theme).zIndex).toBe(z.dropdown);
    expect(deriveOverlayTokens('modal', theme).zIndex).toBe(z.modal);
    expect(deriveOverlayTokens('tooltip', theme).zIndex).toBe(z.tooltip);
  });

  it('the elevation shadow is the EXACT cited motion.elevation level per layer (modal=24/dropdown=8/tooltip=4)', () => {
    // The layer→elevation-LEVEL mapping is the ONE design decision for depth; pin each layer's shadow
    // to the shadow built from the theme's SPECIFIC level so a mutated level selection (or a constant
    // level) fails. The levels share a layer COUNT (4) but differ in OFFSET/BLUR geometry (offset
    // scales with the level), so we pin the first segment's offsets — the per-level discriminator.
    const firstSegmentGeometry = (level: number): string => {
      const l0 = theme.motion.elevation.find((e) => e.level === level)!.layers[0]!;
      return `${String(l0.offsetXPx)}px ${String(l0.offsetYPx)}px ${String(l0.blurPx)}px`;
    };
    const expectLevel = (layer: OverlayLayer, level: number): void => {
      const shadow = deriveOverlayTokens(layer, theme).elevationShadow;
      expect(
        shadow.startsWith(firstSegmentGeometry(level)),
        `${layer}→level ${String(level)}`,
      ).toBe(true);
    };
    expectLevel('modal', 24);
    expectLevel('dropdown', 8);
    expectLevel('tooltip', 4);
    // the three cited levels have DISTINCT first-segment geometry, so the per-layer pins are
    // non-vacuous (a constant level would make two of these collide).
    const geos = [firstSegmentGeometry(24), firstSegmentGeometry(8), firstSegmentGeometry(4)];
    expect(new Set(geos).size).toBe(3);
  });

  it('the font family is the theme body typography role family (the seed text font, derived)', () => {
    const t = deriveOverlayTokens('modal', theme);
    const body = theme.typography.find((r) => r.name === 'body');
    expect(t.fontFamily).toBe(body!.fontFamily);
  });

  it('WEAKEN-TO-CONFIRM: an off-grid px would be rejected by the 4px-grid assertion', () => {
    expect(13 % 4).not.toBe(0);
  });
});

describe('design-correctness (3): the 44px AAA hit-target floor holds in every density', () => {
  it('every density mode keeps the overlay hit target >= 44px (the hard a11y constraint)', () => {
    for (const density of ['relaxed', 'standard', 'dense'] as const) {
      const theme =
        density === 'standard'
          ? generateTheme(C21_SEED)
          : generateTheme(C21_SEED, { density: densityTierForMode(density) });
      for (const layer of LAYERS) {
        const t = deriveOverlayTokens(layer, theme);
        expect(t.hitTargetPx, `${layer}@${density}`).toBeGreaterThanOrEqual(
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
    const touchTok = deriveOverlayTokens('dropdown', touch);
    const pointerTok = deriveOverlayTokens('dropdown', pointer);
    expect(touchTok.hitTargetPx).toBeGreaterThanOrEqual(44);
    expect(pointerTok.hitTargetPx).toBeLessThan(44);
  });
});

describe('design-correctness (provenance): the emitted overlay CSS carries ONLY derived tokens', () => {
  it('overlayStyleVars emits oklch() colors (incl. translucent scrim/shadow) + px — no hand-set hex', () => {
    const theme = generateTheme(C21_SEED);
    for (const layer of LAYERS) {
      const css = overlayStyleVars(deriveOverlayTokens(layer, theme));
      expect(css).toContain('--eden-overlay-surface: oklch(');
      expect(css).toContain('--eden-overlay-on-surface: oklch(');
      expect(css).toContain('--eden-overlay-scrim: oklch(');
      expect(css).toContain('--eden-overlay-shadow:');
      expect(css).toContain('--eden-overlay-hit-target:');
      // the cardinal provenance check: NO hex literal in the emitted style string (the scrim and
      // shadow are translucent oklch, NOT pasted rgba/hex black).
      expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
      expect(css).not.toMatch(/rgba?\(/);
    }
  });

  it('WEAKEN-TO-CONFIRM: the hex-absence check is non-vacuous (a hex literal WOULD be matched)', () => {
    expect('#1a2b3c').toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
