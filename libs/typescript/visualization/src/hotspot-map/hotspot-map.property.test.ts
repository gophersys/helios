/**
 * HotspotMap — the PROPERTY lane (fast-check invariants over the pure scatter math, ADR-0024 / rule
 * 21 §a). The scales/ramp/ticks are the load-bearing, mutation-proof surface: a flipped comparator,
 * an unclamped range, or a non-monotonic ramp must violate an invariant here. Each invariant is the
 * kind a single example test would miss — they hold for ALL inputs fast-check draws.
 */
import { describe, expect } from 'vitest';
import { test, fc } from '@fast-check/vitest';
import { generateTheme, C21_SEED } from '@eden/theme';
import {
  linearScale,
  radiusScale,
  hotspotRamp,
  hotspotColorAt,
  ticks,
  extentOf,
  entityValue,
  type Interval,
} from './scales.js';
import type { Entity } from '../report/index.js';

const finiteNumber = fc.double({ min: -1e6, max: 1e6, noNaN: true, noDefaultInfinity: true });
const orderedInterval = fc
  .tuple(finiteNumber, finiteNumber)
  .map(([a, b]): Interval => ({ min: Math.min(a, b), max: Math.max(a, b) }));

describe('linearScale — clamped, monotonic, ordering-preserving', () => {
  test.prop([orderedInterval, orderedInterval, finiteNumber])(
    'the output is ALWAYS within the range (the clamp is load-bearing)',
    (domain, range, value) => {
      const scale = linearScale(domain, range);
      const out = scale(value);
      const lo = Math.min(range.min, range.max);
      const hi = Math.max(range.min, range.max);
      expect(out).toBeGreaterThanOrEqual(lo - 1e-6);
      expect(out).toBeLessThanOrEqual(hi + 1e-6);
    },
  );

  test.prop([orderedInterval])(
    'the domain ends map to the range ends (a normal, increasing range)',
    (domain) => {
      fc.pre(domain.max > domain.min);
      const range: Interval = { min: 0, max: 100 };
      const scale = linearScale(domain, range);
      expect(scale(domain.min)).toBeCloseTo(0, 6);
      expect(scale(domain.max)).toBeCloseTo(100, 6);
    },
  );

  test.prop([orderedInterval, finiteNumber, finiteNumber])(
    'order is preserved: a larger input never maps below a smaller one (the slope sign is load-bearing)',
    (domain, a, b) => {
      fc.pre(domain.max > domain.min);
      const scale = linearScale(domain, { min: 0, max: 100 });
      const [lo, hi] = a <= b ? [a, b] : [b, a];
      expect(scale(lo)).toBeLessThanOrEqual(scale(hi) + 1e-6);
    },
  );

  test('a degenerate domain maps everything to the range midpoint', () => {
    const scale = linearScale({ min: 5, max: 5 }, { min: 0, max: 100 });
    expect(scale(5)).toBe(50);
    expect(scale(999)).toBe(50);
  });
});

describe('radiusScale — bounded, sqrt-area, monotonic', () => {
  test.prop([orderedInterval, finiteNumber])(
    'the radius is ALWAYS within [minRadius, maxRadius]',
    (domain, value) => {
      const scale = radiusScale(domain, 4, 28);
      const r = scale(value);
      expect(r).toBeGreaterThanOrEqual(4 - 1e-6);
      expect(r).toBeLessThanOrEqual(28 + 1e-6);
    },
  );

  test('AREA (∝ r²) is linear in the value — the midpoint dot has the MEAN area, not the mean radius', () => {
    const scale = radiusScale({ min: 0, max: 100 }, 4, 28);
    const mid = scale(50);
    const meanArea = (4 * 4 + 28 * 28) / 2;
    expect(mid * mid).toBeCloseTo(meanArea, 4);
    // a flipped scale (linear radius) would put it at the mean RADIUS (16) — distinctly different.
    expect(mid).not.toBeCloseTo(16, 1);
  });

  test('a degenerate size domain yields the minimum radius (no size signal)', () => {
    expect(radiusScale({ min: 7, max: 7 }, 4, 28)(7)).toBe(4);
  });
});

