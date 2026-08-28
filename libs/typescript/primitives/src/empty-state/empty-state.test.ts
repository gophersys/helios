/**
 * EmptyState — unit + component render (the application-logic correctness dimension, ADR-0024). The
 * product-surface derivation asserted assertion-richly (the headline SERIF display voice vs the body
 * SANS voice, the reading measure, the exact style string) + the real component (the headline/body/
 * action/content slots, the aria-labelledby link, the derived vars). Assertion-rich so mutation (75)
 * kills a swapped voice, a dropped slot, a mutated var name.
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { createRawSnippet, type Snippet } from 'svelte';
import { generateTheme, C21_SEED, oklchToCss } from '@eden/theme';
import EmptyState from './empty-state.svelte';
import { deriveEmptyStateTokens, emptyStateStyleVars } from './tokens.js';

const theme = generateTheme(C21_SEED);

describe('deriveEmptyStateTokens — the pure derivation contract', () => {
  it('the headline is the SERIF display voice; the body the SANS text voice (distinct families)', () => {
    const t = deriveEmptyStateTokens(theme);
    const display = theme.typography.find((r) => r.name === 'display-small')!;
    const body = theme.typography.find((r) => r.name === 'body')!;
    expect(t.headlineFontFamily).toBe(display.fontFamily);
    expect(t.bodyFontFamily).toBe(body.fontFamily);
    // the identity-moment headline is the DISPLAY font, NOT the interface text font (P-D4)
    expect(t.headlineFontFamily).not.toBe(t.bodyFontFamily);
  });

  it('the headline is larger than the body (a real identity-moment hierarchy)', () => {
    const t = deriveEmptyStateTokens(theme);
    expect(t.headlineFontSizePx).toBe(
      theme.typography.find((r) => r.name === 'display-small')!.fontSizePx,
    );
    expect(t.headlineFontSizePx).toBeGreaterThan(t.bodyFontSizePx);
  });

  it('the headline is onSurface; the body the outline role (a quieter secondary line)', () => {
    const t = deriveEmptyStateTokens(theme);
    expect(t.headlineOklch).toEqual(theme.roles.onSurface.value);
    expect(t.bodyOklch).toEqual(theme.roles.outline.value);
    expect(t.body).toBe(oklchToCss(theme.roles.outline.value));
  });

  it('the max reading width is the medium breakpoint (the anti-void measure); gaps are ramp steps', () => {
    const t = deriveEmptyStateTokens(theme);
    expect(t.maxWidthPx).toBe(theme.breakpoints.find((b) => b.name === 'medium')!.minWidthPx);
    expect(t.maxWidthPx).toBe(600);
    const ramp = theme.spacing.map((s) => s.px);
    expect(ramp).toContain(t.gapPx);
    expect(ramp).toContain(t.paddingPx);
  });
});

describe('totality — the fallback branches keep the derivation total (drive the guards)', () => {
  it('the headline falls back to the headline role when display-small is absent', () => {
    const noDisplaySmall = {
      ...theme,
      typography: theme.typography.filter((r) => r.name !== 'display-small'),
    };
    const t = deriveEmptyStateTokens(noDisplaySmall);
    expect(t.headlineFontFamily).toBe(
      theme.typography.find((r) => r.name === 'headline')!.fontFamily,
    );
  });

  it('the headline falls back to inherit + the control font size when typography is empty', () => {
    const noType = { ...theme, typography: [] };
    const t = deriveEmptyStateTokens(noType);
    expect(t.headlineFontFamily).toBe('inherit');
    expect(t.headlineFontSizePx).toBe(theme.controlGeometry.fontSizePx);
    expect(t.headlineLineHeightPx).toBe(theme.controlGeometry.lineHeightPx);
  });

  it('the reading measure falls back to the first breakpoint when medium is absent', () => {
    const noMedium = {
      ...theme,
      breakpoints: theme.breakpoints.filter((b) => b.name !== 'medium'),
    };
    const t = deriveEmptyStateTokens(noMedium);
    expect(t.maxWidthPx).toBe(theme.breakpoints.find((b) => b.name === 'compact')!.minWidthPx);
  });
});

describe('emptyStateStyleVars — the CSS custom-property emission', () => {
  it('emits the EXACT complete declaration string', () => {
    const tokens = deriveEmptyStateTokens(theme);
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-empty-state-headline: ${tokens.headline};`,
      `--eden-empty-state-body: ${tokens.body};`,
      `--eden-empty-state-surface: ${tokens.surface};`,
      `--eden-empty-state-headline-font-size: ${px(tokens.headlineFontSizePx)};`,
      `--eden-empty-state-headline-line-height: ${px(tokens.headlineLineHeightPx)};`,
      `--eden-empty-state-headline-font-family: ${tokens.headlineFontFamily};`,
      `--eden-empty-state-body-font-size: ${px(tokens.bodyFontSizePx)};`,
      `--eden-empty-state-body-line-height: ${px(tokens.bodyLineHeightPx)};`,
      `--eden-empty-state-body-font-family: ${tokens.bodyFontFamily};`,
      `--eden-empty-state-gap: ${px(tokens.gapPx)};`,
      `--eden-empty-state-padding: ${px(tokens.paddingPx)};`,
      `--eden-empty-state-max-width: ${px(tokens.maxWidthPx)};`,
    ].join(' ');
    expect(emptyStateStyleVars(tokens)).toBe(expected);
  });

  it('carries no hex literal', () => {
    expect(emptyStateStyleVars(deriveEmptyStateTokens(theme))).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});

describe('EmptyState.svelte — the real component', () => {
  it('renders the headline as an h2 wired to the region via aria-labelledby', () => {
    const { container } = render(EmptyState, {
      props: { theme, headline: 'No projects yet', body: 'Create your first project to begin.' },
    });
    const region = container.querySelector('[data-eden-empty-state]')!;
    const headline = container.querySelector('.eden-empty-state-headline')!;
    expect(headline.tagName).toBe('H2');
    expect(headline.textContent).toBe('No projects yet');
    // the region's aria-labelledby points at the headline id (the named landmark)
    expect(region.getAttribute('aria-labelledby')).toBe(headline.id);
    expect(headline.id).toBeTruthy();
  });

  it('renders the action + content slots only when provided (the anti-void product surface)', () => {
    const bare = render(EmptyState, { props: { theme, headline: 'Empty' } });
    expect(bare.container.querySelector('.eden-empty-state-action')).toBeNull();
    expect(bare.container.querySelector('.eden-empty-state-content')).toBeNull();

    const full = render(EmptyState, {
      props: {
        theme,
        headline: 'Empty',
        action: makeContent('Create'),
        content: makeContent('templates'),
      },
    });
    expect(full.container.querySelector('.eden-empty-state-action')!.textContent).toContain(
      'Create',
    );
    expect(full.container.querySelector('.eden-empty-state-content')!.textContent).toContain(
      'templates',
    );
  });

  it('binds the derived serif-headline font-family var', () => {
    const { container } = render(EmptyState, { props: { theme, headline: 'x' } });
    const tokens = deriveEmptyStateTokens(theme);
    expect(container.querySelector('[data-eden-empty-state]')!.getAttribute('style')).toContain(
      `--eden-empty-state-headline-font-family: ${tokens.headlineFontFamily}`,
    );
  });
});

function makeContent(text: string): Snippet {
  return createRawSnippet(() => ({ render: () => `<span>${text}</span>` })) as unknown as Snippet;
}
