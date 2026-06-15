import { fc, test } from '@fast-check/vitest';
import { expect } from 'vitest';
import {
  srgbToOkLab,
  okLabToSrgb,
  srgbToOkLch,
  okLchToSrgb,
  srgbTo8,
  gamutMapOkLch,
  wcagContrastRatio,
  nearestPassingForeground,
  generateRamp,
  typeSizePx,
  lineHeight,
  densify,
  generateTheme,
  C21_SEED,
  type WcagLevel,
  type ContentClass,
} from './index.js';

// Arbitraries over the valid domains.
const channel = fc.double({ min: 0, max: 1, noNaN: true, noDefaultInfinity: true });
const srgb = fc.record({ r: channel, g: channel, b: channel });
const hue = fc.double({ min: 0, max: 360, noNaN: true, noDefaultInfinity: true });
const lightness = fc.double({ min: 0.02, max: 0.98, noNaN: true, noDefaultInfinity: true });
const chroma = fc.double({ min: 0, max: 0.37, noNaN: true, noDefaultInfinity: true });
const oklch = fc.record({ l: lightness, c: chroma, h: hue });

test.prop({ srgb })('sRGB → OKLab → sRGB round-trips within float epsilon', ({ srgb }) => {
  const back = okLabToSrgb(srgbToOkLab(srgb));
  expect(back.r).toBeCloseTo(srgb.r, 5);
  expect(back.g).toBeCloseTo(srgb.g, 5);
  expect(back.b).toBeCloseTo(srgb.b, 5);
});

test.prop({ srgb })('sRGB → OKLCH → sRGB round-trips within float epsilon', ({ srgb }) => {
  const back = okLchToSrgb(srgbToOkLch(srgb));
  expect(back.r).toBeCloseTo(srgb.r, 5);
  expect(back.g).toBeCloseTo(srgb.g, 5);
  expect(back.b).toBeCloseTo(srgb.b, 5);
});

test.prop({ oklch })('gamut mapping always yields an in-[0,1] sRGB color', ({ oklch }) => {
  const mapped = gamutMapOkLch(oklch);
  const { r, g, b } = okLchToSrgb(mapped);
  for (const ch of [r, g, b]) {
    expect(ch).toBeGreaterThanOrEqual(-1e-6);
    expect(ch).toBeLessThanOrEqual(1 + 1e-6);
  }
  // mapping preserves hue and never raises chroma.
  expect(mapped.h).toBe(oklch.h);
  expect(mapped.c).toBeLessThanOrEqual(oklch.c + 1e-9);
});

test.prop({ a: srgb, b: srgb })('WCAG contrast ratio is symmetric and in [1, 21]', ({ a, b }) => {
  const a8 = srgbTo8(a);
  const b8 = srgbTo8(b);
  const ab = wcagContrastRatio(a8, b8);
  expect(ab).toBeCloseTo(wcagContrastRatio(b8, a8), 12); // symmetric
  expect(ab).toBeGreaterThanOrEqual(1 - 1e-9);
  expect(ab).toBeLessThanOrEqual(21 + 1e-9);
});

const level = fc.constantFrom<WcagLevel>('AA', 'AAA');
const contentClass = fc.constantFrom<ContentClass>('normal-text', 'large-text', 'ui-component');

test.prop({ seed: oklch, bg: srgb, level, contentClass })(
  'the inverse gate ALWAYS returns a pair that meets its target (unless clamped)',
  ({ seed, bg, level, contentClass }) => {
    const r = nearestPassingForeground(seed, srgbTo8(bg), contentClass, level);
    // hue/chroma stay on-brand — only L moves (the gate's invariant).
    expect(r.suggestedForeground.h).toBe(seed.h);
    expect(r.suggestedForeground.c).toBe(seed.c);
    // if it did not hit the L=0/1 wall, the achieved ratio meets the target (unrounded).
    if (r.action !== 'clamped') {
      expect(r.achievedRatio).toBeGreaterThanOrEqual(r.targetRatio - 1e-9);
      expect(r.pass).toBe(true);
    }
  },
);

test.prop({ seed: oklch })('a generated ramp holds hue constant and stays in-gamut', ({ seed }) => {
  const ramp = generateRamp(seed);
  for (const step of [50, 500, 950] as const) {
    expect(ramp.steps[step].h).toBeCloseTo(seed.h, 4);
    const { r, g, b } = okLchToSrgb(ramp.steps[step]);
    for (const ch of [r, g, b]) {
      expect(ch).toBeGreaterThanOrEqual(-1e-3);
      expect(ch).toBeLessThanOrEqual(1 + 1e-3);
    }
  }
});

const i = fc.integer({ min: -4, max: 6 });
const ratio = fc.double({ min: 1.05, max: 1.7, noNaN: true, noDefaultInfinity: true });

test.prop({ i, ratio })('the type scale is strictly monotone and geometric', ({ i, ratio }) => {
  const here = typeSizePx(i, 16, ratio);
  const up = typeSizePx(i + 1, 16, ratio);
  expect(up).toBeGreaterThan(here);
  expect(Math.abs(up - here * ratio)).toBeLessThanOrEqual(1e-9 * here * ratio);
});

const sizePx = fc.double({ min: 8, max: 80, noNaN: true, noDefaultInfinity: true });

test.prop({ sizePx })('body line-height never drops below the WCAG 1.5 floor', ({ sizePx }) => {
  expect(lineHeight(sizePx, 60, true)).toBeGreaterThanOrEqual(1.5);
});

const tier = fc.constantFrom('spacious', 'comfortable', 'compact', 'condensed' as const);

test.prop({ tier })('density never changes font/icon size (invariant I7)', ({ tier }) => {
  const base = { componentHeightPx: 40, insetPx: 12, gapPx: 16, fontSizePx: 14, iconSizePx: 20 };
  const g = densify(base, tier);
  expect(g.fontSizePx).toBe(14);
  expect(g.iconSizePx).toBe(20);
  expect(g.lineHeightPx).toBeGreaterThanOrEqual(1.5 * 14); // I3 floor
});

const mode = fc.constantFrom('light', 'dark' as const);

test.prop({ mode, tier })(
  'generateTheme is deterministic — same seed+options → identical theme',
  ({ mode, tier }) => {
    const a = generateTheme(C21_SEED, { mode, density: tier });
    const b = generateTheme(C21_SEED, { mode, density: tier });
    expect(a).toStrictEqual(b);
  },
);
