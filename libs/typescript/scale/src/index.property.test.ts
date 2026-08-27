import { fc, test } from '@fast-check/vitest';
import { expect } from 'vitest';
import { modularScale, stepAt } from './index.js';

// Property arbitraries over the valid seed domain (finite-positive base/ratio, ratio > 1 so the
// scale is strictly monotone — a degenerate ratio of 1 is valid but uninteresting for ordering).
const base = fc.double({ min: 1, max: 1024, noNaN: true, noDefaultInfinity: true });
const ratio = fc.double({ min: 1.01, max: 4, noNaN: true, noDefaultInfinity: true });
const index = fc.integer({ min: -8, max: 8 });

test.prop({ base, ratio })(
  'f(0) === base for every seed (the base is the fixed point)',
  ({ base, ratio }) => {
    expect(stepAt({ base, ratio }, 0)).toBe(base);
  },
);

test.prop({ base, ratio, i: index })(
  'one step up multiplies by exactly ratio (the geometric law)',
  ({ base, ratio, i }) => {
    const here = stepAt({ base, ratio }, i);
    const up = stepAt({ base, ratio }, i + 1);
    // Relative tolerance — absolute float error scales with magnitude, so a fixed-decimal
    // `toBeCloseTo` is wrong at large rungs (base·ratio^8 ≈ millions). The geometric law is
    // exact to within IEEE-754 relative epsilon.
    expect(Math.abs(up - here * ratio)).toBeLessThanOrEqual(1e-9 * Math.abs(here * ratio));
  },
);

test.prop({ base, ratio, i: index })(
  'the scale is strictly monotone increasing for ratio > 1',
  ({ base, ratio, i }) => {
    expect(stepAt({ base, ratio }, i + 1)).toBeGreaterThan(stepAt({ base, ratio }, i));
  },
);

test.prop({ base, ratio, from: index, span: fc.integer({ min: 0, max: 12 }) })(
  'modularScale yields to-from+1 contiguous indexed steps that agree with stepAt',
  ({ base, ratio, from, span }) => {
    const to = from + span;
    const steps = modularScale({ base, ratio }, from, to);
    expect(steps).toHaveLength(span + 1);
    steps.forEach((step, k) => {
      expect(step.index).toBe(from + k);
      expect(step.value).toBe(stepAt({ base, ratio }, step.index));
    });
  },
);
