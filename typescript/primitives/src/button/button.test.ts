/**
 * Button — unit + component render (the application-logic correctness dimension, ADR-0024).
 *
 * Two layers: (1) the pure token-derivation contract (deriveButtonTokens / buttonStyleVars /
 * defaultButtonTheme) asserted directly, and (2) the REAL Svelte 5 component rendered through
 * @testing-library/svelte in jsdom — proving the bits-ui behavior layer mounts, the role is a
 * button, the derived `--eden-button-*` vars reach the element's inline style, and disabled is
 * forwarded. The browser-level a11y + keyboard proof is the separate Playwright lane (tests-a11y).
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { createRawSnippet, type Snippet } from 'svelte';
import { generateTheme, C21_SEED } from '@eden/theme';
import Button from './button.svelte';
import {
  deriveButtonTokens,
  buttonStyleVars,
  defaultButtonTheme,
  type ButtonVariant,
} from './tokens.js';

const VARIANTS: readonly ButtonVariant[] = ['primary', 'secondary', 'ghost', 'danger'];

describe('deriveButtonTokens — the pure derivation contract', () => {
  const theme = generateTheme(C21_SEED);

  it('derives a distinct fg/bg pair for the primary variant (on-primary over primary)', () => {
    const t = deriveButtonTokens('primary', theme);
    expect(t.foreground).toMatch(/^oklch\(/);
    expect(t.background).toMatch(/^oklch\(/);
    expect(t.foreground).not.toBe(t.background);
    expect(t.foregroundOklch).toEqual(theme.roles.onPrimary.value);
    expect(t.backgroundOklch).toEqual(theme.roles.primary.value);
  });

  it('the secondary variant is outlined: surface bg, on-surface fg, the outline role as border', () => {
    const t = deriveButtonTokens('secondary', theme);
    expect(t.backgroundOklch).toEqual(theme.roles.surface.value);
    expect(t.foregroundOklch).toEqual(theme.roles.onSurface.value);
    // the border is the outline role, distinct from the surface fill.
    expect(t.border).not.toBe(t.background);
  });

  it('the ghost variant is text-only over the surface, with the surface as its (invisible) border', () => {
    const t = deriveButtonTokens('ghost', theme);
    // Pin the EXACT role selection (not just border==background): on-surface text over the surface
    // fill, and the border IS the surface role — so a mis-routed case (e.g. a fall-through to danger,
    // which also has border==background but bg==error) is caught here, not silently equivalent.
    expect(t.foregroundOklch).toEqual(theme.roles.onSurface.value);
    expect(t.backgroundOklch).toEqual(theme.roles.surface.value);
    expect(t.border).toBe(t.background);
    // and it is distinct from the danger fill (the destructive role) — ghost is NOT a coloured fill.
    expect(t.backgroundOklch).not.toEqual(theme.roles.error.value);
  });

  it('the danger variant is filled-destructive: on-error fg over the error fill, error border', () => {
    const t = deriveButtonTokens('danger', theme);
    expect(t.foregroundOklch).toEqual(theme.roles.onError.value);
    expect(t.backgroundOklch).toEqual(theme.roles.error.value);
    // filled: the border equals the fill (the error role), not the surface or outline.
    expect(t.border).toBe(t.background);
    // and it is a distinct fill from the primary fill (a real destructive role, not aliased).
    expect(t.backgroundOklch).not.toEqual(theme.roles.primary.value);
  });

  it('defaultButtonTheme returns the C21 reference theme (the seed lives in @eden/theme, cited)', () => {
    const a = deriveButtonTokens('primary', defaultButtonTheme());
    const b = deriveButtonTokens('primary', generateTheme(C21_SEED));
    expect(a).toEqual(b);
  });

  it('defaultButtonTheme forwards options (dark mode flips the derived foreground)', () => {
    const light = deriveButtonTokens('primary', defaultButtonTheme({ mode: 'light' }));
    const dark = deriveButtonTokens('primary', defaultButtonTheme({ mode: 'dark' }));
    expect(dark.foreground).not.toBe(light.foreground);
  });
});

describe('deriveButtonTokens — non-default geometry/typography a host could inject', () => {
  // Exercise the derivation against a NON-default geometry/typography a host could legitimately
  // inject. We clone a real theme and override only the relevant slice — a typed override, never a
  // hand-built Theme — so the derivation (and the font-family fallback) is exercised honestly.
  const base = generateTheme(C21_SEED);

  it('inline padding is inset*2 for any inset (the 2:1 ratio holds off the default ramp too)', () => {
    // inset 7 → inset*2 = 14 (not itself a ramp step for this geometry, but the derivation is the
    // pure 2× — the ramp-membership is a property of the DEFAULT geometry, asserted in the design lane).
    const custom = {
      ...base,
      controlGeometry: { ...base.controlGeometry, insetPx: 7 },
    };
    const t = deriveButtonTokens('primary', custom);
    expect(t.paddingInlinePx).toBe(14);
  });

  it('font family falls back to the first typography role when there is no `body` role', () => {
    const noBody = {
      ...base,
      typography: base.typography.filter((r) => r.name !== 'body'),
    };
    const t = deriveButtonTokens('primary', noBody);
    expect(t.fontFamily).toBe(noBody.typography[0]!.fontFamily);
  });

  it('font family falls back to `inherit` when the typography list is empty (fully total)', () => {
    const noType = { ...base, typography: [] };
    const t = deriveButtonTokens('primary', noType);
    expect(t.fontFamily).toBe('inherit');
  });
});

describe('buttonStyleVars — the CSS custom-property emission', () => {
  const tokens = deriveButtonTokens('primary', generateTheme(C21_SEED));

  it('emits the EXACT complete declaration string — every var name mapped to its own token', () => {
    // Assert the WHOLE output, built from the tokens, so a mutated var-NAME, a mutated px UNIT, a
    // mutated VALUE-to-var mapping, or a dropped declaration all fail (kills the string-literal /
    // array-declaration mutants — every name and mapping is load-bearing, not just "contains").
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-button-fg: ${tokens.foreground};`,
      `--eden-button-bg: ${tokens.background};`,
      `--eden-button-border: ${tokens.border};`,
      `--eden-button-hit-target: ${px(tokens.hitTargetPx)};`,
      `--eden-button-height: ${px(tokens.heightPx)};`,
      `--eden-button-padding-inline: ${px(tokens.paddingInlinePx)};`,
      `--eden-button-padding-block: ${px(tokens.paddingBlockPx)};`,
      `--eden-button-gap: ${px(tokens.gapPx)};`,
      `--eden-button-font-size: ${px(tokens.fontSizePx)};`,
      `--eden-button-line-height: ${px(tokens.lineHeightPx)};`,
      `--eden-button-font-family: ${tokens.fontFamily};`,
    ].join(' ');
    expect(buttonStyleVars(tokens)).toBe(expected);
  });

  it('every dimension var carries the px unit (a dropped/mutated unit is caught)', () => {
    const css = buttonStyleVars(tokens);
    for (const name of [
      'hit-target',
      'height',
      'padding-inline',
      'padding-block',
      'gap',
      'font-size',
      'line-height',
    ]) {
      expect(css).toMatch(new RegExp(`--eden-button-${name}: \\d+px;`));
    }
  });

  it('the color vars carry oklch(...) values and there is no hex literal anywhere', () => {
    const css = buttonStyleVars(tokens);
    expect(css).toContain('--eden-button-fg: oklch(');
    expect(css).toContain('--eden-button-bg: oklch(');
    expect(css).toContain('--eden-button-border: oklch(');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});

describe('Button.svelte — the real component (bits-ui behavior + token binding)', () => {
  it('renders a real <button> with role "button" and the label', () => {
    const { getByRole } = render(Button, {
      props: { variant: 'primary', children: makeLabel('Click me') },
    });
    const el = getByRole('button', { name: 'Click me' });
    expect(el.tagName).toBe('BUTTON');
  });

  it('binds the derived --eden-button-* vars into the element inline style', () => {
    const theme = generateTheme(C21_SEED);
    const { getByRole } = render(Button, {
      props: { variant: 'primary', theme, children: makeLabel('Styled') },
    });
    const el = getByRole('button', { name: 'Styled' });
    const tokens = deriveButtonTokens('primary', theme);
    // the inline style carries the derived foreground/background tokens verbatim.
    expect(el.getAttribute('style')).toContain(`--eden-button-fg: ${tokens.foreground}`);
    expect(el.getAttribute('style')).toContain(`--eden-button-bg: ${tokens.background}`);
    expect(el.getAttribute('data-variant')).toBe('primary');
  });

  it('forwards disabled to the bits-ui primitive (the rendered button is disabled)', () => {
    const { getByRole } = render(Button, {
      props: { variant: 'primary', disabled: true, children: makeLabel('Nope') },
    });
    const el = getByRole('button', { name: 'Nope' }) as HTMLButtonElement;
    expect(el.disabled).toBe(true);
  });

  it('renders every variant with a button role (the behavior layer mounts for all)', () => {
    for (const variant of VARIANTS) {
      const { getByRole, unmount } = render(Button, {
        props: { variant, children: makeLabel(`v-${variant}`) },
      });
      expect(getByRole('button', { name: `v-${variant}` }).tagName).toBe('BUTTON');
      unmount();
    }
  });
});

/**
 * Build a Svelte snippet that renders a plain text label (the `children` prop). A snippet is a
 * function the runtime calls with an anchor; for a text-only label we use the documented
 * createRawSnippet escape hatch so the test needs no separate .svelte fixture file.
 */
function makeLabel(text: string): Snippet {
  return createRawSnippet(() => ({
    render: () => `<span>${text}</span>`,
  })) as unknown as Snippet;
}
