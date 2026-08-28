/**
 * `@eden/primitives` — Kbd token derivation (ADR-0024 §3, doc 17 §4 atoms).
 *
 * MATH IS SOURCE OF TRUTH. A Kbd is a keyboard-key cap — the `⌘K` affordance doc 17 §5 makes global.
 * It decides NOTHING by hand: the reading colours are the theme's `onSurface`/`surface`/`outline`
 * roles (the highest-contrast reading pair the theme resolves — the SAME `proseSurface` pair
 * chat-surface asserts), the size + line height come from the generated `caption` typography role
 * (chat-surface `proportion`), the radius from the `control` ramp step (surface-tokens `radiusPx`),
 * and the paddings from the spacing ramp (chat-surface `space`). Every value is derived; this module
 * CITES the shared homes and re-spells no role selection, ramp lookup, or px.
 *
 * A key cap is rendered in the MONO voice (a key label is data, doc 17 §4), so — like the Chip — it
 * cites the CSS generic `monospace` keyword (the seed's `fonts.code` is not carried on a generated
 * theme role; see chip/tokens.ts header). The `⌘K` label reads as one glyph pair regardless of
 * platform font, and the size stays a generated scale value.
 */

import { type Theme, type OkLch } from '@eden/theme';
import { radiusPx } from '../surface-tokens/tokens.js';
import {
  proseSurface,
  proportion,
  space,
  styleVars,
  type StyleEntry,
} from '../chat-surface/tokens.js';
import { MONO_FONT_FAMILY } from '../chip/tokens.js';

/** The CSS-variable namespace every Kbd custom property carries. */
const VAR_PREFIX = '--eden-kbd';

/**
 * The resolved token set a Kbd instance renders from. Every field is a CSS value DERIVED from a
 * generated {@link Theme}. The raw OKLCH reading pair rides alongside so the design-correctness gate
 * recomputes the contrast ratio from the SAME numbers the CSS carries.
 */
export interface KbdTokens {
  /** The key-label colour as a CSS `oklch(...)` string — the `onSurface` role. */
  readonly foreground: string;
  /** The key-cap fill as a CSS `oklch(...)` string — the `surface` role. */
  readonly background: string;
  /** The key-cap edge as a CSS `oklch(...)` string — the `outline` role (the cap's rim). */
  readonly border: string;
  /** The raw OKLCH of the foreground — the contrast gate recomputes the ratio against the surface. */
  readonly foregroundOklch: OkLch;
  /** The raw OKLCH of the surface — the background the label is read against. */
  readonly backgroundOklch: OkLch;
  /** The corner radius, px — the `control` ramp step (surface-tokens radiusPx). */
  readonly radiusPx: number;
  /** The horizontal padding, px — a spacing-ramp step (chat-surface space). */
  readonly paddingInlinePx: number;
  /** The vertical padding, px — a spacing-ramp step (chat-surface space). */
  readonly paddingBlockPx: number;
  /** The mono font size, px — the `caption` typography role (chat-surface proportion). */
  readonly fontSizePx: number;
  /** The line height, px — the `caption` role's generated line height. */
  readonly lineHeightPx: number;
  /** The mono font family — the CSS generic `monospace` (a key label is data; a generic keyword). */
  readonly fontFamily: string;
}

/**
 * Derive the full {@link KbdTokens} from a generated theme. PURE: the theme is the single input.
 * The reading pair is the shared `proseSurface`; the mono size is the `caption` proportion; the
 * radius/spacing are the shared vocabulary — nothing is re-spelled here.
 */
export function deriveKbdTokens(theme: Theme): KbdTokens {
  const pair = proseSurface(theme);
  const cap = proportion(theme, 'caption');
  return {
    foreground: pair.foreground,
    background: pair.background,
    border: pair.border,
    foregroundOklch: pair.foregroundOklch,
    backgroundOklch: pair.backgroundOklch,
    radiusPx: radiusPx(theme, 'control'),
    // A key cap is tight: `space-1` (4px) inline, `space-0.5` (2px) block — both ramp steps.
    paddingInlinePx: space(theme, 1),
    paddingBlockPx: space(theme, 0),
    fontSizePx: cap.fontSizePx,
    lineHeightPx: cap.lineHeightPx,
    fontFamily: MONO_FONT_FAMILY,
  };
}

/**
 * Render a {@link KbdTokens} as the inline `style` custom-property string the component binds.
 * Cites the shared `styleVars` emitter — the markup references `var(--eden-kbd-*)` only.
 */
export function kbdStyleVars(tokens: KbdTokens): string {
  const entries: readonly StyleEntry[] = [
    ['fg', tokens.foreground],
    ['bg', tokens.background],
    ['border', tokens.border],
    ['radius', tokens.radiusPx],
    ['padding-inline', tokens.paddingInlinePx],
    ['padding-block', tokens.paddingBlockPx],
    ['font-size', tokens.fontSizePx],
    ['line-height', tokens.lineHeightPx],
    ['font-family', tokens.fontFamily],
  ];
  return styleVars(VAR_PREFIX, entries);
}
