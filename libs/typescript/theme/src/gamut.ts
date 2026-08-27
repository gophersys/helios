/**
 * Gamut mapping — keep a generated OKLCH color inside the sRGB gamut without destroying its hue.
 *
 * Algorithm B3-D (docs/research/05-design-foundations.md §B.3): binary-search chroma reduction.
 * Naive chroma reduction destroys yellows; the CSS-Color-4 approach holds L and H fixed and
 * bisects chroma down to the largest value that renders in-gamut. The research cites JND=2 (ΔE2000)
 * with the L≥1→white, L≤0→black escapes; we implement the chroma-bisection core (hue-preserving)
 * with the documented epsilon, sufficient for the ramp generator (the seed-pinning + the contrast
 * gate run on top of in-gamut colors).
 *
 * MATH IS SOURCE OF TRUTH: the bisection is the cited CSS-Color-4 chroma-reduction strategy.
 */

import { okLchToSrgb, type OkLch } from './oklch.js';

/** The chroma-bisection epsilon (research B3-D: `eps=0.0001`). */
const CHROMA_EPS = 0.0001;

/** Is an sRGB color inside the displayable cube? (a tiny tolerance absorbs float round-off.) */
function srgbInGamut(oklch: OkLch): boolean {
  const { r, g, b } = okLchToSrgb(oklch);
  const tol = 1e-7;
  return r >= -tol && r <= 1 + tol && g >= -tol && g <= 1 + tol && b >= -tol && b <= 1 + tol;
}

/**
 * Map an OKLCH color into the sRGB gamut, preserving L and H and reducing only C (research B3-D).
 *
 * - `L ≥ 1` → white, `L ≤ 0` → black (the documented escapes — these tones have no chroma anyway).
 * - If already in-gamut, returned unchanged (the common case for mid-tones).
 * - Otherwise bisect C ∈ [0, C] down to the largest in-gamut chroma (hue-preserving, ~14 iters to
 *   the `eps=0.0001` research threshold).
 */
export function gamutMapOkLch(oklch: OkLch): OkLch {
  if (oklch.l >= 1) return { l: 1, c: 0, h: oklch.h };
  if (oklch.l <= 0) return { l: 0, c: 0, h: oklch.h };
  if (srgbInGamut(oklch)) return oklch;

  let lo = 0;
  let hi = oklch.c;
  while (hi - lo > CHROMA_EPS) {
    const mid = (lo + hi) / 2;
    if (srgbInGamut({ l: oklch.l, c: mid, h: oklch.h })) {
      lo = mid;
    } else {
      hi = mid;
    }
  }
  return { l: oklch.l, c: lo, h: oklch.h };
}
