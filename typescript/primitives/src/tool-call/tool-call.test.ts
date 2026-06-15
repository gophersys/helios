/**
 * ToolCall — unit + component render (application-logic correctness, ADR-0024). The pure derivation
 * asserted directly, plus the REAL Svelte 5 component: the card mounts with an accessible label, the
 * status is conveyed by a visible word (not colour alone), the args render as a code block, the
 * derived vars reach the element.
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { generateTheme, C21_SEED } from '@eden/theme';
import ToolCall from './tool-call.svelte';
import { deriveToolCallTokens, toolCallStyleVars, type ToolCallStatus } from './tokens.js';

const STATUSES: readonly ToolCallStatus[] = ['running', 'success', 'error'];

describe('deriveToolCallTokens — the pure derivation contract', () => {
  const theme = generateTheme(C21_SEED);

  it('the card is the prose container; the status maps running→info/success→success/error→error', () => {
    const t = deriveToolCallTokens('running', theme);
    expect(t.foregroundOklch).toEqual(theme.roles.onSurface.value);
    expect(t.backgroundOklch).toEqual(theme.roles.surface.value);
    expect(deriveToolCallTokens('running', theme).statusOklch).toEqual(theme.roles.info.value);
    expect(deriveToolCallTokens('success', theme).statusOklch).toEqual(theme.roles.success.value);
    expect(deriveToolCallTokens('error', theme).statusOklch).toEqual(theme.roles.error.value);
  });

  it('proportions: label for the tool name, caption for the code, monospace code family', () => {
    const t = deriveToolCallTokens('running', theme);
    const label = theme.typography.find((r) => r.name === 'label')!;
    const caption = theme.typography.find((r) => r.name === 'caption')!;
    expect(t.titleSizePx).toBe(label.fontSizePx);
    expect(t.codeSizePx).toBe(caption.fontSizePx);
    expect(t.codeFontFamily).toBe('monospace');
  });
});

describe('toolCallStyleVars — the exact emission', () => {
  it('emits the EXACT complete declaration string', () => {
    const tokens = deriveToolCallTokens('running', generateTheme(C21_SEED));
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-tool-call-fg: ${tokens.foreground};`,
      `--eden-tool-call-bg: ${tokens.background};`,
      `--eden-tool-call-border: ${tokens.border};`,
      `--eden-tool-call-status: ${tokens.statusColor};`,
      `--eden-tool-call-title-size: ${px(tokens.titleSizePx)};`,
      `--eden-tool-call-title-line-height: ${px(tokens.titleLineHeightPx)};`,
      `--eden-tool-call-title-family: ${tokens.titleFontFamily};`,
      `--eden-tool-call-code-size: ${px(tokens.codeSizePx)};`,
      `--eden-tool-call-code-line-height: ${px(tokens.codeLineHeightPx)};`,
      `--eden-tool-call-code-family: ${tokens.codeFontFamily};`,
      `--eden-tool-call-padding: ${px(tokens.paddingPx)};`,
      `--eden-tool-call-gap: ${px(tokens.gapPx)};`,
      `--eden-tool-call-radius: ${px(tokens.radiusPx)};`,
    ].join(' ');
    expect(toolCallStyleVars(tokens)).toBe(expected);
  });
});

describe('ToolCall.svelte — the real component', () => {
  it('renders a labelled section naming the tool, with a visible status word', () => {
    const { getByRole, getByText } = render(ToolCall, {
      props: { tool: 'read_file', args: '{"path":"a.ts"}', status: 'running' },
    });
    expect(getByRole('group', { name: 'Tool call: read_file' })).toBeTruthy();
    expect(getByText('read_file')).toBeTruthy();
    expect(getByText('Running')).toBeTruthy();
  });

  it('renders the args inside a code block', () => {
    const { container } = render(ToolCall, {
      props: { tool: 'grep', args: 'pattern=foo', status: 'success' },
    });
    const code = container.querySelector('pre.eden-tool-call-args code');
    expect(code).not.toBeNull();
    expect(code!.textContent).toContain('pattern=foo');
  });

  it('omits the code block when there are no args', () => {
    const { container } = render(ToolCall, { props: { tool: 'noop', status: 'success' } });
    expect(container.querySelector('pre.eden-tool-call-args')).toBeNull();
  });

  it('renders a distinct status word for every status (colour is never the only signal)', () => {
    const words = { running: 'Running', success: 'Succeeded', error: 'Failed' } as const;
    for (const status of STATUSES) {
      const { getByText, unmount } = render(ToolCall, { props: { tool: 't', status } });
      expect(getByText(words[status])).toBeTruthy();
      unmount();
    }
  });

  it('binds the derived --eden-tool-call-* vars into the element inline style', () => {
    const theme = generateTheme(C21_SEED);
    const { getByRole } = render(ToolCall, { props: { tool: 't', theme, status: 'error' } });
    const tokens = deriveToolCallTokens('error', theme);
    expect(getByRole('group').getAttribute('style')).toContain(
      `--eden-tool-call-status: ${tokens.statusColor}`,
    );
  });
});
