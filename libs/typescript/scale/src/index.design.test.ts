/**
 * Design-correctness lane (ADR-0024 §3, the ninth dimension): aesthetics made COMPUTABLE.
 *
 * MATH IS SOURCE OF TRUTH. These assertions prove the scale values come from the research
 * formula `f(i) = base · ratio^i` (docs/research/05-design-foundations.md B1) and the cited
 * interval-ratio table — never from eyeballed or hand-set literals. A drift between the generated
 * ladder and the research's worked example FAILS the design gate, exactly the way a contrast-gate
 * failure will fail @eden/theme. The `design-correctness` ctl verb runs this lane.
 */
import { describe, expect, it } from 'vitest';
import { INTERVAL_RATIO, modularScale, renderPx, stepAt } from './index.js';

describe('design-correctness: the type scale is derived, not eyeballed', () => {
  it('every step equals base·ratio^i from the formula (no hand-set literal)', () => {
    const seed = { base: 16, ratio: INTERVAL_RATIO['major-third'] } as const;
    for (let i = -2; i <= 5; i++) {
      // The library value MUST equal the independently-computed formula value.
      const expected = seed.base * seed.ratio ** i;
      expect(stepAt(seed, i)).toBe(expected);
    }
  });

  it('matches the research B1 worked example exactly (base 16, ratio 1.25 → 10/13/16/20/25/31/39/49 px)', () => {
    // The canonical worked example in docs/research/05-design-foundations.md §B1. If the engine
    // ever drifts from the published ladder, this gate goes red — "looks right" is now checked.
    const RESEARCH_B1_LADDER = [10, 13, 16, 20, 25, 31, 39, 49];
    const generated = modularScale({ base: 16, ratio: 1.25 }, -2, 5).map((s) => renderPx(s.value));
    expect(generated).toEqual(RESEARCH_B1_LADDER);
  });

  it('the interval-ratio table carries the cited research values (the table is the structure, the seed is taste)', () => {
    // Spot-check the load-bearing rungs against Table B1-A (cited to type-scale.com / spec.fm).
    expect(INTERVAL_RATIO['minor-third']).toBe(1.2); // research default for general UI/web
    expect(INTERVAL_RATIO['major-third']).toBe(1.25);
    expect(INTERVAL_RATIO['perfect-fourth']).toBe(1.333);
  });
});
