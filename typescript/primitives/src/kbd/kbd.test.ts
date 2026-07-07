/**
 * Kbd — unit + component render (the application-logic correctness dimension, ADR-0024). The key-cap
 * derivation asserted assertion-richly (the reading pair, the mono family, the exact style string) +
 * the real component (a native <kbd>, the derived vars). Assertion-rich so mutation (75) kills a
 * swapped role, a dropped mono family, a mutated var name.
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { createRawSnippet, type Snippet } from 'svelte';
import { generateTheme, C21_SEED } from '@eden/theme';
import Kbd from './kbd.svelte';
import { deriveKbdTokens, kbdStyleVars } from './tokens.js';
import { MONO_FONT_FAMILY } from '../chip/tokens.js';

const theme = generateTheme(C21_SEED);

describe('deriveKbdTokens — the pure derivation contract', () => {
  it('reads the onSurface/surface/outline reading pair (the cap label over the cap fill)', () => {
    const t = deriveKbdTokens(theme);
    expect(t.foregroundOklch).toEqual(theme.roles.onSurface.value);
    expect(t.backgroundOklch).toEqual(theme.roles.surface.value);
  });

  it('renders the key label in the MONO voice (a key label is data)', () => {
    expect(deriveKbdTokens(theme).fontFamily).toBe(MONO_FONT_FAMILY);
  });

  it('the size is the caption role; the radius the control ramp step; paddings on the ramp', () => {
    const t = deriveKbdTokens(theme);
    const ramp = theme.spacing.map((s) => s.px);
    expect(t.fontSizePx).toBe(theme.typography.find((r) => r.name === 'caption')!.fontSizePx);
    expect(t.radiusPx).toBe(theme.spacing.find((s) => s.name === 'space-1')!.px);
    expect(ramp).toContain(t.paddingInlinePx);
    expect(ramp).toContain(t.paddingBlockPx);
    expect(t.paddingInlinePx).toBe(4); // space-1
    expect(t.paddingBlockPx).toBe(2); // space-0.5
  });
});

describe('kbdStyleVars — the CSS custom-property emission', () => {
  it('emits the EXACT complete declaration string', () => {
    const tokens = deriveKbdTokens(theme);
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-kbd-fg: ${tokens.foreground};`,
      `--eden-kbd-bg: ${tokens.background};`,
      `--eden-kbd-border: ${tokens.border};`,
      `--eden-kbd-radius: ${px(tokens.radiusPx)};`,
      `--eden-kbd-padding-inline: ${px(tokens.paddingInlinePx)};`,
      `--eden-kbd-padding-block: ${px(tokens.paddingBlockPx)};`,
      `--eden-kbd-font-size: ${px(tokens.fontSizePx)};`,
      `--eden-kbd-line-height: ${px(tokens.lineHeightPx)};`,
      `--eden-kbd-font-family: ${tokens.fontFamily};`,
    ].join(' ');
    expect(kbdStyleVars(tokens)).toBe(expected);
  });

  it('carries no hex literal', () => {
    expect(kbdStyleVars(deriveKbdTokens(theme))).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});

describe('Kbd.svelte — the real component', () => {
  it('renders a native <kbd> carrying the key label and the derived vars', () => {
    const { container } = render(Kbd, { props: { theme, children: makeLabel('⌘K') } });
    const el = container.querySelector('[data-eden-kbd]')!;
    expect(el.tagName).toBe('KBD');
    expect(el.textContent).toContain('⌘K');
    expect(el.getAttribute('style')).toContain('--eden-kbd-font-family: monospace');
  });
});

function makeLabel(text: string): Snippet {
  return createRawSnippet(() => ({ render: () => `<span>${text}</span>` })) as unknown as Snippet;
}
