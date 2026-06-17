/**
 * `@eden/visualization` — the hotspot-map SCATTER MATH (pure, fully coverable, the mutated surface).
 *
 * MATH IS SOURCE OF TRUTH (ADR-0024 §3, the ninth dimension). The hotspot-map is the signature
 * codebase-insight view: a churn × complexity scatter (contract §5 — x=churnRelative, y=cyclomatic,
 * size=lines, color=hotspotScore, label=path). This module owns every coordinate transform as a PURE
 * function so a flipped scale, an unclamped range, or a non-monotonic colour ramp is caught by the
 * property + design lanes (a mutation that flips `<`/`>` or drops a clamp must change an asserted
 * value). The `.svelte` is a thin render over these scales — it decides no geometry of its own.
 *
 * The four scale families:
 *  - {@link linearScale}: domain→range linear interpolation, CLAMPED to the range (x and y axes).
 *  - {@link radiusScale}: a bounded SQRT-AREA scale (a dot's AREA, not its radius, is proportional to
 *    `lines`, so a 4× file reads as 4× ink — the perceptual-honesty rule for bubble size).
 *  - {@link hotspotRamp} / {@link hotspotColorAt}: a perceptually-ordered SEQUENTIAL colour scale for
 *    `hotspotScore` ∈ [0,1] built from the theme (MONOTONIC lightness: calm/light at 0 → hot/dark at
 *    1), so the ordering is a property of the OKLCH lightness channel, not a hand-picked palette.
 *  - {@link ticks}: evenly-spaced axis ticks across a domain.
 *
 * The colour endpoints and every dimension come from a generated {@link Theme} — nothing hand-set.
 */

import type { Theme, OkLch } from '@eden/theme';
import { oklchToCss } from '@eden/theme';
import type { Entity } from '../report/index.js';

/** A closed numeric interval `[min, max]`. A scale's input domain or output (pixel) range. */
export interface Interval {
  readonly min: number;
  readonly max: number;
}

/**
 * The min/max of a numeric channel across the entities (the data domain a scale spans). A single
 * point or an all-equal channel yields a degenerate `min === max`; the scales below treat that as the
 * midpoint of the range so a one-entity scatter still renders (no divide-by-zero).
 */
export function extentOf(entities: readonly Entity[], read: (entity: Entity) => number): Interval {
  let min = Infinity;
  let max = -Infinity;
  for (const entity of entities) {
    const value = read(entity);
    if (value < min) min = value;
    if (value > max) max = value;
  }
  // An empty set has no domain; fall back to the unit interval so a scale stays total.
  if (!Number.isFinite(min) || !Number.isFinite(max)) return { min: 0, max: 1 };
  return { min, max };
}

/**
 * A linear scale mapping a value in `domain` onto `range`, CLAMPED so an out-of-domain value pins to
 * the nearest range end (a datum never paints outside the plot). A degenerate domain (`min === max`)
 * maps everything to the range MIDPOINT — the honest position for "all the same". Pure and total.
 *
 * The clamp is load-bearing: dropping it lets an extreme entity paint off-canvas; the property lane
 * asserts the output is always within `[range.min, range.max]`.
 */
export function linearScale(domain: Interval, range: Interval): (value: number) => number {
  const span = domain.max - domain.min;
  const lo = Math.min(range.min, range.max);
  const hi = Math.max(range.min, range.max);
  return (value: number): number => {
    if (span === 0) return (range.min + range.max) / 2;
    const t = (value - domain.min) / span;
    const projected = range.min + t * (range.max - range.min);
    return Math.min(hi, Math.max(lo, projected));
  };
}

/**
 * A bounded SQRT-AREA radius scale: a dot's AREA grows linearly with `value` across `domain`, so the
 * radius is `sqrt`-shaped between `minRadius` and `maxRadius`. Area-proportional sizing is the
 * perceptual-honesty rule for bubbles (a value twice as large reads as twice the ink, not 4×). A
 * degenerate domain maps to `minRadius` (no size signal to convey). The result is CLAMPED to
 * `[minRadius, maxRadius]`. Pure and total.
 */
export function radiusScale(
  domain: Interval,
  minRadius: number,
  maxRadius: number,
): (value: number) => number {
  const span = domain.max - domain.min;
  return (value: number): number => {
    if (span <= 0) return minRadius;
    const t = Math.min(1, Math.max(0, (value - domain.min) / span));
    // interpolate AREA linearly (∝ r²), then take the radius — the sqrt-area rule.
    const areaMin = minRadius * minRadius;
    const areaMax = maxRadius * maxRadius;
    const area = areaMin + t * (areaMax - areaMin);
    return Math.sqrt(area);
  };
}