describe('hotspotRamp / hotspotColorAt — perceptually-ordered (monotonic lightness)', () => {
  for (const mode of ['light', 'dark'] as const) {
    const theme = generateTheme(C21_SEED, { mode });
    const ramp = hotspotRamp(theme);
    const surfaceL = theme.roles.surface.value.l;

    test.prop([
      fc.double({ min: 0, max: 1, noNaN: true }),
      fc.double({ min: 0, max: 1, noNaN: true }),
    ])(
      `${mode}: a HIGHER score is monotonically FURTHER from the surface in lightness (the ordering invariant)`,
      (a, b) => {
        const [lo, hi] = a <= b ? [a, b] : [b, a];
        const dLo = Math.abs(hotspotColorAt(lo, ramp).l - surfaceL);
        const dHi = Math.abs(hotspotColorAt(hi, ramp).l - surfaceL);
        // the lightness distance from the reading surface is non-decreasing in score — the hotter
        // entity always stands a larger lightness step off the surface (the pre-attentive ordering).
        expect(dHi).toBeGreaterThanOrEqual(dLo - 1e-9);
      },
    );

    test(`${mode}: score 0 is the calm (near-surface) end, score 1 is the gated error accent`, () => {
      // exact at 0 (t=0 → the low endpoint verbatim); within float epsilon at 1 (t=1 reintroduces a
      // rounding bit through `low + 1·(high-low)`), so close-to, not strict equality.
      expect(hotspotColorAt(0, ramp).l).toBe(ramp.low.l);
      expect(hotspotColorAt(1, ramp).l).toBeCloseTo(ramp.high.l, 10);
      // the hot end is exactly the theme's error role; the ends are genuinely distinct in lightness.
      expect(ramp.high.l).toBe(theme.roles.error.value.l);
      expect(Math.abs(ramp.low.l - ramp.high.l)).toBeGreaterThan(0.05);
      // the calm end sits NEARER the surface than the hot end (low value = low emphasis).
      expect(Math.abs(ramp.low.l - surfaceL)).toBeLessThan(Math.abs(ramp.high.l - surfaceL));
    });

    test.prop([finiteNumber])(
      `${mode}: an out-of-range score clamps to an end (never extrapolates)`,
      (s) => {
        const c = hotspotColorAt(s, ramp);
        const lMin = Math.min(ramp.low.l, ramp.high.l);
        const lMax = Math.max(ramp.low.l, ramp.high.l);
        expect(c.l).toBeGreaterThanOrEqual(lMin - 1e-9);
        expect(c.l).toBeLessThanOrEqual(lMax + 1e-9);
      },
    );
  }
});

describe('ticks — evenly spaced, inclusive', () => {
  test.prop([orderedInterval, fc.integer({ min: 1, max: 12 })])(
    'produces count+1 evenly-spaced ticks spanning the domain ends',
    (domain, count) => {
      fc.pre(domain.max > domain.min);
      const t = ticks(domain, count);
      expect(t).toHaveLength(count + 1);
      expect(t[0]).toBeCloseTo(domain.min, 6);
      expect(t[t.length - 1]).toBeCloseTo(domain.max, 6);
      // even spacing: consecutive deltas are equal.
      const step = (domain.max - domain.min) / count;
      for (let i = 1; i < t.length; i++) expect(t[i]! - t[i - 1]!).toBeCloseTo(step, 6);
    },
  );

  test('a degenerate domain yields a single tick', () => {
    expect(ticks({ min: 3, max: 3 }, 4)).toEqual([3]);
  });
});

describe('extentOf / entityValue — the payload-driven read', () => {
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

  test.prop([fc.array(finiteNumber, { minLength: 1, maxLength: 50 })])(
    'extentOf spans the min and max of the read channel',
    (values) => {
      const entities = values.map((v) => mk({ cyclomatic: v }));
      const ext = extentOf(entities, (e) => entityValue(e, 'cyclomatic'));
      expect(ext.min).toBeCloseTo(Math.min(...values), 6);
      expect(ext.max).toBeCloseTo(Math.max(...values), 6);
    },
  );

  test('an absent optional metric reads as 0, never NaN (the omitempty seam)', () => {
    expect(entityValue(mk({}), 'cyclomatic')).toBe(0);
    expect(entityValue(mk({ cyclomatic: 7 }), 'cyclomatic')).toBe(7);
    expect(entityValue(mk({}), 'unknownField')).toBe(0);
  });
});
