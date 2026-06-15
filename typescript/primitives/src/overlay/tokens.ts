/**
 * `@eden/primitives` — Overlay token derivation (ADR-0024 §3, the ninth dimension).
 *
 * The SHARED token math for every PORTALED overlay surface — Dialog, Popover, Tooltip,
 * DropdownMenu (RD-16/OD-1: compose `*.Portal` / `*.Content` from bits-ui@2.18.1). MATH IS SOURCE
 * OF TRUTH: this module is the ONE place an overlay's appearance is decided, and it decides nothing
 * by hand. Every color is READ OUT of a generated {@link Theme} from `@eden/theme`
 * (`generateTheme(seed)`); every size/space is a value from the theme's spacing ramp or
 * controlGeometry; the surface elevation is the theme's `motion.elevation` shadow recipe; the
 * stacking order is the theme's `motion.zIndex` ladder. The component markup consumes the
 * `--eden-overlay-*` custom properties this module emits — it carries no literal color and no
 * literal px. That is what makes the design-correctness gate mechanical: the contrast of the
 * `fg`/`bg` pair, the scale-provenance of every size, and the 44px hit-target floor are PROPERTIES
 * of the values this function returns, asserted in `overlay.design.test.ts`.
 *
 * THE PORTAL CONTRACT (OD-1): bits-ui renders Content into a Portal whose default host is
 * `document.body` — OUTSIDE the triggering component's DOM subtree. So the tokens cannot ride
 * component-scoped CSS; they are emitted as an inline `style` custom-property string bound onto the
 * portaled Content element ITSELF (bits-ui spreads `style` onto the rendered node, and CSS custom
 * properties inherit down the portaled subtree). The OD-1 spike proved this clears axe with Eden
 * tokens through the Portal on Chromium AND WebKit; this module is the token half of that proof.
 */

import {
  generateTheme,
  oklchToCss,
  C21_SEED,
  type Theme,
  type ThemeSeed,
  type GenerateOptions,
  type OkLch,
} from '@eden/theme';

/** The CSS-variable namespace every overlay custom property carries (one prefix, derived names). */
const VAR_PREFIX = '--eden-overlay';

/**
 * The stacking layer an overlay surface occupies — a SELECTION of a `motion.zIndex` ladder rung,
 * never a hand-typed z value. Each rung is named for the overlay family it serves (the research
 * Table B5-F gapped-100 ladder): a tooltip sits above a dropdown sits above a raised surface, and a
 * modal dialog draws its scrim at the modal rung. The mapping is the ONE design decision here.
 */
export type OverlayLayer = 'dropdown' | 'modal' | 'tooltip';

/**
 * The resolved token set a portaled overlay surface renders from. Every field is a CSS value
 * DERIVED from a generated {@link Theme} — an `oklch(...)` string for a color, a `<n>px` string (or
 * a composed `box-shadow`) for a dimension, a bare ordinal for the z-index. The raw OKLCH / numeric
 * values are kept alongside (the `*Oklch` / `*Px` fields) so the design-correctness gate can
 * recompute the contrast ratio and check scale provenance from the SAME numbers the CSS carries
 * (the proof is honest — it audits the emitted value, not a copy).
 */
export interface OverlayTokens {
  /** The surface (panel) background color as a CSS `oklch(...)` string. */
  readonly surface: string;
  /** The on-surface (text/icon) foreground color as a CSS `oklch(...)` string. */
  readonly onSurface: string;
  /** The hairline border/separator color as a CSS `oklch(...)` string (the outline role). */
  readonly outline: string;
  /** The scrim (modal backdrop) color as a CSS `oklch(...)` string — the surface inverse, dimmed. */
  readonly scrim: string;
  /** The raw OKLCH of the surface — the contrast gate recomputes the ratio from this. */
  readonly surfaceOklch: OkLch;
  /** The raw OKLCH of the on-surface foreground — the contrast gate recomputes the ratio from this. */
  readonly onSurfaceOklch: OkLch;
  /** The composed elevation `box-shadow` string — derived from the theme's `motion.elevation`. */
  readonly elevationShadow: string;
  /** The z-index ordinal — a SELECTION of a `motion.zIndex` ladder rung (the stacking layer). */
  readonly zIndex: number;
  /** The corner radius, px — a value from the spacing ramp (a scale value, never eyeballed). */
  readonly radiusPx: number;
  /** The internal padding, px — a value from the spacing ramp. */
  readonly paddingPx: number;
  /** The trigger↔content offset (gap), px — the theme controlGeometry gap (on the 4px grid). */
  readonly gapPx: number;
  /** The minimum hit target, px — the decoupled AAA tap area (theme.controlGeometry.hitTargetPx). */
  readonly hitTargetPx: number;
  /** The font size, px — INVARIANT under density (theme.controlGeometry.fontSizePx). */
  readonly fontSizePx: number;
  /** The line height, px (theme.controlGeometry.lineHeightPx — WCAG 1.4.12 floor applied upstream). */
  readonly lineHeightPx: number;
  /** The text font family — the theme's `body` typography role family (the seed's text font). */
  readonly fontFamily: string;
}

