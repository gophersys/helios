/**
 * Spinner — unit + component render (the application-logic correctness dimension, ADR-0024). The
 * loading atom's derivation asserted assertion-richly (the arc role per variant, the MOTION tokens —
 * the duration is a ladder rung, the easing a theme curve — the icon diameter, the exact style
 * string) + the real component (role=status, the visually-hidden label, the derived vars). Assertion-
 * rich so mutation (75) kills a swapped role, a hand-typed duration, a mutated var name.
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { generateTheme, C21_SEED, oklchToCss } from '@eden/theme';
import Spinner from './spinner.svelte';
import { deriveSpinnerTokens, spinnerStyleVars, type SpinnerVariant } from './tokens.js';

const theme = generateTheme(C21_SEED);
const VARIANTS: readonly SpinnerVariant[] = ['accent', 'healthy', 'updating', 'degraded', 'down'];

describe('deriveSpinnerTokens — the pure derivation contract', () => {
  it('accent draws the primary role as the arc; the track is the outline role', () => {
    const t = deriveSpinnerTokens('accent', theme);
    expect(t.arcOklch).toEqual(theme.roles.primary.value);
    expect(t.track).toBe(oklchToCss(theme.roles.outline.value));
  });

  it('a status variant draws its status role as the arc (updating → info, down → error)', () => {
    expect(deriveSpinnerTokens('updating', theme).arcOklch).toEqual(theme.roles.info.value);
    expect(deriveSpinnerTokens('down', theme).arcOklch).toEqual(theme.roles.error.value);
    expect(deriveSpinnerTokens('healthy', theme).arcOklch).toEqual(theme.roles.success.value);
  });

  it('the diameter is the theme icon dimension; the stroke is a ramp step (on-grid)', () => {
    const t = deriveSpinnerTokens('accent', theme);
    expect(t.sizePx).toBe(theme.controlGeometry.iconSizePx);
    expect(theme.spacing.map((s) => s.px)).toContain(t.strokePx);
    expect(t.strokePx).toBe(2); // space-0.5
  });

  it('the rotation period is a motion.durations ladder rung — NOT a hand-typed duration', () => {
    const t = deriveSpinnerTokens('accent', theme);
    expect(t.durationMs).toBe(theme.motion.durations['extra-long.3']);
    // the value is a real ladder rung, not an eyeballed 1000
    expect(Object.values(theme.motion.durations)).toContain(t.durationMs);
    expect(t.durationMs).toBe(900);
  });

  it('the easing is the linear theme curve as a cubic-bezier (constant angular velocity)', () => {
    const t = deriveSpinnerTokens('accent', theme);
    const linear = theme.motion.easing['linear']!;
    expect(t.easing).toBe(`cubic-bezier(${[...linear].join(', ')})`);
  });

  it('totality: easing falls back to linear when the named curve is absent from the theme', () => {
    // Drive the first easingCss fallback: a theme whose easing map lacks `linear` entirely → the
    // `?? [0,0,1,1]` guard yields the identity linear curve (the function stays total, no throw).
    const noEasing = { ...theme, motion: { ...theme.motion, easing: {} } };
    expect(deriveSpinnerTokens('accent', noEasing).easing).toBe('cubic-bezier(0, 0, 1, 1)');
  });
});

describe('spinnerStyleVars — the CSS custom-property emission', () => {
  it('emits the EXACT complete declaration string (duration carries ms, easing a bezier)', () => {
    const tokens = deriveSpinnerTokens('accent', theme);
    const expected = [
      `--eden-spinner-arc: ${tokens.arc};`,
      `--eden-spinner-track: ${tokens.track};`,
      `--eden-spinner-size: ${String(tokens.sizePx)}px;`,
      `--eden-spinner-stroke: ${String(tokens.strokePx)}px;`,
      `--eden-spinner-duration: ${String(tokens.durationMs)}ms;`,
      `--eden-spinner-easing: ${tokens.easing};`,
    ].join(' ');
    expect(spinnerStyleVars(tokens)).toBe(expected);
  });

  it('carries no hex literal for any variant', () => {
    for (const v of VARIANTS) {
      expect(spinnerStyleVars(deriveSpinnerTokens(v, theme))).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    }
  });
});

describe('Spinner.svelte — the real component', () => {
  it('renders role=status with an accessible label and binds the derived vars', () => {
    const { container, getByText } = render(Spinner, {
      props: { variant: 'accent', theme, label: 'Loading projects' },
    });
    const el = container.querySelector('[data-eden-spinner]')!;
    expect(el.getAttribute('role')).toBe('status');
    expect(getByText('Loading projects')).toBeTruthy();
    const tokens = deriveSpinnerTokens('accent', theme);
    expect(el.getAttribute('style')).toContain(
      `--eden-spinner-duration: ${String(tokens.durationMs)}ms`,
    );
    expect(el.getAttribute('style')).toContain('--eden-spinner-easing: cubic-bezier(');
  });
});
