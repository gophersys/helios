/**
 * `@eden/primitives` — the Wave-1 surface token vocabulary (ADR-0024 §3, doc 17 §3/§4).
 *
 * MATH IS SOURCE OF TRUTH, and ONE CONCEPT ONE HOME (10 §9). Doc 17 §3 rules THREE radii
 * (control · surface · sheet), and Wave-1's molecules (Card, EmptyState, Tabs) plus its status
 * atoms (Badge, Chip) all draw from the SAME small set of derived primitives: a RADIUS chosen from
 * the generated spacing ramp, an ELEVATION `box-shadow` composed from the theme's `motion.elevation`
 * recipe, and a STATUS role selection onto the theme's semantic hues. This module is the single home
 * those primitives are derived; every Wave-1 component's `tokens.ts` CITES these helpers (and the
 * chat-surface vocabulary — `space`, `proportion`, `rampPx`, `stateSurface`, `styleVars`) and never
 * re-spells a ramp lookup, a shadow recipe, or a status→role mapping.
 *
 * Nothing here is decided by hand. A radius is a real spacing-ramp step (so "on the scale" is a
 * property of the value, asserted in the design lane). An elevation shadow reads the theme's
 * generated `motion.elevation` layers at a named LEVEL — a derived umbra (the on-surface role at the
 * layer's derived alpha), never a pasted `rgba(0,0,0,…)` (this mirrors the overlay lib's proven
 * `elevationShadowAt`, cited in spirit — but the overlay module is portal-scoped and not a
 * foundation export, so the wave surfaces keep their own copy-free home here). A status selection is
 * a pick onto the theme's `success`/`warning`/`error`/`info`/`outline`/`primary` roles — the SAME
 * triple-encoding the Clusters north star reads (a role colour + a word; the shape channel lives in
 * the app's StatusGlyph, cited by the Clusters legend).
 */

import { oklchToCss, type Theme, type OkLch } from '@eden/theme';

// ── radii (doc 17 §3: three radii — control · surface · sheet) ─────────────────────────────────

/**
 * The three named corner radii doc 17 §3 rules. Each is a SELECTION of a spacing-ramp rung, never a
 * hand-set 6/10: `control` (the tightest, for chips/badges/inputs) is `space-1` (4px at the default
 * base), `surface` (cards/panels) is `space-2` (8px), `sheet` (the largest, for side panels/modals)
 * is `space-3` (12px). One monotonic set drawn from ONE ramp — the same ramp every space is drawn
 * from, so radii and spacing read as one system. The mapping is the ONE design decision here.
 */
export type Radius = 'control' | 'surface' | 'sheet';

const RADIUS_RAMP_KEY: Readonly<Record<Radius, string>> = {
  control: '1',
  surface: '2',
  sheet: '3',
};

/** Find a spacing-ramp step by its multiplier key (e.g. `'2'` → 8px) — cites the theme ramp. */
function rampStepPx(theme: Theme, key: string): number {
  const step = theme.spacing.find((s) => s.name === `space-${key}`);
  // The ramp is the curated research Table B2-A and always carries these rungs; the fallback keeps
  // the function total (and would surface in the design test's ramp-membership assertion).
  return step ? step.px : theme.controlGeometry.insetPx;
}

/**
 * The px radius for a named {@link Radius} — a real spacing-ramp step. `radiusPx(theme, 'surface')`
 * yields `8` for the default ramp; the value's ramp-membership is asserted in the design lane, so it
 * is provably a scale value, not eyeballed.
 */
export function radiusPx(theme: Theme, radius: Radius): number {
  return rampStepPx(theme, RADIUS_RAMP_KEY[radius]);
}

// ── elevation (doc 17 §3: two shadows — raised · overlay) ──────────────────────────────────────

/**
 * The two named elevations doc 17 §3 rules. `raised` is the resting card/panel lift (a small, close
 * shadow); `overlay` is the floating-surface lift (a larger, softer shadow for a menu/popover). Each
 * is a SELECTION of a `motion.elevation` ladder LEVEL, never a hand-set shadow — `raised` draws the
 * ladder's level 2 (the first true lift above the flat level 1), `overlay` draws level 8 (the same
 * mid lift the overlay lib gives a dropdown). The mapping rides the SAME name the Card's `raised`
 * variant and any floating surface select, so depth stays consistent across the wave.
 */
export type Elevation = 'raised' | 'overlay';

const ELEVATION_LEVEL: Readonly<Record<Elevation, number>> = {
  raised: 2,
  overlay: 8,
};