/** Map an overlay layer to its z-index ordinal out of the generated theme's `motion.zIndex` ladder. */
function zIndexFor(layer: OverlayLayer, theme: Theme): number {
  const z = theme.motion.zIndex;
  switch (layer) {
    case 'dropdown':
      return z.dropdown;
    case 'modal':
      return z.modal;
    case 'tooltip':
      return z.tooltip;
  }
}

/**
 * Compose the elevation `box-shadow` from the theme's `motion.elevation` recipe at a given level.
 * Each elevation entry is a STACK of `ShadowLayer`s (offset/blur derived from the research B5-E
 * formula `blur = 2·y`, alpha falling off per layer); we render each layer as one `box-shadow`
 * segment whose color is the on-surface role at the layer's alpha (a DERIVED umbra, never a pasted
 * `rgba(0,0,0,…)`). The level is an INDEX into the theme's elevation ladder, not a magic depth.
 */
function elevationShadowAt(theme: Theme, level: number, umbra: OkLch): string {
  const entry = theme.motion.elevation.find((e) => e.level === level) ?? theme.motion.elevation[0];
  // The elevation ladder is always generated (research B5-E, levels 1..24); the fallback keeps the
  // function total if a future seed reshaped the ladder.
  const layers = entry ? entry.layers : [];
  return layers
    .map((layer) => {
      // The umbra color is the on-surface role rendered at the layer's derived alpha (an
      // `oklch(L C H / a)` — alpha is the DERIVED falloff from the theme's elevation recipe, the
      // hue/chroma are the theme's; nothing is invented).
      const color = oklchWithAlpha(umbra, layer.alpha);
      return `${px(layer.offsetXPx)} ${px(layer.offsetYPx)} ${px(layer.blurPx)} ${color}`;
    })
    .join(', ');
}

/** Find a spacing-ramp step by its multiplier key (e.g. `'4'` → 16px) — cites the theme ramp. */
function rampStepPx(theme: Theme, key: string): number {
  const step = theme.spacing.find((s) => s.name === `space-${key}`);
  // The ramp is the curated research Table B2-A and always carries these rungs; the fallback keeps
  // the function total (and would surface in the design test's ramp-membership assertion).
  return step ? step.px : theme.controlGeometry.insetPx;
}

/** The text font family is the theme's `body` typography role family (the seed's text font). */
function bodyFontFamily(theme: Theme): string {
  const body = theme.typography.find((t) => t.name === 'body') ?? theme.typography[0];
  return body ? body.fontFamily : 'inherit';
}

/**
 * Serialize an OKLCH color WITH an alpha channel as a CSS `oklch(L C H / a)` string. `@eden/theme`'s
 * `oklchToCss` is opaque-only (it serializes `{ l, c, h }`); a scrim and a derived shadow umbra need
 * a derived alpha, which is the ONE extra serialization concern this lib owns. The L/C/H come
 * verbatim from the theme role (no color is invented — only the transparency is derived), so this is
 * a translucent VIEW of a theme color, never a hand-set color. The L/C/H rounding mirrors the
 * theme's own `oklchToCss` precision (4 decimals) so the two serializations agree on the same color.
 */
function oklchWithAlpha({ l, c, h }: OkLch, alpha: number): string {
  const r4 = (n: number): number => Math.round(n * 10000) / 10000;
  return `oklch(${String(r4(l))} ${String(r4(c))} ${String(r4(h))} / ${String(alpha)})`;
}

/** Render a number as a `<n>px` CSS length. */
function px(n: number): string {
  return `${String(n)}px`;
}

/**
 * The elevation LEVEL each overlay layer draws at — a SELECTION of a `motion.elevation` ladder rung
 * (research B5-E), never a hand-set shadow. A modal floats highest (level 24, the dialog scrim
 * companion), a dropdown/menu mid (level 8), a tooltip low (level 4 — it is transient and small).
 * The mapping rides the SAME `OverlayLayer` the z-index uses, so order and depth stay consistent.
 */
