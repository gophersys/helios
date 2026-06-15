import { describe, expect, it } from 'vitest';
import {
  // color science
  srgbToOkLab,
  okLabToSrgb,
  srgbToOkLch,
  okLchToSrgb,
  srgbChannelToLinear,
  // codec
  parseHex,
  formatHex,
  hexToOkLch,
  srgbTo8,
  srgb8To,
  okLchTo8,
  HexParseError,
  // gamut
  gamutMapOkLch,
  // contrast
  relativeLuminance,
  wcagContrastRatio,
  wcagTarget,
  wcagPasses,
  apcaLc,
  nearestPassingForeground,
  // ramps
  generateRamp,
  nearestRampStep,
  RAMP_STEPS,
  LIGHTNESS_LADDER,
  // typography
  typeSizePx,
  lineHeight,
  trackingEm,
  fluidType,
  BODY_LINE_HEIGHT_FLOOR,
  // spacing
  generateSpacingRamp,
  BREAKPOINTS,
  BASE_UNIT_PX,
  // density
  densify,
  snap4,
  DENSITY_STEP,
  // motion
  spring,
  layeredShadow,
  emphasizedLinearFallback,
  EASING,
  SPRING_PRESETS,
  // seed + generate
  C21_SEED,
  generateTheme,
  themeToCssVariables,
  oklchToCss,
} from './index.js';

describe('OKLab/OKLCH conversion (research B3-A, verbatim matrices)', () => {
  it('maps sRGB white to OKLab L≈1 and round-trips exactly', () => {
    const lab = srgbToOkLab({ r: 1, g: 1, b: 1 });
    expect(lab.l).toBeCloseTo(1, 5);
    expect(lab.a).toBeCloseTo(0, 4);
    expect(lab.b).toBeCloseTo(0, 4);
    const back = okLabToSrgb(lab);
    expect(back.r).toBeCloseTo(1, 6);
    expect(back.g).toBeCloseTo(1, 6);
    expect(back.b).toBeCloseTo(1, 6);
  });

  it('maps sRGB black to OKLab L≈0', () => {
    expect(srgbToOkLab({ r: 0, g: 0, b: 0 }).l).toBeCloseTo(0, 6);
  });

  it('round-trips an arbitrary color sRGB→OKLCH→sRGB', () => {
    const srgb = { r: 0.36, g: 0.5, b: 0.36 }; // ~moss
    const back = okLchToSrgb(srgbToOkLch(srgb));
    expect(back.r).toBeCloseTo(srgb.r, 5);
    expect(back.g).toBeCloseTo(srgb.g, 5);
    expect(back.b).toBeCloseTo(srgb.b, 5);
  });

  it('uses the corrected 0.04045 gamma threshold (research correction #1)', () => {
    // continuity at the boundary: both branches agree to float epsilon at 0.04045.
    const below = srgbChannelToLinear(0.04045);
    const above = srgbChannelToLinear(0.0404500001);
    expect(Math.abs(below - above)).toBeLessThan(1e-6);
  });
});

describe('hex codec — the seed crossing (research B3-A/B4-A)', () => {
  it('parses #rrggbb and #rgb', () => {
    expect(parseHex('#5C7F5C')).toEqual({ r8: 0x5c, g8: 0x7f, b8: 0x5c });
    expect(parseHex('#abc')).toEqual({ r8: 0xaa, g8: 0xbb, b8: 0xcc });
  });

  it('round-trips a hex through OKLCH and back within a quantization step', () => {
    const oklch = hexToOkLch('#5C7F5C');
    expect(formatHex(srgbTo8(okLchToSrgb(oklch)))).toBe('#5c7f5c');
  });

  it('rejects a malformed hex by type (rule 12)', () => {
    expect(() => parseHex('not-a-color')).toThrow(HexParseError);
    expect(() => parseHex('#12')).toThrow(HexParseError);
  });
});

