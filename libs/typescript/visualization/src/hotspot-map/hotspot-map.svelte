<!--
  @eden/visualization — HotspotMap (ADR-0024 / codeinsight contract §5). The signature codebase-insight
  view: a churn × complexity scatter. x=churnRelative · y=cyclomatic · size=lines · color=hotspotScore ·
  label=path (the contract's default `hotspot-map` encoding) — but PAYLOAD-DRIVEN: the `encoding` prop
  points each visual channel at a report field, so this renders ANY scatter View over a Report's entities.

  The APPEARANCE is decided entirely by buildHotspotPlot (plot.ts) + deriveHotspotMapTokens (tokens.ts):
  every point's cx/cy/radius/fill and every colour/size/space is a CSS custom property whose value is
  DERIVED from an @eden/theme token; this template references var(--eden-hotspot-map-*) and the placed
  plan values only — it carries NO literal colour and NO literal px decided by hand.

  ACCESSIBILITY (a qa-gate blocker): the figure has a role + accessible name; the SVG is role="img" with
  a generated description; an OFFSCREEN data-table fallback enumerates every point (path + the four
  metrics) so a scatter — which a screen reader cannot otherwise read — is fully announced; and each
  point is a keyboard-focusable target with a ≥44px invisible hit area (the AAA tap floor) carrying its
  own accessible label, so the points are reachable and described without colour being the only signal.
-->
<script lang="ts">
  import type { Theme } from '@eden/theme';
  import { generateTheme, C21_SEED } from '@eden/theme';
  import type { Entity } from '../report/index.js';
  import { deriveHotspotMapTokens, hotspotMapStyleVars } from './tokens.js';
  import {
    buildHotspotPlot,
    DEFAULT_HOTSPOT_ENCODING,
    DEFAULT_PLOT_DIMENSIONS,
    type HotspotEncoding,
    type PlotDimensions,
  } from './plot.js';

  interface HotspotMapProps {
    /** The Report entities to plot (Report.entities — contract §3). */
    entities: readonly Entity[];
    /** The visual-channel → report-field map; defaults to the contract's `hotspot-map` binding. */
    encoding?: Partial<HotspotEncoding>;
    /** The plot box + margins; defaults to a 640×480 square-ish scatter. */
    dimensions?: Partial<PlotDimensions>;
    /** An accessible title for the figure (the chart's name). */
    title?: string;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
  }

  let {
    entities,
    encoding,
    dimensions,
    title = 'Hotspot map: churn versus complexity',
    theme,
  }: HotspotMapProps = $props();

  const resolvedTheme = $derived(theme ?? generateTheme(C21_SEED));
  const resolvedEncoding = $derived<HotspotEncoding>({ ...DEFAULT_HOTSPOT_ENCODING, ...encoding });
  const resolvedDimensions = $derived<PlotDimensions>({
    ...DEFAULT_PLOT_DIMENSIONS,
    ...dimensions,
  });
  const tokens = $derived(deriveHotspotMapTokens(resolvedTheme));
  const styleVars = $derived(hotspotMapStyleVars(tokens));
  const plot = $derived(
    buildHotspotPlot(entities, resolvedEncoding, resolvedTheme, resolvedDimensions),
  );

  /** A compact human readout of a number (a tick label / a metric) — at most 2 decimals, trimmed. */
  function fmt(value: number): string {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }

  /** A per-point accessible description: the path and the four encoded metrics, never colour alone. */
  function pointLabel(label: string, x: number, y: number, size: number, score: number): string {
    return `${label}: ${resolvedEncoding.x} ${fmt(x)}, ${resolvedEncoding.y} ${fmt(y)}, ${resolvedEncoding.size} ${fmt(size)}, ${resolvedEncoding.color} ${fmt(score)}`;
  }

  const description = $derived(
    `Scatter of ${String(plot.points.length)} entities. Horizontal axis ${resolvedEncoding.x}, vertical axis ${resolvedEncoding.y}, dot area ${resolvedEncoding.size}, colour ${resolvedEncoding.color}.`,
  );
</script>

<figure
  class="eden-hotspot-map"
  data-eden-hotspot-map=""
  role="group"
  aria-label={title}
  style={styleVars}
>
  <figcaption class="eden-hotspot-map-caption">{title}</figcaption>

  <!-- A visually-hidden description of the encoding (the chart's "what it shows"), announced for the
       figure. The SVG is NOT role="img": an img role makes its subtree presentational, which would
       hide the points AND nest the interactive point-targets under an image (axe nested-interactive).
       Instead the SVG is a plain graphics container — the axes/dots/tick-text are decorative
       (aria-hidden), and the ACCESSIBLE layer is the focusable point-targets (real buttons, kept OUT
       of any aria-hidden subtree) + the offscreen data table below. -->
  <p class="eden-hotspot-map-visually-hidden">{description}</p>

  <svg
    class="eden-hotspot-map-svg"
    viewBox={`0 0 ${String(resolvedDimensions.width)} ${String(resolvedDimensions.height)}`}
    width={resolvedDimensions.width}
    height={resolvedDimensions.height}
  >
    <!-- axes (the outline role) — decorative; the axis meaning is in the description + the data table. -->
    <line
      class="eden-hotspot-map-axis"
      aria-hidden="true"
      x1={resolvedDimensions.margin}
      y1={resolvedDimensions.height - resolvedDimensions.margin}
      x2={resolvedDimensions.width - resolvedDimensions.margin}
      y2={resolvedDimensions.height - resolvedDimensions.margin}
    />
    <line
      class="eden-hotspot-map-axis"
      aria-hidden="true"
      x1={resolvedDimensions.margin}
      y1={resolvedDimensions.margin}
      x2={resolvedDimensions.margin}
      y2={resolvedDimensions.height - resolvedDimensions.margin}
    />

    <!-- x tick labels (decorative) -->
    {#each plot.xTicks as tick (tick.position)}
      <text
        class="eden-hotspot-map-tick"
        aria-hidden="true"
        x={tick.position}
        y={resolvedDimensions.height - resolvedDimensions.margin + tokens.tickLabelSizePx + 4}
        text-anchor="middle">{fmt(tick.value)}</text
      >
    {/each}
    <!-- y tick labels (decorative) -->
    {#each plot.yTicks as tick (tick.position)}
      <text
        class="eden-hotspot-map-tick"
        aria-hidden="true"
        x={resolvedDimensions.margin - 6}
        y={tick.position + tokens.tickLabelSizePx / 3}
        text-anchor="end">{fmt(tick.value)}</text
      >
    {/each}

    <!-- the placed scatter points: a decorative dot + a focusable ≥44px hit-target that IS the
         accessible point. The dot is aria-hidden (its colour is duplicated by the point's label +
         the data table — colour is never the only signal); the hit-target carries the accessible
         name (path + the four metrics). The targets are NOT nested in any interactive/img ancestor. -->
    {#each plot.points as point (point.label)}
      <circle
        class="eden-hotspot-map-dot"
        aria-hidden="true"
        cx={point.cx}
        cy={point.cy}
        r={point.radius}
        fill={point.fill}
      />
      <rect
        class="eden-hotspot-map-hit"
        x={point.cx - tokens.hitTargetPx / 2}
        y={point.cy - tokens.hitTargetPx / 2}
        width={tokens.hitTargetPx}
        height={tokens.hitTargetPx}
        tabindex="0"
        role="button"
        aria-label={pointLabel(
          point.label,
          point.xValue,
          point.yValue,
          point.sizeValue,
          point.colorValue,
        )}
      ></rect>
    {/each}
  </svg>

  <!-- the colour legend (hotspot score low→high), with words so colour is never the only signal -->
  <div class="eden-hotspot-map-legend" aria-label={`${resolvedEncoding.color} legend, low to high`}>
    <span class="eden-hotspot-map-legend-word">low</span>
    {#each plot.legend as stop (stop.score)}
      <span
        class="eden-hotspot-map-legend-swatch"
        style={`background: ${stop.fill};`}
        title={`${resolvedEncoding.color} ${fmt(stop.score)}`}
      ></span>
    {/each}
    <span class="eden-hotspot-map-legend-word">high</span>
  </div>

  <!--
    The OFFSCREEN data-table fallback: a real <table> enumerating every point's path + metrics, so a
    screen reader (which cannot read an SVG scatter) gets the full data. Visually hidden, fully present
    in the accessibility tree.
  -->
  <table class="eden-hotspot-map-visually-hidden">
    <caption>{title} — data table</caption>
    <thead>
      <tr>
        <th scope="col">{resolvedEncoding.label}</th>
        <th scope="col">{resolvedEncoding.x}</th>
        <th scope="col">{resolvedEncoding.y}</th>
        <th scope="col">{resolvedEncoding.size}</th>
        <th scope="col">{resolvedEncoding.color}</th>
      </tr>
    </thead>
    <tbody>
      {#each plot.points as point (point.label)}
        <tr>
          <th scope="row">{point.label}</th>
          <td>{fmt(point.xValue)}</td>
          <td>{fmt(point.yValue)}</td>
          <td>{fmt(point.sizeValue)}</td>
          <td>{fmt(point.colorValue)}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</figure>

<style>
  .eden-hotspot-map {
    display: flex;
    flex-direction: column;
    gap: var(--eden-hotspot-map-gap);
    box-sizing: border-box;
    margin: 0;
    padding: var(--eden-hotspot-map-padding);
    border-radius: var(--eden-hotspot-map-radius);
    color: var(--eden-hotspot-map-fg);
    background: var(--eden-hotspot-map-plot-bg);
    border: 1px solid var(--eden-hotspot-map-axis);
    font-family: var(--eden-hotspot-map-font-family);
  }

  .eden-hotspot-map-caption {
    font-size: var(--eden-hotspot-map-label-size);
    line-height: var(--eden-hotspot-map-label-line-height);
    font-weight: 600;
  }

  .eden-hotspot-map-svg {
    inline-size: 100%;
    block-size: auto;
  }

  .eden-hotspot-map-axis {
    stroke: var(--eden-hotspot-map-axis);
    stroke-width: 1;
  }

  .eden-hotspot-map-tick {
    fill: var(--eden-hotspot-map-fg);
    font-size: var(--eden-hotspot-map-tick-label-size);
  }

  .eden-hotspot-map-dot {
    stroke: var(--eden-hotspot-map-point-stroke);
    stroke-width: 1;
  }

  /* The hit target is invisible ink but a real, focusable, ≥44px box. */
  .eden-hotspot-map-hit {
    fill: transparent;
    cursor: pointer;
  }

  .eden-hotspot-map-hit:focus-visible {
    outline: 2px solid var(--eden-hotspot-map-fg);
    outline-offset: 1px;
  }

  .eden-hotspot-map-legend {
    display: flex;
    align-items: center;
    gap: var(--eden-hotspot-map-gap);
    font-size: var(--eden-hotspot-map-label-size);
  }

  .eden-hotspot-map-legend-swatch {
    inline-size: var(--eden-hotspot-map-label-size);
    block-size: var(--eden-hotspot-map-label-size);
    border-radius: 2px;
    border: 1px solid var(--eden-hotspot-map-axis);
  }

  .eden-hotspot-map-visually-hidden {
    position: absolute;
    inline-size: 1px;
    block-size: 1px;
    margin: -1px;
    padding: 0;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
    border: 0;
  }
</style>
