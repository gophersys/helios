/**
 * Chip — unit + component render (the application-logic correctness dimension, ADR-0024).
 * The mono data chip: the pure derivation contract asserted assertion-richly (the proseSurface
 * reading pair, the mono family, the exact style string) + the real component (removable variant's
 * accessible remove control, the derived vars). Assertion-rich so mutation (75) kills a swapped role,
 * a dropped mono family, a mutated var name.
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { createRawSnippet, type Snippet } from 'svelte';
import { generateTheme, C21_SEED } from '@eden/theme';
import Chip from './chip.svelte';
import { deriveChipTokens, chipStyleVars, MONO_FONT_FAMILY } from './tokens.js';

const theme = generateTheme(C21_SEED);

describe('deriveChipTokens — the pure derivation contract', () => {
  it('reads the onSurface/surface/outline reading pair (the highest-contrast prose surface)', () => {
    const t = deriveChipTokens(theme);
    expect(t.foregroundOklch).toEqual(theme.roles.onSurface.value);
    expect(t.backgroundOklch).toEqual(theme.roles.surface.value);
    expect(t.foreground).not.toBe(t.background);
  });

  it('renders its data in the MONO voice — the CSS generic monospace family', () => {
    expect(deriveChipTokens(theme).fontFamily).toBe(MONO_FONT_FAMILY);
    expect(MONO_FONT_FAMILY).toBe('monospace');
  });

  it('the size is the caption typography role; the radius the control ramp step', () => {
    const t = deriveChipTokens(theme);
    const cap = theme.typography.find((r) => r.name === 'caption')!;
    expect(t.fontSizePx).toBe(cap.fontSizePx);
    expect(t.radiusPx).toBe(theme.spacing.find((s) => s.name === 'space-1')!.px);
  });

  it('the remove control gets the decoupled 44px+ hit target', () => {
    expect(deriveChipTokens(theme).hitTargetPx).toBe(theme.controlGeometry.hitTargetPx);
    expect(deriveChipTokens(theme).hitTargetPx).toBeGreaterThanOrEqual(44);
  });

  it('the paddings + gap are exact ramp steps (scale provenance)', () => {
    const t = deriveChipTokens(theme);
    const ramp = theme.spacing.map((s) => s.px);
    expect(ramp).toContain(t.paddingInlinePx);
    expect(ramp).toContain(t.paddingBlockPx);
    expect(ramp).toContain(t.gapPx);
    expect(t.paddingInlinePx).toBe(8);
    expect(t.paddingBlockPx).toBe(2);
    expect(t.gapPx).toBe(4);
  });
});

describe('chipStyleVars — the CSS custom-property emission', () => {
  it('emits the EXACT complete declaration string', () => {
    const tokens = deriveChipTokens(theme);
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-chip-fg: ${tokens.foreground};`,
      `--eden-chip-bg: ${tokens.background};`,
      `--eden-chip-border: ${tokens.border};`,
      `--eden-chip-radius: ${px(tokens.radiusPx)};`,
      `--eden-chip-padding-inline: ${px(tokens.paddingInlinePx)};`,
      `--eden-chip-padding-block: ${px(tokens.paddingBlockPx)};`,
      `--eden-chip-gap: ${px(tokens.gapPx)};`,
      `--eden-chip-hit-target: ${px(tokens.hitTargetPx)};`,
      `--eden-chip-font-size: ${px(tokens.fontSizePx)};`,
      `--eden-chip-line-height: ${px(tokens.lineHeightPx)};`,
      `--eden-chip-font-family: ${tokens.fontFamily};`,
    ].join(' ');
    expect(chipStyleVars(tokens)).toBe(expected);
  });

  it('carries no hex literal', () => {
    expect(chipStyleVars(deriveChipTokens(theme))).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});

describe('Chip.svelte — the real component', () => {
  it('renders the mono datum and binds the derived vars', () => {
    const { container } = render(Chip, { props: { theme, children: makeLabel('ns/eden-42') } });
    const el = container.querySelector('[data-eden-chip]')!;
    expect(el.textContent).toContain('ns/eden-42');
    expect(el.getAttribute('style')).toContain('--eden-chip-font-family: monospace');
  });

  it('the default variant renders NO remove control', () => {
    const { container } = render(Chip, { props: { theme, children: makeLabel('42') } });
    expect(container.querySelector('.eden-chip-remove')).toBeNull();
  });

  it('the removable variant renders a real button with the accessible remove label + fires onRemove', () => {
    let removed = 0;
    const { getByRole } = render(Chip, {
      props: {
        theme,
        variant: 'removable',
        removeLabel: 'Remove namespace filter',
        onRemove: () => (removed += 1),
        children: makeLabel('namespace'),
      },
    });
    const btn = getByRole('button', { name: 'Remove namespace filter' }) as HTMLButtonElement;
    expect(btn.tagName).toBe('BUTTON');
    btn.click();
    expect(removed).toBe(1);
  });
});

function makeLabel(text: string): Snippet {
  return createRawSnippet(() => ({ render: () => `<span>${text}</span>` })) as unknown as Snippet;
}
