/**
 * `@eden/primitives` — UsageMeter token derivation (ADR-0024 §3, the ninth dimension).
 *
 * MATH IS SOURCE OF TRUTH. UsageMeter surfaces an agent run's token usage + cost against a budget: a
 * numeric readout and a proportional bar. Its appearance is the PROSE card (gated on-surface over
 * surface), a TRACK drawn from the outline role, a FILL whose colour is a state accent chosen by the
 * usage TIER (under→info, near→warning, over→error), the `label`/`caption` proportions, and named
 * spacing-ramp steps. All read out of a generated {@link Theme} — nothing decided by hand.
 *
 * The meter MATH lives here too (pure, fully coverable, the mutated surface): {@link usageFraction}
 * is the clamped used/budget ratio, {@link usageTier} classifies it against the near/over thresholds,
 * and {@link barWidthPercent} renders the fraction as a CSS percentage. Keeping the meter logic pure
 * makes it testable without a DOM and mutation-proof (a flipped comparator or threshold is caught).
 */

import type { Theme, OkLch } from '@eden/theme';
import {
  proseSurface,
  stateSurface,
  proportion,
  space,
  styleVars,
  type StateRole,
} from '../chat-surface/index.js';

/** The CSS-variable namespace every UsageMeter custom property carries (one prefix). */
const VAR_PREFIX = '--eden-usage-meter';

/** The usage tier — under budget (calm), near the budget (caution), or over it (alarm). */
export type UsageTier = 'under' | 'near' | 'over';

/** The fraction at/above which usage reads as NEAR the budget (caution). A named ratio, not magic. */
const NEAR_THRESHOLD = 0.8;

/**
 * The clamped used/budget fraction in [0, 1]. A non-positive budget is unknown → 0 (indeterminate);
 * usage at or past the budget saturates at 1. Pure and total.
 */
export function usageFraction(used: number, budget: number): number {
  if (budget <= 0) return 0;
  return Math.min(1, Math.max(0, used / budget));
}

/**
 * Classify a usage fraction into a {@link UsageTier}: `over` once it reaches the full budget (≥1),
 * `near` at or past the {@link NEAR_THRESHOLD}, else `under`. The comparators are load-bearing — a
 * flipped `>=` is caught by the design lane's tier-boundary assertions.
 */
export function usageTier(fraction: number): UsageTier {
  if (fraction >= 1) return 'over';
  if (fraction >= NEAR_THRESHOLD) return 'near';
  return 'under';
}

/** The tier's state-role accent (under→info, near→warning, over→error). */
function tierState(tier: UsageTier): StateRole {
  return tier === 'over' ? 'error' : tier === 'near' ? 'warning' : 'info';
}

/** Render a fraction as a CSS percentage string (`0`→`0%`, `0.5`→`50%`, `1`→`100%`). */
export function barWidthPercent(fraction: number): string {
  const clamped = Math.min(1, Math.max(0, fraction));
  return `${String(clamped * 100)}%`;
}

/** The resolved token set a UsageMeter renders from (card + track + tier fill + proportions). */
export interface UsageMeterTokens {
  /** The card/readout text colour as a CSS `oklch(...)` string. */
  readonly foreground: string;
  /** The card fill as a CSS `oklch(...)` string. */
  readonly background: string;
  /** The track (unfilled bar) colour as a CSS `oklch(...)` string — the outline role. */
  readonly track: string;
  /** The bar FILL colour (the tier accent) as a CSS `oklch(...)` string. */
  readonly fill: string;
  /** The raw OKLCH of the readout text — the contrast gate recomputes the ratio from this. */
  readonly foregroundOklch: OkLch;
  /** The raw OKLCH of the card fill — the contrast gate recomputes the ratio from this. */
  readonly backgroundOklch: OkLch;
  /** The raw OKLCH of the bar fill — the contrast gate recomputes its ratio over the surface. */
  readonly fillOklch: OkLch;
  /** The readout font size, px — the `label` typography role. */
  readonly readoutSizePx: number;
  /** The readout line height, px — the `label` role's line height. */
  readonly readoutLineHeightPx: number;
  /** The readout font family — the `label` typography role family. */
  readonly readoutFontFamily: string;
  /** The caption (cost detail) font size, px — the `caption` typography role. */
  readonly captionSizePx: number;
  /** The card inner padding, px — a spacing-ramp step. */
  readonly paddingPx: number;
  /** The gap between rows, px — a spacing-ramp step. */
  readonly gapPx: number;
  /** The bar track height, px — a spacing-ramp step (a slim track). */
  readonly trackHeightPx: number;
  /** The card + bar corner radius, px — a spacing-ramp step. */
  readonly radiusPx: number;
}

/**
 * Derive the full {@link UsageMeterTokens} for a usage tier from a generated theme. PURE: the tier is
 * computed by the caller via {@link usageTier}; this maps it to the surface + fill selection.
 */
export function deriveUsageMeterTokens(tier: UsageTier, theme: Theme): UsageMeterTokens {
  const card = proseSurface(theme);
  const fill = stateSurface(tierState(tier), theme);
  const readout = proportion(theme, 'label');
  const caption = proportion(theme, 'caption');
  return {
    foreground: card.foreground,
    background: card.background,
    track: card.border, // the outline role — the chat-surface prose border
    fill: fill.foreground,
    foregroundOklch: card.foregroundOklch,
    backgroundOklch: card.backgroundOklch,
    fillOklch: fill.foregroundOklch,
    readoutSizePx: readout.fontSizePx,
    readoutLineHeightPx: readout.lineHeightPx,
    readoutFontFamily: readout.fontFamily,
    captionSizePx: caption.fontSizePx,
    paddingPx: space(theme, 4), // 16px
    gapPx: space(theme, 2), // 8px
    trackHeightPx: space(theme, 2), // 8px — a slim track, on the ramp
    radiusPx: space(theme, 3), // 12px
  };
}

/** Render {@link UsageMeterTokens} as the inline `style` custom-property string. */
export function usageMeterStyleVars(tokens: UsageMeterTokens): string {
  return styleVars(VAR_PREFIX, [
    ['fg', tokens.foreground],
    ['bg', tokens.background],
    ['track', tokens.track],
    ['fill', tokens.fill],
    ['readout-size', tokens.readoutSizePx],
    ['readout-line-height', tokens.readoutLineHeightPx],
    ['readout-family', tokens.readoutFontFamily],
    ['caption-size', tokens.captionSizePx],
    ['padding', tokens.paddingPx],
    ['gap', tokens.gapPx],
    ['track-height', tokens.trackHeightPx],
    ['radius', tokens.radiusPx],
  ]);
}
