/**
 * StreamingText — unit + component render (application-logic correctness, ADR-0024). The pure
 * derivation + reveal math asserted directly, and the REAL Svelte 5 component rendered through
 * @testing-library/svelte: the live region mounts, the caret shows while streaming and is removed
 * when done, the derived vars reach the element, and aria-busy reflects the state.
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { generateTheme, C21_SEED } from '@eden/theme';
import StreamingText from './streaming-text.svelte';
import {
  deriveStreamingTextTokens,
  streamingTextStyleVars,
  appendChunk,
} from './tokens.js';

describe('deriveStreamingTextTokens — the pure derivation contract', () => {
  const theme = generateTheme(C21_SEED);

  it('is the prose container (on-surface over surface), caret equals the foreground', () => {
    const t = deriveStreamingTextTokens(theme);
    expect(t.foregroundOklch).toEqual(theme.roles.onSurface.value);
    expect(t.backgroundOklch).toEqual(theme.roles.surface.value);
    expect(t.caret).toBe(t.foreground);
  });

  it('the proportion is body and the caret width is the 2px ramp step', () => {
    const t = deriveStreamingTextTokens(theme);
    const body = theme.typography.find((r) => r.name === 'body')!;
    expect(t.fontSizePx).toBe(body.fontSizePx);
    expect(t.caretWidthPx).toBe(2);
  });
});

describe('streamingTextStyleVars — the exact emission', () => {
  it('emits the EXACT complete declaration string', () => {
    const tokens = deriveStreamingTextTokens(generateTheme(C21_SEED));
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-streaming-text-fg: ${tokens.foreground};`,
      `--eden-streaming-text-bg: ${tokens.background};`,
      `--eden-streaming-text-caret: ${tokens.caret};`,
      `--eden-streaming-text-font-size: ${px(tokens.fontSizePx)};`,
      `--eden-streaming-text-line-height: ${px(tokens.lineHeightPx)};`,
      `--eden-streaming-text-font-family: ${tokens.fontFamily};`,
      `--eden-streaming-text-caret-width: ${px(tokens.caretWidthPx)};`,
    ].join(' ');
    expect(streamingTextStyleVars(tokens)).toBe(expected);
  });
});

describe('StreamingText.svelte — the real component', () => {
  it('renders a polite live region carrying the accumulated text', () => {
    const { getByRole } = render(StreamingText, { props: { text: 'Hello world', streaming: true } });
    const el = getByRole('status');
    expect(el.getAttribute('aria-live')).toBe('polite');
    expect(el.textContent).toContain('Hello world');
  });

  it('shows the caret while streaming (aria-busy true)', () => {
    const { getByRole, container } = render(StreamingText, {
      props: { text: 'partial', streaming: true },
    });
    expect(getByRole('status').getAttribute('aria-busy')).toBe('true');
    expect(container.querySelector('.eden-streaming-text-caret')).not.toBeNull();
  });

  it('removes the caret and clears aria-busy when the stream completes', () => {
    const { getByRole, container } = render(StreamingText, {
      props: { text: 'done', streaming: false },
    });
    expect(getByRole('status').getAttribute('aria-busy')).toBe('false');
    expect(container.querySelector('.eden-streaming-text-caret')).toBeNull();
  });

  it('binds the derived --eden-streaming-text-* vars into the element inline style', () => {
    const theme = generateTheme(C21_SEED);
    const { getByRole } = render(StreamingText, { props: { text: 'x', theme, streaming: true } });
    const tokens = deriveStreamingTextTokens(theme);
    expect(getByRole('status').getAttribute('style')).toContain(
      `--eden-streaming-text-fg: ${tokens.foreground}`,
    );
  });

  it('the reveal math composes with the component (append then render the accumulated text)', () => {
    const a = appendChunk('', 'Stream');
    const b = appendChunk(a.text, 'ing');
    const { getByRole } = render(StreamingText, { props: { text: b.text, streaming: false } });
    expect(getByRole('status').textContent).toContain('Streaming');
  });
});
