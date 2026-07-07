/**
 * `@eden/primitives` — StatRow token derivation (ADR-0024 §3, doc 17 §4 molecules).
 *
 * MATH IS SOURCE OF TRUTH. A StatRow is the Clusters header number-row — a horizontal run of
 * label-over-value pairs (the ScorecardBanner `.totals` block: a bold tabular VALUE over a small
 * uppercase LABEL). doc 17 §4 names it "StatRow (the Clusters header numbers)"; doc 17 §4 also rules
 * the VALUE is MONO (data voice). It decides NOTHING by hand: the value colour is the theme's
 * `onSurface` role, the label colour is the `outline` role (a quieter caption — the same
 * `proseSurface` fg + `outline` the Clusters `.tot span` uses), the VALUE size is the `title`
 * typography role (a prominent number), the LABEL size is the `caption` role (a small overline), the
 * value is rendered in the MONO voice, and the inter-pair gap is a spacing-ramp step (chat-surface
 * `space`). Every value is derived; this module CITES the shared homes and re-spells no role
 * selection, ramp lookup, or px.
 */

import { oklchToCss, type Theme, type OkLch } from '@eden/theme';
import {
  proseSurface,
  proportion,
  space,
  styleVars,
  type StyleEntry,
} from '../chat-surface/tokens.js';
import { MONO_FONT_FAMILY } from '../chip/tokens.js';

/** One label-over-value pair the StatRow renders (the Clusters `.tot` unit). */
export interface Stat {
  /** The overline label (e.g. "namespaces", "workloads"). */
  readonly label: string;
  /** The value (a count / a fraction / an id) — rendered in the mono data voice. */
  readonly value: string;
}

/** The CSS-variable namespace every StatRow custom property carries. */
const VAR_PREFIX = '--eden-stat-row';

/**
 * The resolved token set a StatRow instance renders from. Every field is a CSS value DERIVED from a
 * generated {@link Theme}. The raw OKLCH value/label/surface triple rides alongside so the
 * design-correctness gate recomputes both contrast ratios from the SAME numbers the CSS carries.
 */
export interface StatRowTokens {
  /** The value text colour as a CSS `oklch(...)` string — the `onSurface` role (a prominent number). */
  readonly value: string;
  /** The label text colour as a CSS `oklch(...)` string — the `outline` role (a quiet overline). */
  readonly label: string;
  /** The raw OKLCH of the value — the contrast gate recomputes the ratio against the surface. */
  readonly valueOklch: OkLch;
  /** The raw OKLCH of the label — the contrast gate recomputes the ratio against the surface. */
  readonly labelOklch: OkLch;
  /** The raw OKLCH of the surface — the background both texts are read against. */
  readonly surfaceOklch: OkLch;
  /** The gap between adjacent stat pairs, px — a spacing-ramp step. */
  readonly gapPx: number;
  /** The gap between a value and its label, px — a spacing-ramp step (the intra-pair rhythm). */
  readonly pairGapPx: number;
  /** The value font size, px — the `title` typography role (a prominent number). */
  readonly valueFontSizePx: number;
  /** The value line height, px — the `title` role's generated line height. */
  readonly valueLineHeightPx: number;
  /** The value font family — the CSS generic `monospace` (the value is data; a generic keyword). */
  readonly valueFontFamily: string;
  /** The label font size, px — the `caption` typography role (a small overline). */
  readonly labelFontSizePx: number;
  /** The label line height, px — the `caption` role's generated line height. */
  readonly labelLineHeightPx: number;
  /** The label font family — the `caption` typography role family (the seed text font). */
  readonly labelFontFamily: string;
}

/**
 * Derive the full {@link StatRowTokens} from a generated theme. PURE: the theme is the single input.
 * The value/label colours are the shared reading pair + the `outline` role; the value size is the
 * `title` proportion, the label the `caption` proportion — nothing is re-spelled here.
 */
export function deriveStatRowTokens(theme: Theme): StatRowTokens {
  const pair = proseSurface(theme);
  const title = proportion(theme, 'title');
  const caption = proportion(theme, 'caption');
  return {
    value: pair.foreground,
    // the label is the `outline` role — a quieter overline than the value (the Clusters `.tot span`).
    label: oklchToCss(theme.roles.outline.value),
    valueOklch: pair.foregroundOklch,
    labelOklch: theme.roles.outline.value,
    surfaceOklch: pair.backgroundOklch,
    // Adjacent pairs are set `space-6` (24px) apart — the Clusters totals gutter, a ramp step. The
    // value↔label rhythm within a pair is `space-0.5` (2px) — tight, so a pair reads as one unit.
    gapPx: space(theme, 6),
    pairGapPx: space(theme, 0),
    valueFontSizePx: title.fontSizePx,
    valueLineHeightPx: title.lineHeightPx,
    valueFontFamily: MONO_FONT_FAMILY,
    labelFontSizePx: caption.fontSizePx,
    labelLineHeightPx: caption.lineHeightPx,
    labelFontFamily: caption.fontFamily,
  };
}

/**
 * Render a {@link StatRowTokens} as the inline `style` custom-property string the component binds.
 * Cites the shared `styleVars` emitter — the markup references `var(--eden-stat-row-*)` only.
 */
export function statRowStyleVars(tokens: StatRowTokens): string {
  const entries: readonly StyleEntry[] = [
    ['value', tokens.value],
    ['label', tokens.label],
    ['gap', tokens.gapPx],
    ['pair-gap', tokens.pairGapPx],
    ['value-font-size', tokens.valueFontSizePx],
    ['value-line-height', tokens.valueLineHeightPx],
    ['value-font-family', tokens.valueFontFamily],
    ['label-font-size', tokens.labelFontSizePx],
    ['label-line-height', tokens.labelLineHeightPx],
    ['label-font-family', tokens.labelFontFamily],
  ];
  return styleVars(VAR_PREFIX, entries);
}
