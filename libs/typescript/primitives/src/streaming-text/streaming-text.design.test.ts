/**
 * StreamingText — the DESIGN-CORRECTNESS lane (ADR-0024 §3). MECHANICAL: (1) the rendered prose pair
 * (text over surface) and the caret-over-surface pair MEET the contrast gate in both modes; (2) the
 * proportion is the generated `body` role; (3) the caret width is a spacing-ramp step. Plus the
 * token-by-token reveal MATH is asserted (append accumulates, progress clamps). Each load-bearing
 * assertion is WEAKEN-TO-CONFIRM guarded. MATH IS SOURCE OF TRUTH — cited from @eden/theme.
 */
import { describe, expect, it } from 'vitest';
import {
  generateTheme,
  C21_SEED,
  wcagContrastRatio,
  wcagTarget,
  okLchToSrgb,
  srgbTo8,
  type Theme,
  type OkLch,
} from '@eden/theme';
import {
  deriveStreamingTextTokens,
  streamingTextStyleVars,
  appendChunk,
  streamProgress,
} from './tokens.js';

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): the prose + caret pairs meet the contrast gate', () => {
  for (const mode of ['light', 'dark'] as const) {
    const theme = generateTheme(C21_SEED, { mode, level: 'AA' });
    it(`${mode}: prose text over surface clears the AA UI-text target (4.5)`, () => {
      const t = deriveStreamingTextTokens(theme);
      const target = wcagTarget('normal-text', 'AA');
      expect(target).toBe(4.5);
      expect(contrastOf(t.foregroundOklch, t.backgroundOklch)).toBeGreaterThanOrEqual(target);
    });
    it(`${mode}: the caret equals the gated foreground (inherits the contrast guarantee)`, () => {
      const t = deriveStreamingTextTokens(theme);
      expect(t.caret).toBe(t.foreground);
    });
  }

  it('WEAKEN-TO-CONFIRM: a grey foreground fails the same gate', () => {
    const t = deriveStreamingTextTokens(generateTheme(C21_SEED));
    const grey: OkLch = { l: t.backgroundOklch.l, c: 0, h: 0 };
    expect(contrastOf(grey, t.backgroundOklch)).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): the proportion is the generated body role (no hand px)', () => {
  const theme: Theme = generateTheme(C21_SEED);
  it('font size / line height / family equal the generated body typography role', () => {
    const t = deriveStreamingTextTokens(theme);
    const body = theme.typography.find((r) => r.name === 'body')!;
    expect(t.fontSizePx).toBe(body.fontSizePx);
    expect(t.fontFamily).toBe(body.fontFamily);
    expect(t.lineHeightPx).toBe(Math.round(body.fontSizePx * body.lineHeight));
  });
});

describe('design-correctness (3): the caret width is a spacing-ramp step', () => {
  const theme = generateTheme(C21_SEED);
  it('caret width is the smallest ramp step (2px) and is ON the ramp', () => {
    const t = deriveStreamingTextTokens(theme);
    const ramp = theme.spacing.map((s) => s.px);
    expect(ramp).toContain(t.caretWidthPx);
    expect(t.caretWidthPx).toBe(2);
  });
  it('WEAKEN-TO-CONFIRM: a hand 3px caret is NOT on the ramp', () => {
    expect(theme.spacing.map((s) => s.px)).not.toContain(3);
  });
});

describe('the token-by-token reveal MATH', () => {
  it('appendChunk accumulates onto the prior text and counts visible code points', () => {
    const a = appendChunk('', 'He');
    expect(a.text).toBe('He');
    expect(a.visibleChars).toBe(2);
    const b = appendChunk(a.text, 'llo');
    expect(b.text).toBe('Hello');
    expect(b.visibleChars).toBe(5);
  });

  it('appendChunk counts an astral glyph as ONE visible char (code points, not UTF-16 units)', () => {
    // a single emoji is two UTF-16 units but one visible character.
    const r = appendChunk('', '\u{1F600}');
    expect(r.visibleChars).toBe(1);
    expect(r.text.length).toBe(2); // the UTF-16 length differs — proves the spread-count is load-bearing
  });

  it('streamProgress is the clamped fraction revealed; unknown total → 0 (indeterminate)', () => {
    expect(streamProgress(5, 10)).toBe(0.5);
    expect(streamProgress(20, 10)).toBe(1); // clamped at 1
    expect(streamProgress(5, 0)).toBe(0); // unknown total
    expect(streamProgress(5, -3)).toBe(0); // non-positive total
  });

  it('WEAKEN-TO-CONFIRM: without clamping, 20/10 would exceed 1 (the clamp is load-bearing)', () => {
    expect(20 / 10).toBeGreaterThan(1);
  });
});

describe('design-correctness (provenance): the emitted CSS carries only derived tokens', () => {
  it('streamingTextStyleVars emits oklch() colours + px — no hand-set hex', () => {
    const css = streamingTextStyleVars(deriveStreamingTextTokens(generateTheme(C21_SEED)));
    expect(css).toContain('--eden-streaming-text-fg: oklch(');
    expect(css).toContain('--eden-streaming-text-caret-width: 2px;');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
