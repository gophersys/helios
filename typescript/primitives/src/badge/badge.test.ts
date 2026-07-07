/**
 * Badge — unit + component render (the application-logic correctness dimension, ADR-0024).
 *
 * Two layers: (1) the pure token-derivation contract (deriveBadgeTokens / badgeStyleVars) asserted
 * directly and assertion-richly (every variant's role selection, the exact emitted style string), and
 * (2) the REAL Svelte 5 component rendered through @testing-library/svelte — the derived vars reach
 * the element, the status role is announced, the label is present. Assertion-rich so mutation (75)
 * kills a swapped role, a dropped tint, a mutated var name.
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { createRawSnippet, type Snippet } from 'svelte';
import { generateTheme, C21_SEED, oklchToCss } from '@eden/theme';
import Badge from './badge.svelte';
import { deriveBadgeTokens, badgeStyleVars, type BadgeVariant } from './tokens.js';

const theme = generateTheme(C21_SEED);
const VARIANTS: readonly BadgeVariant[] = [
  'healthy',
  'updating',
  'degraded',
  'down',
  'unknown',
  'neutral',
  'accent',
];

describe('deriveBadgeTokens — the pure derivation contract', () => {
  it('healthy selects the success role as its foreground (the Clusters health mapping)', () => {
    const t = deriveBadgeTokens('healthy', theme);
    expect(t.foregroundOklch).toEqual(theme.roles.success.value);
    expect(t.foreground).toBe(oklchToCss(theme.roles.success.value));
    expect(t.surfaceOklch).toEqual(theme.roles.surface.value);
  });

  it('down selects the error role; degraded the warning role; updating the info role (all distinct)', () => {
    expect(deriveBadgeTokens('down', theme).foregroundOklch).toEqual(theme.roles.error.value);
    expect(deriveBadgeTokens('degraded', theme).foregroundOklch).toEqual(theme.roles.warning.value);
    expect(deriveBadgeTokens('updating', theme).foregroundOklch).toEqual(theme.roles.info.value);
    const set = new Set(
      (['down', 'degraded', 'updating', 'healthy'] as const).map(
        (v) => deriveBadgeTokens(v, theme).foreground,
      ),
    );
    expect(set.size).toBe(4);
  });

  it('accent selects the primary role; neutral/unknown the outline role', () => {
    expect(deriveBadgeTokens('accent', theme).foregroundOklch).toEqual(theme.roles.primary.value);
    expect(deriveBadgeTokens('neutral', theme).foregroundOklch).toEqual(theme.roles.outline.value);
    expect(deriveBadgeTokens('unknown', theme).foregroundOklch).toEqual(theme.roles.outline.value);
  });

  it('the tint fill + edge are translucent views of the SAME hue as the foreground (the wash)', () => {
    const t = deriveBadgeTokens('down', theme);
    // both carry the error role's lightness prefix and an alpha channel (the Clusters color-mix wash)
    expect(t.background).toContain('/ 0.12');
    expect(t.border).toContain('/ 0.35');
    expect(t.background).not.toBe(t.border);
    expect(t.background).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it('the radius is the control ramp step, the paddings + gap are ramp steps (scale provenance)', () => {
    const t = deriveBadgeTokens('neutral', theme);
    const ramp = theme.spacing.map((s) => s.px);
    expect(t.radiusPx).toBe(theme.spacing.find((s) => s.name === 'space-1')!.px);
    expect(ramp).toContain(t.paddingInlinePx);
    expect(ramp).toContain(t.paddingBlockPx);
    expect(ramp).toContain(t.gapPx);
    expect(t.paddingInlinePx).toBe(8); // space-2
    expect(t.paddingBlockPx).toBe(2); // space-0.5
    expect(t.gapPx).toBe(4); // space-1
  });

  it('the type is the caption typography role (size + line-height + family)', () => {
    const t = deriveBadgeTokens('neutral', theme);
    const cap = theme.typography.find((r) => r.name === 'caption')!;
    expect(t.fontSizePx).toBe(cap.fontSizePx);
    expect(t.fontFamily).toBe(cap.fontFamily);
  });
});

describe('badgeStyleVars — the CSS custom-property emission', () => {
  it('emits the EXACT complete declaration string — every var name mapped to its own token', () => {
    const tokens = deriveBadgeTokens('healthy', theme);
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-badge-fg: ${tokens.foreground};`,
      `--eden-badge-bg: ${tokens.background};`,
      `--eden-badge-border: ${tokens.border};`,
      `--eden-badge-radius: ${px(tokens.radiusPx)};`,
      `--eden-badge-padding-inline: ${px(tokens.paddingInlinePx)};`,
      `--eden-badge-padding-block: ${px(tokens.paddingBlockPx)};`,
      `--eden-badge-gap: ${px(tokens.gapPx)};`,
      `--eden-badge-font-size: ${px(tokens.fontSizePx)};`,
      `--eden-badge-line-height: ${px(tokens.lineHeightPx)};`,
      `--eden-badge-font-family: ${tokens.fontFamily};`,
    ].join(' ');
    expect(badgeStyleVars(tokens)).toBe(expected);
  });

  it('carries no hex literal anywhere (provenance)', () => {
    for (const v of VARIANTS) {
      expect(badgeStyleVars(deriveBadgeTokens(v, theme))).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    }
  });
});

describe('Badge.svelte — the real component', () => {
  it('renders a span carrying the label text and the derived --eden-badge-* vars', () => {
    const { container } = render(Badge, {
      props: { variant: 'healthy', theme, status: true, children: makeLabel('Healthy') },
    });
    const el = container.querySelector('[data-eden-badge]')!;
    expect(el.textContent.trim()).toBe('Healthy');
    const tokens = deriveBadgeTokens('healthy', theme);
    expect(el.getAttribute('style')).toContain(`--eden-badge-fg: ${tokens.foreground}`);
    expect(el.getAttribute('data-variant')).toBe('healthy');
  });

  it('adds role="status" only when the status flag is set (chrome badges are not over-announced)', () => {
    const withStatus = render(Badge, {
      props: { variant: 'down', status: true, children: makeLabel('Down') },
    });
    expect(withStatus.container.querySelector('[data-eden-badge]')!.getAttribute('role')).toBe(
      'status',
    );
    const chrome = render(Badge, {
      props: { variant: 'neutral', children: makeLabel('12') },
    });
    expect(chrome.container.querySelector('[data-eden-badge]')!.getAttribute('role')).toBeNull();
  });
});

function makeLabel(text: string): Snippet {
  return createRawSnippet(() => ({ render: () => `<span>${text}</span>` })) as unknown as Snippet;
}
