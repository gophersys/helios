/**
 * Tabs — unit + component render (the application-logic correctness dimension, ADR-0024). The
 * segmented switcher derivation asserted assertion-richly (the active/inactive/foreground roles, the
 * 44px hit target, the label proportion, the exact style string) + the real component (the bits-ui
 * tablist/tab/tabpanel roles mount, the active panel renders, disabled is forwarded). Assertion-rich
 * so mutation (75) kills a swapped role, a wrong proportion, a mutated var name.
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { createRawSnippet, type Snippet } from 'svelte';
import { generateTheme, C21_SEED, oklchToCss } from '@eden/theme';
import Tabs from './tabs.svelte';
import { deriveTabsTokens, tabsStyleVars, type Tab } from './tokens.js';

const theme = generateTheme(C21_SEED);
const TABS: readonly Tab[] = [
  { value: 'overview', label: 'Overview' },
  { value: 'build', label: 'Build' },
  { value: 'insight', label: 'Insight', disabled: true },
];

describe('deriveTabsTokens — the pure derivation contract', () => {
  it('active = primary, inactive = outline, foreground = onSurface, rail = outline', () => {
    const t = deriveTabsTokens(theme);
    expect(t.activeOklch).toEqual(theme.roles.primary.value);
    expect(t.inactiveOklch).toEqual(theme.roles.outline.value);
    expect(t.foregroundOklch).toEqual(theme.roles.onSurface.value);
    expect(t.rail).toBe(oklchToCss(theme.roles.outline.value));
    // active and inactive are distinct (a real selected/unselected contrast)
    expect(t.active).not.toBe(t.inactive);
  });

  it('each trigger honours the decoupled 44px+ hit target', () => {
    expect(deriveTabsTokens(theme).hitTargetPx).toBe(theme.controlGeometry.hitTargetPx);
    expect(deriveTabsTokens(theme).hitTargetPx).toBeGreaterThanOrEqual(44);
  });

  it('the label type is the label typography role; the paddings/gap are ramp steps', () => {
    const t = deriveTabsTokens(theme);
    const ramp = theme.spacing.map((s) => s.px);
    expect(t.fontSizePx).toBe(theme.typography.find((r) => r.name === 'label')!.fontSizePx);
    expect(ramp).toContain(t.paddingInlinePx);
    expect(ramp).toContain(t.paddingBlockPx);
    expect(ramp).toContain(t.gapPx);
    expect(t.paddingInlinePx).toBe(12); // space-3
    expect(t.paddingBlockPx).toBe(8); // space-2
  });
});

describe('tabsStyleVars — the CSS custom-property emission', () => {
  it('emits the EXACT complete declaration string', () => {
    const tokens = deriveTabsTokens(theme);
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-tabs-active: ${tokens.active};`,
      `--eden-tabs-inactive: ${tokens.inactive};`,
      `--eden-tabs-fg: ${tokens.foreground};`,
      `--eden-tabs-rail: ${tokens.rail};`,
      `--eden-tabs-surface: ${tokens.surface};`,
      `--eden-tabs-hit-target: ${px(tokens.hitTargetPx)};`,
      `--eden-tabs-padding-inline: ${px(tokens.paddingInlinePx)};`,
      `--eden-tabs-padding-block: ${px(tokens.paddingBlockPx)};`,
      `--eden-tabs-gap: ${px(tokens.gapPx)};`,
      `--eden-tabs-font-size: ${px(tokens.fontSizePx)};`,
      `--eden-tabs-line-height: ${px(tokens.lineHeightPx)};`,
      `--eden-tabs-font-family: ${tokens.fontFamily};`,
    ].join(' ');
    expect(tabsStyleVars(tokens)).toBe(expected);
  });

  it('carries no hex literal', () => {
    expect(tabsStyleVars(deriveTabsTokens(theme))).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});

describe('Tabs.svelte — the real component (bits-ui behavior + token binding)', () => {
  it('mounts the tablist/tab roles and renders each tab label', () => {
    const { getByRole } = render(Tabs, {
      props: { theme, tabs: TABS, label: 'Project views', panel: makePanel() },
    });
    expect(getByRole('tablist', { name: 'Project views' })).toBeTruthy();
    expect(getByRole('tab', { name: 'Overview' })).toBeTruthy();
    expect(getByRole('tab', { name: 'Build' })).toBeTruthy();
  });

  it('renders the active tab panel content (the first tab by default)', () => {
    const { getByText } = render(Tabs, {
      props: { theme, tabs: TABS, panel: makePanel() },
    });
    expect(getByText('panel:overview')).toBeTruthy();
  });

  it('forwards disabled to the bits-ui trigger (the insight tab is disabled)', () => {
    const { getByRole } = render(Tabs, {
      props: { theme, tabs: TABS, panel: makePanel() },
    });
    const insight = getByRole('tab', { name: 'Insight' });
    expect(insight.getAttribute('data-disabled')).not.toBeNull();
  });

  it('binds the derived active-colour var onto the root', () => {
    const { container } = render(Tabs, { props: { theme, tabs: TABS, panel: makePanel() } });
    const root = container.querySelector('.eden-tabs')!;
    const tokens = deriveTabsTokens(theme);
    expect(root.getAttribute('style')).toContain(`--eden-tabs-active: ${tokens.active}`);
  });
});

/** A panel snippet that renders `panel:<value>` so the active tab is identifiable in the DOM. */
function makePanel(): Snippet<[string]> {
  return createRawSnippet((value: () => string) => ({
    render: () => `<span>panel:${value()}</span>`,
  })) as unknown as Snippet<[string]>;
}