describe('gamut mapping (research B3-D)', () => {
  it('returns an in-gamut color unchanged', () => {
    const inGamut = srgbToOkLch({ r: 0.5, g: 0.5, b: 0.5 });
    expect(gamutMapOkLch(inGamut)).toEqual(inGamut);
  });

  it('reduces chroma until in-gamut for an impossible high-chroma request', () => {
    const mapped = gamutMapOkLch({ l: 0.6, c: 0.4, h: 150 });
    expect(mapped.c).toBeLessThan(0.4);
    // the mapped color must now render inside [0,1].
    const srgb = okLchToSrgb(mapped);
    for (const ch of [srgb.r, srgb.g, srgb.b]) {
      expect(ch).toBeGreaterThanOrEqual(-1e-6);
      expect(ch).toBeLessThanOrEqual(1 + 1e-6);
    }
  });

  it('collapses L≥1 to white and L≤0 to black (the documented escapes)', () => {
    expect(gamutMapOkLch({ l: 1.2, c: 0.1, h: 30 })).toEqual({ l: 1, c: 0, h: 30 });
    expect(gamutMapOkLch({ l: -0.1, c: 0.1, h: 30 })).toEqual({ l: 0, c: 0, h: 30 });
  });
});

describe('WCAG contrast (research B4-A/B4-B, exact + unrounded)', () => {
  const white = { r8: 255, g8: 255, b8: 255 };
  const black = { r8: 0, g8: 0, b8: 0 };

  it('black on white is exactly 21:1', () => {
    expect(wcagContrastRatio(black, white)).toBeCloseTo(21, 10);
  });

  it('a color against itself is exactly 1:1', () => {
    expect(wcagContrastRatio(white, white)).toBe(1);
  });

  it('relative luminance of white is 1 and black is 0', () => {
    expect(relativeLuminance(white)).toBeCloseTo(1, 10);
    expect(relativeLuminance(black)).toBe(0);
  });

  it('encodes the Table B4-B thresholds', () => {
    expect(wcagTarget('normal-text', 'AA')).toBe(4.5);
    expect(wcagTarget('normal-text', 'AAA')).toBe(7);
    expect(wcagTarget('large-text', 'AA')).toBe(3);
    expect(wcagTarget('large-text', 'AAA')).toBe(4.5);
    expect(wcagTarget('ui-component', 'AA')).toBe(3);
  });

  it('is UNROUNDED: 4.499:1 does NOT meet 4.5:1 (research no-rounding rule)', () => {
    // A grey at exactly the boundary — construct a pair just under 4.5 and confirm it fails.
    // #767676 on white ≈ 4.54:1 (passes); #777777 on white ≈ 4.48:1 (fails) — the classic pair.
    const passGrey = parseHex('#767676');
    const failGrey = parseHex('#777777');
    expect(wcagPasses(passGrey, white, 'normal-text', 'AA')).toBe(true);
    expect(wcagPasses(failGrey, white, 'normal-text', 'AA')).toBe(false);
  });
});

describe('APCA (research B4-C, advisory) — signed, polarity-aware', () => {
  it('is positive for dark-on-light and negative for light-on-dark', () => {
    const black = { r8: 0, g8: 0, b8: 0 };
    const white = { r8: 255, g8: 255, b8: 255 };
    expect(apcaLc(black, white)).toBeGreaterThan(90); // dark text on light bg
    expect(apcaLc(white, black)).toBeLessThan(-90); // light text on dark bg
  });

  it('returns 0 for an indistinguishable pair', () => {
    const grey = { r8: 128, g8: 128, b8: 128 };
    expect(apcaLc(grey, grey)).toBe(0);
  });
});

describe('the inverse gate (research B4-E) — has TEETH', () => {
  const white = { r8: 255, g8: 255, b8: 255 };

  it('accepts a seed that already passes (action=accept, deltaL=0)', () => {
    const darkSeed = hexToOkLch('#1a1a1a');
    const r = nearestPassingForeground(darkSeed, white, 'normal-text', 'AA');
    expect(r.pass).toBe(true);
    expect(r.action).toBe('accept');
    expect(r.deltaL).toBe(0);
  });

  it('REPAIRS a failing on-brand foreground to the nearest passing one', () => {
    // A light moss against white fails 4.5:1 — the gate must darken it until it passes.
    const lightMoss = { l: 0.75, c: 0.06, h: 145 };
    const before = wcagContrastRatio(srgbTo8(okLchToSrgb(lightMoss)), white);
    expect(before).toBeLessThan(4.5); // precondition: the seed really fails
    const r = nearestPassingForeground(lightMoss, white, 'normal-text', 'AA');
    expect(r.pass).toBe(true);
    expect(r.action).toBe('lightness-shift');
    expect(r.achievedRatio).toBeGreaterThanOrEqual(4.5);
    // hue/chroma stay on-brand — only L moved.
    expect(r.suggestedForeground.h).toBe(lightMoss.h);
    expect(r.suggestedForeground.c).toBe(lightMoss.c);
    expect(r.suggestedForeground.l).toBeLessThan(lightMoss.l); // darkened toward black
  });

  it('clamps to the extreme when even L=0/1 cannot reach the target', () => {
    // AAA (7:1) text against a mid-grey background is unreachable → clamped.
    const midGrey = { r8: 130, g8: 130, b8: 130 };
    const seed = { l: 0.5, c: 0.0, h: 0 };
    const r = nearestPassingForeground(seed, midGrey, 'normal-text', 'AAA');
    expect(r.action).toBe('clamped');
  });
});

