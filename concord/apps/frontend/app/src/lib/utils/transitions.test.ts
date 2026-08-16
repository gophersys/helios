/**
 * Tests for transition utilities.
 * Ensures consistent animations across the app.
 */
import { describe, it, expect } from 'vitest';
import {
  LOADER_OUT_DURATION,
  LOADER_IN_DURATION,
  CONTENT_IN_DURATION,
  CONTENT_IN_DELAY,
  ERROR_IN_DURATION,
  loaderIn,
  loaderOut,
  contentIn,
  errorIn,
  overlayIn,
  overlayOut,
  modalIn,
  modalOut,
  createFade,
  createFly,
  createScale
} from './transitions';

describe('Duration Constants', () => {
  it('has reasonable loader durations', () => {
    expect(LOADER_OUT_DURATION).toBeGreaterThan(0);
    expect(LOADER_OUT_DURATION).toBeLessThan(500);
    expect(LOADER_IN_DURATION).toBeGreaterThan(0);
    expect(LOADER_IN_DURATION).toBeLessThan(500);
  });

  it('has reasonable content durations', () => {
    expect(CONTENT_IN_DURATION).toBeGreaterThan(0);
    expect(CONTENT_IN_DURATION).toBeLessThan(500);
    expect(CONTENT_IN_DELAY).toBeLessThan(CONTENT_IN_DURATION);
  });

  it('has reasonable error duration', () => {
    expect(ERROR_IN_DURATION).toBeGreaterThan(0);
    expect(ERROR_IN_DURATION).toBeLessThan(500);
  });
});

describe('Transition Presets', () => {
  describe('loaderIn', () => {
    it('has duration property', () => {
      expect(loaderIn.duration).toBe(LOADER_IN_DURATION);
    });

    it('has easing property', () => {
      expect(loaderIn.easing).toBeDefined();
    });
  });

  describe('loaderOut', () => {
    it('has duration property', () => {
      expect(loaderOut.duration).toBe(LOADER_OUT_DURATION);
    });

    it('has easing property', () => {
      expect(loaderOut.easing).toBeDefined();
    });
  });

  describe('contentIn', () => {
    it('has duration property', () => {
      expect(contentIn.duration).toBe(CONTENT_IN_DURATION);
    });

    it('has delay property', () => {
      expect(contentIn.delay).toBe(CONTENT_IN_DELAY);
    });

    it('has easing property', () => {
      expect(contentIn.easing).toBeDefined();
    });
  });

  describe('errorIn', () => {
    it('has duration property', () => {
      expect(errorIn.duration).toBe(ERROR_IN_DURATION);
    });
  });

  describe('overlayIn/overlayOut', () => {
    it('has matching structure', () => {
      expect(overlayIn.duration).toBeDefined();
      expect(overlayOut.duration).toBeDefined();
      expect(overlayIn.duration).toBeGreaterThanOrEqual(overlayOut.duration!);
    });
  });

  describe('modalIn/modalOut', () => {
    it('has fly parameters', () => {
      expect(modalIn.y).toBeDefined();
      expect(modalIn.duration).toBeDefined();
      expect(modalOut.y).toBeDefined();
      expect(modalOut.duration).toBeDefined();
    });

    it('enters from below (positive y)', () => {
      expect(modalIn.y).toBeGreaterThan(0);
    });
  });
});

describe('Factory Functions', () => {
  describe('createFade', () => {
    it('returns default fade params', () => {
      const fade = createFade();

      expect(fade.duration).toBe(CONTENT_IN_DURATION);
      expect(fade.easing).toBeDefined();
    });

    it('allows overriding duration', () => {
      const fade = createFade({ duration: 500 });

      expect(fade.duration).toBe(500);
    });

    it('allows overriding delay', () => {
      const fade = createFade({ delay: 100 });

      expect(fade.delay).toBe(100);
    });

    it('preserves default easing when not overridden', () => {
      const fade = createFade({ duration: 300 });

      expect(fade.easing).toBeDefined();
    });
  });

  describe('createFly', () => {
    it('returns default fly params', () => {
      const fly = createFly();

      expect(fly.duration).toBe(CONTENT_IN_DURATION);
      expect(fly.y).toBe(10);
      expect(fly.easing).toBeDefined();
    });

    it('allows overriding y offset', () => {
      const fly = createFly({ y: 50 });

      expect(fly.y).toBe(50);
    });

    it('allows overriding x offset', () => {
      const fly = createFly({ x: 100 });

      expect(fly.x).toBe(100);
    });

    it('allows overriding duration', () => {
      const fly = createFly({ duration: 400 });

      expect(fly.duration).toBe(400);
    });
  });

  describe('createScale', () => {
    it('returns default scale params', () => {
      const scale = createScale();

      expect(scale.duration).toBe(CONTENT_IN_DURATION);
      expect(scale.start).toBe(0.95);
      expect(scale.easing).toBeDefined();
    });

    it('allows overriding start scale', () => {
      const scale = createScale({ start: 0.5 });

      expect(scale.start).toBe(0.5);
    });

    it('allows overriding duration', () => {
      const scale = createScale({ duration: 250 });

      expect(scale.duration).toBe(250);
    });
  });
});

describe('Transition Consistency', () => {
  it('loader out is faster than content in (smooth handoff)', () => {
    expect(LOADER_OUT_DURATION).toBeLessThanOrEqual(CONTENT_IN_DURATION);
  });

  it('content delay allows loader to fade out', () => {
    expect(CONTENT_IN_DELAY).toBeLessThanOrEqual(LOADER_OUT_DURATION);
  });

  it('modal animations are symmetrical', () => {
    // Modal in duration should be >= modal out for smooth UX
    expect(modalIn.duration).toBeGreaterThanOrEqual(modalOut.duration!);
  });
});
