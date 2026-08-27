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

/**
 * Capture the `ScaleSeedError` a fault path throws, so a test can assert its CONTENT — the
 * classification (`name`, `kind`) and the message that names the offending value.
 *
 * `expect(fn).toThrow(ScaleSeedError)` proves only that *something* of that class was thrown. It
 * cannot tell a real diagnostic from an empty one, and the mutation lane measured exactly that:
 * emptying every template literal in `assertSeed`/`stepAt`/`modularScale` and deleting
 * `this.name = 'ScaleSeedError'` left the suite green (ADR-0024 §2 — a survived mutant on covered
 * code is a real test gap, rule 21 §h). The message is the caller's only diagnosis of WHICH seed
 * value was rejected, so it is part of the contract and is asserted as such.
 */
function captureScaleSeedError(act: () => unknown): ScaleSeedError {
  try {
    act();
  } catch (error) {
    if (error instanceof ScaleSeedError) {
      return error;
    }
    return expect.fail(`expected a ScaleSeedError, got ${String(error)}`);
  }
  return expect.fail('expected a ScaleSeedError, but the call returned normally');
}

describe('stepAt', () => {
  it('returns the base at index 0', () => {
    expect(stepAt({ base: 16, ratio: 1.25 }, 0)).toBe(16);
  });

  it('applies the geometric ratio above and below the base', () => {
    expect(stepAt({ base: 16, ratio: 2 }, 3)).toBe(128);
    expect(stepAt({ base: 16, ratio: 2 }, -2)).toBe(4);
  });

  it('rejects a non-finite or non-positive base, naming the offending value', () => {
    const zeroBase = captureScaleSeedError(() => stepAt({ base: 0, ratio: 1.25 }, 0));
    expect(zeroBase.name).toBe('ScaleSeedError');
    expect(zeroBase.kind).toBe('scale-seed-invalid');
    expect(zeroBase.message).toBe('base must be a finite number > 0, got 0');

    const notANumberBase = captureScaleSeedError(() =>
      stepAt({ base: Number.NaN, ratio: 1.25 }, 0),
    );
    expect(notANumberBase.name).toBe('ScaleSeedError');
    expect(notANumberBase.message).toBe('base must be a finite number > 0, got NaN');
  });

  it('rejects a non-finite or non-positive ratio, naming the offending value', () => {
    const negativeRatio = captureScaleSeedError(() => stepAt({ base: 16, ratio: -1 }, 0));
    expect(negativeRatio.name).toBe('ScaleSeedError');
    expect(negativeRatio.kind).toBe('scale-seed-invalid');
    expect(negativeRatio.message).toBe('ratio must be a finite number > 0, got -1');

    // The boundary itself: a ratio of exactly 0 collapses every step to 0, so the guard is
    // `<= 0`, not `< 0`. Without this case the two spellings are indistinguishable.
    const zeroRatio = captureScaleSeedError(() => stepAt({ base: 16, ratio: 0 }, 0));
    expect(zeroRatio.message).toBe('ratio must be a finite number > 0, got 0');
  });

  it('rejects a non-integer index, naming the offending index', () => {
    const fractionalIndex = captureScaleSeedError(() => stepAt({ base: 16, ratio: 1.25 }, 1.5));
    expect(fractionalIndex.name).toBe('ScaleSeedError');
    expect(fractionalIndex.kind).toBe('scale-seed-invalid');
    expect(fractionalIndex.message).toBe('index must be an integer, got 1.5');
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

  it('rejects a non-integer bound on EITHER side, naming both bounds', () => {
    // Either bound alone is disqualifying, so both single-sided cases are asserted: a guard that
    // required BOTH to be fractional would pass a one-sided call and step by a fractional index.
    const fractionalFrom = captureScaleSeedError(() =>
      modularScale({ base: 16, ratio: 1.25 }, 0.5, 3),
    );
    expect(fractionalFrom.name).toBe('ScaleSeedError');
    expect(fractionalFrom.kind).toBe('scale-seed-invalid');
    expect(fractionalFrom.message).toBe('from/to must be integers, got 0.5..3');

    const fractionalTo = captureScaleSeedError(() =>
      modularScale({ base: 16, ratio: 1.25 }, 0, 2.5),
    );
    expect(fractionalTo.name).toBe('ScaleSeedError');
    expect(fractionalTo.message).toBe('from/to must be integers, got 0..2.5');
  });

  it('rejects from > to, naming both bounds', () => {
    const invertedRange = captureScaleSeedError(() =>
      modularScale({ base: 16, ratio: 1.25 }, 3, 1),
    );
    expect(invertedRange.name).toBe('ScaleSeedError');
    expect(invertedRange.kind).toBe('scale-seed-invalid');
    expect(invertedRange.message).toBe('from (3) must be <= to (1)');
  });
});

describe('renderPx', () => {
  it('rounds to the nearest integer pixel by default', () => {
    expect(renderPx(12.4)).toBe(12);
    expect(renderPx(12.6)).toBe(13);
  });

  it('divides by the same factor it multiplied by when asked for fraction digits', () => {
    // `fractionDigits > 0` is what makes the round-trip observable at all: at the default 0 the
    // factor is 1, and multiplying by 1 is indistinguishable from dividing by it.
    expect(renderPx(12.3456, 2)).toBe(12.35);
    expect(renderPx(0.014, 2)).toBe(0.01);
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
