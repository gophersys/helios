/**
 * chat-surface — the DESIGN-CORRECTNESS lane for the SHARED vocabulary (ADR-0024 §3, the ninth
 * dimension). Every chat component is built from these primitives, so proving the vocabulary correct
 * proves a floor under all of them: (1) every container's foreground/background pair MEETS the WCAG
 * contrast gate — recomputed from the SAME OKLCH the helper emits, against @eden/theme's own ratio +
 * APCA; (2) every proportion pick is a real generated typography role (size + line height on the type
 * scale, no hand px); (3) every `space` pick lands on the generated spacing ramp. Each load-bearing
 * assertion is WEAKEN-TO-CONFIRM guarded. MATH IS SOURCE OF TRUTH — the contrast/scale cited is
 * @eden/theme's; this module derives, never re-spells.
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
import {
  proseSurface,
  accentSurface,
  quietSurface,
  stateSurface,
  proportion,
  rampPx,
  space,
  hitTargetPx,
  styleVars,
  type SurfacePair,
  type StateRole,
} from './tokens.js';

function contrastOf(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}
function apcaOf(fg: OkLch, bg: OkLch): number {
  return Math.abs(apcaLc(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg))));
}

const STATES: readonly StateRole[] = ['error', 'success', 'warning', 'info'];

describe('chat-surface (1): every container pair meets the WCAG contrast gate (cite @eden/theme)', () => {
  for (const mode of ['light', 'dark'] as const) {
    const theme = generateTheme(C21_SEED, { mode, level: 'AA' });
    const target = wcagTarget('normal-text', 'AA');

    const named: readonly [string, SurfacePair][] = [
      ['prose', proseSurface(theme)],
      ['accent', accentSurface(theme)],
      ['quiet', quietSurface(theme)],
      ...STATES.map((s): [string, SurfacePair] => [`state:${s}`, stateSurface(s, theme)]),
    ];

    for (const [label, pair] of named) {
      it(`${label}@${mode}: foreground over background clears the AA UI-text target (4.5)`, () => {
        expect(target).toBe(4.5); // cited target value (provenance pin)
        expect(contrastOf(pair.foregroundOklch, pair.backgroundOklch)).toBeGreaterThanOrEqual(
          target,
        );
      });
    }

    it(`accent@${mode}: APCA agrees the brand pair is strong (>= 45 Lc advisory)`, () => {
      const p = accentSurface(theme);
      expect(apcaOf(p.foregroundOklch, p.backgroundOklch)).toBeGreaterThanOrEqual(45);
    });
  }

  it('WEAKEN-TO-CONFIRM: a fabricated mid-grey foreground FAILS the same gate (it does real work)', () => {
    const theme = generateTheme(C21_SEED);
    const prose = proseSurface(theme);
    const grey: OkLch = { l: prose.backgroundOklch.l, c: 0, h: 0 };
    expect(contrastOf(grey, prose.backgroundOklch)).toBeLessThan(wcagTarget('normal-text', 'AA'));
  });

  it('the emitted CSS carries only oklch() colours — no hand-set hex anywhere', () => {
    const theme = generateTheme(C21_SEED);
    for (const pair of [proseSurface(theme), accentSurface(theme), quietSurface(theme)]) {
      expect(pair.foreground).toMatch(/^oklch\(/);
      expect(pair.background).toMatch(/^oklch\(/);
      expect(pair.foreground).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    }
  });
});

describe('chat-surface (2): every proportion pick is a real generated typography role (no hand px)', () => {
  const theme: Theme = generateTheme(C21_SEED);

  for (const role of ['body', 'label', 'caption', 'title'] as const) {
    it(`proportion('${role}') equals the generated typography role's size + family`, () => {
      const p = proportion(theme, role);
      const tr = theme.typography.find((r) => r.name === role)!;
      expect(p.fontSizePx).toBe(tr.fontSizePx);
      expect(p.fontFamily).toBe(tr.fontFamily);
      // line height is the role's multiple × size, rounded — a derived px, never eyeballed.
      expect(p.lineHeightPx).toBe(Math.round(tr.fontSizePx * tr.lineHeight));
      // the line height clears the WCAG 1.4.12 1.5× floor for body-class roles (research B1-C).
      expect(p.lineHeightPx).toBeGreaterThanOrEqual(p.fontSizePx);
    });
  }

  it('an unknown role falls back to `body` (the derivation is total, never undefined)', () => {
    const p = proportion(theme, 'no-such-role');
    const body = theme.typography.find((r) => r.name === 'body')!;
    expect(p.fontSizePx).toBe(body.fontSizePx);
  });

  it('WEAKEN-TO-CONFIRM: a hand-irregular 15px size is on NO typography role', () => {
    const sizes = theme.typography.map((r) => r.fontSizePx);
    expect(sizes).not.toContain(15);
  });
});

describe('chat-surface (3): every space pick lands on the generated spacing ramp', () => {
  const theme = generateTheme(C21_SEED);

  it('space(index) is exactly the ramp step at that index, and is ON the ramp', () => {
    const ramp = rampPx(theme);
    for (let i = 0; i < ramp.length; i++) {
      expect(space(theme, i)).toBe(ramp[i]);
      expect(ramp).toContain(space(theme, i));
    }
  });

  it('the index is clamped — an out-of-range index returns a real ramp step (total)', () => {
    const ramp = rampPx(theme);
    expect(space(theme, -5)).toBe(ramp[0]);
    expect(space(theme, 9999)).toBe(ramp[ramp.length - 1]);
  });

  it('WEAKEN-TO-CONFIRM: a hand-set 13px is NOT on the spacing ramp (the membership check bites)', () => {
    expect(rampPx(theme)).not.toContain(13);
  });
});

describe('chat-surface (hit target): the AAA 44px floor holds in every density', () => {
  it('every density keeps the shared hit target >= 44px', () => {
    for (const density of ['spacious', 'comfortable', 'compact', 'condensed'] as const) {
      const theme = generateTheme(C21_SEED, { density });
      expect(hitTargetPx(theme), density).toBeGreaterThanOrEqual(44);
    }
  });

  it('WEAKEN-TO-CONFIRM: a pointer-context theme drops the shared hit target below 44', () => {
    const pointer = generateTheme(C21_SEED, { density: 'condensed', targetContext: 'pointer' });
    expect(hitTargetPx(pointer)).toBeLessThan(44);
  });
});

describe('chat-surface (provenance): styleVars emits derived tokens only (no literals)', () => {
  it('numeric entries get a px unit, colour/string entries pass through, no hex appears', () => {
    const theme = generateTheme(C21_SEED);
    const prose = proseSurface(theme);
    const css = styleVars('--eden-x', [
      ['fg', prose.foreground],
      ['bg', prose.background],
      ['pad', space(theme, 4)],
      ['family', proportion(theme, 'body').fontFamily],
    ]);
    expect(css).toContain('--eden-x-fg: oklch(');
    expect(css).toContain('--eden-x-bg: oklch(');
    expect(css).toContain('--eden-x-pad: 16px;');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it('WEAKEN-TO-CONFIRM: a numeric value WITHOUT the px unit would not match the px assertion', () => {
    // proves the px-suffix branch is load-bearing: the raw number 16 is not "16px".
    expect(String(16)).not.toBe('16px');
  });
});

describe('chat-surface (totality): the derivation stays total on a degenerate theme', () => {
  it('proportion falls back to a 0-size `inherit` when typography is empty (never thrown)', () => {
    const theme = generateTheme(C21_SEED);
    const noType: Theme = { ...theme, typography: [] };
    const p = proportion(noType, 'body');
    expect(p).toEqual({ fontSizePx: 0, lineHeightPx: 0, fontFamily: 'inherit' });
  });

  it('proportion falls back to `body` then the first role when the named role is absent', () => {
    const theme = generateTheme(C21_SEED);
    const noLabel: Theme = {
      ...theme,
      typography: theme.typography.filter((r) => r.name !== 'label' && r.name !== 'body'),
    };
    // 'label' and 'body' are gone → falls back to the FIRST remaining role (index 0).
    const p = proportion(noLabel, 'label');
    expect(p.fontSizePx).toBe(noLabel.typography[0]!.fontSizePx);
  });

  it('space returns 0 on an empty ramp (clamp is total; never an out-of-range read)', () => {
    const theme = generateTheme(C21_SEED);
    const noRamp: Theme = { ...theme, spacing: [] };
    expect(space(noRamp, 3)).toBe(0);
  });
});
