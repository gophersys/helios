/**
 * `@eden/primitives` — Message token derivation (ADR-0024 §3, the ninth dimension).
 *
 * MATH IS SOURCE OF TRUTH, ONE CONCEPT ONE HOME. A Message is a chat bubble whose appearance is a
 * SELECTION of a chat-surface container by ROLE (user vs assistant), plus proportion + space picks —
 * all read out of a generated {@link Theme} via the shared chat-surface vocabulary. This module
 * decides NOTHING by hand: it CITES `accentSurface`/`quietSurface` (the gated `{ fg, bg, border }`
 * pairs), the `body` proportion (prose size + line height on the type scale), and named spacing-ramp
 * steps for padding/gap/radius. The contrast of the rendered prose, the scale-provenance of every
 * size, and the prose `body` proportion are PROPERTIES of the values this returns, asserted in
 * `message.design.test.ts`.
 *
 * The role→surface mapping is the ONE design decision: a `user` message reads as the user's own
 * filled accent (on-primary over primary); an `assistant` message reads as the quieter tonal
 * container (on-primary-container over primary-container). Both are gated pairs the theme guarantees.
 */

import type { Theme, OkLch } from '@eden/theme';
import {
  accentSurface,
  quietSurface,
  proportion,
  space,
  styleVars,
  type SurfacePair,
} from '../chat-surface/index.js';

/** The Message role — the agent-event taxonomy's two conversational authors. */
export type MessageRole = 'user' | 'assistant';

/** The CSS-variable namespace every Message custom property carries (one prefix, derived names). */
const VAR_PREFIX = '--eden-message';

/**
 * The resolved token set a Message renders from: the role's container colours (CSS + raw OKLCH for
 * the contrast recompute) and the prose proportion + space picks (every px a scale value).
 */
export interface MessageTokens {
  /** The bubble text colour as a CSS `oklch(...)` string. */
  readonly foreground: string;
  /** The bubble fill colour as a CSS `oklch(...)` string. */
  readonly background: string;
  /** The bubble edge colour as a CSS `oklch(...)` string. */
  readonly border: string;
  /** The raw OKLCH of the text — the contrast gate recomputes the ratio from this. */
  readonly foregroundOklch: OkLch;
  /** The raw OKLCH of the fill — the contrast gate recomputes the ratio from this. */
  readonly backgroundOklch: OkLch;
  /** The prose font size, px — the `body` typography role (a type-scale value). */
  readonly fontSizePx: number;
  /** The prose line height, px — the `body` role's line height (WCAG 1.4.12 floor applied upstream). */
  readonly lineHeightPx: number;
  /** The prose font family — the `body` typography role family (the seed text font). */
  readonly fontFamily: string;
  /** The bubble inner padding, px — a spacing-ramp step (not eyeballed). */
  readonly paddingPx: number;
  /** The gap between the role label and the prose, px — a spacing-ramp step. */
  readonly gapPx: number;
  /** The bubble corner radius, px — a spacing-ramp step. */
  readonly radiusPx: number;
}

/** Select the chat-surface container for a Message role (cited, never re-derived). */
function surfaceForRole(role: MessageRole, theme: Theme): SurfacePair {
  return role === 'user' ? accentSurface(theme) : quietSurface(theme);
}

/**
 * Derive the full {@link MessageTokens} for a role from a generated theme. PURE: the theme is the
 * single input. The proportion is the `body` prose role; padding/gap/radius are named spacing-ramp
 * indices (4→16px, 2→8px, 3→12px for the default ramp) — each provably a ramp step.
 */
export function deriveMessageTokens(role: MessageRole, theme: Theme): MessageTokens {
  const surface = surfaceForRole(role, theme);
  const prose = proportion(theme, 'body');
  return {
    foreground: surface.foreground,
    background: surface.background,
    border: surface.border,
    foregroundOklch: surface.foregroundOklch,
    backgroundOklch: surface.backgroundOklch,
    fontSizePx: prose.fontSizePx,
    lineHeightPx: prose.lineHeightPx,
    fontFamily: prose.fontFamily,
    paddingPx: space(theme, 4), // 16px
    gapPx: space(theme, 2), // 8px
    radiusPx: space(theme, 3), // 12px
  };
}

/** Render {@link MessageTokens} as the inline `style` custom-property string the component binds. */
export function messageStyleVars(tokens: MessageTokens): string {
  return styleVars(VAR_PREFIX, [
    ['fg', tokens.foreground],
    ['bg', tokens.background],
    ['border', tokens.border],
    ['font-size', tokens.fontSizePx],
    ['line-height', tokens.lineHeightPx],
    ['font-family', tokens.fontFamily],
    ['padding', tokens.paddingPx],
    ['gap', tokens.gapPx],
    ['radius', tokens.radiusPx],
  ]);
}
