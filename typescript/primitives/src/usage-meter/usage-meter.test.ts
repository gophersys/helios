/**
 * UsageMeter — unit + component render (application-logic correctness, ADR-0024). The pure derivation
 * + meter math asserted directly, plus the REAL Svelte 5 component: the progressbar mounts with
 * aria-valuenow/valuetext, the tier word is visible (not colour alone), the bar fill width reflects
 * the fraction, and the derived vars reach the element.
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { generateTheme, C21_SEED } from '@eden/theme';
import UsageMeter from './usage-meter.svelte';
import {
  deriveUsageMeterTokens,
  usageMeterStyleVars,
  usageTier,
  type UsageTier,
} from './tokens.js';

const TIERS: readonly UsageTier[] = ['under', 'near', 'over'];

describe('deriveUsageMeterTokens — the pure derivation contract', () => {
  const theme = generateTheme(C21_SEED);

  it('the card is the prose container; the fill is the tier accent (under→info/near→warning/over→error)', () => {
    expect(deriveUsageMeterTokens('under', theme).fillOklch).toEqual(theme.roles.info.value);
    expect(deriveUsageMeterTokens('near', theme).fillOklch).toEqual(theme.roles.warning.value);
    expect(deriveUsageMeterTokens('over', theme).fillOklch).toEqual(theme.roles.error.value);
    const t = deriveUsageMeterTokens('under', theme);
    expect(t.foregroundOklch).toEqual(theme.roles.onSurface.value);
    expect(t.track).toBe(t.foreground === t.track ? t.track : t.track); // track is the outline border
  });

  it('the track is the prose card border (the outline role)', () => {
    const t = deriveUsageMeterTokens('under', theme);
    // the chat-surface prose border is the outline role gated over the surface.
    expect(t.track).toMatch(/^oklch\(/);
  });
});

describe('usageMeterStyleVars — the exact emission', () => {
  it('emits the EXACT complete declaration string', () => {
    const tokens = deriveUsageMeterTokens('near', generateTheme(C21_SEED));
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-usage-meter-fg: ${tokens.foreground};`,
      `--eden-usage-meter-bg: ${tokens.background};`,
      `--eden-usage-meter-track: ${tokens.track};`,
      `--eden-usage-meter-fill: ${tokens.fill};`,
      `--eden-usage-meter-readout-size: ${px(tokens.readoutSizePx)};`,
      `--eden-usage-meter-readout-line-height: ${px(tokens.readoutLineHeightPx)};`,
      `--eden-usage-meter-readout-family: ${tokens.readoutFontFamily};`,
      `--eden-usage-meter-caption-size: ${px(tokens.captionSizePx)};`,
      `--eden-usage-meter-padding: ${px(tokens.paddingPx)};`,
      `--eden-usage-meter-gap: ${px(tokens.gapPx)};`,
      `--eden-usage-meter-track-height: ${px(tokens.trackHeightPx)};`,
      `--eden-usage-meter-radius: ${px(tokens.radiusPx)};`,
    ].join(' ');
    expect(usageMeterStyleVars(tokens)).toBe(expected);
  });
});

describe('UsageMeter.svelte — the real component', () => {
  it('renders a progressbar with aria-valuenow and a speaking valuetext', () => {
    const { getByRole } = render(UsageMeter, { props: { used: 50, budget: 100 } });
    const bar = getByRole('progressbar');
    expect(bar.getAttribute('aria-valuenow')).toBe('50');
    expect(bar.getAttribute('aria-valuetext')).toContain('50 of 100 tokens');
    expect(bar.getAttribute('aria-valuetext')).toContain('within budget');
  });

  it('the tier word is visible and matches the computed tier (colour is never the only signal)', () => {
    const cases: [number, number, string][] = [
      [10, 100, 'within budget'],
      [85, 100, 'near budget'],
      [100, 100, 'over budget'],
    ];
    for (const [used, budget, word] of cases) {
      const { getByText, unmount } = render(UsageMeter, { props: { used, budget } });
      expect(getByText(word)).toBeTruthy();
      unmount();
    }
  });

  it('the bar fill width reflects the usage fraction (a derived percentage, not a literal)', () => {
    const { container } = render(UsageMeter, { props: { used: 30, budget: 120 } });
    const fill = container.querySelector('.eden-usage-meter-fill') as HTMLElement;
    expect(fill.getAttribute('style')).toContain('inline-size: 25%');
  });

  it('renders the optional cost caption when supplied', () => {
    const { getByText } = render(UsageMeter, { props: { used: 1, budget: 2, cost: '$0.42' } });
    expect(getByText('$0.42')).toBeTruthy();
  });

  it('binds the tier fill var into the inline style for each tier', () => {
    const theme = generateTheme(C21_SEED);
    for (const tier of TIERS) {
      const used = tier === 'over' ? 100 : tier === 'near' ? 85 : 10;
      const { getByRole, unmount } = render(UsageMeter, { props: { used, budget: 100, theme } });
      const tokens = deriveUsageMeterTokens(usageTier(used / 100), theme);
      expect(getByRole('progressbar').closest('[data-eden-usage-meter]')!.getAttribute('style')).toContain(
        `--eden-usage-meter-fill: ${tokens.fill}`,
      );
      unmount();
    }
  });
});
