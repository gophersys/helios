/**
 * ToolCall — the DESIGN-CORRECTNESS lane (ADR-0024 §3). MECHANICAL: (1) the card prose pair, the
 * CODE-BLOCK pair, and the STATUS-accent-over-surface pair (for every status) MEET the contrast gate
 * in both modes — recomputed from the SAME OKLCH the component emits; (2) the title/code proportions
 * are generated typography roles (label/caption, no hand px); (3) padding/gap/radius land on the
 * spacing ramp. Each load-bearing assertion is WEAKEN-TO-CONFIRM guarded. MATH IS SOURCE OF TRUTH.
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
import { deriveToolCallTokens, toolCallStyleVars, type ToolCallStatus } from './tokens.js';

const STATUSES: readonly ToolCallStatus[] = ['running', 'success', 'error'];

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): card prose, code block, and status accent meet the contrast gate', () => {
  for (const mode of ['light', 'dark'] as const) {
    const theme = generateTheme(C21_SEED, { mode, level: 'AA' });
    const target = wcagTarget('normal-text', 'AA');

    it(`${mode}: card text over card fill clears AA (4.5) — the card prose AND the code block`, () => {
      const t = deriveToolCallTokens('running', theme);
      expect(target).toBe(4.5);
      // the code block uses the SAME card fg/bg pair, so this pair covers both prose and code text.
      expect(contrastOf(t.foregroundOklch, t.backgroundOklch)).toBeGreaterThanOrEqual(target);
    });

    for (const status of STATUSES) {
      it(`${mode}: the ${status} status accent over the card fill clears AA (4.5)`, () => {
        const t = deriveToolCallTokens(status, theme);
        expect(contrastOf(t.statusOklch, t.backgroundOklch)).toBeGreaterThanOrEqual(target);
      });
    }
  }

  it('the three statuses render DISTINCT accents (info / success / error)', () => {
    const theme = generateTheme(C21_SEED);
    const colors = STATUSES.map((s) => deriveToolCallTokens(s, theme).statusColor);
    expect(new Set(colors).size).toBe(3);
  });

  it('WEAKEN-TO-CONFIRM: a grey status accent fails the same gate', () => {
    const theme = generateTheme(C21_SEED);
    const t = deriveToolCallTokens('error', theme);
    const grey: OkLch = { l: t.backgroundOklch.l, c: 0, h: 0 };
    expect(contrastOf(grey, t.backgroundOklch)).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });
});

describe('design-correctness (2): the proportions are generated typography roles (no hand px)', () => {
  const theme: Theme = generateTheme(C21_SEED);
  it('the tool-name proportion is the generated `label` role', () => {
    const t = deriveToolCallTokens('running', theme);
    const label = theme.typography.find((r) => r.name === 'label')!;
    expect(t.titleSizePx).toBe(label.fontSizePx);
    expect(t.titleFontFamily).toBe(label.fontFamily);
    expect(t.titleLineHeightPx).toBe(Math.round(label.fontSizePx * label.lineHeight));
  });
  it('the code size is the generated `caption` role; the family is the monospace keyword', () => {
    const t = deriveToolCallTokens('running', theme);
    const caption = theme.typography.find((r) => r.name === 'caption')!;
    expect(t.codeSizePx).toBe(caption.fontSizePx);
    expect(t.codeFontFamily).toBe('monospace');
  });
  it('WEAKEN-TO-CONFIRM: 15px is on NO typography role', () => {
    expect(theme.typography.map((r) => r.fontSizePx)).not.toContain(15);
  });
});

describe('design-correctness (3): padding/gap/radius land on the spacing ramp', () => {
  const theme = generateTheme(C21_SEED);
  it('padding / gap / radius are each a ramp step (16/8/12 default)', () => {
    const t = deriveToolCallTokens('running', theme);
    const ramp = theme.spacing.map((s) => s.px);
    for (const v of [t.paddingPx, t.gapPx, t.radiusPx]) expect(ramp).toContain(v);
    expect([t.paddingPx, t.gapPx, t.radiusPx]).toEqual([16, 8, 12]);
  });
  it('WEAKEN-TO-CONFIRM: 13px is not on the ramp', () => {
    expect(theme.spacing.map((s) => s.px)).not.toContain(13);
  });
});

describe('design-correctness (provenance): the emitted CSS carries only derived tokens', () => {
  it('toolCallStyleVars emits oklch() colours + px + the monospace keyword, no hex', () => {
    const css = toolCallStyleVars(deriveToolCallTokens('success', generateTheme(C21_SEED)));
    expect(css).toContain('--eden-tool-call-fg: oklch(');
    expect(css).toContain('--eden-tool-call-status: oklch(');
    expect(css).toContain('--eden-tool-call-code-family: monospace;');
    expect(css).toContain('--eden-tool-call-padding: 16px;');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
