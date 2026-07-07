/**
 * `@eden/primitives` — Divider token derivation (ADR-0024 §3, doc 17 §4 atoms).
 *
 * MATH IS SOURCE OF TRUTH. A Divider is a horizontal/vertical rule. doc 17 §1.6 names the failure it
 * fixes: "hairline full-width rules that cut pages arbitrarily" — so an Eden Divider is INSET by
 * default (it never bleeds to the page edge). It decides NOTHING by hand: the rule colour is the
 * theme's `outline` role (the same hairline the overlay/field cite), the thickness is a hairline
 * `1px` device rule, and the INSET (the margin pulling the rule off the edge) is a spacing-ramp step
 * (chat-surface `space`). Every value is derived; this module CITES the shared homes and re-spells no
 * role selection, ramp lookup, or px.
 *
 * The `1px` thickness is the ONE device-pixel literal here — a rule is a single hairline, the
 * thinnest renderable edge (below the 4px grid, exactly as the component borders are `1px solid`); it
 * is a HAIRLINE constant, not an eyeballed size, and it is not a colour. The inset (which IS on the
 * grid) is the design decision, and it is a ramp step.
 */

import { oklchToCss, type Theme, type OkLch } from '@eden/theme';
import { space, styleVars, type StyleEntry } from '../chat-surface/tokens.js';

/** A Divider orientation — a horizontal rule (row separator) or a vertical rule (column separator). */
export type DividerOrientation = 'horizontal' | 'vertical';

/** The CSS-variable namespace every Divider custom property carries. */
const VAR_PREFIX = '--eden-divider';

/**
 * The resolved token set a Divider instance renders from. Every field is a CSS value DERIVED from a
 * generated {@link Theme}. The raw OKLCH rule colour rides alongside so the design-correctness gate
 * recomputes the rule-over-surface contrast from the SAME number the CSS carries.
 */
export interface DividerTokens {
  /** The rule colour as a CSS `oklch(...)` string — the `outline` role. */
  readonly line: string;
  /** The raw OKLCH of the rule — the design gate recomputes the ratio against the surface. */
  readonly lineOklch: OkLch;
  /** The raw OKLCH of the surface the rule is drawn on — the design gate's background. */
  readonly surfaceOklch: OkLch;
  /** The rule thickness, px — a hairline device rule (the thinnest renderable edge; see header). */
  readonly thicknessPx: number;
  /** The inset, px — the margin pulling the rule off the edge (a spacing-ramp step; the anti-full-bleed). */
  readonly insetPx: number;
}

/** The hairline thickness of a rule, px — a single device pixel (the thinnest edge; see header). */
const HAIRLINE_PX = 1;

/**
 * Derive the full {@link DividerTokens} from a generated theme. PURE: the theme is the single input.
 * The rule colour is the `outline` role; the inset is a ramp step — nothing is re-spelled here.
 */
export function deriveDividerTokens(theme: Theme): DividerTokens {
  return {
    line: oklchToCss(theme.roles.outline.value),
    lineOklch: theme.roles.outline.value,
    surfaceOklch: theme.roles.surface.value,
    thicknessPx: HAIRLINE_PX,
    // The default inset is `space-4` (16px) — the comfortable reading gutter, a ramp step. A rule is
    // pulled this far off each edge so it separates content without cutting the surface to the bone.
    insetPx: space(theme, 4),
  };
}

/**
 * Render a {@link DividerTokens} as the inline `style` custom-property string the component binds.
 * Cites the shared `styleVars` emitter — the markup references `var(--eden-divider-*)` only.
 */
export function dividerStyleVars(tokens: DividerTokens): string {
  const entries: readonly StyleEntry[] = [
    ['line', tokens.line],
    ['thickness', tokens.thicknessPx],
    ['inset', tokens.insetPx],
  ];
  return styleVars(VAR_PREFIX, entries);
}
