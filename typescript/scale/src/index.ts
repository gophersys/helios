/**
 * `@eden/scale` — the modular (geometric) scale generator.
 *
 * The reference library that proves the ADR-0024 TypeScript/Svelte pipeline end-to-end. It is a
 * pure, dependency-free utility: a deterministic function that derives a proportional scale from a
 * `base` and a `ratio` seed via the research formula `f(i) = base · ratio^i`
 * (docs/research/05-design-foundations.md B1, "the scale generator"). Type scales, spacing-widening
 * curves, and the modular-step rungs `@eden/theme` will emit all share this one generator.
 *
 * MATH IS SOURCE OF TRUTH (ADR-0024 §7): the scale is GENERATED from the `base`+`ratio` seeds. The
 * sizes are never hand-set irregular literals — `@eden/theme` will re-derive C21's type sizes for
 * harmony through this function rather than pin C21's mathematically-irregular hand-picked values.
 */

/** A named musical-interval ratio from the research type-scale table (B1, Table B1-A). */
export type IntervalRatio =
  | 'minor-second' // 1.067
  | 'major-second' // 1.125
  | 'minor-third' // 1.200 — the research default for general UI/web
  | 'major-third' // 1.250
  | 'perfect-fourth' // 1.333
  | 'augmented-fourth' // 1.414
  | 'perfect-fifth' // 1.500
  | 'golden'; // 1.618 — offered, but demoted from "beauty law" (research ⚠️)

/**
 * The named-interval ratio table (docs/research/05-design-foundations.md B1, Table B1-A). Values
 * are the cited interval ratios, not invented — the seed carries taste, the table carries the
 * proportional structure.
 */
export const INTERVAL_RATIO: Readonly<Record<IntervalRatio, number>> = Object.freeze({
  'minor-second': 1.067,
  'major-second': 1.125,
  'minor-third': 1.2,
  'major-third': 1.25,
  'perfect-fourth': 1.333,
  'augmented-fourth': 1.414,
  'perfect-fifth': 1.5,
  golden: 1.618,
});

/**
 * The research default ratio for general UI/web: the **minor third** (1.200) — "clear but not
 * loud" (Table B1-A). A `@eden/theme` brand seed overrides it; absent a seed this is the floor.
 */
export const DEFAULT_TYPE_RATIO: number = INTERVAL_RATIO['minor-third'];

/** The shared origin for the type and spacing scales: a 16px root (research B1/B2). */
export const DEFAULT_BASE_PX = 16;

/** A single derived step: its integer index `i` and its exact (unrounded) value. */
export interface ScaleStep {
  /** The modular index; `i = 0` is the base, negative below, positive above. */
  readonly index: number;
  /** The exact value `base · ratio^i`, kept as a float (round only at render — research B1). */
  readonly value: number;
}

/** The seed for a modular scale: the two scalars the generator composes. */
export interface ScaleSeed {
  /** The base value at index 0 (e.g. 16px root). Must be a finite number > 0. */
  readonly base: number;
  /** The geometric ratio between adjacent steps (e.g. 1.2). Must be a finite number > 0. */
  readonly ratio: number;
}

/** Thrown when a scale seed or step bound is not a usable finite, positive number. */
export class ScaleSeedError extends Error {
  /** A stable, inspectable classification (rule 12 — inspect by type, not by string). */
  readonly kind = 'scale-seed-invalid' as const;
  constructor(message: string) {
    super(message);
    this.name = 'ScaleSeedError';
  }
}

function assertSeed({ base, ratio }: ScaleSeed): void {
  if (!Number.isFinite(base) || base <= 0) {
    throw new ScaleSeedError(`base must be a finite number > 0, got ${String(base)}`);
  }
  if (!Number.isFinite(ratio) || ratio <= 0) {
    throw new ScaleSeedError(`ratio must be a finite number > 0, got ${String(ratio)}`);
  }
}

/**
 * The scale generator: the exact value at a single modular index, `f(i) = base · ratio^i`
 * (docs/research/05-design-foundations.md B1). Pure: no I/O, no clock, no globals (rule 10).
 *
 * @throws {ScaleSeedError} if the seed is not finite-positive.
 */
export function stepAt(seed: ScaleSeed, index: number): number {
  assertSeed(seed);
  if (!Number.isInteger(index)) {
    throw new ScaleSeedError(`index must be an integer, got ${String(index)}`);
  }
  return seed.base * seed.ratio ** index;
}

/**
 * Generate the inclusive run of steps `[from … to]` from a seed, each as an exact (unrounded)
 * `ScaleStep`. The canonical worked example (B1) — base 16, ratio 1.25, i ∈ [−2…+5] → the
 * xs…3xl ladder — is reproduced by `modularScale({ base: 16, ratio: 1.25 }, -2, 5)`.
 *
 * @throws {ScaleSeedError} if the seed is invalid or `from > to`.
 */
export function modularScale(seed: ScaleSeed, from: number, to: number): ScaleStep[] {
  assertSeed(seed);
  if (!Number.isInteger(from) || !Number.isInteger(to)) {
    throw new ScaleSeedError(`from/to must be integers, got ${String(from)}..${String(to)}`);
  }
  if (from > to) {
    throw new ScaleSeedError(`from (${String(from)}) must be <= to (${String(to)})`);
  }
  const steps: ScaleStep[] = [];
  for (let index = from; index <= to; index++) {
    steps.push({ index, value: seed.base * seed.ratio ** index });
  }
  return steps;
}

/**
 * Round a step value for render. The research keeps the float internally and rounds only at
 * render (B1); this is that render-time rounding, to the nearest integer pixel by default.
 */
export function renderPx(value: number, fractionDigits = 0): number {
  const factor = 10 ** fractionDigits;
  return Math.round(value * factor) / factor;
}
