/**
 * Spacing, grid & breakpoints — BRAND-INVARIANT geometry (research §B.2).
 *
 * The base unit is 4px (a manufacturing convention for integer rendering across device-pixel-
 * ratios, not a perceptual law — research §B.2 🔶). The ramp is a HYBRID: fine linear at the
 * bottom, multiplicative widening at the top (research Table B2-A, the Refactoring-UI/Tailwind/
 * Carbon convergence). Spacing carries NO brand information and is brand-invariant — stated
 * explicitly to forbid pseudo-scientific brand→spacing coupling (research §B.2 / ADR-0024 §7).
 *
 * Breakpoints are the semantic Material window classes (OD-17-breakpoint resolved-as-default:
 * semantic canonical + device-width aliases). The touch-target floors (Table B2-D) are the hard
 * accessibility floors that recur across the contrast and density domains.
 */

/** The base unit, px (research §B.2 Decision 🧩: 4px, with 8px the preferred subset). */
export const BASE_UNIT_PX = 4;

/** The hard touch/click-target floors (research Table B2-D — never emit below these). */
export const TARGET_FLOOR_PX = {
  /** WCAG 2.2 SC 2.5.8 AA minimum. */
  wcagAa: 24,
  /** WCAG SC 2.5.5 AAA / Apple HIG minimum. */
  wcagAaa: 44,
  /** Material / Android dp minimum. */
  material: 48,
} as const;

/** The prose measure target, ch (research §B.1/§B.2: 60–66 ideal, cap ≤75). */
export const PROSE_MEASURE_CH = 66;

/** A single spacing-ramp rung: its token name, px value, rem value, and t-shirt alias. */
export interface SpaceToken {
  /** The token name (e.g. `space-4`). */
  readonly name: string;
  /** The pixel value — always an integer multiple of {@link BASE_UNIT_PX}. */
  readonly px: number;
  /** The rem value (px / 16). */
  readonly rem: number;
  /** The optional t-shirt-size alias (research Table B2-A), where one exists. */
  readonly tshirt: string | undefined;
}

/**
 * The Eden spacing ramp (research Table B2-A): every value an integer multiple of 4, integer at
 * 1×/1.5×/2×/3×. The multipliers and t-shirt aliases are the cited table — the ramp is data, not a
 * pure function, because it is a curated hybrid (fine linear ↓, multiplicative widening ↑), NOT a
 * single generating function (research §B.2: pure-linear wastes decisions, pure-geometric leaves
 * holes). Sizes are GENERATED from the multipliers × the base unit, never hand-set.
 */
const SPACE_MULTIPLIERS: readonly { readonly key: string; readonly tshirt?: string }[] = [
  { key: '0.5', tshirt: '3xs' },
  { key: '1', tshirt: '2xs' },
  { key: '2', tshirt: 'xs' },
  { key: '3', tshirt: 'sm' },
  { key: '4', tshirt: 'md' },
  { key: '5' },
  { key: '6', tshirt: 'lg' },
  { key: '8', tshirt: 'xl' },
  { key: '10' },
  { key: '12', tshirt: '2xl' },
  { key: '16', tshirt: '3xl' },
  { key: '24', tshirt: '4xl' },
  { key: '32', tshirt: '5xl' },
  { key: '48', tshirt: '6xl' },
  { key: '64', tshirt: '7xl' },
  { key: '96', tshirt: '8xl' },
];

/**
 * Generate the full spacing ramp. Each rung's px is `multiplier · BASE_UNIT_PX` (so `space-4` →
 * 16px, `space-6` → 24px — the research Table B2-A values), proving the sizes are DERIVED from the
 * 4px base, never pasted.
 */
export function generateSpacingRamp(): readonly SpaceToken[] {
  return SPACE_MULTIPLIERS.map(({ key, tshirt }) => {
    const multiplier = Number.parseFloat(key);
    const px = multiplier * BASE_UNIT_PX;
    return { name: `space-${key}`, px, rem: px / 16, tshirt };
  });
}

/** A semantic breakpoint class (research Table B2-B — Material window size classes). */
export interface Breakpoint {
  /** The class name (Material window class). */
  readonly name: string;
  /** The min viewport width, px. */
  readonly minWidthPx: number;
  /** The grid column count at this class. */
  readonly columns: number;
  /** The layout margin, px. */
  readonly marginPx: number;
  /** The grid gutter, px. */
  readonly gutterPx: number;
  /** The recommended device-width alias (Tailwind) for developer familiarity (research note). */
  readonly deviceAlias: string;
}

/**
 * The breakpoint config (research Table B2-B): the semantic Material window classes 0/600/840/
 * 1200/1600, the canonical axis (OD-17-breakpoint resolved-as-default), with Tailwind device-width
 * aliases mapped on top. These are a config map, not a generated curve (research §B.2: "no
 * breakpoint set is correct" — they are device-histogram curve-fits, so they are cited data).
 */
export const BREAKPOINTS: readonly Breakpoint[] = [
  { name: 'compact', minWidthPx: 0, columns: 4, marginPx: 16, gutterPx: 16, deviceAlias: 'base' },
  { name: 'medium', minWidthPx: 600, columns: 8, marginPx: 24, gutterPx: 24, deviceAlias: 'sm' },
  { name: 'expanded', minWidthPx: 840, columns: 12, marginPx: 24, gutterPx: 24, deviceAlias: 'lg' },
  { name: 'large', minWidthPx: 1200, columns: 12, marginPx: 24, gutterPx: 24, deviceAlias: 'xl' },
  {
    name: 'extra-large',
    minWidthPx: 1600,
    columns: 12,
    marginPx: 24,
    gutterPx: 24,
    deviceAlias: '2xl',
  },
];
