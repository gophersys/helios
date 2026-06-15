/**
 * Design-correctness lane (ADR-0024 §3, the ninth dimension): aesthetics made COMPUTABLE.
 *
 * MATH IS SOURCE OF TRUTH. These assertions prove every generated value comes from the research
 * tables/formulas in docs/research/05-design-foundations.md — never an eyeballed or hand-set
 * literal — and that the CONTRAST GATE is satisfied by construction (the hard constraint, §B.4/
 * §C.3). A drift between the engine and the published research FAILS the design gate, exactly the
 * way "looks right" is now a checked property of the build. The `design-correctness` ctl verb runs
 * this lane (it also runs the no-hand-set-hex provenance lint over non-test src).
 */
import { describe, expect, it } from 'vitest';
import {
  // verbatim research constants
  LIGHTNESS_LADDER,
  CHROMA_ENVELOPE,
  EASING,
  DURATION_LADDER,
  BREAKPOINTS,
  TARGET_FLOOR_PX,
  EMPHASIZED_SPLINE_PATH,
  // formulas
  srgbToOkLab,
  relativeLuminance,
  wcagContrastRatio,
  apcaLc,
  typeSizePx,
  spring,
  generateSpacingRamp,
  // pipeline
  generateTheme,
  C21_SEED,
  C21_SURFACE,
  hexToOkLch,
  srgbTo8,
  okLchToSrgb,
  parseHex,
  // density modes (the user-facing three-step density control; OD-17-c21)
  DENSITY_MODES,
  RECOMMENDED_DENSITY_MODE,
  EXPERT_DENSITY_MODE,
  DENSITY_MODE_TIER,
  densityTierForMode,
  DENSITY_STEP,
  DEFAULT_DENSITY,
} from './index.js';

describe('design-correctness: the color math is the verbatim research matrices (B3-A)', () => {
  it('reproduces the WCAG relative-luminance weights (0.2126/0.7152/0.0722)', () => {
    // pure-channel probes isolate each weight (research B4-A).
    expect(relativeLuminance({ r8: 255, g8: 0, b8: 0 })).toBeCloseTo(0.2126, 6);
    expect(relativeLuminance({ r8: 0, g8: 255, b8: 0 })).toBeCloseTo(0.7152, 6);
    expect(relativeLuminance({ r8: 0, g8: 0, b8: 255 })).toBeCloseTo(0.0722, 6);
  });

  it('the OKLab L of mid-grey matches the published matrices (not an approximation)', () => {
    // 50% grey: a known fixed point of the B3-A matrices. The value is fully determined by the
    // matrices — if a coefficient is wrong, this drifts.
    const lab = srgbToOkLab({ r: 0.5, g: 0.5, b: 0.5 });
    expect(lab.l).toBeCloseTo(0.5981807, 5); // computed from the verbatim B3-A matrices
    expect(lab.a).toBeCloseTo(0, 6);
    expect(lab.b).toBeCloseTo(0, 6);
  });
});

describe('design-correctness: the lightness ladder & chroma curve are the cited research arrays', () => {
  it('the lightness ladder is the verbatim Tailwind-v4 OKLCH L set (Table B3-B)', () => {
    expect(LIGHTNESS_LADDER).toEqual([
      0.978, 0.936, 0.881, 0.827, 0.742, 0.648, 0.573, 0.469, 0.394, 0.32, 0.238,
    ]);
  });

  it('the chroma envelope peaks in the mid-tones and falls toward both extremes (B3-C)', () => {
    const peak = Math.max(...CHROMA_ENVELOPE);
    const peakIndex = CHROMA_ENVELOPE.indexOf(peak);
    expect(peak).toBeCloseTo(0.147, 6); // research: "peaks ~0.147 at step 400"
    expect(peakIndex).toBe(5); // step 500 region (index 5 = ramp step 500, neighbour of 400)
    expect(CHROMA_ENVELOPE[0]!).toBeLessThan(peak); // falls toward white
    expect(CHROMA_ENVELOPE[10]!).toBeLessThan(peak); // falls toward black
  });
});

describe('design-correctness: the type scale is geometrically derived (B1)', () => {
  it('reproduces the research B1 worked ladder (base 16, ratio 1.25 → 10/13/16/20/25/31/39/49)', () => {
    const ladder = [];
    for (let i = -2; i <= 5; i++) ladder.push(Math.round(typeSizePx(i, 16, 1.25)));
    expect(ladder).toEqual([10, 13, 16, 20, 25, 31, 39, 49]);
  });

  it('the C21 theme re-derives every type size from base·ratio^i — never a hand-set value (D2)', () => {
    const theme = generateTheme(C21_SEED);
    const base = C21_SEED.baseSizePx!;
    const ratio = C21_SEED.typeRatio!;
    // body (i=0) must be the base; each role's size must equal the formula at its index.
    const indexByName: Record<string, number> = {
      'display-large': 5,
      'display-small': 4,
      headline: 3,
      title: 2,
      'body-large': 1,
      body: 0,
      label: -1,
      caption: -2,
    };
    for (const role of theme.typography) {
      const i = indexByName[role.name]!;
      expect(role.fontSizePx).toBeCloseTo(base * ratio ** i, 10);
    }
  });

  it('floors EVERY body role line-height at the WCAG 1.4.12 ≥1.5× (computed, not assumed)', () => {
    const theme = generateTheme(C21_SEED);
    for (const role of theme.typography) {
      if (role.name.startsWith('body')) {
        expect(role.lineHeight).toBeGreaterThanOrEqual(1.5);
      }
    }
  });
});

