/**
 * Motion & elevation — duration ladder, easing, springs, shadow, z-index (research §B.5).
 *
 * Motion serves cognition (focus attention, maintain continuity), the only defensible reason to
 * ship it. The duration LADDER (Table B5-A) and the easing SET (Table B5-B) are the Material 3
 * verified tokens. The `emphasized` easing is a two-segment spline a single bezier cannot
 * represent (verifier correction #4) → it ships a CSS `linear()` fallback. Springs use the iOS-17
 * two-parameter model (Formula B5-C, corrected damping). Shadows are the Comeau/Ahlin parametric
 * layered generator (OD-17-shadow resolved-as-default) with Material opacity anchors. z-index is a
 * static ordinal scale (Table B5-F).
 *
 * OD-17-spring resolved-as-default: `.snappy`/`.bouncy` shipped TAGGED practitioner-measured.
 * OD-17-motion-personality resolved-as-default: a single neutral personality in v1 (conservative);
 * the brand→personality hook is present but defers to neutral.
 */

/** The duration ladder, ms (research Table B5-A: 50ms steps to 600, then 100ms to 1000). */
export const DURATION_LADDER = {
  'short.1': 50,
  'short.2': 100,
  'short.3': 150,
  'short.4': 200,
  'medium.1': 250,
  'medium.2': 300,
  'medium.3': 350,
  'medium.4': 400,
  'long.1': 450,
  'long.2': 500,
  'long.3': 550,
  'long.4': 600,
  'extra-long.1': 700,
  'extra-long.2': 800,
  'extra-long.3': 900,
  'extra-long.4': 1000,
} as const;

/** A duration ladder token name. */
export type DurationToken = keyof typeof DURATION_LADDER;

/** A cubic-bezier control-point quadruple `[x1, y1, x2, y2]` (the DTCG `cubicBezier` value). */
export type CubicBezier = readonly [number, number, number, number];

/** The easing set (research Table B5-B, M3 verbatim). `standard` is the default on-screen move. */
export const EASING: Readonly<Record<string, CubicBezier>> = Object.freeze({
  linear: [0, 0, 1, 1],
  standard: [0.2, 0, 0, 1],
  'standard-decelerate': [0, 0, 0, 1], // enter
  'standard-accelerate': [0.3, 0, 1, 1], // exit
  'emphasized-decelerate': [0.05, 0.7, 0.1, 1],
  'emphasized-accelerate': [0.3, 0, 0.8, 0.15],
});

/**
 * The `emphasized` easing is a TWO-SEGMENT spline a single cubic-bezier CANNOT represent (verifier
 * correction #4); `cubic-bezier(0.2,0,0,1)` is literally the `standard` curve, only an
 * approximation. The research mandates a CSS `linear()` fallback (sample the spline). This is the
 * verbatim path; {@link emphasizedLinearFallback} samples it into a `linear()` string.
 */
export const EMPHASIZED_SPLINE_PATH =
  'M 0,0 C 0.05,0 0.133333,0.06 0.166666,0.4 C 0.208333,0.82 0.25,1 1,1';

/**
 * Sample the `emphasized` two-segment cubic spline into a CSS `linear()` easing fallback (research
 * §B.5 correction #4). The path is two cubic Béziers in (progress, value) space joined at x=1/6;
 * we evaluate each at uniform x-samples and emit the `linear(v0, v1, …)` value list. n samples.
 */
export function emphasizedLinearFallback(samples = 16): string {
  // First segment: C0=(0,0) C1=(0.05,0) C2=(0.133333,0.06) C3=(0.166666,0.4).
  // Second segment: C0=(0.166666,0.4) C1=(0.208333,0.82) C2=(0.25,1) C3=(1,1).
  const seg1 = [
    [0, 0],
    [0.05, 0],
    [0.133333, 0.06],
    [0.166666, 0.4],
  ] as const;
  const seg2 = [
    [0.166666, 0.4],
    [0.208333, 0.82],
    [0.25, 1],
    [1, 1],
  ] as const;

  type Point = readonly [number, number];
  type Segment = readonly [Point, Point, Point, Point];

  const cubic = (p: Segment, t: number, axis: 0 | 1): number => {
    const mt = 1 - t;
    return (
      mt ** 3 * p[0][axis] +
      3 * mt ** 2 * t * p[1][axis] +
      3 * mt * t ** 2 * p[2][axis] +
      t ** 3 * p[3][axis]
    );
  };

  // Solve for the parameter t on a segment whose Bézier x equals a target x (monotone x → bisect).
  const valueAtX = (p: Segment, targetX: number): number => {
    let lo = 0;
    let hi = 1;
    for (let i = 0; i < 24; i++) {
      const mid = (lo + hi) / 2;
      if (cubic(p, mid, 0) < targetX) lo = mid;
      else hi = mid;
    }
    return cubic(p, (lo + hi) / 2, 1);
  };

  const round = (x: number): number => Math.round(x * 10000) / 10000;
  const values: string[] = [];
  for (let i = 0; i <= samples; i++) {
    const x = i / samples;
    const v = x <= 0.166666 ? valueAtX(seg1, x) : valueAtX(seg2, x);
    values.push(String(round(v)));
  }
  return `linear(${values.join(', ')})`;
}

