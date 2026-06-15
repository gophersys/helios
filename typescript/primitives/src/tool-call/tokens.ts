/**
 * `@eden/primitives` — ToolCall token derivation (ADR-0024 §3, the ninth dimension).
 *
 * MATH IS SOURCE OF TRUTH. A ToolCall card surfaces one agent-event: a tool the assistant invoked,
 * its arguments (a code block), and a status. Its appearance is the PROSE chat-surface card (gated
 * on-surface over surface) plus a STATUS accent drawn from the state vocabulary (running→info,
 * success→success, error→error) as gated TEXT over the surface, plus the `label` proportion for the
 * tool name, the `caption` monospace proportion for the args code block, and named spacing-ramp steps.
 * All read out of a generated {@link Theme} via the shared chat-surface vocabulary — nothing by hand.
 *
 * The code block is rendered in a monospace family: the seed carries no monospace font, so the family
 * is the CSS generic keyword `monospace` (a keyword, never a colour/px literal — the provenance lint
 * targets hex, not font keywords). Its SIZE is still a generated type-scale value, and its text/bg
 * pair is the same gated on-surface/surface pair, so the code block clears the contrast gate too.
 */

import type { Theme, OkLch } from '@eden/theme';
import {
  proseSurface,
  stateSurface,
  proportion,
  space,
  styleVars,
  type SurfacePair,
} from '../chat-surface/index.js';

/** The ToolCall lifecycle status — the agent-event's three observable outcomes. */
export type ToolCallStatus = 'running' | 'success' | 'error';

/** The CSS-variable namespace every ToolCall custom property carries (one prefix). */
const VAR_PREFIX = '--eden-tool-call';

/** The monospace family for code blocks — a CSS generic keyword, never a hand-set literal colour/px. */
const CODE_FONT_FAMILY = 'monospace';

/** The resolved token set a ToolCall renders from (card container + status accent + proportions). */
export interface ToolCallTokens {
  /** The card text colour as a CSS `oklch(...)` string. */
  readonly foreground: string;
  /** The card fill as a CSS `oklch(...)` string. */
  readonly background: string;
  /** The card edge as a CSS `oklch(...)` string. */
  readonly border: string;
  /** The status accent colour (the running/success/error state) as a CSS `oklch(...)` string. */
  readonly statusColor: string;
  /** The raw OKLCH of the card text — the contrast gate recomputes the ratio from this. */
  readonly foregroundOklch: OkLch;
  /** The raw OKLCH of the card fill — the contrast gate recomputes the ratio from this. */
  readonly backgroundOklch: OkLch;
  /** The raw OKLCH of the status accent — the contrast gate recomputes its ratio over the surface. */
  readonly statusOklch: OkLch;
  /** The tool-name font size, px — the `label` typography role. */
  readonly titleSizePx: number;
  /** The tool-name line height, px — the `label` role's line height. */
  readonly titleLineHeightPx: number;
  /** The tool-name font family — the `label` typography role family. */
  readonly titleFontFamily: string;
  /** The args code font size, px — the `caption` typography role (a type-scale value). */
  readonly codeSizePx: number;
  /** The args code line height, px — the `caption` role's line height. */
  readonly codeLineHeightPx: number;
  /** The args code font family — the monospace generic keyword. */
  readonly codeFontFamily: string;
  /** The card inner padding, px — a spacing-ramp step. */
  readonly paddingPx: number;
  /** The vertical gap between rows, px — a spacing-ramp step. */
  readonly gapPx: number;
  /** The card corner radius, px — a spacing-ramp step. */
  readonly radiusPx: number;
}

/** Map a ToolCall status to its state-role accent (running reads as info — neutral in-progress). */
function statusSurface(status: ToolCallStatus, theme: Theme): SurfacePair {
  switch (status) {
    case 'running':
      return stateSurface('info', theme);
    case 'success':
      return stateSurface('success', theme);
    case 'error':
      return stateSurface('error', theme);
  }
}

/** Derive the full {@link ToolCallTokens} for a status from a generated theme. PURE. */
export function deriveToolCallTokens(status: ToolCallStatus, theme: Theme): ToolCallTokens {
  const card = proseSurface(theme);
  const status_ = statusSurface(status, theme);
  const title = proportion(theme, 'label');
  const code = proportion(theme, 'caption');
  return {
    foreground: card.foreground,
    background: card.background,
    border: card.border,
    statusColor: status_.foreground,
    foregroundOklch: card.foregroundOklch,
    backgroundOklch: card.backgroundOklch,
    statusOklch: status_.foregroundOklch,
    titleSizePx: title.fontSizePx,
    titleLineHeightPx: title.lineHeightPx,
    titleFontFamily: title.fontFamily,
    codeSizePx: code.fontSizePx,
    codeLineHeightPx: code.lineHeightPx,
    codeFontFamily: CODE_FONT_FAMILY,
    paddingPx: space(theme, 4), // 16px
    gapPx: space(theme, 2), // 8px
    radiusPx: space(theme, 3), // 12px
  };
}

/** Render {@link ToolCallTokens} as the inline `style` custom-property string. */
export function toolCallStyleVars(tokens: ToolCallTokens): string {
  return styleVars(VAR_PREFIX, [
    ['fg', tokens.foreground],
    ['bg', tokens.background],
    ['border', tokens.border],
    ['status', tokens.statusColor],
    ['title-size', tokens.titleSizePx],
    ['title-line-height', tokens.titleLineHeightPx],
    ['title-family', tokens.titleFontFamily],
    ['code-size', tokens.codeSizePx],
    ['code-line-height', tokens.codeLineHeightPx],
    ['code-family', tokens.codeFontFamily],
    ['padding', tokens.paddingPx],
    ['gap', tokens.gapPx],
    ['radius', tokens.radiusPx],
  ]);
}
