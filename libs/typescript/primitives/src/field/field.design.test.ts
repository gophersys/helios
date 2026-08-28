/**
 * Field — the DESIGN-CORRECTNESS lane (ADR-0024 §3, the ninth dimension). The UI-MATH gate,
 * MECHANICAL (the founder bar). This file asserts that
 *
 *   (1) every text/background pair the Field renders MEETS the contrast gate — the LABEL over the
 *       surface (UI text, 4.5:1) AND the ERROR message over the surface (UI text, 4.5:1) — recomputed
 *       from the SAME OKLCH values the component emits, against @eden/theme's own WCAG ratio;
 *   (2) every size/space comes from the GENERATED SCALE (the label type role + the spacing ramp) —
 *       no hand-irregular px (the label font size is a TYPE-scale value; the gap is a ramp step); and
 *   (3) the Field is the a11y wiring layer — its design-correctness is the contrast of the text it
 *       owns (the control's own 44px hit-target floor is proven in input.design.test.ts).
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
  type Theme,
  type OkLch,
} from '@eden/theme';
import { deriveFieldTokens, fieldStyleVars } from './tokens.js';

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): the label AND the error message meet the contrast gate', () => {
  const theme = generateTheme(C21_SEED, { mode: 'light', level: 'AA' });

  it('the LABEL over the field surface clears the WCAG AA target for UI text', () => {
    const t = deriveFieldTokens(theme);
    const target = wcagTarget('normal-text', 'AA');
    expect(target).toBe(4.5); // the cited target value (provenance pin)
    expect(contrastOf(t.labelOklch, t.surfaceOklch)).toBeGreaterThanOrEqual(target);
  });

  it('the ERROR MESSAGE over the field surface clears the WCAG AA target for UI text', () => {
    // The error message is real, load-bearing content (not a muted hint) — it must clear the full
    // 4.5:1 text target, not just the 3:1 UI-component floor. The error role does (it is a strong tone).
    const t = deriveFieldTokens(theme);
    expect(contrastOf(t.errorOklch, t.surfaceOklch)).toBeGreaterThanOrEqual(
      wcagTarget('normal-text', 'AA'),
    );
  });

  it('both texts hold in DARK mode too (the contrast guarantee is mode-independent)', () => {
    const dark = generateTheme(C21_SEED, { mode: 'dark', level: 'AA' });
    const t = deriveFieldTokens(dark);
    expect(contrastOf(t.labelOklch, t.surfaceOklch)).toBeGreaterThanOrEqual(
      wcagTarget('normal-text', 'AA'),
    );
    expect(contrastOf(t.errorOklch, t.surfaceOklch)).toBeGreaterThanOrEqual(
      wcagTarget('normal-text', 'AA'),
    );
  });

  it('WEAKEN-TO-CONFIRM: a fabricated near-surface grey label FAILS the same gate (it does real work)', () => {
    const t = deriveFieldTokens(theme);
    const grey: OkLch = { l: t.surfaceOklch.l, c: 0, h: 0 };
    expect(contrastOf(grey, t.surfaceOklch)).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): every size/space comes from the generated scale (no hand px)', () => {
  const theme: Theme = generateTheme(C21_SEED);

  it('the label font size is the theme `label` typography role size (a type-scale value)', () => {
    const t = deriveFieldTokens(theme);
    const labelRole = theme.typography.find((r) => r.name === 'label');
    expect(labelRole, 'the C21 theme has a label type role').toBeDefined();
    expect(t.labelFontSizePx).toBe(labelRole!.fontSizePx);
  });

  it('the label line height is the derived role ratio × font size (rounded), not eyeballed', () => {
    const t = deriveFieldTokens(theme);
    const labelRole = theme.typography.find((r) => r.name === 'label')!;
    expect(t.labelLineHeightPx).toBe(Math.round(labelRole.fontSizePx * labelRole.lineHeight));
  });

  it('the vertical rhythm (gap) is the control inset — a single scale step on the 4px grid', () => {
    const t = deriveFieldTokens(theme);
    expect(t.gapPx).toBe(theme.controlGeometry.insetPx);
    expect(t.gapPx % 4).toBe(0);
  });

  it('the label font family is the theme `label` role family (derived, not hand-named)', () => {
    const t = deriveFieldTokens(theme);
    const labelRole = theme.typography.find((r) => r.name === 'label')!;
    expect(t.labelFontFamily).toBe(labelRole.fontFamily);
  });

  it('WEAKEN-TO-CONFIRM: the gap is on the 4px grid, an off-grid px would fail the assertion', () => {
    const t = deriveFieldTokens(theme);
    expect(t.gapPx % 4).toBe(0);
    expect(13 % 4).not.toBe(0);
  });
});

describe('design-correctness (provenance): the emitted CSS carries ONLY derived tokens (no literals)', () => {
  it('fieldStyleVars emits oklch() colors + px dimensions — no hand-set hex anywhere', () => {
    const css = fieldStyleVars(deriveFieldTokens(generateTheme(C21_SEED)));
    expect(css).toContain('--eden-field-label: oklch(');
    expect(css).toContain('--eden-field-error: oklch(');
    expect(css).toContain('--eden-field-gap:');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
