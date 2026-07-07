/**
 * WizardShell — the DESIGN-CORRECTNESS lane (ADR-0024 §3). BOTH the title and the lead clear the
 * contrast gate over the surface in BOTH modes; the title is the SERIF display voice at the LARGEST
 * generated display step (doc 17 §6 "serif display at the largest step" — a checked property, its size
 * == the display-large step AND == the max of the display steps); the reading measure is a generated
 * breakpoint; the thin bar + its transition are scale/motion derivations; the progress fraction is the
 * exact `index / (count − 1)`. Weaken-to-confirm guarded.
 */
import { describe, expect, it } from 'vitest';
import {
  generateTheme,
  C21_SEED,
  wcagContrastRatio,
  wcagTarget,
  okLchToSrgb,
  srgbTo8,
  type OkLch,
} from '@eden/theme';
import { deriveWizardShellTokens, wizardProgressFraction } from './tokens.js';

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): title + lead clear the contrast gate over the surface', () => {
  for (const mode of ['light', 'dark'] as const) {
    it(`${mode}: the title (onSurface) and lead (outline) both clear AA 4.5`, () => {
      const t = deriveWizardShellTokens(generateTheme(C21_SEED, { mode, level: 'AA' }));
      expect(contrastOf(t.titleOklch, t.surfaceOklch)).toBeGreaterThanOrEqual(
        wcagTarget('normal-text', 'AA'),
      );
      expect(contrastOf(t.leadOklch, t.surfaceOklch)).toBeGreaterThanOrEqual(
        wcagTarget('normal-text', 'AA'),
      );
    });
  }

  it('WEAKEN-TO-CONFIRM: a grey title near the surface lightness fails the gate', () => {
    const t = deriveWizardShellTokens(generateTheme(C21_SEED));
    const grey: OkLch = { l: t.surfaceOklch.l, c: 0, h: 0 };
    expect(contrastOf(grey, t.surfaceOklch)).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): the title is the SERIF display voice at the LARGEST step (doc 17 §6)', () => {
  const theme = generateTheme(C21_SEED);

  it('the title family is a DISPLAY role family, distinct from the lead/text family', () => {
    const t = deriveWizardShellTokens(theme);
    const displayFamilies = new Set(
      theme.typography.filter((r) => r.name.startsWith('display')).map((r) => r.fontFamily),
    );
    expect(displayFamilies.has(t.titleFontFamily)).toBe(true);
    // the interface lead voice is a DIFFERENT family (P-D4: never mixed within one block)
    expect(t.titleFontFamily).not.toBe(t.leadFontFamily);
  });

  it('the title size is EXACTLY display-large AND is the MAX of every display step (the largest)', () => {
    const t = deriveWizardShellTokens(theme);
    const displaySizes = theme.typography
      .filter((r) => r.name.startsWith('display'))
      .map((r) => r.fontSizePx);
    expect(t.titleFontSizePx).toBe(
      theme.typography.find((r) => r.name === 'display-large')!.fontSizePx,
    );
    expect(t.titleFontSizePx).toBe(Math.max(...displaySizes));
  });

  it('WEAKEN-TO-CONFIRM: display-large is strictly larger than display-small (the pick is not the small one)', () => {
    const large = theme.typography.find((r) => r.name === 'display-large')!.fontSizePx;
    const small = theme.typography.find((r) => r.name === 'display-small')!.fontSizePx;
    expect(large).toBeGreaterThan(small);
    expect(deriveWizardShellTokens(theme).titleFontSizePx).not.toBe(small);
  });

  it('the reading measure is a generated breakpoint (the focus-content cap, not eyeballed)', () => {
    const t = deriveWizardShellTokens(theme);
    expect(theme.breakpoints.map((b) => b.minWidthPx)).toContain(t.measurePx);
  });
});

describe('design-correctness (3): the thin bar + its motion are scale/motion derivations', () => {
  const theme = generateTheme(C21_SEED);

  it('the bar thickness + radius are ramp steps; the bar is the tightest (a THIN bar, doc 17 §6)', () => {
    const t = deriveWizardShellTokens(theme);
    const ramp = theme.spacing.map((s) => s.px);
    expect(ramp).toContain(t.barThicknessPx);
    expect(ramp).toContain(t.barRadiusPx);
    // WEAKEN-TO-CONFIRM: the bar is thinner than the content gap (it is a hairline, not a slab)
    expect(t.barThicknessPx).toBeLessThan(t.gapPx);
  });

  it('the transition is the theme medium.2 duration + the standard easing curve (motion-slice sourced)', () => {
    const t = deriveWizardShellTokens(theme);
    expect(t.transitionMs).toBe(theme.motion.durations['medium.2']);
    const standard = theme.motion.easing['standard']!;
    expect(t.easing).toBe(`cubic-bezier(${standard.join(', ')})`);
  });
});

describe('design-correctness (4): the progress fraction is the exact step-index math', () => {
  it('a 3-step wizard reads 0 · 0.5 · 1 across its steps', () => {
    expect(wizardProgressFraction(0, 3)).toBe(0);
    expect(wizardProgressFraction(1, 3)).toBeCloseTo(0.5, 12);
    expect(wizardProgressFraction(2, 3)).toBe(1);
  });

  it('WEAKEN-TO-CONFIRM: the fraction is NOT index/count (an off-by-one bar would misreport arrival)', () => {
    // the correct denominator is (count − 1) — the LAST step must read a FULL bar (1), never 2/3
    expect(wizardProgressFraction(2, 3)).not.toBeCloseTo(2 / 3, 6);
    expect(wizardProgressFraction(2, 3)).toBe(1);
  });
});
