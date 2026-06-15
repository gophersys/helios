/**
 * Color ramps — the OKLCH tonal palette generator (docs/research/05-design-foundations.md §B.3).
 *
 * A ramp is the 11-step tonal palette (50…950) for one brand hue: the lightness LADDER (Table
 * B3-B, the Tailwind-v4 empirically-tuned ramp) crossed with the CHROMA CURVE (Formula B3-C, which
 * must peak in the mid-tones and fall toward both extremes — gamut geometry, not aesthetics), each
 * step gamut-mapped (Algorithm B3-D). The seed is SNAPPED to its nearest ramp step and PINNED so
 * brand identity survives generation (Table B3-E).
 *
 * MATH IS SOURCE OF TRUTH (ADR-0024 §7): the ladder and the chroma reference array are the cited
 * research values; the seed carries only its hue/chroma, the ramp structure comes from the tables.
 */

import { gamutMapOkLch } from './gamut.js';
import type { OkLch } from './oklch.js';

/** The 11 canonical ramp steps (Tailwind/Material convention; research Table B3-B). */
export const RAMP_STEPS = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950] as const;

/** A single ramp step number (50…950). */
export type RampStep = (typeof RAMP_STEPS)[number];

/**
 * The lightness LADDER (research Table B3-B): the Tailwind-v4 OKLCH L values, empirically tuned and
 * light-biased — the de-facto industry ramp. Transcribed verbatim; index-aligned with RAMP_STEPS.
 */
export const LIGHTNESS_LADDER: readonly number[] = [
  0.978, 0.936, 0.881, 0.827, 0.742, 0.648, 0.573, 0.469, 0.394, 0.32, 0.238,
];

/**
 * The chroma ENVELOPE reference array (research Formula B3-C): chroma peaks ~0.147 at step 400 and
 * falls toward both extremes. This is the cited "consistent" curve-set (no hue gaps), preferred
 * over "vivid/max-chroma" which drifts hue at the bright end. Index-aligned with RAMP_STEPS.
 */
export const CHROMA_ENVELOPE: readonly number[] = [
  0.011, 0.032, 0.061, 0.091, 0.14, 0.147, 0.13, 0.107, 0.09, 0.073, 0.054,
];

/** One rung of the generating ladder: a step number with its ladder lightness + envelope chroma. */
interface LadderRung {
  readonly step: RampStep;
  readonly l: number;
  readonly c: number;
}

/**
 * The generating ladder: RAMP_STEPS zipped with the lightness ladder + chroma envelope into one
 * index-aligned source of truth, so the generator iterates rungs (`for...of`) rather than indexing
 * three parallel arrays (which the strict `noUncheckedIndexedAccess` would force `!` onto).
 */
const LADDER: readonly LadderRung[] = RAMP_STEPS.map((step, i) => ({
  step,
  l: LIGHTNESS_LADDER[i] ?? 0,
  c: CHROMA_ENVELOPE[i] ?? 0,
}));

/** A full generated ramp: the 11 OKLCH steps keyed by step number, plus the pinned seed step. */
export interface ColorRamp {
  /** The 11 OKLCH steps, index-aligned with {@link RAMP_STEPS}. */
  readonly steps: Readonly<Record<RampStep, OkLch>>;
  /** The ramp step the seed was snapped to and pinned at (its identity anchor; research B3-E). */
  readonly seedStep: RampStep;
  /** The hue (degrees) the whole ramp holds constant (OKLCH's advantage; research §B.3 "Hue"). */
  readonly hue: number;
}

/** Find the ramp step whose ladder lightness is closest to a target L (the seed-snap; research B3-E). */
export function nearestRampStep(targetL: number): RampStep {
  let best: LadderRung = LADDER[5] ?? { step: 500, l: 0.648, c: 0 };
  let bestDistance = Infinity;
  for (const rung of LADDER) {
    const distance = Math.abs(rung.l - targetL);
    if (distance < bestDistance) {
      bestDistance = distance;
      best = rung;
    }
  }
  return best.step;
}

/**
 * Generate a full 11-step OKLCH ramp from a seed color (research §B.3, the ramp algorithm in C.3):
 *
 *   for step, L in LADDER:
 *       C = Cseed · envelope(L);  (L,C,H) = gamutMap(L, C, seedHue)
 *   ramp[nearestStep(seed.L)] = snapToSeed(seed)            # pin identity
 *
 * Hue is held CONSTANT across the ramp (the whole OKLCH advantage). The chroma at each step is the
 * envelope value scaled by the seed's chroma RELATIVE to the envelope peak, so a muted brand stays
 * muted and a vivid one stays vivid while the curve shape is preserved. The seed's own step is
 * overwritten with the exact seed so brand identity is bit-exact at its anchor.
 */
export function generateRamp(seed: OkLch): ColorRamp {
  const hue = seed.h;
  const envelopePeak = Math.max(...CHROMA_ENVELOPE);
  // Scale the whole envelope so the seed's chroma lands at the curve's peak proportion — a muted
  // seed (low C) yields a muted ramp, a saturated seed a saturated ramp, curve shape preserved.
  const chromaScale = envelopePeak > 0 ? seed.c / envelopePeak : 0;

  const steps = {} as Record<RampStep, OkLch>;
  for (const rung of LADDER) {
    steps[rung.step] = gamutMapOkLch({ l: rung.l, c: rung.c * chromaScale, h: hue });
  }

  // Pin the seed at its nearest ladder step so brand identity survives generation (research B3-E).
  const seedStep = nearestRampStep(seed.l);
  steps[seedStep] = gamutMapOkLch(seed);

  return { steps, seedStep, hue };
}
