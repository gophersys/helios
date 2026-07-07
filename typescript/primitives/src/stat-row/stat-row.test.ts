/**
 * StatRow — unit + component render (the application-logic correctness dimension, ADR-0024). The
 * Clusters number-row derivation asserted assertion-richly (the value/label roles, the MONO value
 * family, the title/caption proportions, the exact style string) + the real component (a <dl> of
 * dt/dd pairs, the mono values, the derived vars). Assertion-rich so mutation (75) kills a swapped
 * role, a dropped mono family, a wrong proportion, a mutated var name.
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { generateTheme, C21_SEED, oklchToCss } from '@eden/theme';
import StatRow from './stat-row.svelte';
import { deriveStatRowTokens, statRowStyleVars, type Stat } from './tokens.js';
import { MONO_FONT_FAMILY } from '../chip/tokens.js';

const theme = generateTheme(C21_SEED);
const STATS: readonly Stat[] = [
  { label: 'namespaces', value: '12' },
  { label: 'workloads', value: '48' },
  { label: 'services', value: '31' },
];

describe('deriveStatRowTokens — the pure derivation contract', () => {
  it('the value is onSurface (prominent); the label is the outline role (a quiet overline)', () => {
    const t = deriveStatRowTokens(theme);
    expect(t.valueOklch).toEqual(theme.roles.onSurface.value);
    expect(t.labelOklch).toEqual(theme.roles.outline.value);
    expect(t.label).toBe(oklchToCss(theme.roles.outline.value));
    expect(t.value).not.toBe(t.label);
  });

  it('the value is rendered in the MONO voice; the label in the caption text voice', () => {
    const t = deriveStatRowTokens(theme);
    expect(t.valueFontFamily).toBe(MONO_FONT_FAMILY);
    expect(t.labelFontFamily).toBe(theme.typography.find((r) => r.name === 'caption')!.fontFamily);
  });

  it('the value size is the title role; the label size the caption role (a prominent number)', () => {
    const t = deriveStatRowTokens(theme);
    expect(t.valueFontSizePx).toBe(theme.typography.find((r) => r.name === 'title')!.fontSizePx);
    expect(t.labelFontSizePx).toBe(theme.typography.find((r) => r.name === 'caption')!.fontSizePx);
    // the value is larger than the label (a real number-over-overline hierarchy)
    expect(t.valueFontSizePx).toBeGreaterThan(t.labelFontSizePx);
  });

  it('the inter-pair gap + intra-pair rhythm are ramp steps', () => {
    const t = deriveStatRowTokens(theme);
    const ramp = theme.spacing.map((s) => s.px);
    expect(ramp).toContain(t.gapPx);
    expect(ramp).toContain(t.pairGapPx);
    expect(t.gapPx).toBe(24); // space-6
    expect(t.pairGapPx).toBe(2); // space-0.5
  });
});

describe('statRowStyleVars — the CSS custom-property emission', () => {
  it('emits the EXACT complete declaration string', () => {
    const tokens = deriveStatRowTokens(theme);
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-stat-row-value: ${tokens.value};`,
      `--eden-stat-row-label: ${tokens.label};`,
      `--eden-stat-row-gap: ${px(tokens.gapPx)};`,
      `--eden-stat-row-pair-gap: ${px(tokens.pairGapPx)};`,
      `--eden-stat-row-value-font-size: ${px(tokens.valueFontSizePx)};`,
      `--eden-stat-row-value-line-height: ${px(tokens.valueLineHeightPx)};`,
      `--eden-stat-row-value-font-family: ${tokens.valueFontFamily};`,
      `--eden-stat-row-label-font-size: ${px(tokens.labelFontSizePx)};`,
      `--eden-stat-row-label-line-height: ${px(tokens.labelLineHeightPx)};`,
      `--eden-stat-row-label-font-family: ${tokens.labelFontFamily};`,
    ].join(' ');
    expect(statRowStyleVars(tokens)).toBe(expected);
  });

  it('carries no hex literal', () => {
    expect(statRowStyleVars(deriveStatRowTokens(theme))).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});

describe('StatRow.svelte — the real component', () => {
  it('renders a <dl> of dt(label)/dd(value) pairs for each stat', () => {
    const { container } = render(StatRow, { props: { theme, stats: STATS } });
    const dl = container.querySelector('[data-eden-stat-row]')!;
    expect(dl.tagName).toBe('DL');
    const values = [...container.querySelectorAll('.eden-stat-row-value')].map(
      (n) => n.textContent,
    );
    const labels = [...container.querySelectorAll('.eden-stat-row-label')].map(
      (n) => n.textContent,
    );
    expect(values).toEqual(['12', '48', '31']);
    expect(labels).toEqual(['namespaces', 'workloads', 'services']);
  });

  it('binds the derived mono value font family var', () => {
    const { container } = render(StatRow, { props: { theme, stats: STATS } });
    expect(container.querySelector('[data-eden-stat-row]')!.getAttribute('style')).toContain(
      '--eden-stat-row-value-font-family: monospace',
    );
  });
});
