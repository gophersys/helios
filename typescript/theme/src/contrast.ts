/**
 * The contrast gate — the HARD CONSTRAINT (docs/research/05-design-foundations.md §B.4).
 *
 * Unlike the rest of the engine, contrast is a hard, numeric, legally-load-bearing gate: a pair
 * passes or fails, the threshold is EXACT, and the spec FORBIDS rounding (`4.499:1` does NOT meet
 * `4.5:1`). Two regimes coexist:
 *   - WCAG 2.x — the MANDATORY legal gate (luminance-only). Formula B4-A, thresholds B4-B.
 *   - APCA (SA98G) — a better perceptual predictor but NON-NORMATIVE → ADVISORY only. Formula B4-C.
 *
 * Eden's policy (OD-17-apca, resolved-as-default below): WCAG 2.x is the only gate; APCA is stored
 * as a non-blocking warning. The generator INVERTS the gate (Algorithm B4-E): given a background +
 * brand hue, it finds the nearest on-brand foreground that passes by moving only OKLCH lightness.
 *
 * MATH IS SOURCE OF TRUTH (ADR-0024 §7): every constant is transcribed from §B.4; the 0.04045 and
 * APCA SA98G constants are the verifier-corrected values.
 */

import { okLchToSrgb, srgbChannelToLinear, type OkLch } from './oklch.js';
import { srgbTo8, type Srgb8 } from './srgb.js';

// ── WCAG 2.x relative luminance & contrast (Formula B4-A, exact constants) ────────────────────

/**
 * WCAG relative luminance of an 8-bit sRGB color (research B4-A). Linearizes each channel with the
 * corrected 0.04045 threshold (verifier correction #1), then the 0.2126/0.7152/0.0722 weights.
 */
export function relativeLuminance({ r8, g8, b8 }: Srgb8): number {
  const rl = srgbChannelToLinear(r8 / 255);
  const gl = srgbChannelToLinear(g8 / 255);
  const bl = srgbChannelToLinear(b8 / 255);
  return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl;
}

/**
 * The WCAG 2.x contrast RATIO of two 8-bit colors (research B4-A): `(L1+0.05)/(L2+0.05)`, L1 the
 * lighter. Range 1…21. Returned UNROUNDED — the caller compares unrounded against the threshold
 * (no-rounding is normative; research B4-A §Correction #1).
 */
export function wcagContrastRatio(a: Srgb8, b: Srgb8): number {
  const la = relativeLuminance(a);
  const lb = relativeLuminance(b);
  const lighter = Math.max(la, lb);
  const darker = Math.min(la, lb);
  return (lighter + 0.05) / (darker + 0.05);
}

/** A WCAG conformance level (research §B.4 Table B4-B). */
export type WcagLevel = 'AA' | 'AAA';

/** A content class selecting which threshold row of Table B4-B applies. */
export type ContentClass = 'normal-text' | 'large-text' | 'ui-component';

/**
 * The WCAG required ratio for a content class at a level (research Table B4-B). UI components and
 * focus indicators are a flat ≥3.0 (research: "UI component / focus indicator / graphic | AA").
 */
export function wcagTarget(contentClass: ContentClass, level: WcagLevel): number {
  switch (contentClass) {
    case 'normal-text':
      return level === 'AAA' ? 7.0 : 4.5;
    case 'large-text':
      return level === 'AAA' ? 4.5 : 3.0;
    case 'ui-component':
      // The non-text 1.4.11 floor is a flat 3.0 regardless of level (research Table B4-B).
      return 3.0;
  }
}

/** Does a pair MEET its WCAG target? UNROUNDED comparison (research: no-rounding is normative). */
export function wcagPasses(
  a: Srgb8,
  b: Srgb8,
  contentClass: ContentClass,
  level: WcagLevel,
): boolean {
  return wcagContrastRatio(a, b) >= wcagTarget(contentClass, level);
}

// ── APCA (SA98G, ADVISORY — Formula B4-C, constants verbatim) ─────────────────────────────────

const APCA_MAIN_TRC = 2.4;
const APCA_R = 0.2126729;
const APCA_G = 0.7151522;
const APCA_B = 0.072175;
const APCA_BLK_THRS = 0.022;
const APCA_BLK_CLMP = 1.414;
const APCA_NORM_BG = 0.56;
const APCA_NORM_TXT = 0.57;
const APCA_REV_TXT = 0.62;
const APCA_REV_BG = 0.65;
const APCA_SCALE = 1.14;
const APCA_LO_CLIP = 0.1;
const APCA_LO_OFFSET = 0.027;
const APCA_DELTA_Y_MIN = 0.0005;

function apcaScreenLuminance({ r8, g8, b8 }: Srgb8): number {
  const y =
    APCA_R * (r8 / 255) ** APCA_MAIN_TRC +
    APCA_G * (g8 / 255) ** APCA_MAIN_TRC +
    APCA_B * (b8 / 255) ** APCA_MAIN_TRC;
  // Soft black-clamp (research B4-C).
  return y < APCA_BLK_THRS ? y + (APCA_BLK_THRS - y) ** APCA_BLK_CLMP : y;
}

/**
 * APCA lightness-contrast Lc (research Formula B4-C, SA98G). SIGNED (~−108…+106): positive is
 * dark-text-on-light, negative is light-on-dark. ADVISORY ONLY — never the gate (OD-17-apca).
 */
