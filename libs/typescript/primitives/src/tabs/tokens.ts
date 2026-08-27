/**
 * `@eden/primitives` — Tabs token derivation (ADR-0024 §3, doc 17 §4 molecules).
 *
 * MATH IS SOURCE OF TRUTH. Tabs is the segmented view-switcher (doc 17 §4: "Tabs"). It decides
 * NOTHING by hand: the ACTIVE tab's text + underline indicator are the theme's `primary` role, the
 * INACTIVE tab text is the `outline` role (a quiet, unselected label — still AA-legible over the
 * surface), the reading surface is the `surface` role, the tablist's bottom rail is the `outline`
 * hairline, the label type is the `label` typography role (chat-surface `proportion`), the trigger
 * padding is a spacing-ramp step (chat-surface `space`), and each trigger honours the decoupled 44px
 * AAA hit floor (`controlGeometry.hitTargetPx`). Every value is derived; this module CITES the shared
 * homes and re-spells no role selection, ramp lookup, or px.
 *
 * The behaviour (roving `Tab`/`ArrowKey` focus, `tab`/`tablist`/`tabpanel` ARIA, activation) is the
 * bits-ui `Tabs` primitive — this module is only the appearance half.
 */

import { oklchToCss, type Theme, type OkLch } from '@eden/theme';
import {
  proseSurface,
  proportion,
  space,
  styleVars,
  type StyleEntry,
} from '../chat-surface/tokens.js';

/** One tab the Tabs renders — a value (the panel key) + its visible label. */
export interface Tab {
  /** The tab's value — the key linking a trigger to its panel (and the controlled `value`). */
  readonly value: string;
  /** The visible tab label. */
  readonly label: string;
  /** Whether this tab is disabled (excluded from activation + the roving focus order). */
  readonly disabled?: boolean;
}

/** The CSS-variable namespace every Tabs custom property carries. */
const VAR_PREFIX = '--eden-tabs';

/**
 * The resolved token set a Tabs instance renders from. Every field is a CSS value DERIVED from a
 * generated {@link Theme}. The raw OKLCH active/inactive/surface triple rides alongside so the
 * design-correctness gate recomputes both contrast ratios from the SAME numbers the CSS carries.
 */
export interface TabsTokens {
  /** The active tab text + indicator colour as a CSS `oklch(...)` string — the `primary` role. */
  readonly active: string;
  /** The inactive tab text colour as a CSS `oklch(...)` string — the `outline` role (a quiet label). */
  readonly inactive: string;
  /** The panel body reading text colour as a CSS `oklch(...)` string — the `onSurface` role. */
  readonly foreground: string;
  /** The tablist rail + separators colour as a CSS `oklch(...)` string — the `outline` role. */
  readonly rail: string;
  /** The reading surface as a CSS `oklch(...)` string — the `surface` role. */
  readonly surface: string;
  /** The raw OKLCH of the active colour — the contrast gate recomputes the ratio against the surface. */
  readonly activeOklch: OkLch;
  /** The raw OKLCH of the inactive colour — the contrast gate recomputes the ratio against the surface. */
  readonly inactiveOklch: OkLch;
  /** The raw OKLCH of the panel foreground — the contrast gate recomputes the ratio against the surface. */
  readonly foregroundOklch: OkLch;
  /** The raw OKLCH of the surface — the background the tab labels are read against. */
  readonly surfaceOklch: OkLch;
  /** The minimum hit target, px — the decoupled AAA tap floor for each trigger. */
  readonly hitTargetPx: number;
  /** The horizontal trigger padding, px — a spacing-ramp step. */
  readonly paddingInlinePx: number;
  /** The vertical trigger padding, px — a spacing-ramp step. */
  readonly paddingBlockPx: number;
  /** The gap between triggers + between the list and the panel, px — a spacing-ramp step. */
  readonly gapPx: number;
  /** The label font size, px — the `label` typography role (chat-surface proportion). */
  readonly fontSizePx: number;
  /** The line height, px — the `label` role's generated line height. */
  readonly lineHeightPx: number;
  /** The font family — the `label` typography role family (the seed text font). */
  readonly fontFamily: string;
}

/**
 * Derive the full {@link TabsTokens} from a generated theme. PURE: the theme is the single input.
 * The active colour is the `primary` role, the inactive the `outline` role, the label size the
 * `label` proportion — nothing is re-spelled here.
 */
export function deriveTabsTokens(theme: Theme): TabsTokens {
  const roles = theme.roles;
  const pair = proseSurface(theme);
  const label = proportion(theme, 'label');
  return {
    active: oklchToCss(roles.primary.value),
    inactive: oklchToCss(roles.outline.value),
    foreground: pair.foreground,
    rail: oklchToCss(roles.outline.value),
    surface: oklchToCss(roles.surface.value),
    activeOklch: roles.primary.value,
    inactiveOklch: roles.outline.value,
    foregroundOklch: pair.foregroundOklch,
    surfaceOklch: roles.surface.value,
    hitTargetPx: theme.controlGeometry.hitTargetPx,
    // A trigger's inset is `space-3` (12px) inline, `space-2` (8px) block — a comfortable tab label
    // hit area, both ramp steps. The gap (trigger↔trigger, list↔panel) is `space-4` (16px).
    paddingInlinePx: space(theme, 3),
    paddingBlockPx: space(theme, 2),
    gapPx: space(theme, 4),
    fontSizePx: label.fontSizePx,
    lineHeightPx: label.lineHeightPx,
    fontFamily: label.fontFamily,
  };
}

/**
 * Render a {@link TabsTokens} as the inline `style` custom-property string the component binds.
 * Cites the shared `styleVars` emitter — the markup references `var(--eden-tabs-*)` only.
 */
export function tabsStyleVars(tokens: TabsTokens): string {
  const entries: readonly StyleEntry[] = [
    ['active', tokens.active],
    ['inactive', tokens.inactive],
    ['fg', tokens.foreground],
    ['rail', tokens.rail],
    ['surface', tokens.surface],
    ['hit-target', tokens.hitTargetPx],
    ['padding-inline', tokens.paddingInlinePx],
    ['padding-block', tokens.paddingBlockPx],
    ['gap', tokens.gapPx],
    ['font-size', tokens.fontSizePx],
    ['line-height', tokens.lineHeightPx],
    ['font-family', tokens.fontFamily],
  ];
  return styleVars(VAR_PREFIX, entries);
}
