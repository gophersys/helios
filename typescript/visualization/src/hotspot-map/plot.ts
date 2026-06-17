/**
 * `@eden/visualization` — the hotspot-map RENDER PLAN (pure composition of the scales + tokens).
 *
 * MATH IS SOURCE OF TRUTH. This module composes the pure scatter scales (./scales.ts) with the
 * encoding (the View's channel→field map, contract §5) and the plot dimensions into a fully PLACED
 * render plan: every point's `cx`/`cy`/`radius`/`fill`, the axis tick positions, and the legend
 * stops. The `.svelte` renders this plan verbatim — it computes no geometry of its own, so a flipped
 * scale or a swapped axis shows up as a changed plan value the property/design lanes catch.
 *
 * The encoding is the payload-driven seam: pass `{ x, y, size, color, label }` channel names and the
 * plan reads those fields off each entity, so the hotspot-map generalizes to ANY scatter View.
 */

import type { Theme } from '@eden/theme';
import type { Entity } from '../report/index.js';
import {
  extentOf,
  linearScale,
  radiusScale,
  hotspotRamp,
  hotspotColorAt,
  hotspotColorCssAt,
  ticks,
  entityValue,
  entityLabel,
  type Interval,
  type HotspotRamp,
} from './scales.js';

/** The visual-channel → report-field map (the View's `encoding`, contract §5). */
export interface HotspotEncoding {
  /** The field for the x position (default `churnRelative`). */
  readonly x: string;
  /** The field for the y position (default `cyclomatic`). */
  readonly y: string;
  /** The field for the dot size (default `lines`). */
  readonly size: string;
  /** The field for the dot colour (default `hotspotScore`). */
  readonly color: string;
  /** The field for the point label (default `path`). */
  readonly label: string;
}

/** The default hotspot-map binding (contract §5 — the `hotspot-map` primitive's default encoding). */
export const DEFAULT_HOTSPOT_ENCODING: HotspotEncoding = {
  x: 'churnRelative',
  y: 'cyclomatic',
  size: 'lines',
  color: 'hotspotScore',
  label: 'path',
};

/** The plot's pixel box + the inner margin reserved for the axes/labels. */
export interface PlotDimensions {
  /** The full SVG width, px. */
  readonly width: number;
  /** The full SVG height, px. */
  readonly height: number;
  /** The inner margin (axis gutter) on every side, px. */
  readonly margin: number;
  /** The min dot radius, px (the smallest file). */
  readonly minRadius: number;
  /** The max dot radius, px (the largest file). */
  readonly maxRadius: number;
}

/** One placed scatter point — the geometry + the encoded values the `.svelte` paints + announces. */
export interface PlacedPoint {
  /** The source entity (so the `.svelte` can announce path / metrics in the data table). */
  readonly entity: Entity;
  /** The centre x, px (already scaled + clamped into the plot box). */
  readonly cx: number;
  /** The centre y, px (y is FLIPPED — a higher metric sits HIGHER on screen). */
  readonly cy: number;
  /** The dot radius, px (sqrt-area scaled). */
  readonly radius: number;
  /** The fill as a CSS `oklch(...)` string (the hotspot ramp at the entity's score). */
  readonly fill: string;
  /** The encoded label (e.g. the path). */
  readonly label: string;
  /** The encoded x value (for the data-table fallback + the title). */
  readonly xValue: number;
  /** The encoded y value. */
  readonly yValue: number;
  /** The encoded size value. */
  readonly sizeValue: number;
  /** The encoded colour (hotspot) score. */
  readonly colorValue: number;
}

/** One axis tick — its data value + the pixel position along the axis. */
export interface AxisTick {
  /** The data value at this tick. */
  readonly value: number;
  /** The pixel position along the axis (x for the x-axis, y for the y-axis). */
  readonly position: number;
}

/** One legend stop — a hotspot score and its swatch fill (the colour ramp made readable). */
export interface LegendStop {
  /** The hotspot score (0..1) this swatch represents. */
  readonly score: number;
  /** The swatch fill as a CSS `oklch(...)` string. */
  readonly fill: string;
}