export function apcaLc(textColor: Srgb8, backgroundColor: Srgb8): number {
  const ytxt = apcaScreenLuminance(textColor);
  const ybg = apcaScreenLuminance(backgroundColor);
  if (Math.abs(ybg - ytxt) < APCA_DELTA_Y_MIN) return 0;

  let sapc: number;
  let lc: number;
  if (ybg > ytxt) {
    // dark text on light background (positive polarity).
    sapc = (ybg ** APCA_NORM_BG - ytxt ** APCA_NORM_TXT) * APCA_SCALE;
    lc = sapc < APCA_LO_CLIP ? 0 : sapc - APCA_LO_OFFSET;
  } else {
    // light text on dark background (negative polarity).
    sapc = (ybg ** APCA_REV_BG - ytxt ** APCA_REV_TXT) * APCA_SCALE;
    lc = sapc > -APCA_LO_CLIP ? 0 : sapc + APCA_LO_OFFSET;
  }
  return lc * 100;
}

// ── the inverse gate (Algorithm B4-E — nearest on-brand passing foreground) ───────────────────

/** The auditable result of running the gate on a fg/bg pair (research §B.4 "Return contract"). */
export interface ContrastResult {
  /** Did the (possibly-repaired) foreground meet the WCAG target? Always true on a successful repair. */
  readonly pass: boolean;
  /** The achieved (unrounded) WCAG ratio of the returned foreground against the background. */
  readonly achievedRatio: number;
  /** The WCAG target the pair was held to. */
  readonly targetRatio: number;
  /** The conformance level the gate ran at. */
  readonly level: WcagLevel;
  /** The foreground actually returned — the seed if it passed, else the nearest on-brand repair. */
  readonly suggestedForeground: OkLch;
  /** The OKLCH-lightness delta applied to reach the target (0 if the seed passed as-is). */
  readonly deltaL: number;
  /** The advisory APCA Lc of the returned pair (signed; |Lc| compared against Table B4-D). */
  readonly apcaLc: number;
  /** Advisory: true when |APCA Lc| is below the body-text floor (Lc 75) — non-blocking (OD-17-apca). */
  readonly apcaWarn: boolean;
  /** What the gate did: `accept` (seed passed), `lightness-shift`, or `clamped` (hit L=0/1). */
  readonly action: 'accept' | 'lightness-shift' | 'clamped';
}

/** Lc 75 — the APCA minimum-body floor (research Table B4-D); used for the advisory warning only. */
const APCA_BODY_FLOOR = 75;

function ratio(fg: OkLch, bg: Srgb8): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), bg);
}

/**
 * The inverse gate (research Algorithm B4-E): the nearest on-brand foreground that passes WCAG.
 *
 * Runs in OKLCH — hue/chroma stay on-brand, only L moves (research §B.4):
 * 1. Trivial accept if the seed already meets the target.
 * 2. Pick direction: light bg → darken fg; dark bg → lighten fg.
 * 3. Bisect OKLCH.L (hue/chroma fixed) to the SMALLEST |ΔL| that hits the unrounded target —
 *    exact because contrast is monotone in luminance and L is monotone in luminance at fixed h/c.
 * 4. If even L=0/1 cannot reach the target, return the clamped extreme (`action: 'clamped'`) — the
 *    caller's chroma fallback / ink-paper snap is a higher-layer concern (research B4-E step 4).
 * 5. Compute the advisory APCA cross-check (non-blocking; research B4-E step 5).
 *
 * `seedForeground` carries the brand hue/chroma; `background` is the resolved surface color.
 */
export function nearestPassingForeground(
  seedForeground: OkLch,
  background: Srgb8,
  contentClass: ContentClass,
  level: WcagLevel,
): ContrastResult {
  const target = wcagTarget(contentClass, level);
  const bgLuminance = relativeLuminance(background);

  const finish = (fg: OkLch, action: ContrastResult['action']): ContrastResult => {
    const achieved = ratio(fg, background);
    const lc = apcaLc(srgbTo8(okLchToSrgb(fg)), background);
    return {
      pass: achieved >= target,
      achievedRatio: achieved,
      targetRatio: target,
      level,
      suggestedForeground: fg,
      deltaL: fg.l - seedForeground.l,
      apcaLc: lc,
      apcaWarn: Math.abs(lc) < APCA_BODY_FLOOR,
      action,
    };
  };

  // 1. trivial accept.
  if (ratio(seedForeground, background) >= target) {
    return finish(seedForeground, 'accept');
  }

  // 2. direction: a light background needs a darker fg (L→0), a dark background a lighter fg (L→1).
  const towardDark = bgLuminance > 0.18; // ~the perceptual mid-luminance pivot.
  const extreme: OkLch = { ...seedForeground, l: towardDark ? 0 : 1 };

  // If even the extreme cannot reach the target, return it clamped (step 4 boundary).
  if (ratio(extreme, background) < target) {
    return finish(extreme, 'clamped');
  }

  // 3. bisect L between the seed and the extreme to the smallest passing shift (~24 iters → 1e-7).
  let lo = seedForeground.l;
  let hi = extreme.l;
  for (let i = 0; i < 24; i++) {
    const mid = (lo + hi) / 2;
    if (ratio({ ...seedForeground, l: mid }, background) >= target) {
      hi = mid;
    } else {
      lo = mid;
    }
  }
  return finish({ ...seedForeground, l: hi }, 'lightness-shift');
}