describe('color ramps (research B3-B/B3-C)', () => {
  it('generates all 11 steps holding hue constant', () => {
    const ramp = generateRamp({ l: 0.56, c: 0.066, h: 144.6 });
    for (const step of RAMP_STEPS) {
      expect(ramp.steps[step].h).toBeCloseTo(144.6, 6);
    }
  });

  it('pins the seed at its nearest ladder step (brand identity survives)', () => {
    const seed = { l: 0.56, c: 0.066, h: 144.6 };
    const ramp = generateRamp(seed);
    // the seed step's lightness is the seed's exact L (pinned), not the ladder value.
    expect(ramp.steps[ramp.seedStep].l).toBeCloseTo(seed.l, 6);
  });

  it('snaps a target lightness to the nearest ramp step', () => {
    expect(nearestRampStep(LIGHTNESS_LADDER[0]!)).toBe(50); // brightest
    expect(nearestRampStep(LIGHTNESS_LADDER[10]!)).toBe(950); // darkest
  });
});

describe('typography (research B1)', () => {
  it('generates the geometric scale size(i)=base·ratio^i', () => {
    expect(typeSizePx(0, 16, 1.25)).toBe(16);
    expect(typeSizePx(1, 16, 1.25)).toBe(20);
    expect(typeSizePx(-1, 16, 1.25)).toBeCloseTo(12.8, 10);
  });

  it('floors body line-height at 1.5× (WCAG 1.4.12)', () => {
    expect(lineHeight(16, 60, true)).toBeGreaterThanOrEqual(BODY_LINE_HEIGHT_FLOOR);
  });

  it('reproduces the research B1-B worked fluid example exactly', () => {
    const fluid = fluidType(36, 52, { minViewportPx: 600, maxViewportPx: 1400 });
    expect(fluid.css).toBe('clamp(2.25rem, 2vw + 1.5rem, 3.25rem)');
    expect(fluid.slopeVw).toBe(2);
  });
});

describe('spacing (research B2) — brand-invariant', () => {
  it('every rung is an integer px; whole-number rungs are 4px multiples (the half-step is 2px)', () => {
    for (const token of generateSpacingRamp()) {
      expect(Number.isInteger(token.px)).toBe(true);
      // space-0.5 is the deliberate sub-grid 2px half-step (3xs); all whole-number rungs land on
      // the 4px grid (research Table B2-A).
      if (token.name !== 'space-0.5') {
        expect(token.px % BASE_UNIT_PX).toBe(0);
      }
    }
  });

  it('space-4 is 16px (the md base) and space-6 is 24px (the baseline)', () => {
    const ramp = generateSpacingRamp();
    expect(ramp.find((t) => t.name === 'space-4')?.px).toBe(16);
    expect(ramp.find((t) => t.name === 'space-6')?.px).toBe(24);
  });

  it('encodes the Material window-class breakpoints (research B2-B)', () => {
    expect(BREAKPOINTS.map((b) => b.minWidthPx)).toEqual([0, 600, 840, 1200, 1600]);
  });
});