/** A spring's two perceptual knobs + the derived physical parameters (research Formula B5-C). */
export interface Spring {
  /** Settling-time knob, seconds (research B5-C `duration`). */
  readonly durationSec: number;
  /** Bounce ∈ [−1, 1]: 0 critically damped, 0.3 ≈ visible overshoot (research B5-C). */
  readonly bounce: number;
  /** Derived stiffness `(2π/duration)²` (mass=1). */
  readonly stiffness: number;
  /** Derived damping (research B5-C, corrected). */
  readonly damping: number;
  /** Damping ratio ζ = 1 − bounce for bounce ≥ 0 (research B5-C: "bounce is just 1−ζ"). */
  readonly dampingRatio: number;
}

/**
 * Derive a spring from the iOS-17 two-parameter model (research Formula B5-C, corrected damping):
 *   mass=1; stiffness=(2π/duration)²;
 *   bounce ≥ 0: damping = 4π·(1−bounce)/duration;   bounce < 0: damping = 4π/(duration·(1+bounce)).
 *   ζ = damping/(2·√(stiffness·mass)); for bounce ≥ 0, ζ = 1 − bounce.
 */
export function spring(durationSec: number, bounce: number): Spring {
  const stiffness = ((2 * Math.PI) / durationSec) ** 2;
  const damping =
    bounce >= 0
      ? (4 * Math.PI * (1 - bounce)) / durationSec
      : (4 * Math.PI) / (durationSec * (1 + bounce));
  const dampingRatio = damping / (2 * Math.sqrt(stiffness)); // mass=1
  return { durationSec, bounce, stiffness, damping, dampingRatio };
}

/**
 * The spring presets (research Table B5-D). `.snappy`/`.bouncy` bounce constants are practitioner-
 * measured, NOT first-party Apple-documented (research ⚠️ / OD-17-spring resolved-as-default:
 * shipped TAGGED as such). `legacy` is the first-party-documented (0.55, 0.825) bridged to the new
 * model via `bounce = 1 − ζ ⇒ (0.55, 0.175)` (research B5-D verified re-derivation).
 */
export const SPRING_PRESETS = {
  smooth: { durationSec: 0.5, bounce: 0, firstParty: true },
  snappy: { durationSec: 0.5, bounce: 0.15, firstParty: false },
  bouncy: { durationSec: 0.5, bounce: 0.3, firstParty: false },
  legacy: { durationSec: 0.55, bounce: 0.175, firstParty: true },
} as const;

/** A single shadow layer (the DTCG `shadow` composite is an ARRAY of these). */
export interface ShadowLayer {
  /** Horizontal offset, px (research B5-E: `x = y/2`). */
  readonly offsetXPx: number;
  /** Vertical offset, px. */
  readonly offsetYPx: number;
  /** Blur radius, px (research B5-E: `blur = 2·y`). */
  readonly blurPx: number;
  /** Layer opacity (research B5-E: falls with layer index). */
  readonly alpha: number;
}

/** The shadow generator's per-mode opacity seed (research B5-E: 0.10–0.13 light / 0.18–0.22 dark). */
export const SHADOW_ALPHA0 = { light: 0.12, dark: 0.2 } as const;

/**
 * The parametric layered shadow generator (research Formula B5-E; OD-17-shadow resolved-as-default:
 * the Comeau/Ahlin parametric generator with Material opacities as anchors). For elevation `e`,
 * stacking `layers` shadows:
 *   base_offset(e) = round(a·e^p), a≈0.5, p≈1.3;
 *   y_i = base_offset·(2^i)/(2^k);  x_i = y_i/2;  blur_i = 2·y_i;
 *   alpha_i = a0·(1 − i/(k+1)).
 * Dark mode carries depth by surface lightening too (research §B.5 "Dark-mode rule") — that lives
 * in the elevation-overlay token; here we raise alpha0 for dark.
 */
export function layeredShadow(
  elevation: number,
  layers = 4,
  mode: 'light' | 'dark' = 'light',
): readonly ShadowLayer[] {
  const a = 0.5;
  const p = 1.3;
  const a0 = SHADOW_ALPHA0[mode];
  const baseOffset = Math.round(a * elevation ** p);
  const k = layers;
  const out: ShadowLayer[] = [];
  for (let i = 0; i < layers; i++) {
    const y = (baseOffset * 2 ** i) / 2 ** k;
    out.push({
      offsetXPx: y / 2,
      offsetYPx: y,
      blurPx: 2 * y,
      alpha: a0 * (1 - i / (k + 1)),
    });
  }
  return out;
}

/** The z-index ordinal scale (research Table B5-F, gapped 100). Stacking ORDER, not shadow depth. */
export const Z_INDEX = {
  base: 0,
  raised: 10,
  dropdown: 1000,
  sticky: 1100,
  drawer: 1200,
  modal: 1300,
  snackbar: 1400,
  tooltip: 1500,
  max: 2147483647,
} as const;
