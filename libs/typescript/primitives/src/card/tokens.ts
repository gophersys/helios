/**
 * `@eden/primitives` — Card token derivation (ADR-0024 §3, doc 17 §4 molecules).
 *
 * MATH IS SOURCE OF TRUTH. A Card is the surface molecule — a panel with header/body/footer slots.
 * It decides NOTHING by hand: the reading colours are the theme's `onSurface`/`surface`/`outline`
 * roles (the shared `proseSurface` reading pair chat-surface asserts), the RADIUS is EXACTLY the
 * `surface` radius (surface-tokens `radiusPx(theme, 'surface')` — doc 17 §4's explicit ruling for
 * the Card), the ELEVATION is EXACTLY the `raised` shadow (surface-tokens `elevationShadow(theme,
 * 'raised')` — doc 17 §4's explicit ruling), the interior padding is the comfortable reading inset
 * from the spacing ramp (chat-surface `space`), and the slot rhythm + type come from the ramp + the
 * `body` typography role. Every value is derived; this module CITES the shared homes and re-spells no
 * role selection, ramp lookup, radius, shadow, or px.
 *
 * The `raised` VARIANT paints the `raised` shadow; the `flat` variant paints NO shadow (an outlined
 * surface, the `outline` role as its edge). Both share the `surface` radius and the same reading
 * pair — the elevation is the ONE thing the variant selects.
 */

import { type Theme, type OkLch } from '@eden/theme';
import { radiusPx, elevationShadow } from '../surface-tokens/tokens.js';
import {
  proseSurface,
  proportion,
  space,
  styleVars,
  type StyleEntry,
} from '../chat-surface/tokens.js';

/** A Card variant — `raised` (the `raised` shadow) or `flat` (an outlined surface, no shadow). */
export type CardVariant = 'raised' | 'flat';

/** The CSS-variable namespace every Card custom property carries. */
const VAR_PREFIX = '--eden-card';

/** The `flat` variant paints no shadow (an outlined surface). The CSS keyword `none`, not a colour. */
const NO_SHADOW = 'none';

/**
 * The resolved token set a Card instance renders from. Every field is a CSS value DERIVED from a
 * generated {@link Theme}. The raw OKLCH reading pair rides alongside so the design-correctness gate
 * recomputes the contrast ratio from the SAME numbers the CSS carries.
 */
export interface CardTokens {
  /** The body/heading text colour as a CSS `oklch(...)` string — the `onSurface` role. */
  readonly foreground: string;
  /** The card fill as a CSS `oklch(...)` string — the `surface` role. */
  readonly background: string;
  /** The card edge + the header/footer separators as a CSS `oklch(...)` string — the `outline` role. */
  readonly border: string;
  /** The raw OKLCH of the foreground — the contrast gate recomputes the ratio against the surface. */
  readonly foregroundOklch: OkLch;
  /** The raw OKLCH of the surface — the background the text is read against. */
  readonly backgroundOklch: OkLch;
  /** The corner radius, px — EXACTLY the `surface` radius (doc 17 §4 Card ruling). */
  readonly radiusPx: number;
  /** The composed elevation `box-shadow` string — EXACTLY the `raised` shadow, or `none` for flat. */
  readonly shadow: string;
  /** The interior padding, px — the comfortable reading inset (a spacing-ramp step). */
  readonly paddingPx: number;
  /** The gap between stacked slot content, px — a spacing-ramp step. */
  readonly gapPx: number;
  /** The body font size, px — the `body` typography role (chat-surface proportion). */
  readonly fontSizePx: number;
  /** The line height, px — the `body` role's generated line height. */
  readonly lineHeightPx: number;
  /** The font family — the `body` typography role family (the seed text font). */
  readonly fontFamily: string;
}

/**
 * Derive the full {@link CardTokens} for a variant from a generated theme. PURE: the theme is the
 * single input. The radius is the `surface` radius and the raised shadow is the `raised` elevation —
 * doc 17 §4's two explicit rulings for the Card — both drawn from the shared vocabulary.
 */
export function deriveCardTokens(variant: CardVariant, theme: Theme): CardTokens {
  const pair = proseSurface(theme);
  const body = proportion(theme, 'body');
  return {
    foreground: pair.foreground,
    background: pair.background,
    border: pair.border,
    foregroundOklch: pair.foregroundOklch,
    backgroundOklch: pair.backgroundOklch,
    radiusPx: radiusPx(theme, 'surface'),
    shadow: variant === 'raised' ? elevationShadow(theme, 'raised') : NO_SHADOW,
    // The interior inset is `space-4` (16px) — the comfortable reading gutter, a ramp step. The slot
    // rhythm (header↔body↔footer) is `space-3` (12px) — a slightly tighter ramp step so the slots
    // read as one card, not three stacked blocks.
    paddingPx: space(theme, 4),
    gapPx: space(theme, 3),
    fontSizePx: body.fontSizePx,
    lineHeightPx: body.lineHeightPx,
    fontFamily: body.fontFamily,
  };
}

/**
 * Render a {@link CardTokens} as the inline `style` custom-property string the component binds.
 * Cites the shared `styleVars` emitter — the markup references `var(--eden-card-*)` only. The shadow
 * is string-valued (a composed `box-shadow` or `none`), so it passes through the emitter verbatim.
 */
export function cardStyleVars(tokens: CardTokens): string {
  const entries: readonly StyleEntry[] = [
    ['fg', tokens.foreground],
    ['bg', tokens.background],
    ['border', tokens.border],
    ['radius', tokens.radiusPx],
    ['shadow', tokens.shadow],
    ['padding', tokens.paddingPx],
    ['gap', tokens.gapPx],
    ['font-size', tokens.fontSizePx],
    ['line-height', tokens.lineHeightPx],
    ['font-family', tokens.fontFamily],
  ];
  return styleVars(VAR_PREFIX, entries);
}