describe('density (research B6) — invariants never violated', () => {
  it('encodes the named-tier steps (Table B6-C)', () => {
    expect(DENSITY_STEP).toEqual({ spacious: 1, comfortable: 0, compact: -2, condensed: -3 });
  });

  it('NEVER scales font or icon size (invariant I7)', () => {
    const base = { componentHeightPx: 40, insetPx: 12, gapPx: 16, fontSizePx: 14, iconSizePx: 20 };
    for (const tier of ['spacious', 'comfortable', 'compact', 'condensed'] as const) {
      const g = densify(base, tier);
      expect(g.fontSizePx).toBe(14);
      expect(g.iconSizePx).toBe(20);
    }
  });

  it('floors body line-height at 1.5×font even at the densest tier (I3)', () => {
    const base = { componentHeightPx: 40, insetPx: 12, gapPx: 16, fontSizePx: 14, iconSizePx: 20 };
    const g = densify(base, 'condensed');
    expect(g.lineHeightPx).toBeGreaterThanOrEqual(1.5 * 14);
  });

  it('keeps the hit target ≥ the floor even as the visual box shrinks (I1, touch)', () => {
    const base = { componentHeightPx: 40, insetPx: 12, gapPx: 16, fontSizePx: 14, iconSizePx: 20 };
    const g = densify(base, 'condensed', 'touch');
    expect(g.hitTargetPx).toBeGreaterThanOrEqual(44);
    expect(g.componentHeightPx).toBeLessThan(g.hitTargetPx); // decoupled
  });

  it('snaps to the 4px grid', () => {
    expect(snap4(13)).toBe(12);
    expect(snap4(14)).toBe(16);
  });
});

describe('motion (research B5)', () => {
  it('derives a critically-damped spring (bounce 0 → ζ 1)', () => {
    const s = spring(0.5, 0);
    expect(s.dampingRatio).toBeCloseTo(1, 6);
  });

  it('a bouncy spring has ζ = 1 − bounce', () => {
    expect(spring(0.5, 0.3).dampingRatio).toBeCloseTo(0.7, 6);
  });

  it('layers a parametric shadow with x=y/2 and blur=2y', () => {
    for (const layer of layeredShadow(8, 4, 'light')) {
      expect(layer.offsetXPx).toBeCloseTo(layer.offsetYPx / 2, 10);
      expect(layer.blurPx).toBeCloseTo(2 * layer.offsetYPx, 10);
    }
  });

  it('emits a CSS linear() fallback for the emphasized two-segment spline (correction #4)', () => {
    const fallback = emphasizedLinearFallback(8);
    expect(fallback.startsWith('linear(')).toBe(true);
    expect(fallback).toContain('0,');
    expect(fallback.endsWith(')')).toBe(true);
  });

  it('the standard easing is the M3 default cubic-bezier(0.2,0,0,1)', () => {
    expect(EASING['standard']).toEqual([0.2, 0, 0, 1]);
  });
});

describe('generateTheme(C21_SEED) — the full pipeline (research C.3)', () => {
  it('produces a complete light theme', () => {
    const theme = generateTheme(C21_SEED, { mode: 'light' });
    expect(theme.mode).toBe('light');
    expect(theme.typography).toHaveLength(8);
    expect(theme.spacing.length).toBeGreaterThan(10);
    expect(theme.breakpoints).toHaveLength(5);
  });

  it('GATES every on-* foreground against its surface (the hard constraint)', () => {
    const theme = generateTheme(C21_SEED, { mode: 'light', level: 'AA' });
    const gated = [
      [theme.roles.onSurface, theme.roles.surface, 4.5],
      [theme.roles.onPrimary, theme.roles.primary, 4.5],
      [theme.roles.outline, theme.roles.surface, 3.0],
    ] as const;
    for (const [fg, bg, target] of gated) {
      expect(fg.contrast).toBeDefined();
      const ratio = wcagContrastRatio(
        srgbTo8(okLchToSrgb(fg.value)),
        srgbTo8(okLchToSrgb(bg.value)),
      );
      expect(ratio).toBeGreaterThanOrEqual(target);
      expect(fg.contrast!.ratio).toBeCloseTo(ratio, 4);
    }
  });

  it('re-derives C21 type sizes from the math (no hand-set irregular values; D2)', () => {
    const theme = generateTheme(C21_SEED);
    const body = theme.typography.find((t) => t.name === 'body');
    expect(body?.fontSizePx).toBe(16); // base·1.2^0
    const bodyLarge = theme.typography.find((t) => t.name === 'body-large');
    expect(bodyLarge?.fontSizePx).toBeCloseTo(16 * 1.2, 10);
  });

  it('renders dark mode by REMAPPING roles, not inverting (research B3 dark-mode)', () => {
    const light = generateTheme(C21_SEED, { mode: 'light' });
    const dark = generateTheme(C21_SEED, { mode: 'dark' });
    // dark surface is darker than light surface; dark on-surface is lighter than light on-surface.
    expect(dark.roles.surface.value.l).toBeLessThan(light.roles.surface.value.l);
    expect(dark.roles.onSurface.value.l).toBeGreaterThan(light.roles.onSurface.value.l);
  });

  it('applies density to control geometry while holding font invariant', () => {
    const compact = generateTheme(C21_SEED, { density: 'compact' });
    const comfortable = generateTheme(C21_SEED, { density: 'comfortable' });
    expect(compact.controlGeometry.componentHeightPx).toBeLessThan(
      comfortable.controlGeometry.componentHeightPx,
    );
    expect(compact.controlGeometry.fontSizePx).toBe(comfortable.controlGeometry.fontSizePx);
  });
});

