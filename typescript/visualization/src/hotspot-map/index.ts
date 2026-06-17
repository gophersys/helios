/**
 * `@eden/visualization` — the HotspotMap public surface. One concept, one home — the appearance is
 * decided in `tokens.ts`, the scatter math in `scales.ts`, and the placed render plan in `plot.ts`;
 * cited here.
 */
export { default as HotspotMap } from './hotspot-map.svelte';

export {
  deriveHotspotMapTokens,
  hotspotMapStyleVars,
  rampPx,
  hitTargetPx,
  type HotspotMapTokens,
  type StyleEntry,
} from './tokens.js';

export {
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

export {
  buildHotspotPlot,
  DEFAULT_HOTSPOT_ENCODING,
  DEFAULT_PLOT_DIMENSIONS,
  type HotspotEncoding,
  type PlotDimensions,
  type PlacedPoint,
  type AxisTick,
  type LegendStop,
  type HotspotPlot,
} from './plot.js';
