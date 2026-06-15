import { describe, expect, it } from 'vitest';
import {
  DEFAULT_BASE_PX,
  DEFAULT_TYPE_RATIO,
  INTERVAL_RATIO,
  modularScale,
  renderPx,
  ScaleSeedError,
  stepAt,
} from './index.js';

describe('stepAt', () => {
  it('returns the base at index 0', () => {
    expect(stepAt({ base: 16, ratio: 1.25 }, 0)).toBe(16);
  });

  it('applies the geometric ratio above and below the base', () => {
    expect(stepAt({ base: 16, ratio: 2 }, 3)).toBe(128);
    expect(stepAt({ base: 16, ratio: 2 }, -2)).toBe(4);
  });

  it('rejects a non-finite or non-positive seed', () => {
    expect(() => stepAt({ base: 0, ratio: 1.25 }, 0)).toThrow(ScaleSeedError);
    expect(() => stepAt({ base: 16, ratio: -1 }, 0)).toThrow(ScaleSeedError);
    expect(() => stepAt({ base: Number.NaN, ratio: 1.25 }, 0)).toThrow(ScaleSeedError);
  });

  it('rejects a non-integer index', () => {
    expect(() => stepAt({ base: 16, ratio: 1.25 }, 1.5)).toThrow(ScaleSeedError);
  });
});

describe('modularScale', () => {
  it('reproduces the research worked example (base 16, ratio 1.25, i ∈ [-2..5] → 10/13/16/20/25/31/39/49)', () => {
    const ladder = modularScale({ base: 16, ratio: 1.25 }, -2, 5).map((s) => renderPx(s.value));
    expect(ladder).toEqual([10, 13, 16, 20, 25, 31, 39, 49]);
  });

  it('keeps the unrounded float internally (rounds only at render)', () => {
    const [first] = modularScale({ base: 16, ratio: 1.25 }, -2, -2);
    expect(first?.value).toBeCloseTo(16 * 1.25 ** -2, 12);
    expect(first?.value).not.toBe(10); // the float, not the rounded render value
  });

  it('rejects from > to', () => {
    expect(() => modularScale({ base: 16, ratio: 1.25 }, 3, 1)).toThrow(ScaleSeedError);
  });
});

describe('the research seeds', () => {
  it('defaults the type ratio to the minor third (1.200), the research UI default', () => {
    expect(DEFAULT_TYPE_RATIO).toBe(1.2);
    expect(DEFAULT_TYPE_RATIO).toBe(INTERVAL_RATIO['minor-third']);
  });

  it('shares the 16px origin with the spacing scale', () => {
    expect(DEFAULT_BASE_PX).toBe(16);
  });
});