function elevationLevelFor(layer: OverlayLayer): number {
  switch (layer) {
    case 'modal':
      return 24;
    case 'dropdown':
      return 8;
    case 'tooltip':
      return 4;
  }
}

/**
 * Derive the full {@link OverlayTokens} for a layer from a generated theme. PURE: no globals, no
 * I/O — the theme is the single input (the New(configuration) spine, rule 10). `deriveOverlayTokens`
 * is the function the design-correctness gate audits and every overlay component renders from.
 */
export function deriveOverlayTokens(layer: OverlayLayer, theme: Theme): OverlayTokens {
  const roles = theme.roles;
  const g = theme.controlGeometry;
  return {
    surface: oklchToCss(roles.surface.value),
    onSurface: oklchToCss(roles.onSurface.value),
    outline: oklchToCss(roles.outline.value),
    // The scrim is the on-surface role at a dimming alpha (a DERIVED backdrop, never a pasted
    // black): on a light surface on-surface is near-black, on a dark surface near-white, so the
    // scrim always darkens/contrasts the right way for the mode. 0.5 is the research B5 modal-scrim
    // opacity; it is the ONE scalar here and it is a fraction, not a color literal.
    scrim: oklchWithAlpha(roles.onSurface.value, 0.5),
    surfaceOklch: roles.surface.value,
    onSurfaceOklch: roles.onSurface.value,
    elevationShadow: elevationShadowAt(theme, elevationLevelFor(layer), roles.onSurface.value),
    zIndex: zIndexFor(layer, theme),
    // The panel corner radius is the `space-2` ramp step (8px at the default base) — a small, even
    // radius from the SCALE, not an eyeballed 6/10. The interior padding is `space-4` (16px) — the
    // research comfortable reading inset, again a ramp step.
    radiusPx: rampStepPx(theme, '2'),
    paddingPx: rampStepPx(theme, '4'),
    gapPx: g.gapPx,
    hitTargetPx: g.hitTargetPx,
    fontSizePx: g.fontSizePx,
    lineHeightPx: g.lineHeightPx,
    fontFamily: bodyFontFamily(theme),
  };
}

/**
 * Render an {@link OverlayTokens} as the inline `style` custom-property string the portaled Content
 * element binds. Every entry is an `--eden-overlay-*` var whose VALUE is a derived token — the
 * markup references `var(--eden-overlay-surface)` etc. and carries no literal. This is the seam that
 * carries the Eden tokens THROUGH the bits-ui Portal (OD-1): bits-ui spreads this `style` onto the
 * rendered Content node, and the custom properties inherit to the whole portaled subtree.
 */
export function overlayStyleVars(tokens: OverlayTokens): string {
  const entries: readonly [string, string][] = [
    [`${VAR_PREFIX}-surface`, tokens.surface],
    [`${VAR_PREFIX}-on-surface`, tokens.onSurface],
    [`${VAR_PREFIX}-outline`, tokens.outline],
    [`${VAR_PREFIX}-scrim`, tokens.scrim],
    [`${VAR_PREFIX}-shadow`, tokens.elevationShadow],
    [`${VAR_PREFIX}-z`, String(tokens.zIndex)],
    [`${VAR_PREFIX}-radius`, px(tokens.radiusPx)],
    [`${VAR_PREFIX}-padding`, px(tokens.paddingPx)],
    [`${VAR_PREFIX}-gap`, px(tokens.gapPx)],
    [`${VAR_PREFIX}-hit-target`, px(tokens.hitTargetPx)],
    [`${VAR_PREFIX}-font-size`, px(tokens.fontSizePx)],
    [`${VAR_PREFIX}-line-height`, px(tokens.lineHeightPx)],
    [`${VAR_PREFIX}-font-family`, tokens.fontFamily],
  ];
  return entries.map(([k, v]) => `${k}: ${v};`).join(' ');
}

/**
 * The default theme every overlay derives from when a host does not inject one: the C21 reference
 * brand seed run through `generateTheme`. A host overrides by passing its own theme (the wiring is
 * the `theme` prop on each component); the SEED is the only literal crossing and it lives in
 * `@eden/theme` (cited here, never re-spelled — one concept, one home).
 */
export function defaultOverlayTheme(options?: GenerateOptions): Theme {
  return generateTheme(C21_SEED, options);
}

/** Re-export the seed type so a host can type its own seed without reaching past this barrel. */
export type { ThemeSeed };
