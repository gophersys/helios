/**
 * `@eden/primitives` — StreamingText token derivation (ADR-0024 §3, the ninth dimension).
 *
 * MATH IS SOURCE OF TRUTH. StreamingText renders an assistant's prose as it arrives token-by-token,
 * with a blinking caret while the stream is live. Its appearance is the PROSE chat-surface container
 * (on-surface over surface — the highest-contrast reading pair) plus the `body` proportion; the caret
 * is the SAME gated foreground (so it inherits the contrast guarantee). All read out of a generated
 * {@link Theme} via the shared chat-surface vocabulary — nothing decided by hand.
 *
 * The token-by-token MATH lives here too (pure, fully coverable, the mutated surface):
 * {@link appendChunk} accumulates a chunk onto the prior text and reports the visible character count
 * (what the renderer reveals); {@link streamProgress} is the fraction revealed of an expected total.
 * Keeping the accumulation pure makes the streaming logic testable without a DOM and mutation-proof.
 */

import type { Theme, OkLch } from '@eden/theme';
import {
  proseSurface,
  proportion,
  space,
  styleVars,
  type SurfacePair,
} from '../chat-surface/index.js';

/** The CSS-variable namespace every StreamingText custom property carries (one prefix). */
const VAR_PREFIX = '--eden-streaming-text';

/** The resolved token set a StreamingText renders from (prose container + proportion + caret space). */
export interface StreamingTextTokens {
  /** The prose text colour as a CSS `oklch(...)` string. */
  readonly foreground: string;
  /** The reading surface fill as a CSS `oklch(...)` string. */
  readonly background: string;
  /** The caret colour as a CSS `oklch(...)` string — equals the foreground (gated by construction). */
  readonly caret: string;
  /** The raw OKLCH of the text — the contrast gate recomputes the ratio from this. */
  readonly foregroundOklch: OkLch;
  /** The raw OKLCH of the fill — the contrast gate recomputes the ratio from this. */
  readonly backgroundOklch: OkLch;
  /** The prose font size, px — the `body` typography role. */
  readonly fontSizePx: number;
  /** The prose line height, px — the `body` role's line height. */
  readonly lineHeightPx: number;
  /** The prose font family — the `body` typography role family. */
  readonly fontFamily: string;
  /** The caret width, px — the smallest spacing-ramp step (a hairline, on the scale). */
  readonly caretWidthPx: number;
}

function prose(theme: Theme): SurfacePair {
  return proseSurface(theme);
}

/** Derive the full {@link StreamingTextTokens} from a generated theme. PURE: the theme is the input. */
export function deriveStreamingTextTokens(theme: Theme): StreamingTextTokens {
  const surface = prose(theme);
  const body = proportion(theme, 'body');
  return {
    foreground: surface.foreground,
    background: surface.background,
    caret: surface.foreground,
    foregroundOklch: surface.foregroundOklch,
    backgroundOklch: surface.backgroundOklch,
    fontSizePx: body.fontSizePx,
    lineHeightPx: body.lineHeightPx,
    fontFamily: body.fontFamily,
    caretWidthPx: space(theme, 0), // 2px — the smallest ramp step (a hairline caret)
  };
}

/** Render {@link StreamingTextTokens} as the inline `style` custom-property string. */
export function streamingTextStyleVars(tokens: StreamingTextTokens): string {
  return styleVars(VAR_PREFIX, [
    ['fg', tokens.foreground],
    ['bg', tokens.background],
    ['caret', tokens.caret],
    ['font-size', tokens.fontSizePx],
    ['line-height', tokens.lineHeightPx],
    ['font-family', tokens.fontFamily],
    ['caret-width', tokens.caretWidthPx],
  ]);
}

/**
 * Append a streamed chunk onto the accumulated text. PURE: returns the new text and the visible
 * character count (the spread `[...text]` counts code points, so an emoji or combined glyph reveals
 * as one character, not its UTF-16 unit count — what a reader actually sees). This is the
 * token-by-token reveal math the renderer drives, kept out of the DOM so it is unit-testable.
 */
export function appendChunk(
  accumulated: string,
  chunk: string,
): { readonly text: string; readonly visibleChars: number } {
  const text = accumulated + chunk;
  // The code-point spread is DELIBERATE and is exactly the behaviour the design lane asserts: a
  // reader sees an astral glyph (an emoji) as ONE visible character, not its two UTF-16 units. The
  // lint's worry (decomposing complex emoji) is the very property we want — reveal-by-code-point.
  // eslint-disable-next-line @typescript-eslint/no-misused-spread -- code-point count is intended (tested)
  return { text, visibleChars: [...text].length };
}

/**
 * The fraction of an expected total revealed so far, clamped to [0, 1]. A non-positive expected total
 * means the total is unknown → progress is reported as 0 (indeterminate); a revealed count at or past
 * the total is a full 1. Pure, total, and the basis for an optional progress affordance.
 */
export function streamProgress(visibleChars: number, expectedTotal: number): number {
  if (expectedTotal <= 0) return 0;
  return Math.min(1, Math.max(0, visibleChars / expectedTotal));
}
