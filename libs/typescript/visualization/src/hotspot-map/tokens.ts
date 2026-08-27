/**
 * `@eden/visualization` — the hotspot-map TOKEN DERIVATION (ADR-0024 §3, the ninth dimension).
 *
 * MATH IS SOURCE OF TRUTH. The scatter's CHROME — the plot background, the axis lines + tick labels,
 * the point labels, the colour-legend caption, the spacing and the corner radius — is decided here,
 * every value DERIVED from a generated {@link Theme}: a colour is an OKLCH read out of a semantic role
 * (`surface` / `onSurface` / `outline`), a size is a generated typography role, a space is a
 * spacing-ramp step, the hit floor is the theme's decoupled 44px tap target. Nothing is hand-set.
 *
 * `@eden/visualization` depends ONLY on `@eden/theme` (not on `@eden/primitives`), so it reads the
 * roles straight from the theme rather than citing the chat-surface vocabulary — there is no
 * cross-lib duplication of a FORMULA here (the role/scale tables live once in `@eden/theme`; this
 * module merely SELECTS roles), which the cohesion scan permits. The scatter SCALE math lives in its
 * own home (./scales.ts); this module is the colour/size/space chrome.
 */

import type { Theme, OkLch } from '@eden/theme';
import { oklchToCss } from '@eden/theme';

/** The CSS-variable namespace every hotspot-map custom property carries (one prefix). */
const VAR_PREFIX = '--eden-hotspot-map';

/**
 * Find a typography role by name, falling back to `body` then the first generated role. A generated
 * theme always carries `body` (index 0), so the final fallback is defensive totality, never hit in
 * practice — the same totality contract the chat-surface `proportion` keeps. Returns the size +
 * line-height (px) of the role.
 */
function roleSizePx(theme: Theme, name: string): { fontSizePx: number; lineHeightPx: number } {
  const role =
    theme.typography.find((r) => r.name === name) ??
    theme.typography.find((r) => r.name === 'body') ??
    theme.typography[0];
  if (!role) return { fontSizePx: 0, lineHeightPx: 0 };
  return {
    fontSizePx: role.fontSizePx,
    lineHeightPx: Math.round(role.fontSizePx * role.lineHeight),
  };
}

/** The font family of the reading (`body`) role — the family the chart text renders in. */
function bodyFontFamily(theme: Theme): string {
  const role = theme.typography.find((r) => r.name === 'body') ?? theme.typography[0];
  return role ? role.fontFamily : 'inherit';
}

/**
 * Pick the spacing-ramp step at a 0-based INDEX into the generated ramp, so every space the chart
 * renders is provably a ramp step (the ramp is brand-invariant: 2, 4, 8, 12, 16, 20, 24, …). The
 * index is clamped into range so the pick is total for any ramp length. (The same selection the
 * chat-surface `space` makes; this is a ROLE/STEP pick, not a re-derivation of the ramp FORMULA,
 * which lives once in `@eden/theme`.)
 */
function spaceAt(theme: Theme, index: number): number {
  const ramp = theme.spacing;
  const i = Math.max(0, Math.min(index, ramp.length - 1));
  const step = ramp[i];
  return step ? step.px : 0;
}

/** The set of px values on the generated spacing ramp — the membership oracle the design lane asserts. */
export function rampPx(theme: Theme): readonly number[] {
  return theme.spacing.map((s) => s.px);
}

/** The decoupled AAA hit-target floor (px) — the SAME value every Eden control guarantees (≥44 touch). */
export function hitTargetPx(theme: Theme): number {
  return theme.controlGeometry.hitTargetPx;
}

