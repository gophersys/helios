/**
 * Centralized transition configurations for the app.
 * Change these values to update transitions globally across all pages.
 */

import { fade, fly, slide, scale, type FadeParams, type FlyParams, type SlideParams, type ScaleParams } from 'svelte/transition';
import { cubicOut, cubicIn, cubicInOut } from 'svelte/easing';

// ============================================================================
// TRANSITION DURATIONS (in milliseconds)
// ============================================================================

/** Duration for loader fade out */
export const LOADER_OUT_DURATION = 100;

/** Duration for loader fade in */
export const LOADER_IN_DURATION = 150;

/** Duration for content fade in after loading */
export const CONTENT_IN_DURATION = 200;

/** Delay before content starts fading in (allows loader to fade out first) */
export const CONTENT_IN_DELAY = 50;

/** Duration for error message fade in */
export const ERROR_IN_DURATION = 200;

// ============================================================================
// TRANSITION PRESETS
// These are the standard transitions used throughout the app.
// Use these presets to ensure consistency.
// ============================================================================

/** Transition for loader appearing */
export const loaderIn: FadeParams = {
  duration: LOADER_IN_DURATION,
  easing: cubicOut
};

/** Transition for loader disappearing */
export const loaderOut: FadeParams = {
  duration: LOADER_OUT_DURATION,
  easing: cubicIn
};

/** Transition for content appearing after loading */
export const contentIn: FadeParams = {
  duration: CONTENT_IN_DURATION,
  delay: CONTENT_IN_DELAY,
  easing: cubicOut
};

/** Transition for error messages appearing */
export const errorIn: FadeParams = {
  duration: ERROR_IN_DURATION,
  easing: cubicOut
};

/** Transition for modal/overlay backgrounds */
export const overlayIn: FadeParams = {
  duration: 150,
  easing: cubicOut
};

export const overlayOut: FadeParams = {
  duration: 100,
  easing: cubicIn
};

/** Transition for modal content (slides up) */
export const modalIn: FlyParams = {
  y: 20,
  duration: 200,
  easing: cubicOut
};

export const modalOut: FlyParams = {
  y: 10,
  duration: 150,
  easing: cubicIn
};

// ============================================================================
// TRANSITION FACTORIES
// Use these to create custom transitions while maintaining consistency
// ============================================================================

/** Create a fade transition with custom options */
export function createFade(overrides: Partial<FadeParams> = {}): FadeParams {
  return {
    duration: CONTENT_IN_DURATION,
    easing: cubicOut,
    ...overrides
  };
}

/** Create a fly transition with custom options */
export function createFly(overrides: Partial<FlyParams> = {}): FlyParams {
  return {
    y: 10,
    duration: CONTENT_IN_DURATION,
    easing: cubicOut,
    ...overrides
  };
}

/** Create a scale transition with custom options */
export function createScale(overrides: Partial<ScaleParams> = {}): ScaleParams {
  return {
    start: 0.95,
    duration: CONTENT_IN_DURATION,
    easing: cubicOut,
    ...overrides
  };
}