/** The full placed render plan a hotspot-map `.svelte` paints verbatim. */
export interface HotspotPlot {
  /** The placed scatter points (in entity order). */
  readonly points: readonly PlacedPoint[];
  /** The x-axis ticks (data value + pixel x). */
  readonly xTicks: readonly AxisTick[];
  /** The y-axis ticks (data value + pixel y). */
  readonly yTicks: readonly AxisTick[];
  /** The colour-legend stops (low→high hotspot score). */
  readonly legend: readonly LegendStop[];
  /** The x data domain (for the axis title / aria). */
  readonly xDomain: Interval;
  /** The y data domain. */
  readonly yDomain: Interval;
  /** The size data domain. */
  readonly sizeDomain: Interval;
  /** The hotspot ramp the points + legend were coloured from. */
  readonly ramp: HotspotRamp;
}

const DEFAULT_TICK_COUNT = 4;
const DEFAULT_LEGEND_STOPS = 5;

/**
 * Build the full {@link HotspotPlot} from the entities, the encoding, the theme, and the plot
 * dimensions. PURE: it derives the four domains, the x/y/radius scales, the hotspot ramp, then places
 * every point and lays out the axis ticks + the colour legend. The y axis is FLIPPED (range
 * `[height-margin, margin]`) so a higher metric value sits higher on screen — the natural reading.
 */
export function buildHotspotPlot(
  entities: readonly Entity[],
  encoding: HotspotEncoding,
  theme: Theme,
  dimensions: PlotDimensions,
): HotspotPlot {
  const { width, height, margin, minRadius, maxRadius } = dimensions;

  const xDomain = extentOf(entities, (e) => entityValue(e, encoding.x));
  const yDomain = extentOf(entities, (e) => entityValue(e, encoding.y));
  const sizeDomain = extentOf(entities, (e) => entityValue(e, encoding.size));

  const xScale = linearScale(xDomain, { min: margin, max: width - margin });
  // y range is inverted: max metric → top (small pixel y), min metric → bottom.
  const yScale = linearScale(yDomain, { min: height - margin, max: margin });
  const rScale = radiusScale(sizeDomain, minRadius, maxRadius);
  const ramp = hotspotRamp(theme);

  const points: PlacedPoint[] = entities.map((entity) => {
    const xValue = entityValue(entity, encoding.x);
    const yValue = entityValue(entity, encoding.y);
    const sizeValue = entityValue(entity, encoding.size);
    const colorValue = entityValue(entity, encoding.color);
    return {
      entity,
      cx: xScale(xValue),
      cy: yScale(yValue),
      radius: rScale(sizeValue),
      fill: hotspotColorCssAt(colorValue, ramp),
      label: entityLabel(entity, encoding.label),
      xValue,
      yValue,
      sizeValue,
      colorValue,
    };
  });

  const xTicks: AxisTick[] = ticks(xDomain, DEFAULT_TICK_COUNT).map((value) => ({
    value,
    position: xScale(value),
  }));
  const yTicks: AxisTick[] = ticks(yDomain, DEFAULT_TICK_COUNT).map((value) => ({
    value,
    position: yScale(value),
  }));

  const legend: LegendStop[] = ticks({ min: 0, max: 1 }, DEFAULT_LEGEND_STOPS - 1).map((score) => ({
    score,
    fill: hotspotColorCssAt(score, ramp),
  }));

  return { points, xTicks, yTicks, legend, xDomain, yDomain, sizeDomain, ramp };
}

/** A sensible default plot box (a square-ish scatter) when a caller does not size it explicitly. */
export const DEFAULT_PLOT_DIMENSIONS: PlotDimensions = {
  width: 640,
  height: 480,
  margin: 48,
  minRadius: 4,
  maxRadius: 28,
};

/** Re-export the ramp colour helper so a consumer can recolour a stop without reaching into scales. */
export { hotspotColorAt };
