/**
 * Density & adaptivity — ONE continuous axis applied as a scalar transform (research §B.6).
 *
 * Density is a scalar transform over a fixed base scale (NOT a forked "simple mode"). It scales
 * spacing and component heights but NEVER touch targets, color/contrast, font size, or icon size
 * (research Table B6-A invariants I1–I7; the naive global-multiplier trap breaks accessibility).
 * The transform is piecewise-linear in 4px steps: `Δpx(d) = 4·d` (Formula B6-B). Invariants are
 * CLAMPED LAST — density can never win against a floor (research §B.6 "Precedence").
 *
 * OD-17-density-default resolved-as-default: `compact` is the default for IDE/agent working
 * surfaces (research Table B6-C, the "earned density" call 🔶).
 */

import { BASE_UNIT_PX, TARGET_FLOOR_PX } from './spacing.js';
import { BODY_LINE_HEIGHT_FLOOR } from './typography.js';

/** A named Eden density tier (research Table B6-C). */
export type DensityTier = 'spacious' | 'comfortable' | 'compact' | 'condensed';

/** The density STEP `d` for each named tier (research Table B6-C, "densityStep d" column). */
export const DENSITY_STEP: Readonly<Record<DensityTier, number>> = Object.freeze({
  spacious: 1,
  comfortable: 0,
  compact: -2,
  condensed: -3,
});

/**
 * The default density per surface (OD-17-density-default resolved-as-default; research Table B6-C):
 * IDE/agent working surfaces earn `compact`; human-facing/marketing surfaces stay `comfortable`.
 */
export const DEFAULT_DENSITY: Readonly<Record<'agent' | 'application' | 'marketing', DensityTier>> =
  Object.freeze({
    agent: 'compact',
    application: 'comfortable',
    marketing: 'spacious',
  });

/** Snap a value to the nearest 4px grid step (research §B.6: `snap4(x)=round(x/4)·4`). */
export function snap4(x: number): number {
  return Math.round(x / BASE_UNIT_PX) * BASE_UNIT_PX;
}

/** The geometry a density transform produces for one component row (research §B.6 "Generator"). */
export interface DensifiedGeometry {
  /** The visual component height, px — scaled, but the hit target is decoupled (see below). */
  readonly componentHeightPx: number;
  /** The vertical inset (padding), px — scaled with a 4px floor. */
  readonly insetPx: number;
  /** The stack gap, px — scaled. */
  readonly gapPx: number;
  /** The line-height, px — scaled WITH the WCAG 1.4.12 ≥1.5×font floor applied. */
  readonly lineHeightPx: number;
  /** The hit target, px — DECOUPLED from the visual box and clamped to the context floor (I1/I2). */
  readonly hitTargetPx: number;
  /** The font size, px — INVARIANT (I7: density never scales the font). */
  readonly fontSizePx: number;
  /** The icon size, px — INVARIANT (I7: density never scales the icon). */
  readonly iconSizePx: number;
}

/** The hit-target context, selecting the floor (research §B.6: `FLOOR={web:24,touch:44,android:48}`). */
export type TargetContext = 'pointer' | 'touch' | 'android';

function targetFloor(context: TargetContext): number {
  switch (context) {
    case 'pointer':
      return TARGET_FLOOR_PX.wcagAa;
    case 'touch':
      return TARGET_FLOOR_PX.wcagAaa;
    case 'android':
      return TARGET_FLOOR_PX.material;
  }
}

/** The base (d=0) geometry a component starts from, before the density transform. */
export interface BaseGeometry {
  /** Base visual height, px. */
  readonly componentHeightPx: number;
  /** Base inset, px. */
  readonly insetPx: number;
  /** Base gap, px. */
  readonly gapPx: number;
  /** The font size, px (invariant under density). */
  readonly fontSizePx: number;
  /** The icon size, px (invariant under density). */
  readonly iconSizePx: number;
}

/**
 * Apply the density transform to a component's base geometry (research §B.6 "Generator"):
 *   - geometry scaled: `componentHeight = clampToTarget(snap4(base + 4d))`, inset/gap likewise (with
 *     a 4px floor on inset);
 *   - leading scaled WITH the WCAG floor: `lineHeight = max(base + ~1·d, 1.5·fontSize)` (the floor
 *     stops over-tightening even at the densest tier);
 *   - INVARIANTS: fontSize/iconSize unchanged; `hitTarget = max(visualHeight, FLOOR[context])`
 *     decoupled from the (shrinkable) visual box (I1/I2).
 *
 * Precedence is brand→mode→density→CLAMP(floors): the floors apply LAST (research §B.6).
 */
export function densify(
  base: BaseGeometry,
  tier: DensityTier,
  context: TargetContext = 'pointer',
): DensifiedGeometry {
  const d = DENSITY_STEP[tier];
  const delta = BASE_UNIT_PX * d;

  const visualHeight = snap4(base.componentHeightPx + delta);
  const inset = snap4(Math.max(base.insetPx + delta, BASE_UNIT_PX));
  const gap = snap4(Math.max(base.gapPx + delta, BASE_UNIT_PX));

  // Leading scales by ~1px/step but is floored at 1.5×font (WCAG 1.4.12).
  const leadingFloor = BODY_LINE_HEIGHT_FLOOR * base.fontSizePx;
  const lineHeight = Math.max(base.fontSizePx + 4 + d, leadingFloor);

  const floor = targetFloor(context);
  const hitTarget = Math.max(visualHeight, floor);

  return {
    componentHeightPx: visualHeight,
    insetPx: inset,
    gapPx: gap,
    lineHeightPx: lineHeight,
    hitTargetPx: hitTarget,
    fontSizePx: base.fontSizePx, // invariant (I7)
    iconSizePx: base.iconSizePx, // invariant (I7)
  };
}
