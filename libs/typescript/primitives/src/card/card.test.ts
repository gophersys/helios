/**
 * Card — unit + component render (the application-logic correctness dimension, ADR-0024). The surface
 * molecule's derivation asserted assertion-richly (the reading pair, the EXACT surface radius + raised
 * shadow per doc 17 §4, the flat variant's no-shadow, the exact style string) + the real component
 * (the header/body/footer slots render only when present, the derived vars). Assertion-rich so
 * mutation (75) kills a swapped radius, a dropped shadow, a wrong variant branch.
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { createRawSnippet, type Snippet } from 'svelte';
import { generateTheme, C21_SEED } from '@eden/theme';
import Card from './card.svelte';
import { deriveCardTokens, cardStyleVars, type CardVariant } from './tokens.js';
import { radiusPx, elevationShadow } from '../surface-tokens/tokens.js';

const theme = generateTheme(C21_SEED);
const VARIANTS: readonly CardVariant[] = ['raised', 'flat'];

describe('deriveCardTokens — the pure derivation contract', () => {
  it('reads the onSurface/surface/outline reading pair (a legible card body)', () => {
    const t = deriveCardTokens('raised', theme);
    expect(t.foregroundOklch).toEqual(theme.roles.onSurface.value);
    expect(t.backgroundOklch).toEqual(theme.roles.surface.value);
  });

  it('the radius is EXACTLY the surface radius (doc 17 §4 Card ruling)', () => {
    const t = deriveCardTokens('raised', theme);
    expect(t.radiusPx).toBe(radiusPx(theme, 'surface'));
    expect(t.radiusPx).toBe(8); // space-2
  });

  it('the raised variant paints EXACTLY the raised shadow; the flat variant paints none', () => {
    expect(deriveCardTokens('raised', theme).shadow).toBe(elevationShadow(theme, 'raised'));
    expect(deriveCardTokens('flat', theme).shadow).toBe('none');
    // the two variants differ ONLY in the shadow (the elevation is the variant selector)
    const raised = deriveCardTokens('raised', theme);
    const flat = deriveCardTokens('flat', theme);
    expect(raised.radiusPx).toBe(flat.radiusPx);
    expect(raised.foreground).toBe(flat.foreground);
    expect(raised.shadow).not.toBe(flat.shadow);
  });

  it('the padding + slot gap are ramp steps; the type is the body role', () => {
    const t = deriveCardTokens('raised', theme);
    const ramp = theme.spacing.map((s) => s.px);
    expect(ramp).toContain(t.paddingPx);
    expect(ramp).toContain(t.gapPx);
    expect(t.paddingPx).toBe(16); // space-4
    expect(t.gapPx).toBe(12); // space-3
    expect(t.fontSizePx).toBe(theme.typography.find((r) => r.name === 'body')!.fontSizePx);
  });
});

describe('cardStyleVars — the CSS custom-property emission', () => {
  it('emits the EXACT complete declaration string (the shadow passes through verbatim)', () => {
    const tokens = deriveCardTokens('raised', theme);
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-card-fg: ${tokens.foreground};`,
      `--eden-card-bg: ${tokens.background};`,
      `--eden-card-border: ${tokens.border};`,
      `--eden-card-radius: ${px(tokens.radiusPx)};`,
      `--eden-card-shadow: ${tokens.shadow};`,
      `--eden-card-padding: ${px(tokens.paddingPx)};`,
      `--eden-card-gap: ${px(tokens.gapPx)};`,
      `--eden-card-font-size: ${px(tokens.fontSizePx)};`,
      `--eden-card-line-height: ${px(tokens.lineHeightPx)};`,
      `--eden-card-font-family: ${tokens.fontFamily};`,
    ].join(' ');
    expect(cardStyleVars(tokens)).toBe(expected);
  });

  it('carries no hex literal for either variant (the shadow umbra is oklch, not rgba/hex)', () => {
    for (const v of VARIANTS) {
      expect(cardStyleVars(deriveCardTokens(v, theme))).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    }
  });
});

describe('Card.svelte — the real component', () => {
  it('renders only the slots that are provided', () => {
    const { container } = render(Card, {
      props: { theme, header: makeContent('H'), body: makeContent('B') },
    });
    expect(container.querySelector('.eden-card-header')!.textContent).toContain('H');
    expect(container.querySelector('.eden-card-body')!.textContent).toContain('B');
    expect(container.querySelector('.eden-card-footer')).toBeNull();
  });

  it('binds the derived surface radius + raised shadow vars, and the data-variant', () => {
    const { container } = render(Card, {
      props: { theme, variant: 'raised', body: makeContent('x') },
    });
    const el = container.querySelector('[data-eden-card]')!;
    const tokens = deriveCardTokens('raised', theme);
    expect(el.getAttribute('style')).toContain(`--eden-card-radius: ${String(tokens.radiusPx)}px`);
    expect(el.getAttribute('style')).toContain(`--eden-card-shadow: ${tokens.shadow}`);
    expect(el.getAttribute('data-variant')).toBe('raised');
  });
});

function makeContent(text: string): Snippet {
  return createRawSnippet(() => ({ render: () => `<span>${text}</span>` })) as unknown as Snippet;
}
