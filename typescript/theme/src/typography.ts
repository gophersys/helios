/**
 * Typography scale — type sizes, line-height, tracking, and fluid clamp (research §B.1).
 *
 * The type scale is a GEOMETRIC progression `size(i) = base · ratio^i` (the same generator as
 * `@eden/scale`, re-derived here so `@eden/theme` stays a dependency-free leaf — one concept, the
 * scale formula, is cited not re-invented). Line-height FALLS with size and RISES with measure
 * (Formula in B1-C), with the WCAG 1.4.12 hard floor that BODY line-height survives ≥1.5×.
 * Tracking crosses zero (positive small, negative display). Fluid type is the clamp() of B1-B, and
 * MUST keep a rem term (WCAG 1.4.4 — zoom must enlarge text).
 *
 * MATH IS SOURCE OF TRUTH (ADR-0024 §7): C21's hand-picked irregular sizes are RE-DERIVED through
 * this geometric generator (D2 / OD-17-c21), never pinned.
 */

/** The shared 16px origin for the type and spacing scales (research §B.1 / §B.2). */
export const BASE_SIZE_PX = 16;

/**
 * The default type ratio: the MINOR THIRD, 1.20 (research §B.1 Table B1-A, "the research default
 * for general UI/web"). OD-17-type-ratio resolved-as-default: 1.20 for general UI (1.25 marketing,
 * φ=1.618 opt-in only — never privileged, golden-ratio-as-beauty is research ⚠️ myth).
 */
export const DEFAULT_TYPE_RATIO = 1.2;

/** WCAG 1.4.12 hard floor: body line-height must survive a user override to ≥1.5× (research B1-C). */
export const BODY_LINE_HEIGHT_FLOOR = 1.5;

/** The line-height function calibration constants (research B1-C "Encodable line-height function"). */
const LH_A = 2.6;
const LH_B = 0.38;
const LH_C = 0.1;

/** The tracking function calibration constants (research B1-C "Tracking function"). */
const TRACK_K = 0.02;
const TRACK_W = 0.0; // weight term; 0 until a per-role weight axis is wired (kept explicit).
const TRACK_MIN_EM = -0.03;
const TRACK_MAX_EM = 0.05;

const clamp = (x: number, lo: number, hi: number): number => (x < lo ? lo : x > hi ? hi : x);

/** The geometric type-scale generator `size(i) = base · ratio^i` (research §B.1). */
export function typeSizePx(index: number, base = BASE_SIZE_PX, ratio = DEFAULT_TYPE_RATIO): number {
  return base * ratio ** index;
}

/**
 * Line-height as a function of size (px) and measure (ch), smooth + calibrated to Material 3
 * (research B1-C): `clamp(1.1, A − B·ln(size) + C·(measure−50)/50, 1.7)` with A=2.6, B=0.38, C=0.10
 * → ≈1.50 @16px, ≈1.33 @28px, ≈1.15 @57px. When `isBody`, the WCAG 1.4.12 ≥1.5× floor is applied.
 */
export function lineHeight(sizePx: number, measureCh = 60, isBody = false): number {
  const raw = clamp(LH_A - LH_B * Math.log(sizePx) + (LH_C * (measureCh - 50)) / 50, 1.1, 1.7);
  return isBody ? Math.max(raw, BODY_LINE_HEIGHT_FLOOR) : raw;
}

/**
 * Letter-spacing (tracking) in em as a function of size and weight (research B1-C "Tracking
 * function"): `clamp(−0.03, K·(16−size)/16 + W·(weight−400)/400, +0.05)`. Positive for small text,
 * negative for display — it crosses zero (research §B.1 Principles).
 */
export function trackingEm(sizePx: number, weight = 400): number {
  const raw = (TRACK_K * (16 - sizePx)) / 16 + (TRACK_W * (weight - 400)) / 400;
  return clamp(raw, TRACK_MIN_EM, TRACK_MAX_EM);
}

/** The fluid-type viewport endpoints, px (research B1-B verified worked example: 600→1400). */
export interface FluidRange {
  /** The min viewport, px. */
  readonly minViewportPx: number;
  /** The max viewport, px. */
  readonly maxViewportPx: number;
}

/** A resolved fluid-type value: the CSS `clamp(...)` string + its provenance for auditability. */
export interface FluidType {
  /** The CSS `clamp(min, preferred, max)` string — always carries a rem term (WCAG 1.4.4). */
  readonly css: string;
  /** The slope expressed in vw (`100·m`). */
  readonly slopeVw: number;
  /** The min/max viewport endpoints. */
  readonly range: FluidRange;
}

const REM = 16;
const round = (x: number, dp = 4): number => {
  const f = 10 ** dp;
  return Math.round(x * f) / f;
};

/**
 * Fluid type via clamp() (research Formula B1-B, exact constants). Given min/max sizes and the
 * viewport range: slope `m=(S₂−S₁)/(V₂−V₁)`, intercept `b=S₁−m·V₁`, slope-in-vw `100·m`, and the
 * rem-normalized `clamp(S₁/16 rem, (b/16)rem + (100·m)vw, S₂/16 rem)`. The rem term is mandatory
 * (research: "always keep a rem term … or zoom can't enlarge text → WCAG 1.4.4 fail").
 *
 * Verified worked example: 36→52px over 600→1400 ⇒ `clamp(2.25rem, 2vw + 1.5rem, 3.25rem)`.
 */
export function fluidType(minSizePx: number, maxSizePx: number, range: FluidRange): FluidType {
  const m = (maxSizePx - minSizePx) / (range.maxViewportPx - range.minViewportPx);
  const interceptPx = minSizePx - m * range.minViewportPx;
  const slopeVw = round(100 * m);
  const minRem = round(minSizePx / REM);
  const maxRem = round(maxSizePx / REM);
  const interceptRem = round(interceptPx / REM);
  const css = `clamp(${String(minRem)}rem, ${String(slopeVw)}vw + ${String(interceptRem)}rem, ${String(maxRem)}rem)`;
  return { css, slopeVw, range };
}
