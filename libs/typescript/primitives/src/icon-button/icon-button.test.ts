/**
 * IconButton — unit + component render (the application-logic correctness dimension, ADR-0024).
 *
 * Two layers: (1) the pure token-derivation contract (deriveIconButtonTokens / iconButtonStyleVars)
 * asserted directly — including that it CITES the Button's role selection (one concept, one home),
 * and (2) the REAL Svelte 5 component rendered through @testing-library/svelte in jsdom — proving
 * the bits-ui behavior layer mounts, the role is a button, the REQUIRED accessible name is bound via
 * aria-label, the derived `--eden-icon-button-*` vars reach the element, and disabled is forwarded.
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { createRawSnippet, type Snippet } from 'svelte';
import { generateTheme, C21_SEED } from '@eden/theme';
import IconButton from './icon-button.svelte';
import { deriveIconButtonTokens, iconButtonStyleVars } from './tokens.js';
import { deriveButtonTokens, type ButtonVariant } from '../button/tokens.js';

const VARIANTS: readonly ButtonVariant[] = ['primary', 'secondary', 'ghost', 'danger'];

describe('deriveIconButtonTokens — the pure derivation contract', () => {
  const theme = generateTheme(C21_SEED);

  it('CITES the Button role selection — the fg/bg/border match deriveButtonTokens exactly', () => {
    for (const variant of VARIANTS) {
      const icon = deriveIconButtonTokens(variant, theme);
      const button = deriveButtonTokens(variant, theme);
      // one concept, one home: the IconButton does NOT re-derive the variant→role mapping.
      expect(icon.foregroundOklch).toEqual(button.foregroundOklch);
      expect(icon.backgroundOklch).toEqual(button.backgroundOklch);
      expect(icon.border).toBe(button.border);
    }
  });

  it('derives the square geometry from controlGeometry (edge = height, glyph = icon size)', () => {
    const t = deriveIconButtonTokens('primary', theme);
    expect(t.sizePx).toBe(theme.controlGeometry.componentHeightPx);
    expect(t.iconSizePx).toBe(theme.controlGeometry.iconSizePx);
    expect(t.hitTargetPx).toBe(theme.controlGeometry.hitTargetPx);
  });

  it('the danger variant selects the error role pair (filled-destructive icon button)', () => {
    const t = deriveIconButtonTokens('danger', theme);
    expect(t.foregroundOklch).toEqual(theme.roles.onError.value);
    expect(t.backgroundOklch).toEqual(theme.roles.error.value);
  });
});

describe('iconButtonStyleVars — the CSS custom-property emission', () => {
  const tokens = deriveIconButtonTokens('primary', generateTheme(C21_SEED));

  it('emits the EXACT complete declaration string — every var name mapped to its own token', () => {
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-icon-button-fg: ${tokens.foreground};`,
      `--eden-icon-button-bg: ${tokens.background};`,
      `--eden-icon-button-border: ${tokens.border};`,
      `--eden-icon-button-hit-target: ${px(tokens.hitTargetPx)};`,
      `--eden-icon-button-size: ${px(tokens.sizePx)};`,
      `--eden-icon-button-icon-size: ${px(tokens.iconSizePx)};`,
    ].join(' ');
    expect(iconButtonStyleVars(tokens)).toBe(expected);
  });

  it('every dimension var carries the px unit (a dropped/mutated unit is caught)', () => {
    const css = iconButtonStyleVars(tokens);
    for (const name of ['hit-target', 'size', 'icon-size']) {
      expect(css).toMatch(new RegExp(`--eden-icon-button-${name}: \\d+px;`));
    }
  });

  it('the color vars carry oklch(...) values and there is no hex literal anywhere', () => {
    const css = iconButtonStyleVars(tokens);
    expect(css).toContain('--eden-icon-button-fg: oklch(');
    expect(css).toContain('--eden-icon-button-bg: oklch(');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});

describe('IconButton.svelte — the real component (bits-ui behavior + token binding + a11y name)', () => {
  it('renders a real <button> whose accessible name is the REQUIRED label (aria-label)', () => {
    const { getByRole } = render(IconButton, {
      props: { variant: 'primary', label: 'Close dialog', children: makeGlyph() },
    });
    const el = getByRole('button', { name: 'Close dialog' });
    expect(el.tagName).toBe('BUTTON');
    expect(el.getAttribute('aria-label')).toBe('Close dialog');
  });

  it('binds the derived --eden-icon-button-* vars into the element inline style', () => {
    const theme = generateTheme(C21_SEED);
    const { getByRole } = render(IconButton, {
      props: { variant: 'primary', theme, label: 'Settings', children: makeGlyph() },
    });
    const el = getByRole('button', { name: 'Settings' });
    const tokens = deriveIconButtonTokens('primary', theme);
    expect(el.getAttribute('style')).toContain(`--eden-icon-button-fg: ${tokens.foreground}`);
    expect(el.getAttribute('style')).toContain(
      `--eden-icon-button-size: ${String(tokens.sizePx)}px`,
    );
    expect(el.getAttribute('data-variant')).toBe('primary');
  });

  it('forwards disabled to the bits-ui primitive (the rendered button is disabled)', () => {
    const { getByRole } = render(IconButton, {
      props: { variant: 'danger', disabled: true, label: 'Delete', children: makeGlyph() },
    });
    const el = getByRole('button', { name: 'Delete' }) as HTMLButtonElement;
    expect(el.disabled).toBe(true);
  });

  it('renders every variant with a button role and an accessible name (all mount)', () => {
    for (const variant of VARIANTS) {
      const { getByRole, unmount } = render(IconButton, {
        props: { variant, label: `v-${variant}`, children: makeGlyph() },
      });
      expect(getByRole('button', { name: `v-${variant}` }).tagName).toBe('BUTTON');
      unmount();
    }
  });
});

/** Build a Svelte snippet rendering a minimal inline SVG glyph (the `children` prop). */
function makeGlyph(): Snippet {
  return createRawSnippet(() => ({
    render: () => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12" /></svg>`,
  })) as unknown as Snippet;
}