describe('design-correctness: spacing is on the 4px grid (B2) — brand-invariant', () => {
  it('matches the Refactoring-UI ramp px values (the cited Table B2-A)', () => {
    const byName = new Map(generateSpacingRamp().map((t) => [t.name, t.px]));
    expect(byName.get('space-1')).toBe(4);
    expect(byName.get('space-2')).toBe(8);
    expect(byName.get('space-4')).toBe(16);
    expect(byName.get('space-6')).toBe(24);
    expect(byName.get('space-12')).toBe(48);
    expect(byName.get('space-16')).toBe(64);
  });

  it('the breakpoints are the Material window classes (Table B2-B, resolved-as-default)', () => {
    expect(BREAKPOINTS.map((b) => b.minWidthPx)).toEqual([0, 600, 840, 1200, 1600]);
  });

  it('the touch-target floors are the WCAG/Apple/Material hard minimums (Table B2-D)', () => {
    expect(TARGET_FLOOR_PX).toEqual({ wcagAa: 24, wcagAaa: 44, material: 48 });
  });
});

describe('design-correctness: motion constants are the M3-verbatim values (B5)', () => {
  it('the easing set is the M3 verbatim cubic-beziers (Table B5-B)', () => {
    expect(EASING['standard']).toEqual([0.2, 0, 0, 1]);
    expect(EASING['standard-decelerate']).toEqual([0, 0, 0, 1]); // enter
    expect(EASING['standard-accelerate']).toEqual([0.3, 0, 1, 1]); // exit
    expect(EASING['emphasized-decelerate']).toEqual([0.05, 0.7, 0.1, 1]);
  });

  it('the emphasized easing is the two-segment SPLINE, not a single bezier (correction #4)', () => {
    // The spline path is the verbatim research value; a single bezier cannot represent it.
    expect(EMPHASIZED_SPLINE_PATH).toContain('C 0.05,0 0.133333,0.06 0.166666,0.4');
  });

  it('the duration ladder is 50ms steps to 600 then 100ms to 1000 (Table B5-A)', () => {
    expect(DURATION_LADDER['short.1']).toBe(50);
    expect(DURATION_LADDER['medium.2']).toBe(300);
    expect(DURATION_LADDER['long.4']).toBe(600);
    expect(DURATION_LADDER['extra-long.4']).toBe(1000);
  });

  it('spring damping is the corrected iOS-17 math: ζ = 1 − bounce (B5-C)', () => {
    expect(spring(0.5, 0).dampingRatio).toBeCloseTo(1, 6); // critically damped
    expect(spring(0.5, 0.15).dampingRatio).toBeCloseTo(0.85, 6);
    expect(spring(0.5, 0.3).dampingRatio).toBeCloseTo(0.7, 6);
  });
});

describe('design-correctness: the C21 SEEDS are the locked founder values (D2 — immutable)', () => {
  it('carries the five locked colors as seeds (Moss/Sage/Deep-Forest/Ink + Bone surface)', () => {
    expect(C21_SEED.hues.primary).toBe('#5C7F5C'); // Moss
    expect(C21_SEED.hues.secondary).toBe('#A8B89C'); // Sage
    expect(C21_SEED.hues.tertiary).toBe('#243D2C'); // Deep Forest
    expect(C21_SEED.hues.neutral).toBe('#1A1A1A'); // Ink
    expect(C21_SURFACE.paper).toBe('#F4F1E8'); // Bone
  });

  it('carries the three locked font families', () => {
    expect(C21_SEED.fonts).toEqual({
      display: 'Fraunces',
      text: 'Inter',
      code: 'JetBrains Mono',
    });
  });

  it('pins the Moss seed bit-exact at its ramp step (brand identity survives generation; B3-E)', () => {
    const theme = generateTheme(C21_SEED);
    const moss = hexToOkLch(C21_SEED.hues.primary);
    const pinned = theme.ramps.primary.steps[theme.ramps.primary.seedStep];
    expect(pinned.l).toBeCloseTo(moss.l, 6);
    expect(pinned.h).toBeCloseTo(moss.h, 6);
  });
});

