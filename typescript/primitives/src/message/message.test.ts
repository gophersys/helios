/**
 * Message — unit + component render (the application-logic correctness dimension, ADR-0024).
 * Two layers: the pure token-derivation contract asserted directly, and the REAL Svelte 5 component
 * rendered through @testing-library/svelte in jsdom (the bubble mounts, the derived vars reach the
 * element, the role/author semantics render, the prose slot fills). The browser-level a11y + keyboard
 * proof is the separate Playwright lane (tests-a11y/specs/message.spec.ts).
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { createRawSnippet, type Snippet } from 'svelte';
import { generateTheme, C21_SEED } from '@eden/theme';
import Message from './message.svelte';
import { deriveMessageTokens, messageStyleVars, type MessageRole } from './tokens.js';

const ROLES: readonly MessageRole[] = ['user', 'assistant'];

describe('deriveMessageTokens — the pure derivation contract', () => {
  const theme = generateTheme(C21_SEED);

  it('the user role is the accent container (on-primary over primary)', () => {
    const t = deriveMessageTokens('user', theme);
    expect(t.foregroundOklch).toEqual(theme.roles.onPrimary.value);
    expect(t.backgroundOklch).toEqual(theme.roles.primary.value);
  });

  it('the assistant role is the quiet container (on-primary-container over primary-container)', () => {
    const t = deriveMessageTokens('assistant', theme);
    expect(t.foregroundOklch).toEqual(theme.roles.onPrimaryContainer.value);
    expect(t.backgroundOklch).toEqual(theme.roles.primaryContainer.value);
  });

  it('the prose is the body proportion; padding/gap/radius are 16/8/12 ramp steps', () => {
    const t = deriveMessageTokens('assistant', theme);
    const body = theme.typography.find((r) => r.name === 'body')!;
    expect(t.fontSizePx).toBe(body.fontSizePx);
    expect([t.paddingPx, t.gapPx, t.radiusPx]).toEqual([16, 8, 12]);
  });

  it('dark mode flips the derived foreground (the container is mode-aware)', () => {
    const light = deriveMessageTokens('user', generateTheme(C21_SEED, { mode: 'light' }));
    const dark = deriveMessageTokens('user', generateTheme(C21_SEED, { mode: 'dark' }));
    expect(dark.foreground).not.toBe(light.foreground);
  });
});

describe('messageStyleVars — the CSS custom-property emission', () => {
  const tokens = deriveMessageTokens('assistant', generateTheme(C21_SEED));

  it('emits the EXACT complete declaration string (every var name → its own token)', () => {
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-message-fg: ${tokens.foreground};`,
      `--eden-message-bg: ${tokens.background};`,
      `--eden-message-border: ${tokens.border};`,
      `--eden-message-font-size: ${px(tokens.fontSizePx)};`,
      `--eden-message-line-height: ${px(tokens.lineHeightPx)};`,
      `--eden-message-font-family: ${tokens.fontFamily};`,
      `--eden-message-padding: ${px(tokens.paddingPx)};`,
      `--eden-message-gap: ${px(tokens.gapPx)};`,
      `--eden-message-radius: ${px(tokens.radiusPx)};`,
    ].join(' ');
    expect(messageStyleVars(tokens)).toBe(expected);
  });

  it('the color vars carry oklch(...) values and there is no hex literal anywhere', () => {
    const css = messageStyleVars(tokens);
    expect(css).toContain('--eden-message-fg: oklch(');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});

describe('Message.svelte — the real component', () => {
  it('renders an article with role listitem and an accessible author label', () => {
    const { getByRole } = render(Message, {
      props: { role: 'assistant', children: makeBody('Hello') },
    });
    const el = getByRole('listitem', { name: 'Assistant message' });
    expect(el.tagName).toBe('DIV');
    expect(el.textContent).toContain('Hello');
  });

  it('surfaces the author visibly (role not conveyed by colour alone — WCAG 1.4.1)', () => {
    const { getByText } = render(Message, {
      props: { role: 'user', children: makeBody('hi') },
    });
    expect(getByText('User')).toBeTruthy();
  });

  it('an author override replaces the default visible + accessible label', () => {
    const { getByRole } = render(Message, {
      props: { role: 'assistant', author: 'Claude', children: makeBody('hi') },
    });
    expect(getByRole('listitem', { name: 'Claude message' })).toBeTruthy();
  });

  it('binds the derived --eden-message-* vars into the element inline style', () => {
    const theme = generateTheme(C21_SEED);
    const { getByRole } = render(Message, {
      props: { role: 'user', theme, children: makeBody('styled') },
    });
    const el = getByRole('listitem', { name: 'User message' });
    const tokens = deriveMessageTokens('user', theme);
    expect(el.getAttribute('style')).toContain(`--eden-message-fg: ${tokens.foreground}`);
    expect(el.getAttribute('data-role')).toBe('user');
  });

  it('renders both roles (the bubble mounts for all)', () => {
    for (const role of ROLES) {
      const { getByRole, unmount } = render(Message, {
        props: { role, children: makeBody(`body-${role}`) },
      });
      expect(getByRole('listitem').textContent).toContain(`body-${role}`);
      unmount();
    }
  });
});

function makeBody(text: string): Snippet {
  return createRawSnippet(() => ({ render: () => `<span>${text}</span>` })) as unknown as Snippet;
}
