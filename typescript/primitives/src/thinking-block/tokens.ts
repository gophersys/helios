/**
 * `@eden/primitives` — ThinkingBlock token derivation (ADR-0024 §3, the ninth dimension).
 *
 * MATH IS SOURCE OF TRUTH. ThinkingBlock is the collapsible reasoning surface: the assistant's
 * intermediate thinking, hidden behind a disclosure so it does not crowd the conversation. Its
 * appearance is the QUIET chat-surface container (gated on-primary-container over primary-container —
 * a recessed, lower-energy block that reads as "aside"), the `label` proportion for the summary
 * trigger, the `body` proportion for the reasoning prose, named spacing-ramp steps, and the decoupled
 * 44px AAA hit-target floor on the trigger. All read out of a generated {@link Theme} — nothing by hand.
 *
 * The disclosure BEHAVIOUR (open/close state, the aria-expanded wiring, focus) is delegated to the
 * bits-ui Collapsible primitive (one concept, one home — the behaviour layer, RD-16/OD-1); this
 * module decides only the block's own surface + proportions + hit target.
 */

import type { Theme, OkLch } from '@eden/theme';
import { quietSurface, proportion, space, hitTargetPx, styleVars } from '../chat-surface/index.js';

/** The CSS-variable namespace every ThinkingBlock custom property carries (one prefix). */
const VAR_PREFIX = '--eden-thinking-block';

/** The resolved token set a ThinkingBlock renders from (the quiet aside container + proportions). */
export interface ThinkingBlockTokens {
  /** The block text colour as a CSS `oklch(...)` string. */
  readonly foreground: string;
  /** The block fill as a CSS `oklch(...)` string. */
  readonly background: string;
  /** The block edge as a CSS `oklch(...)` string. */
  readonly border: string;
  /** The raw OKLCH of the block text — the contrast gate recomputes the ratio from this. */
  readonly foregroundOklch: OkLch;
  /** The raw OKLCH of the block fill — the contrast gate recomputes the ratio from this. */
  readonly backgroundOklch: OkLch;
  /** The summary/trigger font size, px — the `label` typography role. */
  readonly summarySizePx: number;
  /** The summary line height, px — the `label` role's line height. */
  readonly summaryLineHeightPx: number;
  /** The summary font family — the `label` typography role family. */
  readonly summaryFontFamily: string;
  /** The reasoning prose font size, px — the `body` typography role. */
  readonly proseSizePx: number;
  /** The reasoning prose line height, px — the `body` role's line height. */
  readonly proseLineHeightPx: number;
  /** The reasoning prose font family — the `body` typography role family. */
  readonly proseFontFamily: string;
  /** The block inner padding, px — a spacing-ramp step. */
  readonly paddingPx: number;
  /** The gap between the trigger and the content, px — a spacing-ramp step. */
  readonly gapPx: number;
  /** The block corner radius, px — a spacing-ramp step. */
  readonly radiusPx: number;
  /** The minimum trigger hit target, px — the decoupled AAA 44px floor (shared with Button). */
  readonly hitTargetPx: number;
}

/** Derive the full {@link ThinkingBlockTokens} from a generated theme. PURE: the theme is the input. */
export function deriveThinkingBlockTokens(theme: Theme): ThinkingBlockTokens {
  const block = quietSurface(theme);
  const summary = proportion(theme, 'label');
  const prose = proportion(theme, 'body');
  return {
    foreground: block.foreground,
    background: block.background,
    border: block.border,
    foregroundOklch: block.foregroundOklch,
    backgroundOklch: block.backgroundOklch,
    summarySizePx: summary.fontSizePx,
    summaryLineHeightPx: summary.lineHeightPx,
    summaryFontFamily: summary.fontFamily,
    proseSizePx: prose.fontSizePx,
    proseLineHeightPx: prose.lineHeightPx,
    proseFontFamily: prose.fontFamily,
    paddingPx: space(theme, 4), // 16px
    gapPx: space(theme, 2), // 8px
    radiusPx: space(theme, 3), // 12px
    hitTargetPx: hitTargetPx(theme),
  };
}

/** Render {@link ThinkingBlockTokens} as the inline `style` custom-property string. */
export function thinkingBlockStyleVars(tokens: ThinkingBlockTokens): string {
  return styleVars(VAR_PREFIX, [
    ['fg', tokens.foreground],
    ['bg', tokens.background],
    ['border', tokens.border],
    ['summary-size', tokens.summarySizePx],
    ['summary-line-height', tokens.summaryLineHeightPx],
    ['summary-family', tokens.summaryFontFamily],
    ['prose-size', tokens.proseSizePx],
    ['prose-line-height', tokens.proseLineHeightPx],
    ['prose-family', tokens.proseFontFamily],
    ['padding', tokens.paddingPx],
    ['gap', tokens.gapPx],
    ['radius', tokens.radiusPx],
    ['hit-target', tokens.hitTargetPx],
  ]);
}