/** The resolved token set a hotspot-map renders its chrome from (plot + axes + labels + legend). */
export interface HotspotMapTokens {
  /** The plot fill (the reading surface) as a CSS `oklch(...)` string. */
  readonly plotBackground: string;
  /** The reading text colour (axis tick labels, point labels) as a CSS `oklch(...)` string. */
  readonly foreground: string;
  /** The axis / gridline colour (the outline role) as a CSS `oklch(...)` string. */
  readonly axis: string;
  /** A point's stroke (the outline role) so a light dot stays visible on the surface. */
  readonly pointStroke: string;
  /** The raw OKLCH of the reading text — the contrast gate recomputes the ratio from THIS. */
  readonly foregroundOklch: OkLch;
  /** The raw OKLCH of the plot fill — the contrast gate recomputes the ratio from THIS. */
  readonly plotBackgroundOklch: OkLch;
  /** The raw OKLCH of the axis colour — the contrast gate recomputes its UI-contrast over the surface. */
  readonly axisOklch: OkLch;
  /** The axis tick-label font size, px — the `caption` typography role. */
  readonly tickLabelSizePx: number;
  /** The point-label / legend font size, px — the `label` typography role. */
  readonly labelSizePx: number;
  /** The label line height, px — the `label` role's line height. */
  readonly labelLineHeightPx: number;
  /** The chart font family — the `body` role family. */
  readonly fontFamily: string;
  /** The chart outer padding, px — a spacing-ramp step. */
  readonly paddingPx: number;
  /** The gap between the legend swatches, px — a spacing-ramp step. */
  readonly gapPx: number;
  /** The plot corner radius, px — a spacing-ramp step. */
  readonly radiusPx: number;
  /** The decoupled 44px hit-target floor for an interactive point's tap area. */
  readonly hitTargetPx: number;
}

/**
 * Derive the full {@link HotspotMapTokens} from a generated theme. PURE: every colour is an OKLCH read
 * out of a semantic role; every size is a typography role; every space is a ramp step; the hit floor
 * is the theme's decoupled tap target. The plot is the reading surface (`onSurface` text over
 * `surface` — the highest-contrast pair the theme resolves), the axes are the `outline` role.
 */
export function deriveHotspotMapTokens(theme: Theme): HotspotMapTokens {
  const roles = theme.roles;
  const tickLabel = roleSizePx(theme, 'caption');
  const label = roleSizePx(theme, 'label');
  return {
    plotBackground: oklchToCss(roles.surface.value),
    foreground: oklchToCss(roles.onSurface.value),
    axis: oklchToCss(roles.outline.value),
    pointStroke: oklchToCss(roles.outline.value),
    foregroundOklch: roles.onSurface.value,
    plotBackgroundOklch: roles.surface.value,
    axisOklch: roles.outline.value,
    tickLabelSizePx: tickLabel.fontSizePx,
    labelSizePx: label.fontSizePx,
    labelLineHeightPx: label.lineHeightPx,
    fontFamily: bodyFontFamily(theme),
    paddingPx: spaceAt(theme, 4), // 16px
    gapPx: spaceAt(theme, 2), // 8px
    radiusPx: spaceAt(theme, 3), // 12px
    hitTargetPx: hitTargetPx(theme),
  };
}

/** A `[suffix, value]` style entry — a colour string passes through, a number is suffixed `px`. */
export type StyleEntry = readonly [suffix: string, value: string | number];

/**
 * Render a list of `[suffix, value]` pairs as an inline `style` custom-property string under the
 * hotspot-map prefix — the seam that keeps the `.svelte` free of literals (it references
 * `var(--eden-hotspot-map-*)` only). A numeric value is suffixed `px`; a string passes through. This
 * is local to the lib (no cross-lib import of the chat-surface emitter, which lives in a sibling lib
 * `@eden/visualization` does not depend on); it is the same trivial join, not a duplicated FORMULA.
 */
export function hotspotMapStyleVars(tokens: HotspotMapTokens): string {
  const entries: readonly StyleEntry[] = [
    ['plot-bg', tokens.plotBackground],
    ['fg', tokens.foreground],
    ['axis', tokens.axis],
    ['point-stroke', tokens.pointStroke],
    ['tick-label-size', tokens.tickLabelSizePx],
    ['label-size', tokens.labelSizePx],
    ['label-line-height', tokens.labelLineHeightPx],
    ['font-family', tokens.fontFamily],
    ['padding', tokens.paddingPx],
    ['gap', tokens.gapPx],
    ['radius', tokens.radiusPx],
    ['hit-target', tokens.hitTargetPx],
  ];
  return entries
    .map(([suffix, value]) => {
      const css = typeof value === 'number' ? `${String(value)}px` : value;
      return `${VAR_PREFIX}-${suffix}: ${css};`;
    })
    .join(' ');
}
