/**
 * HotspotMap scatter math — EXACT-VALUE unit assertions (the mutation-killing lane). The property
 * lane proves invariants over all inputs; this lane pins the EXACT computed values, so a mutated
 * arithmetic operator, a flipped comparator, a dropped clamp, or a swapped string literal changes a
 * concrete number/string a test reads (rule 21 §h: a survived mutant on covered code is a real test
 * gap — kill it with a stronger assertion, never lower the floor).
 */
import { describe, expect, it } from 'vitest';
import {
  extentOf,
  linearScale,
  radiusScale,
  hotspotColorAt,
  hotspotColorCssAt,
  ticks,
  entityValue,
  entityLabel,
  type HotspotRamp,
} from './scales.js';
import { deriveHotspotMapTokens, hotspotMapStyleVars } from './tokens.js';
import { generateTheme, C21_SEED, oklchToCss } from '@eden/theme';
import type { Entity } from '../report/index.js';

const mk = (over: Partial<Entity>): Entity => ({
  path: 'x',
  kind: 'file',
  lines: 1,
  churnAbsolute: 0,
  churnRelative: 0,
  changeFrequency: 0,
  hotspotScore: 0,
  ageDays: 0,
  ...over,
});

describe('extentOf — exact min/max, the empty-set guard, and the comparator boundaries', () => {
  it('an EMPTY set falls back to the unit interval {0,1} (the !isFinite guard)', () => {
    expect(extentOf([], (e) => entityValue(e, 'lines'))).toEqual({ min: 0, max: 1 });
  });

  it('spans the exact min and max (and is not the first/last value — the < / > are load-bearing)', () => {
    const entities = [mk({ lines: 5 }), mk({ lines: 1 }), mk({ lines: 9 }), mk({ lines: 3 })];
    const ext = extentOf(entities, (e) => entityValue(e, 'lines'));
    expect(ext.min).toBe(1);
    expect(ext.max).toBe(9);
  });

  it('a single entity yields min === max === its value (not Infinity — the loop assigns both)', () => {
    expect(extentOf([mk({ lines: 7 })], (e) => entityValue(e, 'lines'))).toEqual({
      min: 7,
      max: 7,
    });
  });
});

describe('linearScale — exact projection + the exact degenerate midpoint', () => {
  it('projects the exact interpolated pixel (pins the arithmetic, not just the bounds)', () => {
    const scale = linearScale({ min: 0, max: 10 }, { min: 100, max: 200 });
    expect(scale(0)).toBe(100);
    expect(scale(10)).toBe(200);
    expect(scale(2.5)).toBe(125); // 100 + 0.25·100 — kills a mutated + / − / · in the projection
    expect(scale(7)).toBe(170);
  });

  it('an INVERTED range projects exactly (the y-axis flip): 0→bottom, max→top', () => {
    const yScale = linearScale({ min: 0, max: 100 }, { min: 480, max: 48 });
    expect(yScale(0)).toBe(480); // min metric → bottom
    expect(yScale(100)).toBe(48); // max metric → top
    expect(yScale(50)).toBe(264); // 480 + 0.5·(48−480)
  });

  it('the degenerate-domain midpoint is EXACTLY (min+max)/2', () => {
    expect(linearScale({ min: 4, max: 4 }, { min: 10, max: 30 })(4)).toBe(20);
  });
});

describe('radiusScale — exact sqrt-area values + the degenerate floor', () => {
  it('the ends are EXACTLY min/max radius and the midpoint is the sqrt of the MEAN AREA', () => {
    const r = radiusScale({ min: 0, max: 100 }, 3, 9);
    expect(r(0)).toBe(3);
    expect(r(100)).toBe(9);
    // area at 0.5 = 9 + 0.5·(81−9) = 45 → radius = sqrt(45)
    expect(r(50)).toBeCloseTo(Math.sqrt(45), 10);
    // a LINEAR-radius mutant would give 6 here; sqrt(45) ≈ 6.708 ≠ 6.
    expect(r(50)).not.toBeCloseTo(6, 2);
  });

  it('a degenerate domain (span ≤ 0) returns EXACTLY minRadius', () => {
    expect(radiusScale({ min: 5, max: 5 }, 3, 9)(5)).toBe(3);
    expect(radiusScale({ min: 9, max: 1 }, 3, 9)(4)).toBe(3); // max<min → span<0
  });
});

describe('hotspotColorAt — exact channel interpolation (l, c, h)', () => {
  const ramp: HotspotRamp = { low: { l: 0.9, c: 0.02, h: 30 }, high: { l: 0.4, c: 0.18, h: 30 } };

  it('interpolates EACH OKLCH channel linearly at the midpoint', () => {
    const mid = hotspotColorAt(0.5, ramp);
    expect(mid.l).toBeCloseTo(0.65, 10); // 0.9 + 0.5·(0.4−0.9)
    expect(mid.c).toBeCloseTo(0.1, 10); // 0.02 + 0.5·(0.18−0.02) — kills a dropped c interpolation
    expect(mid.h).toBeCloseTo(30, 10); // single hue
  });

  it('clamps an out-of-range score to the endpoints (kills the Math.min/max clamp mutants)', () => {
    expect(hotspotColorAt(-1, ramp).l).toBeCloseTo(0.9, 10);
    expect(hotspotColorAt(2, ramp).l).toBeCloseTo(0.4, 10);
  });

  it('hotspotColorCssAt emits the oklch() string of the interpolated colour', () => {
    expect(hotspotColorCssAt(0, ramp)).toBe(oklchToCss(ramp.low));
    expect(hotspotColorCssAt(1, ramp)).toBe(oklchToCss(ramp.high));
  });
});

