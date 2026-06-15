/**
 * PermissionRequest — unit + component render (application-logic correctness, ADR-0024). The pure
 * derivation asserted directly, plus the REAL Svelte 5 component: the prompt mounts with an
 * accessible group label and a heading word (colour is never the only signal), all three actions
 * render as Buttons, and a decision fires the callback.
 */
import { describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/svelte';
import { generateTheme, C21_SEED } from '@eden/theme';
import PermissionRequest from './permission-request.svelte';
import {
  derivePermissionRequestTokens,
  permissionRequestStyleVars,
} from './tokens.js';

describe('derivePermissionRequestTokens — the pure derivation contract', () => {
  const theme = generateTheme(C21_SEED);

  it('the card is the prose container; the heading is the warning state accent', () => {
    const t = derivePermissionRequestTokens(theme);
    expect(t.foregroundOklch).toEqual(theme.roles.onSurface.value);
    expect(t.backgroundOklch).toEqual(theme.roles.surface.value);
    expect(t.headingOklch).toEqual(theme.roles.warning.value);
  });

  it('proportions: title heading, body reason, caption code; hit target 44px', () => {
    const t = derivePermissionRequestTokens(theme);
    const title = theme.typography.find((r) => r.name === 'title')!;
    expect(t.headingSizePx).toBe(title.fontSizePx);
    expect(t.hitTargetPx).toBe(44);
  });
});

describe('permissionRequestStyleVars — the exact emission', () => {
  it('emits the EXACT complete declaration string', () => {
    const tokens = derivePermissionRequestTokens(generateTheme(C21_SEED));
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-permission-request-fg: ${tokens.foreground};`,
      `--eden-permission-request-bg: ${tokens.background};`,
      `--eden-permission-request-border: ${tokens.border};`,
      `--eden-permission-request-heading: ${tokens.headingColor};`,
      `--eden-permission-request-heading-size: ${px(tokens.headingSizePx)};`,
      `--eden-permission-request-heading-line-height: ${px(tokens.headingLineHeightPx)};`,
      `--eden-permission-request-heading-family: ${tokens.headingFontFamily};`,
      `--eden-permission-request-body-size: ${px(tokens.bodySizePx)};`,
      `--eden-permission-request-body-line-height: ${px(tokens.bodyLineHeightPx)};`,
      `--eden-permission-request-body-family: ${tokens.bodyFontFamily};`,
      `--eden-permission-request-code-size: ${px(tokens.codeSizePx)};`,
      `--eden-permission-request-code-family: ${tokens.codeFontFamily};`,
      `--eden-permission-request-padding: ${px(tokens.paddingPx)};`,
      `--eden-permission-request-gap: ${px(tokens.gapPx)};`,
      `--eden-permission-request-action-gap: ${px(tokens.actionGapPx)};`,
      `--eden-permission-request-radius: ${px(tokens.radiusPx)};`,
      `--eden-permission-request-hit-target: ${px(tokens.hitTargetPx)};`,
    ].join(' ');
    expect(permissionRequestStyleVars(tokens)).toBe(expected);
  });
});

describe('PermissionRequest.svelte — the real component', () => {
  it('mounts a labelled group naming the tool, with the heading word and the tool name', () => {
    const { getByRole, getByText } = render(PermissionRequest, {
      props: { tool: 'write_file', reason: 'to save your edits', args: '{"path":"x"}' },
    });
    expect(getByRole('group', { name: 'Permission required to run write_file' })).toBeTruthy();
    expect(getByText('Permission required')).toBeTruthy();
    expect(getByText('write_file')).toBeTruthy();
    expect(getByText('to save your edits')).toBeTruthy();
  });

  it('renders all three actions as Buttons (Allow once / Allow for session / Deny)', () => {
    const { getByRole } = render(PermissionRequest, { props: { tool: 't' } });
    expect(getByRole('button', { name: 'Allow once' })).toBeTruthy();
    expect(getByRole('button', { name: 'Allow for session' })).toBeTruthy();
    expect(getByRole('button', { name: 'Deny' })).toBeTruthy();
  });

  it('fires onDecision with the chosen decision for each action', () => {
    const onDecision = vi.fn();
    const { getByRole } = render(PermissionRequest, { props: { tool: 't', onDecision } });
    (getByRole('button', { name: 'Allow once' }) as HTMLButtonElement).click();
    (getByRole('button', { name: 'Allow for session' }) as HTMLButtonElement).click();
    (getByRole('button', { name: 'Deny' }) as HTMLButtonElement).click();
    expect(onDecision).toHaveBeenNthCalledWith(1, 'allow-once');
    expect(onDecision).toHaveBeenNthCalledWith(2, 'allow-session');
    expect(onDecision).toHaveBeenNthCalledWith(3, 'deny');
  });

  it('omits the reason + code block when not supplied', () => {
    const { container } = render(PermissionRequest, { props: { tool: 't' } });
    expect(container.querySelector('.eden-permission-request-reason')).toBeNull();
    expect(container.querySelector('.eden-permission-request-args')).toBeNull();
  });

  it('binds the derived --eden-permission-request-* vars into the element inline style', () => {
    const theme = generateTheme(C21_SEED);
    const { getByRole } = render(PermissionRequest, { props: { tool: 't', theme } });
    const tokens = derivePermissionRequestTokens(theme);
    expect(getByRole('group', { name: /Permission required/ }).getAttribute('style')).toContain(
      `--eden-permission-request-heading: ${tokens.headingColor}`,
    );
  });
});