/** Serialize an OKLCH colour WITH an alpha channel as a CSS `oklch(L C H / a)` string. The L/C/H
 *  come verbatim from a theme role (no colour invented — only the transparency is derived), and the
 *  4-decimal rounding mirrors @eden/theme's own `oklchToCss` precision so the two agree on the
 *  colour. This is the one extra serialization concern a shadow umbra needs (`oklchToCss` is
 *  opaque-only). */
function oklchWithAlpha({ l, c, h }: OkLch, alpha: number): string {
  const r4 = (n: number): number => Math.round(n * 10000) / 10000;
  return `oklch(${String(r4(l))} ${String(r4(c))} ${String(r4(h))} / ${String(alpha)})`;
}

/**
 * Compose the elevation `box-shadow` from the theme's `motion.elevation` recipe at a named level.
 * Each elevation entry is a STACK of `ShadowLayer`s (offset/blur derived from the research B5-E
 * formula `blur = 2·y`, alpha falling off per layer); we render each layer as one `box-shadow`
 * segment whose colour is the on-surface role at the layer's derived alpha (a DERIVED umbra, never a
 * pasted `rgba(0,0,0,…)`). The LEVEL is an index into the theme's generated ladder, not a magic
 * depth — so a raised card's lift is a property of the theme's motion slice, asserted in the design
 * lane (the emitted shadow segments equal the theme's `motion.elevation` layers).
 */
export function elevationShadow(theme: Theme, elevation: Elevation): string {
  const level = ELEVATION_LEVEL[elevation];
  const entry = theme.motion.elevation.find((e) => e.level === level) ?? theme.motion.elevation[0];
  // The elevation ladder is always generated (research B5-E, levels 1..24); the fallback keeps the
  // function total if a future seed reshaped the ladder.
  const layers = entry ? entry.layers : [];
  const umbra = theme.roles.onSurface.value;
  return layers
    .map((layer) => {
      const color = oklchWithAlpha(umbra, layer.alpha);
      return `${px(layer.offsetXPx)} ${px(layer.offsetYPx)} ${px(layer.blurPx)} ${color}`;
    })
    .join(', ');
}

/** Render a number as a `<n>px` CSS length. */
function px(n: number): string {
  return `${String(n)}px`;
}

// ── status (the Clusters health vocabulary: a role colour + a word) ────────────────────────────

/**
 * The status/health vocabulary the Clusters north star reads — a role colour keyed to a cultural
 * hue. `healthy` → `success`, `updating` → `info`, `degraded` → `warning`, `down` → `error`,
 * `unknown` → `outline` (the exact mapping the app's `topology/status.ts` table uses), plus two
 * chrome variants: `neutral` → `outline` (a quiet count/label) and `accent` → `primary` (a brand
 * emphasis). These are the SAME semantic roles @eden/theme resolves through the contrast gate, so a
 * status colour rendered as text over the surface clears AA by construction (asserted in the design
 * lane). The mapping is the ONE design decision here; colour is never the ONLY channel — the atoms
 * that use it always pair the colour with a WORD (Badge/Chip render a label), the third
 * grayscale-safe channel (the glyph SHAPE) is the Clusters `StatusGlyph`'s job, cited by the legend.
 */
export type Status =
  | 'healthy'
  | 'updating'
  | 'degraded'
  | 'down'
  | 'unknown'
  | 'neutral'
  | 'accent';

/** Resolve a {@link Status} to its semantic-role OKLCH out of a generated theme (never a hex). */
export function statusRoleOklch(status: Status, theme: Theme): OkLch {
  const r = theme.roles;
  switch (status) {
    case 'healthy':
      return r.success.value;
    case 'updating':
      return r.info.value;
    case 'degraded':
      return r.warning.value;
    case 'down':
      return r.error.value;
    case 'unknown':
    case 'neutral':
      return r.outline.value;
    case 'accent':
      return r.primary.value;
  }
}

/** Resolve a {@link Status} to its role colour as a CSS `oklch(...)` string (cites the OKLCH above). */
export function statusRole(status: Status, theme: Theme): string {
  return oklchToCss(statusRoleOklch(status, theme));
}

/**
 * A translucent VIEW of a status role at a given alpha — used for a Badge/Chip TINT fill (a soft
 * wash of the status colour behind the legible text/border), mirroring the Clusters chip's
 * `color-mix(in oklab, var(--tint) …%, …)` wash. The L/C/H are the role's verbatim (no colour
 * invented — only transparency is derived), so the tint is provably a view of a theme colour.
 */
export function statusTint(status: Status, theme: Theme, alpha: number): string {
  return oklchWithAlpha(statusRoleOklch(status, theme), alpha);
}