describe('hotspotColorAt — hue takes the SHORTER arc (the interpolateHue branches)', () => {
  it('a +20° short arc across the 0°/360° seam (350°→10°) lands at 0° at the midpoint', () => {
    const ramp: HotspotRamp = { low: { l: 0.9, c: 0.1, h: 350 }, high: { l: 0.4, c: 0.1, h: 10 } };
    const mid = hotspotColorAt(0.5, ramp).h;
    // short arc midpoint is 0° (≡360°); the LONG arc (the >180 branch NOT taken) would give 180°.
    expect(Math.min(mid, 360 - mid)).toBeLessThan(1e-6);
  });

  it('a −20° short arc the other way (10°→350°) also stays on the seam (the delta -= 360 branch)', () => {
    const ramp: HotspotRamp = { low: { l: 0.9, c: 0.1, h: 10 }, high: { l: 0.4, c: 0.1, h: 350 } };
    const mid = hotspotColorAt(0.5, ramp).h;
    expect(Math.min(mid, 360 - mid)).toBeLessThan(1e-6);
  });

  it('a 0°→120° ramp interpolates the DIRECT 120° arc (no long-way detour) at the midpoint = 60°', () => {
    const ramp: HotspotRamp = { low: { l: 0.9, c: 0.1, h: 0 }, high: { l: 0.4, c: 0.1, h: 120 } };
    expect(hotspotColorAt(0.5, ramp).h).toBeCloseTo(60, 10);
  });
});

describe('ticks — exact values, step, and the floored count', () => {
  it('produces the exact evenly-spaced tick values (pins the step arithmetic)', () => {
    expect(ticks({ min: 0, max: 100 }, 4)).toEqual([0, 25, 50, 75, 100]);
    expect(ticks({ min: 10, max: 20 }, 2)).toEqual([10, 15, 20]);
  });

  it('floors count to ≥1 (a count of 0 / a fraction still yields a 2-tick axis)', () => {
    expect(ticks({ min: 0, max: 8 }, 0)).toEqual([0, 8]);
    expect(ticks({ min: 0, max: 8 }, 1.9)).toEqual([0, 8]);
  });

  it('a degenerate domain yields exactly the single value', () => {
    expect(ticks({ min: 5, max: 5 }, 4)).toEqual([5]);
  });
});

describe('entityValue / entityLabel — the numeric + string guards', () => {
  it('reads a finite number; an Infinity / NaN / missing field reads as 0 (kills the && guard mutants)', () => {
    expect(entityValue(mk({ cyclomatic: 42 }), 'cyclomatic')).toBe(42);
    expect(entityValue(mk({ cyclomatic: 0 }), 'cyclomatic')).toBe(0);
    const inf = { ...mk({}), churnRelative: Infinity } as unknown as Entity;
    expect(entityValue(inf, 'churnRelative')).toBe(0); // !Number.isFinite → 0
    expect(entityValue(mk({}), 'language')).toBe(0); // a string field is not numeric → 0
    expect(entityValue(mk({}), 'missing')).toBe(0);
  });

  it('reads a string label; a numeric / missing field reads as the empty string', () => {
    expect(entityLabel(mk({ path: 'a/b.ts' }), 'path')).toBe('a/b.ts');
    expect(entityLabel(mk({ lines: 9 }), 'lines')).toBe('');
    expect(entityLabel(mk({}), 'missing')).toBe('');
  });
});

describe('hotspotMapStyleVars — the EXACT complete declaration string (kills suffix/value mutants)', () => {
  it('emits every custom property with its exact suffix + value', () => {
    const theme = generateTheme(C21_SEED);
    const t = deriveHotspotMapTokens(theme);
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-hotspot-map-plot-bg: ${t.plotBackground};`,
      `--eden-hotspot-map-fg: ${t.foreground};`,
      `--eden-hotspot-map-axis: ${t.axis};`,
      `--eden-hotspot-map-point-stroke: ${t.pointStroke};`,
      `--eden-hotspot-map-tick-label-size: ${px(t.tickLabelSizePx)};`,
      `--eden-hotspot-map-label-size: ${px(t.labelSizePx)};`,
      `--eden-hotspot-map-label-line-height: ${px(t.labelLineHeightPx)};`,
      `--eden-hotspot-map-font-family: ${t.fontFamily};`,
      `--eden-hotspot-map-padding: ${px(t.paddingPx)};`,
      `--eden-hotspot-map-gap: ${px(t.gapPx)};`,
      `--eden-hotspot-map-radius: ${px(t.radiusPx)};`,
      `--eden-hotspot-map-hit-target: ${px(t.hitTargetPx)};`,
    ].join(' ');
    expect(hotspotMapStyleVars(t)).toBe(expected);
  });
});
