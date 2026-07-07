/**
 * Divider — unit + component render (the application-logic correctness dimension, ADR-0024). The
 * inset-rule derivation asserted assertion-richly (the outline role, the hairline, the inset ramp
 * step, the exact style string) + the real component (a native <hr> horizontal / a role=separator
 * vertical, the inset default). Assertion-rich so mutation (75) kills a swapped role, a dropped
 * inset, a mutated var name.
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { generateTheme, C21_SEED, oklchToCss } from '@eden/theme';
import Divider from './divider.svelte';
import { deriveDividerTokens, dividerStyleVars } from './tokens.js';

const theme = generateTheme(C21_SEED);

describe('deriveDividerTokens — the pure derivation contract', () => {
  it('the rule colour is the outline role', () => {
    const t = deriveDividerTokens(theme);
    expect(t.lineOklch).toEqual(theme.roles.outline.value);
    expect(t.line).toBe(oklchToCss(theme.roles.outline.value));
    expect(t.surfaceOklch).toEqual(theme.roles.surface.value);
  });

  it('the thickness is a single hairline pixel', () => {
    expect(deriveDividerTokens(theme).thicknessPx).toBe(1);
  });

  it('the inset is the space-4 ramp step (the anti-full-bleed default — doc 17 §1.6)', () => {
    const t = deriveDividerTokens(theme);
    expect(t.insetPx).toBe(theme.spacing.find((s) => s.name === 'space-4')!.px);
    expect(theme.spacing.map((s) => s.px)).toContain(t.insetPx);
    expect(t.insetPx).toBe(16);
  });
});

describe('dividerStyleVars — the CSS custom-property emission', () => {
  it('emits the EXACT complete declaration string', () => {
    const tokens = deriveDividerTokens(theme);
    const expected = [
      `--eden-divider-line: ${tokens.line};`,
      `--eden-divider-thickness: ${String(tokens.thicknessPx)}px;`,
      `--eden-divider-inset: ${String(tokens.insetPx)}px;`,
    ].join(' ');
    expect(dividerStyleVars(tokens)).toBe(expected);
  });

  it('carries no hex literal', () => {
    expect(dividerStyleVars(deriveDividerTokens(theme))).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});

describe('Divider.svelte — the real component', () => {
  it('renders a native <hr> for the horizontal orientation, inset by default', () => {
    const { container } = render(Divider, { props: { theme } });
    const el = container.querySelector('[data-eden-divider]')!;
    expect(el.tagName).toBe('HR');
    expect(el.getAttribute('data-orientation')).toBe('horizontal');
    expect(el.classList.contains('inset')).toBe(true);
  });

  it('renders a role=separator span with aria-orientation for the vertical orientation', () => {
    const { container } = render(Divider, { props: { theme, orientation: 'vertical' } });
    const el = container.querySelector('[data-eden-divider]')!;
    expect(el.getAttribute('role')).toBe('separator');
    expect(el.getAttribute('aria-orientation')).toBe('vertical');
  });

  it('inset={false} drops the inset class (the deliberate full-bleed escape hatch)', () => {
    const { container } = render(Divider, { props: { theme, inset: false } });
    expect(container.querySelector('[data-eden-divider]')!.classList.contains('inset')).toBe(false);
  });
});