describe('CSS emission (research C.4)', () => {
  it('emits oklch() custom properties for the role colors', () => {
    const css = themeToCssVariables(generateTheme(C21_SEED));
    expect(css).toContain('--color-primary: oklch(');
    expect(css).toContain('--space-4: 16px;');
    expect(css).toContain('--duration-medium-2: 300ms;');
  });

  it('renders an OKLCH color as a CSS oklch() function', () => {
    expect(oklchToCss({ l: 0.5, c: 0.1, h: 145 })).toBe('oklch(0.5 0.1 145)');
  });
});

describe('tracking (research B1-C) — crosses zero', () => {
  it('is positive for small text and trends negative for large display', () => {
    expect(trackingEm(11)).toBeGreaterThan(0); // small → positive
    expect(trackingEm(16)).toBeCloseTo(0, 6); // at base → ~0
    expect(trackingEm(57)).toBeLessThan(0); // display → negative
  });

  it('clamps to the [-0.03, +0.05]em bounds', () => {
    expect(trackingEm(2)).toBeLessThanOrEqual(0.05);
    expect(trackingEm(400)).toBeGreaterThanOrEqual(-0.03);
  });
});

describe('codec helpers round-trip', () => {
  it('srgb8To and srgbTo8 are inverse on 8-bit channels', () => {
    const c8 = { r8: 92, g8: 127, b8: 92 };
    expect(srgbTo8(srgb8To(c8))).toEqual(c8);
  });

  it('okLchTo8 quantizes an OKLCH color to 8-bit (clamping to gamut)', () => {
    // a wildly out-of-gamut request still yields valid 8-bit channels (clamped, not NaN).
    const c8 = okLchTo8({ l: 0.6, c: 0.4, h: 150 });
    for (const v of [c8.r8, c8.g8, c8.b8]) {
      expect(Number.isInteger(v)).toBe(true);
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(255);
    }
  });

  it('formatHex pads single-digit channels', () => {
    expect(formatHex({ r8: 1, g8: 2, b8: 3 })).toBe('#010203');
  });
});

describe('motion presets + elevation (research B5-D/B5-E)', () => {
  it('the legacy spring preset bridges (0.55, 0.825) → bounce 0.175 (ζ ≈ 0.825)', () => {
    expect(SPRING_PRESETS.legacy.bounce).toBeCloseTo(0.175, 6);
    expect(
      spring(SPRING_PRESETS.legacy.durationSec, SPRING_PRESETS.legacy.bounce).dampingRatio,
    ).toBeCloseTo(0.825, 6);
  });

  it('tags .snappy/.bouncy as practitioner-measured, not first-party (OD-17-spring)', () => {
    expect(SPRING_PRESETS.snappy.firstParty).toBe(false);
    expect(SPRING_PRESETS.bouncy.firstParty).toBe(false);
    expect(SPRING_PRESETS.smooth.firstParty).toBe(true);
  });

  it('dark-mode shadows carry a higher base opacity than light (research B5-E)', () => {
    const light = layeredShadow(8, 4, 'light')[0]!;
    const dark = layeredShadow(8, 4, 'dark')[0]!;
    expect(dark.alpha).toBeGreaterThan(light.alpha);
  });

  it('emphasized fallback samples BOTH spline segments (x past the 1/6 join)', () => {
    // a fine sampling crosses the join at x≈0.1667 — the second-segment branch must execute.
    const fallback = emphasizedLinearFallback(24);
    expect(fallback.split(',').length).toBeGreaterThan(20);
  });
});

describe('fluid type across a wider role range (research B1-B)', () => {
  it('produces a clamp() with a rem term for a large display role (WCAG 1.4.4)', () => {
    const fluid = fluidType(28, 40, { minViewportPx: 320, maxViewportPx: 1280 });
    expect(fluid.css).toContain('rem');
    expect(fluid.css.startsWith('clamp(')).toBe(true);
  });
});
