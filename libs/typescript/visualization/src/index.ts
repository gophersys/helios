/**
 * `@eden/visualization` — the Eden codebase-insight visualization primitives barrel (ADR-0024,
 * codeinsight contract §5).
 *
 * Accessible Svelte 5 widgets GENERATED FROM THE MATH that render a codeinsight `Report`'s `Views`
 * with zero per-repo code: every colour/size/space is DERIVED from an `@eden/theme` token (never
 * hand-set), the scatter scales + the perceptually-ordered sequential hotspot ramp are pure math
 * (mutation-proof), and each widget carries a mechanical design-correctness proof (the contrast gate +
 * perceptual ordering + the 44px hit-target floor, in `*.design.test.ts`) and an a11y-evidence record
 * (axe on Chromium+WebKit + keyboard + an offscreen data-table fallback, in `tests-a11y/`).
 * MATH IS SOURCE OF TRUTH.
 *
 * This barrel is a pure re-export (no logic; excluded from the coverage floor — see vitest.config).
 */

// ── the codeinsight Report types — the CONSUMER half of the contract seam (contract §3) ─────────
// The TypeScript projection of the Go `codeinsight.Report` wire shape (JSON tags mirrored exactly).
// A widget's props ARE these contract types, so the producer (Go) and consumer (this lib) build
// independently against the one envelope.
export type {
  Report,
  RepositoryRef,
  Window,
  Entity,
  Coupling,
  Ownership,
  DoraKeys,
  Summary,
  TrendPoint,
  TrendSeries,
  View,
} from './report/index.js';

// ── HotspotMap — the signature churn × complexity scatter (the first of the 8 primitives) ───────
// Payload-driven: `entities` + an `encoding` channel→field map render any scatter View. Its
// appearance is DERIVED from @eden/theme (tokens.ts), its geometry from the pure scales (scales.ts)
// composed into a placed plan (plot.ts), and it is proven by a design-correctness test (contrast gate
// + perceptual ordering + the 44px floor) and an a11y-evidence record (axe Chromium+WebKit + keyboard
// + the offscreen data-table fallback).
export {
  HotspotMap,
  deriveHotspotMapTokens,
  hotspotMapStyleVars,
  rampPx,
  hitTargetPx,
  extentOf,
  linearScale,
  radiusScale,
  hotspotRamp,
  hotspotColorAt,
  hotspotColorCssAt,
  ticks,
  entityValue,
  entityLabel,
  buildHotspotPlot,
  DEFAULT_HOTSPOT_ENCODING,
  DEFAULT_PLOT_DIMENSIONS,
  type HotspotMapTokens,
  type StyleEntry,
  type Interval,
  type HotspotRamp,
  type HotspotEncoding,
  type PlotDimensions,
  type PlacedPoint,
  type AxisTick,
  type LegendStop,
  type HotspotPlot,
} from './hotspot-map/index.js';
