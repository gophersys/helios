/**
 * `@eden/primitives` — Chip token derivation (ADR-0024 §3, doc 17 §4 atoms).
 *
 * MATH IS SOURCE OF TRUTH. A Chip is the MONO DATA chip the Clusters north star reads — an id, a
 * count, a path, a resource name rendered in the monospace voice (doc 17 §4: "Chip (the mono data
 * chip from Clusters)"; doc 17 §3 rules "one mono size"). It decides NOTHING by hand: the reading
 * colours are the theme's `onSurface`/`surface`/`outline` roles (the highest-contrast reading pair
 * the theme resolves, ≈19:1 light / ≈15:1 dark — the SAME `proseSurface` pair chat-surface uses and
 * asserts), the size + line height come from the generated `caption` typography role (chat-surface
 * `proportion`), the radius from the `control` ramp step (surface-tokens `radiusPx`), and the
 * paddings/gap from the spacing ramp (chat-surface `space`). Every value is derived; this module
 * CITES the shared homes and re-spells no role selection, ramp lookup, or px.
 *
 * The MONO FONT: a generated {@link Theme}'s typography roles carry only the seed's display/text
 * families — the seed's `fonts.code` (JetBrains Mono for C21) is NOT re-emitted onto any generated
 * role (see @eden/theme generate.ts / css.ts). So the honest citation for the Chip's monospace voice
 * is the CSS GENERIC `monospace` keyword (the platform's mono, always available) — a generic
 * keyword, never a hand-set font NAME, exactly as the Button falls back to the generic `inherit`.
 * The mono SIZE is still a generated scale value (the `caption` role); only the FAMILY is the
 * generic. When @eden/theme later emits a code-typography role, this one line swaps to cite it.
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

/**
 * The CSS generic monospace family the Chip renders its data in — a generic KEYWORD, never a
 * hand-set font name (the seed's `fonts.code` is not carried on a generated theme role; see header).
 */
export const MONO_FONT_FAMILY = 'monospace';

/** A Chip variant: `default` (a static data chip) or `removable` (carries an inline remove affordance). */
export type ChipVariant = 'default' | 'removable';

/** The CSS-variable namespace every Chip custom property carries. */
const VAR_PREFIX = '--eden-chip';

/**
 * The resolved token set a Chip instance renders from. Every field is a CSS value DERIVED from a
 * generated {@link Theme}. The raw OKLCH reading pair rides alongside so the design-correctness gate
 * recomputes the contrast ratio from the SAME numbers the CSS carries.
 */
export interface ChipTokens {
  /** The data text/icon colour as a CSS `oklch(...)` string — the `onSurface` role. */
  readonly foreground: string;
  /** The chip fill as a CSS `oklch(...)` string — the `surface` role (a quiet, flush data pill). */
  readonly background: string;
  /** The hairline edge as a CSS `oklch(...)` string — the `outline` role. */
  readonly border: string;
  /** The raw OKLCH of the foreground — the contrast gate recomputes the ratio against the surface. */
  readonly foregroundOklch: OkLch;
  /** The raw OKLCH of the surface — the background the data text is read against. */
  readonly backgroundOklch: OkLch;
  /** The corner radius, px — the `control` ramp step (surface-tokens radiusPx). */
  readonly radiusPx: number;
  /** The horizontal padding, px — a spacing-ramp step (chat-surface space). */
  readonly paddingInlinePx: number;
  /** The vertical padding, px — a spacing-ramp step (chat-surface space). */
  readonly paddingBlockPx: number;
  /** The gap between the data and the remove affordance, px — a spacing-ramp step. */
  readonly gapPx: number;
  /** The minimum hit target, px — the decoupled AAA tap area (the remove control's floor). */
  readonly hitTargetPx: number;
  /** The mono font size, px — the `caption` typography role (chat-surface proportion). */
  readonly fontSizePx: number;
  /** The line height, px — the `caption` role's generated line height. */
  readonly lineHeightPx: number;
  /** The mono font family — the CSS generic `monospace` (see header; a generic keyword). */
  readonly fontFamily: string;
}

/**
 * Derive the full {@link ChipTokens} from a generated theme. PURE: the theme is the single input.
 * The reading pair is the shared `proseSurface`; the mono size is the `caption` proportion; the
 * radius/spacing are the shared vocabulary — nothing is re-spelled here.
 */
export function deriveChipTokens(theme: Theme): ChipTokens {
  const pair = proseSurface(theme);
  const cap = proportion(theme, 'caption');
  return {
    foreground: pair.foreground,
    background: pair.background,
    border: pair.border,
    foregroundOklch: pair.foregroundOklch,
    backgroundOklch: pair.backgroundOklch,
    radiusPx: radiusPx(theme, 'control'),
    // A data chip's inset is tight: `space-2` (8px) inline, `space-0.5` (2px) block — Clusters-grade.
    paddingInlinePx: space(theme, 2),
    paddingBlockPx: space(theme, 0),
    gapPx: space(theme, 1),
    hitTargetPx: theme.controlGeometry.hitTargetPx,
    fontSizePx: cap.fontSizePx,
    lineHeightPx: cap.lineHeightPx,
    fontFamily: MONO_FONT_FAMILY,
  };
}

/**
 * Render a {@link ChipTokens} as the inline `style` custom-property string the component binds.
 * Cites the shared `styleVars` emitter — the markup references `var(--eden-chip-*)` only.
 */
export function chipStyleVars(tokens: ChipTokens): string {
  const entries: readonly StyleEntry[] = [
    ['fg', tokens.foreground],
    ['bg', tokens.background],
    ['border', tokens.border],
    ['radius', tokens.radiusPx],
    ['padding-inline', tokens.paddingInlinePx],
    ['padding-block', tokens.paddingBlockPx],
    ['gap', tokens.gapPx],
    ['hit-target', tokens.hitTargetPx],
    ['font-size', tokens.fontSizePx],
    ['line-height', tokens.lineHeightPx],
    ['font-family', tokens.fontFamily],
  ];
  return styleVars(VAR_PREFIX, entries);
}