/**
 * A perceptually-ordered SEQUENTIAL colour ramp for `hotspotScore` ∈ [0, 1], built from a generated
 * theme. This is a SINGLE-HUE sequential scale in the theme's `error` (alarm) hue — the canonical
 * shape of a sequential colormap (a light tint at the calm end deepening to the saturated accent at
 * the hot end, like YlOrRd). The HOT end (score 1) is exactly the theme's gated `error` role, so the
 * most intense hotspots read in the alarm colour the rest of Eden uses for "destructive / over"; the
 * CALM end (score 0) is the SAME hue + chroma pulled in LIGHTNESS toward the reading surface, so a
 * low-score entity is a faint warm tint that recedes (low value = low emphasis — the sequential rule).
 *
 * Because only the LIGHTNESS channel moves between the ends (hue + chroma are the error role's), the
 * scale is MONOTONIC in lightness BY CONSTRUCTION: in light mode the surface is light and the error
 * accent is darker, so the ramp deepens (lighter→darker) with score; in dark mode the surface is dark
 * and the accent is lighter, so it brightens (darker→lighter) with score. Either way a higher score is
 * always a larger lightness STEP away from the surface — the pre-attentive ordering (research §B.3).
 * Nothing is hand-picked: the hue/chroma are the gated `error` role and the calm lightness is a fixed
 * fraction of the surface→accent lightness span.
 *
 * Returned as the two OKLCH endpoints so {@link hotspotColorAt} interpolates per entity and the design
 * lane recomputes the contrast/lightness invariants from the SAME numbers.
 */
export interface HotspotRamp {
  /** The calm (score 0) OKLCH — a faint warm tint near the surface lightness. */
  readonly low: OkLch;
  /** The hot (score 1) OKLCH — the gated `error` accent (the alarm colour). */
  readonly high: OkLch;
}

/** The fraction of the surface→accent lightness span the CALM end sits at (a faint tint, not flush). */
const CALM_LIGHTNESS_FRACTION = 0.15;

export function hotspotRamp(theme: Theme): HotspotRamp {
  const roles = theme.roles;
  const accent = roles.error.value; // the HOT end — the gated alarm accent.
  const surfaceL = roles.surface.value.l;
  // The CALM end keeps the accent's hue + chroma but takes a lightness a small fraction of the way
  // from the surface toward the accent — a faint warm tint that recedes against the reading surface.
  const low: OkLch = {
    l: surfaceL + CALM_LIGHTNESS_FRACTION * (accent.l - surfaceL),
    c: accent.c,
    h: accent.h,
  };
  return { low, high: accent };
}

/**
 * The OKLCH colour for a hotspot score ∈ [0, 1] on a {@link HotspotRamp}: a linear OKLCH interpolation
 * from the calm (`low`) end at 0 to the hot (`high`) end at 1. Hue takes the SHORTER arc around the
 * wheel (a no-op for the single-hue ramp, but correct for any future two-hue ramp). The score is
 * clamped to [0, 1] so an out-of-range datum pins to an end. Pure and total — the per-entity fill.
 */
export function hotspotColorAt(score: number, ramp: HotspotRamp): OkLch {
  const t = Math.min(1, Math.max(0, score));
  return {
    l: ramp.low.l + t * (ramp.high.l - ramp.low.l),
    c: ramp.low.c + t * (ramp.high.c - ramp.low.c),
    h: interpolateHue(ramp.low.h, ramp.high.h, t),
  };
}

/** The hotspot fill as a CSS `oklch(...)` string for a score on a ramp (the value the SVG paints). */
export function hotspotColorCssAt(score: number, ramp: HotspotRamp): string {
  return oklchToCss(hotspotColorAt(score, ramp));
}

/**
 * Interpolate a hue (degrees) along the SHORTER arc of the colour wheel. A naive linear blend of two
 * hues 350° and 10° would sweep the long way (350→190→10) through the opposite side of the wheel;
 * taking the signed delta in `(-180, 180]` keeps the perceptual path direct. Pure.
 */
function interpolateHue(from: number, to: number, t: number): number {
  let delta = (((to - from) % 360) + 360) % 360;
  if (delta > 180) delta -= 360;
  const h = from + delta * t;
  return ((h % 360) + 360) % 360;
}

/**
 * Evenly-spaced tick values across a domain (inclusive of both ends): `count + 1` ticks at
 * `domain.min + i·step`. Used by the axes + the colour legend. A degenerate domain yields the single
 * value repeated (a one-tick axis). `count` is floored to ≥1 so the result always has ≥2 ticks for a
 * non-degenerate domain. Pure and total.
 */
export function ticks(domain: Interval, count: number): readonly number[] {
  const n = Math.max(1, Math.floor(count));
  if (domain.max === domain.min) return [domain.min];
  const step = (domain.max - domain.min) / n;
  const out: number[] = [];
  for (let i = 0; i <= n; i++) out.push(domain.min + i * step);
  return out;
}

/**
 * Read a numeric Report field off an {@link Entity} by its encoding CHANNEL name (the View's
 * `encoding` map points a visual channel at a report field — contract §5). This is the payload-driven
 * seam: the hotspot-map renders ANY entities the encoding points at, so it generalizes to other
 * scatter views (the same scales over a different field pair). An unknown / non-numeric / absent
 * (`omitempty`) field reads as 0 — a missing optional metric plots at the origin of its axis, never
 * `NaN`. Pure and total.
 */
export function entityValue(entity: Entity, field: string): number {
  const raw = (entity as unknown as Record<string, unknown>)[field];
  return typeof raw === 'number' && Number.isFinite(raw) ? raw : 0;
}

/**
 * Read the LABEL field (a string channel — e.g. `path`) off an entity by encoding name. A missing /
 * non-string field reads as the empty string (no label), never `undefined`. Pure and total.
 */
export function entityLabel(entity: Entity, field: string): string {
  const raw = (entity as unknown as Record<string, unknown>)[field];
  return typeof raw === 'string' ? raw : '';
}
