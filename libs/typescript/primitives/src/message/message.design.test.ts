/**
 * Message — the DESIGN-CORRECTNESS lane (ADR-0024 §3, the ninth dimension). MECHANICAL per component:
 * (1) the rendered prose pair (bubble text over bubble fill) MEETS the WCAG+APCA contrast gate for
 * BOTH roles in BOTH modes — recomputed from the SAME OKLCH the component emits; (2) the prose
 * proportion is the generated `body` typography role (size + line height on the type scale, no hand
 * px); (3) every padding/gap/radius lands on the generated spacing ramp. Each load-bearing assertion
 * is WEAKEN-TO-CONFIRM guarded. MATH IS SOURCE OF TRUTH — contrast + scale cited from @eden/theme.
 */
import { describe, expect, it } from 'vitest';
import {
  generateTheme,
  C21_SEED,
  wcagContrastRatio,
  wcagTarget,
  apcaLc,
  okLchToSrgb,
  srgbTo8,
  type Theme,
  type OkLch,
} from '@eden/theme';
import { deriveMessageTokens, messageStyleVars, type MessageRole } from './tokens.js';

const ROLES: readonly MessageRole[] = ['user', 'assistant'];

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

describe('design-correctness (1): the bubble prose pair meets the contrast gate (cite @eden/theme)', () => {
  for (const mode of ['light', 'dark'] as const) {
    const theme = generateTheme(C21_SEED, { mode, level: 'AA' });
    for (const role of ROLES) {
      it(`${role}@${mode}: bubble text over bubble fill clears the AA UI-text target (4.5)`, () => {
        const t = deriveMessageTokens(role, theme);
        const target = wcagTarget('normal-text', 'AA');
        expect(target).toBe(4.5); // cited provenance pin
        expect(contrastOf(t.foregroundOklch, t.backgroundOklch)).toBeGreaterThanOrEqual(target);
      });
    }
  }

  it('APCA agrees both role bubbles are strong perceptual pairs (>= 45 Lc advisory)', () => {
    const theme = generateTheme(C21_SEED);
    for (const role of ROLES) {
      const t = deriveMessageTokens(role, theme);
      const lc = Math.abs(
        apcaLc(srgbTo8(okLchToSrgb(t.foregroundOklch)), srgbTo8(okLchToSrgb(t.backgroundOklch))),
      );
      expect(lc, role).toBeGreaterThanOrEqual(45);
    }
  });

  it('WEAKEN-TO-CONFIRM: a fabricated grey foreground FAILS the same gate (it does real work)', () => {
    const theme = generateTheme(C21_SEED);
    const t = deriveMessageTokens('assistant', theme);
    const grey: OkLch = { l: t.backgroundOklch.l, c: 0, h: 0 };
    expect(contrastOf(grey, t.backgroundOklch)).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });

  it('the two roles render DISTINCT containers (user accent vs assistant quiet)', () => {
    const theme = generateTheme(C21_SEED);
    const user = deriveMessageTokens('user', theme);
    const assistant = deriveMessageTokens('assistant', theme);
    expect(user.background).not.toBe(assistant.background);
  });
});

describe('design-correctness (2): the prose proportion is the generated body role (no hand px)', () => {
  const theme: Theme = generateTheme(C21_SEED);

  it('font size + line height + family equal the generated `body` typography role', () => {
    const t = deriveMessageTokens('assistant', theme);
    const body = theme.typography.find((r) => r.name === 'body')!;
    expect(t.fontSizePx).toBe(body.fontSizePx);
    expect(t.fontFamily).toBe(body.fontFamily);
    expect(t.lineHeightPx).toBe(Math.round(body.fontSizePx * body.lineHeight));
  });

  it('the prose line height clears the WCAG 1.4.12 floor (>= the font size)', () => {
    const t = deriveMessageTokens('user', theme);
    expect(t.lineHeightPx).toBeGreaterThanOrEqual(t.fontSizePx);
  });

  it('WEAKEN-TO-CONFIRM: a hand-irregular 15px is on NO typography role', () => {
    expect(theme.typography.map((r) => r.fontSizePx)).not.toContain(15);
  });
});

describe('design-correctness (3): every padding/gap/radius lands on the spacing ramp', () => {
  const theme = generateTheme(C21_SEED);

  it('padding / gap / radius are each a generated spacing-ramp step', () => {
    const t = deriveMessageTokens('assistant', theme);
    const ramp = theme.spacing.map((s) => s.px);
    expect(ramp).toContain(t.paddingPx);
    expect(ramp).toContain(t.gapPx);
    expect(ramp).toContain(t.radiusPx);
  });

  it('the exact ramp picks are 16/8/12 for the default ramp (kills an always-first mutant)', () => {
    const t = deriveMessageTokens('assistant', theme);
    expect(t.paddingPx).toBe(16);
    expect(t.gapPx).toBe(8);
    expect(t.radiusPx).toBe(12);
  });

  it('WEAKEN-TO-CONFIRM: a hand 13px is NOT on the spacing ramp', () => {
    expect(theme.spacing.map((s) => s.px)).not.toContain(13);
  });
});

describe('design-correctness (provenance): the emitted CSS carries only derived tokens', () => {
  it('messageStyleVars emits oklch() colours + px dimensions — no hand-set hex anywhere', () => {
    const theme = generateTheme(C21_SEED);
    for (const role of ROLES) {
      const css = messageStyleVars(deriveMessageTokens(role, theme));
      expect(css).toContain('--eden-message-fg: oklch(');
      expect(css).toContain('--eden-message-bg: oklch(');
      expect(css).toContain('--eden-message-padding: 16px;');
      expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    }
  });
});