describe('design-correctness: the CONTRAST GATE is satisfied by construction (the hard constraint)', () => {
  it('EVERY on-* foreground in the light C21 theme meets its WCAG target (unrounded)', () => {
    const t = generateTheme(C21_SEED, { mode: 'light', level: 'AA' });
    const pairs = [
      [t.roles.onSurface, t.roles.surface],
      [t.roles.onPrimary, t.roles.primary],
      [t.roles.onPrimaryContainer, t.roles.primaryContainer],
      [t.roles.onError, t.roles.error],
      [t.roles.outline, t.roles.surface],
    ] as const;
    for (const [fg, bg] of pairs) {
      expect(fg.contrast).toBeDefined();
      const ratio = wcagContrastRatio(
        srgbTo8(okLchToSrgb(fg.value)),
        srgbTo8(okLchToSrgb(bg.value)),
      );
      // the audit ratio matches the recomputed ratio (the proof is honest)…
      expect(fg.contrast!.ratio).toBeCloseTo(ratio, 4);
      // …and the pair meets its recorded target (unrounded — the hard constraint).
      expect(ratio).toBeGreaterThanOrEqual(fg.contrast!.target);
    }
  });

  it('the gate holds in DARK mode too (where WCAG 2 under-protects — APCA advisory recorded)', () => {
    const t = generateTheme(C21_SEED, { mode: 'dark', level: 'AA' });
    const ratio = wcagContrastRatio(
      srgbTo8(okLchToSrgb(t.roles.onSurface.value)),
      srgbTo8(okLchToSrgb(t.roles.surface.value)),
    );
    expect(ratio).toBeGreaterThanOrEqual(4.5);
    // the advisory APCA Lc is recorded (non-blocking — OD-17-apca resolved-as-default).
    expect(typeof t.roles.onSurface.contrast!.apcaLc).toBe('number');
  });

  it('the Bone/Ink paper-ink pair clears AAA body contrast (the C21 reading surface)', () => {
    // The two locked surface colors must form a high-contrast reading pair by construction.
    const ratio = wcagContrastRatio(parseHex(C21_SURFACE.ink), parseHex(C21_SURFACE.paper));
    expect(ratio).toBeGreaterThanOrEqual(7); // AAA normal text
    // APCA agrees it is a strong dark-on-light pair.
    expect(apcaLc(parseHex(C21_SURFACE.ink), parseHex(C21_SURFACE.paper))).toBeGreaterThan(90);
  });
});

describe('design-correctness: the three-step density mode keeps EVERY mode accessible (B6, OD-17-c21)', () => {
  it('offers exactly three modes, ordered loosest → densest, with the middle recommended', () => {
    expect(DENSITY_MODES).toEqual(['relaxed', 'standard', 'dense']);
    // the recommended mode is literally the MIDDLE of the ordered control (founder: "middle recommended").
    expect(RECOMMENDED_DENSITY_MODE).toBe(DENSITY_MODES[1]);
    // the density STEP is strictly monotonic decreasing across the modes — "dense" is genuinely denser.
    const steps = DENSITY_MODES.map((m) => DENSITY_STEP[DENSITY_MODE_TIER[m]]);
    expect(steps[0]!).toBeGreaterThan(steps[1]!);
    expect(steps[1]!).toBeGreaterThan(steps[2]!);
  });

  it('the expert/Eden mode is the agent default tier — the two rulings agree (no drift)', () => {
    // founder: "high density for expert users, directly applicable to Eden itself". Eden's agent
    // surfaces already default to `compact` (OD-17-density-default) — the expert mode must resolve there.
    expect(densityTierForMode(EXPERT_DENSITY_MODE)).toBe(DEFAULT_DENSITY.agent);
  });

  it('the 44px TOUCH floor holds the hit target in ALL three modes — even the densest (the hard a11y constraint)', () => {
    // default targetContext is `touch` (44px AAA floor). The visual box shrinks with density; the
    // DECOUPLED hit target must never fall below 44 — accessible by construction at any density.
    for (const mode of DENSITY_MODES) {
      const t = generateTheme(C21_SEED, { density: densityTierForMode(mode) });
      expect(t.controlGeometry.hitTargetPx).toBeGreaterThanOrEqual(44);
      // I7: the font size is INVARIANT under density — density never scales type.
      expect(t.controlGeometry.fontSizePx).toBe(14);
      // the visual geometry stays on the 4px grid in every mode (snap4).
      expect(t.controlGeometry.componentHeightPx % 4).toBe(0);
      expect(t.controlGeometry.insetPx % 4).toBe(0);
    }
  });

  it('WEAKEN-TO-CONFIRM: a pointer-only context drops the densest hit target BELOW 44 (the touch default does real work)', () => {
    // The touch default is non-vacuous: with pointer (24px floor) the dense visual box (32px) yields a
    // 32px hit target — below 44. Proves the touch default is what guarantees the AAA tap area, not luck.
    const dense = densityTierForMode(EXPERT_DENSITY_MODE);
    const touch = generateTheme(C21_SEED, { density: dense }); // default targetContext = touch
    const pointer = generateTheme(C21_SEED, { density: dense, targetContext: 'pointer' });
    expect(touch.controlGeometry.hitTargetPx).toBeGreaterThanOrEqual(44);
    expect(pointer.controlGeometry.hitTargetPx).toBeLessThan(44);
    // …and the VISUAL box is identical either way — only the decoupled hit target differs (I1/I2).
    expect(pointer.controlGeometry.componentHeightPx).toBe(touch.controlGeometry.componentHeightPx);
  });
});
