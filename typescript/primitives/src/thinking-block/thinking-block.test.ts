/**
 * ThinkingBlock — unit + component render (application-logic correctness, ADR-0024). The pure
 * derivation asserted directly, plus the REAL Svelte 5 component on the bits-ui Collapsible: the
 * disclosure mounts, the trigger is a real button with aria-expanded, the content is hidden when
 * collapsed and present when open, and the derived vars reach the block element.
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { createRawSnippet, type Snippet } from 'svelte';
import { generateTheme, C21_SEED } from '@eden/theme';
import ThinkingBlock from './thinking-block.svelte';
import { deriveThinkingBlockTokens, thinkingBlockStyleVars } from './tokens.js';

describe('deriveThinkingBlockTokens — the pure derivation contract', () => {
  const theme = generateTheme(C21_SEED);

  it('is the quiet container (on-primary-container over primary-container)', () => {
    const t = deriveThinkingBlockTokens(theme);
    expect(t.foregroundOklch).toEqual(theme.roles.onPrimaryContainer.value);
    expect(t.backgroundOklch).toEqual(theme.roles.primaryContainer.value);
  });

  it('proportions: label summary, body prose; hit target 44px', () => {
    const t = deriveThinkingBlockTokens(theme);
    const label = theme.typography.find((r) => r.name === 'label')!;
    const body = theme.typography.find((r) => r.name === 'body')!;
    expect(t.summarySizePx).toBe(label.fontSizePx);
    expect(t.proseSizePx).toBe(body.fontSizePx);
    expect(t.hitTargetPx).toBe(44);
  });
});

describe('thinkingBlockStyleVars — the exact emission', () => {
  it('emits the EXACT complete declaration string', () => {
    const tokens = deriveThinkingBlockTokens(generateTheme(C21_SEED));
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-thinking-block-fg: ${tokens.foreground};`,
      `--eden-thinking-block-bg: ${tokens.background};`,
      `--eden-thinking-block-border: ${tokens.border};`,
      `--eden-thinking-block-summary-size: ${px(tokens.summarySizePx)};`,
      `--eden-thinking-block-summary-line-height: ${px(tokens.summaryLineHeightPx)};`,
      `--eden-thinking-block-summary-family: ${tokens.summaryFontFamily};`,
      `--eden-thinking-block-prose-size: ${px(tokens.proseSizePx)};`,
      `--eden-thinking-block-prose-line-height: ${px(tokens.proseLineHeightPx)};`,
      `--eden-thinking-block-prose-family: ${tokens.proseFontFamily};`,
      `--eden-thinking-block-padding: ${px(tokens.paddingPx)};`,
      `--eden-thinking-block-gap: ${px(tokens.gapPx)};`,
      `--eden-thinking-block-radius: ${px(tokens.radiusPx)};`,
      `--eden-thinking-block-hit-target: ${px(tokens.hitTargetPx)};`,
    ].join(' ');
    expect(thinkingBlockStyleVars(tokens)).toBe(expected);
  });
});

describe('ThinkingBlock.svelte — the real component', () => {
  it('mounts a disclosure trigger (a real button) showing the summary word', () => {
    const { getByRole } = render(ThinkingBlock, {
      props: { summary: 'Thinking', children: makeProse('reasoning') },
    });
    const trigger = getByRole('button');
    expect(trigger.tagName).toBe('BUTTON');
    expect(trigger.textContent).toContain('Thinking');
  });

  it('the trigger carries aria-expanded reflecting the open state', () => {
    const collapsed = render(ThinkingBlock, {
      props: { open: false, children: makeProse('x') },
    });
    expect(collapsed.getByRole('button').getAttribute('aria-expanded')).toBe('false');
    collapsed.unmount();

    const open = render(ThinkingBlock, { props: { open: true, children: makeProse('x') } });
    expect(open.getByRole('button').getAttribute('aria-expanded')).toBe('true');
  });

  it('reveals the reasoning content when open', () => {
    const { container } = render(ThinkingBlock, {
      props: { open: true, children: makeProse('the chain of thought') },
    });
    expect(container.textContent).toContain('the chain of thought');
  });

  it('binds the derived --eden-thinking-block-* vars into the block inline style', () => {
    const theme = generateTheme(C21_SEED);
    const { container } = render(ThinkingBlock, {
      props: { theme, children: makeProse('x') },
    });
    const block = container.querySelector<HTMLElement>('.eden-thinking-block')!;
    const tokens = deriveThinkingBlockTokens(theme);
    expect(block.getAttribute('style')).toContain(`--eden-thinking-block-fg: ${tokens.foreground}`);
  });
});

function makeProse(text: string): Snippet {
  return createRawSnippet(() => ({ render: () => `<span>${text}</span>` })) as unknown as Snippet;
}
