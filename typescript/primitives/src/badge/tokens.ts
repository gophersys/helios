/**
 * `@eden/primitives` — Badge token derivation (ADR-0024 §3, doc 17 §4 atoms).
 *
 * MATH IS SOURCE OF TRUTH. A Badge is the status/count label the Clusters north star reads: a small
 * pill carrying a health/status WORD (or a count) tinted from the theme's semantic role for that
 * status. It decides NOTHING by hand — the tint fill, the legible text colour, and the edge are all
 * READ OUT of a generated {@link Theme} via the shared `statusRole*`/`statusTint` vocabulary
 * (surface-tokens), the proportion (font size + line height) from the `caption` typography role via
 * chat-surface `proportion`, the radius from the `control` ramp step via surface-tokens `radiusPx`,
 * and the paddings from the spacing ramp via chat-surface `space`. Every value is derived; this
 * module CITES the shared homes and re-spells no role selection, ramp lookup, or px.
 *
 * The status ROLE COLOUR is drawn as TEXT over the surface (the gated way to surface a state hue —
 * every state role clears AA 4.5 over the surface in both modes, the same pair chat-surface's
 * `stateSurface` uses and asserts), with a soft same-hue TINT behind it (mirrors the Clusters chip's
 * `color-mix` wash). The text is never colour-alone: a Badge always renders a word/count, so the
 * meaning survives grayscale (doc 17 §1 / R3 E1 triple-encoding — the shape channel is the app's
 * StatusGlyph's job, cited by the Clusters legend).
 */

import { oklchToCss, type Theme, type OkLch } from '@eden/theme';
import { statusRoleOklch, statusTint, radiusPx, type Status } from '../surface-tokens/tokens.js';
import { proportion, space, styleVars, type StyleEntry } from '../chat-surface/tokens.js';

/** A Badge variant — a SELECTION of a status role (the Clusters health vocabulary + chrome). */
export type BadgeVariant = Status;

/** The CSS-variable namespace every Badge custom property carries. */
const VAR_PREFIX = '--eden-badge';

/** The tint alpha of a Badge fill — the soft same-hue wash behind the legible text (the Clusters
 *  chip uses a ~12% wash). It is the ONE scalar here and it is a FRACTION, not a colour literal. */
const TINT_ALPHA = 0.12;

/** The border alpha of a Badge edge — a stronger same-hue line than the fill (the Clusters chip
 *  uses a ~35% edge). A FRACTION, not a colour literal. */
const BORDER_ALPHA = 0.35;

/**
 * The resolved token set a Badge instance renders from. Every field is a CSS value DERIVED from a
 * generated {@link Theme}. The raw OKLCH text/surface pair rides alongside so the design-correctness
 * gate recomputes the contrast ratio from the SAME numbers the CSS carries.
 */
export interface BadgeTokens {
  /** The status text/icon colour as a CSS `oklch(...)` string — the status role over the surface. */
  readonly foreground: string;
  /** The soft same-hue tint fill as a CSS `oklch(L C H / a)` string (the Clusters wash). */
  readonly background: string;
  /** The same-hue edge as a CSS `oklch(L C H / a)` string (a stronger line than the fill). */
  readonly border: string;
  /** The raw OKLCH of the foreground — the contrast gate recomputes the ratio against the surface. */
  readonly foregroundOklch: OkLch;
  /** The raw OKLCH of the surface the badge is read against — the contrast gate's background. */
  readonly surfaceOklch: OkLch;
  /** The corner radius, px — the `control` ramp step (surface-tokens radiusPx). */
  readonly radiusPx: number;
  /** The horizontal padding, px — a spacing-ramp step (chat-surface space). */
  readonly paddingInlinePx: number;
  /** The vertical padding, px — a spacing-ramp step (chat-surface space). */
  readonly paddingBlockPx: number;
  /** The gap between the count/word and any adjacent glyph, px — a spacing-ramp step. */
  readonly gapPx: number;
  /** The font size, px — the `caption` typography role (chat-surface proportion). */
  readonly fontSizePx: number;
  /** The line height, px — the `caption` role's generated line height. */
  readonly lineHeightPx: number;
  /** The font family — the `caption` typography role family (the seed text font). */
  readonly fontFamily: string;
}

/**
 * Derive the full {@link BadgeTokens} for a variant from a generated theme. PURE: the theme is the
 * single input (the New(configuration) spine, rule 10). The variant SELECTS a status role; the
 * proportion, radius, and spacing are drawn from the shared vocabulary — nothing is re-spelled here.
 */
export function deriveBadgeTokens(variant: BadgeVariant, theme: Theme): BadgeTokens {
  const roleOklch = statusRoleOklch(variant, theme);
  const cap = proportion(theme, 'caption');
  return {
    foreground: oklchToCss(roleOklch),
    background: statusTint(variant, theme, TINT_ALPHA),
    border: statusTint(variant, theme, BORDER_ALPHA),
    foregroundOklch: roleOklch,
    surfaceOklch: theme.roles.surface.value,
    radiusPx: radiusPx(theme, 'control'),
    // A pill's inset is the tight end of the ramp: `space-2` (8px) inline, `space-0.5` (2px) block —
    // a Clusters-grade dense chip, both ramp steps (asserted in the design lane).
    paddingInlinePx: space(theme, 2),
    paddingBlockPx: space(theme, 0),
    gapPx: space(theme, 1),
    fontSizePx: cap.fontSizePx,
    lineHeightPx: cap.lineHeightPx,
    fontFamily: cap.fontFamily,
  };
}

/**
 * Render a {@link BadgeTokens} as the inline `style` custom-property string the component binds.
 * Cites the shared `styleVars` emitter (one concept, one home) — the markup references
 * `var(--eden-badge-*)` only and carries no literal (the provenance lint passes by construction).
 */
export function badgeStyleVars(tokens: BadgeTokens): string {
  const entries: readonly StyleEntry[] = [
    ['fg', tokens.foreground],
    ['bg', tokens.background],
    ['border', tokens.border],
    ['radius', tokens.radiusPx],
    ['padding-inline', tokens.paddingInlinePx],
    ['padding-block', tokens.paddingBlockPx],
    ['gap', tokens.gapPx],
    ['font-size', tokens.fontSizePx],
    ['line-height', tokens.lineHeightPx],
    ['font-family', tokens.fontFamily],
  ];
  return styleVars(VAR_PREFIX, entries);
}
