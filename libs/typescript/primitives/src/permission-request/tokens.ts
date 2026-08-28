/**
 * `@eden/primitives` — PermissionRequest token derivation (ADR-0024 §3, the ninth dimension).
 *
 * MATH IS SOURCE OF TRUTH. PermissionRequest is the human-in-the-loop prompt (the 5b surface): the
 * agent asks to run a tool, showing the tool, its arguments, and a reason, and offers three actions —
 * Allow once, Allow for session, Deny. Its appearance is the PROSE reading card (on-surface over
 * surface — the highest-contrast pair, so the consequential ask is the clearest thing on screen),
 * raised by its OUTLINE edge rather than a tonal fill that would compete with the conversation, a
 * WARNING accent on the heading (this is a consequential decision the human owns), the
 * `title`/`body`/`caption` proportions, and named spacing-ramp steps. The interactive actions also
 * carry the decoupled 44px AAA hit-target floor. All read out of a generated {@link Theme}.
 *
 * The three actions DELEGATE their appearance to the Button primitive (one concept, one home — the
 * action affordance is the Button, cited, never re-styled here): Allow-once = primary, Allow-for-
 * session = secondary, Deny = danger. This module decides only the CARD's own surface + proportions.
 */

import type { Theme, OkLch } from '@eden/theme';
import {
  proseSurface,
  stateSurface,
  proportion,
  space,
  hitTargetPx,
  styleVars,
} from '../chat-surface/index.js';

/** The CSS-variable namespace every PermissionRequest custom property carries (one prefix). */
const VAR_PREFIX = '--eden-permission-request';

/** The resolved token set a PermissionRequest renders from (the ask card surface + proportions). */
export interface PermissionRequestTokens {
  /** The card text colour as a CSS `oklch(...)` string. */
  readonly foreground: string;
  /** The card fill as a CSS `oklch(...)` string. */
  readonly background: string;
  /** The card edge as a CSS `oklch(...)` string. */
  readonly border: string;
  /** The heading accent colour (the warning state — a consequential ask) as a CSS `oklch(...)`. */
  readonly headingColor: string;
  /** The raw OKLCH of the card text — the contrast gate recomputes the ratio from this. */
  readonly foregroundOklch: OkLch;
  /** The raw OKLCH of the card fill — the contrast gate recomputes the ratio from this. */
  readonly backgroundOklch: OkLch;
  /** The raw OKLCH of the heading accent — the contrast gate recomputes its ratio over the fill. */
  readonly headingOklch: OkLch;
  /** The heading font size, px — the `title` typography role. */
  readonly headingSizePx: number;
  /** The heading line height, px — the `title` role's line height. */
  readonly headingLineHeightPx: number;
  /** The heading font family — the `title` typography role family. */
  readonly headingFontFamily: string;
  /** The body (reason) font size, px — the `body` typography role. */
  readonly bodySizePx: number;
  /** The body line height, px — the `body` role's line height. */
  readonly bodyLineHeightPx: number;
  /** The body font family — the `body` typography role family. */
  readonly bodyFontFamily: string;
  /** The args code font size, px — the `caption` typography role. */
  readonly codeSizePx: number;
  /** The args code font family — the monospace generic keyword. */
  readonly codeFontFamily: string;
  /** The card inner padding, px — a spacing-ramp step. */
  readonly paddingPx: number;
  /** The vertical gap between sections, px — a spacing-ramp step. */
  readonly gapPx: number;
  /** The gap between the action buttons, px — a spacing-ramp step. */
  readonly actionGapPx: number;
  /** The card corner radius, px — a spacing-ramp step. */
  readonly radiusPx: number;
  /** The minimum interactive hit target, px — the decoupled AAA 44px floor (shared with Button). */
  readonly hitTargetPx: number;
}

/** The monospace family for the args code block — a CSS generic keyword, never a literal colour/px. */
const CODE_FONT_FAMILY = 'monospace';

/** Derive the full {@link PermissionRequestTokens} from a generated theme. PURE. */
export function derivePermissionRequestTokens(theme: Theme): PermissionRequestTokens {
  const card = proseSurface(theme);
  const warning = stateSurface('warning', theme);
  const heading = proportion(theme, 'title');
  const body = proportion(theme, 'body');
  const code = proportion(theme, 'caption');
  return {
    foreground: card.foreground,
    background: card.background,
    border: card.border,
    headingColor: warning.foreground,
    foregroundOklch: card.foregroundOklch,
    backgroundOklch: card.backgroundOklch,
    headingOklch: warning.foregroundOklch,
    headingSizePx: heading.fontSizePx,
    headingLineHeightPx: heading.lineHeightPx,
    headingFontFamily: heading.fontFamily,
    bodySizePx: body.fontSizePx,
    bodyLineHeightPx: body.lineHeightPx,
    bodyFontFamily: body.fontFamily,
    codeSizePx: code.fontSizePx,
    codeFontFamily: CODE_FONT_FAMILY,
    paddingPx: space(theme, 5), // 20px — a raised modal ask reads with more air than a flow card
    gapPx: space(theme, 4), // 16px
    actionGapPx: space(theme, 2), // 8px
    radiusPx: space(theme, 3), // 12px
    hitTargetPx: hitTargetPx(theme),
  };
}

/**
 * The heading-accent contrast is over the card fill (the heading is drawn ON the prose card) — so the
 * design gate recomputes warning-over-surface from this exact pair. We keep the raw pair here so the
 * gate audits the rendered pair (the card text/fill pair carries its own guarantee separately).
 */
export function permissionHeadingPairOklch(theme: Theme): { fg: OkLch; bg: OkLch } {
  const card = proseSurface(theme);
  const warning = stateSurface('warning', theme);
  return { fg: warning.foregroundOklch, bg: card.backgroundOklch };
}

/** Render {@link PermissionRequestTokens} as the inline `style` custom-property string. */
export function permissionRequestStyleVars(tokens: PermissionRequestTokens): string {
  return styleVars(VAR_PREFIX, [
    ['fg', tokens.foreground],
    ['bg', tokens.background],
    ['border', tokens.border],
    ['heading', tokens.headingColor],
    ['heading-size', tokens.headingSizePx],
    ['heading-line-height', tokens.headingLineHeightPx],
    ['heading-family', tokens.headingFontFamily],
    ['body-size', tokens.bodySizePx],
    ['body-line-height', tokens.bodyLineHeightPx],
    ['body-family', tokens.bodyFontFamily],
    ['code-size', tokens.codeSizePx],
    ['code-family', tokens.codeFontFamily],
    ['padding', tokens.paddingPx],
    ['gap', tokens.gapPx],
    ['action-gap', tokens.actionGapPx],
    ['radius', tokens.radiusPx],
    ['hit-target', tokens.hitTargetPx],
  ]);
}
