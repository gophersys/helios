/**
 * Input/Textarea — unit + component render (the application-logic correctness dimension, ADR-0024).
 *
 * Two layers: (1) the pure token-derivation contract (deriveInputTokens / inputStyleVars) asserted
 * directly, and (2) the REAL Svelte 5 components rendered through @testing-library/svelte in jsdom —
 * proving the native field mounts with the right role, the derived `--eden-input-*` vars reach the
 * element, two-way `bind:value` flows, `invalid` sets aria-invalid + the data-invalid hook, and the
 * Field wiring hooks (id / aria-describedby) pass through. The browser-level a11y + keyboard proof is
 * the separate Playwright lane (tests-a11y).
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { generateTheme, C21_SEED } from '@eden/theme';
import Input from './input.svelte';
import Textarea from './textarea.svelte';
import { deriveInputTokens, inputStyleVars } from './tokens.js';

describe('deriveInputTokens — the pure derivation contract', () => {
  const theme = generateTheme(C21_SEED);

  it('selects the text-field role set: on-surface text, surface fill, outline border', () => {
    const t = deriveInputTokens(theme);
    expect(t.foregroundOklch).toEqual(theme.roles.onSurface.value);
    expect(t.backgroundOklch).toEqual(theme.roles.surface.value);
    expect(t.borderOklch).toEqual(theme.roles.outline.value);
  });

  it('the invalid border is the error role, distinct from the resting outline', () => {
    const t = deriveInputTokens(theme);
    expect(t.borderInvalidOklch).toEqual(theme.roles.error.value);
    expect(t.borderInvalid).not.toBe(t.border);
  });

  it('the placeholder is the outline role (muted, gate-checked separately in the design lane)', () => {
    const t = deriveInputTokens(theme);
    expect(t.placeholderOklch).toEqual(theme.roles.outline.value);
  });

  it('derives the geometry from controlGeometry (height, symmetric inset, hit target)', () => {
    const t = deriveInputTokens(theme);
    const g = theme.controlGeometry;
    expect(t.heightPx).toBe(g.componentHeightPx);
    expect(t.paddingInlinePx).toBe(g.insetPx);
    expect(t.paddingBlockPx).toBe(g.insetPx);
    expect(t.hitTargetPx).toBe(g.hitTargetPx);
  });

  it('font family falls back to `inherit` when the typography list is empty (fully total)', () => {
    const noType = { ...theme, typography: [] };
    expect(deriveInputTokens(noType).fontFamily).toBe('inherit');
  });

  it('font family falls back to the first typography role when there is no `body` role', () => {
    const noBody = { ...theme, typography: theme.typography.filter((r) => r.name !== 'body') };
    expect(deriveInputTokens(noBody).fontFamily).toBe(noBody.typography[0]!.fontFamily);
  });

  it('dark mode flips the derived text foreground (the derivation forwards options)', () => {
    const light = deriveInputTokens(generateTheme(C21_SEED, { mode: 'light' }));
    const dark = deriveInputTokens(generateTheme(C21_SEED, { mode: 'dark' }));
    expect(dark.foreground).not.toBe(light.foreground);
  });
});

describe('inputStyleVars — the CSS custom-property emission', () => {
  const tokens = deriveInputTokens(generateTheme(C21_SEED));

  it('emits the EXACT complete declaration string — every var name mapped to its own token', () => {
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-input-fg: ${tokens.foreground};`,
      `--eden-input-bg: ${tokens.background};`,
      `--eden-input-border: ${tokens.border};`,
      `--eden-input-border-invalid: ${tokens.borderInvalid};`,
      `--eden-input-placeholder: ${tokens.placeholder};`,
      `--eden-input-hit-target: ${px(tokens.hitTargetPx)};`,
      `--eden-input-height: ${px(tokens.heightPx)};`,
      `--eden-input-padding-inline: ${px(tokens.paddingInlinePx)};`,
      `--eden-input-padding-block: ${px(tokens.paddingBlockPx)};`,
      `--eden-input-font-size: ${px(tokens.fontSizePx)};`,
      `--eden-input-line-height: ${px(tokens.lineHeightPx)};`,
      `--eden-input-font-family: ${tokens.fontFamily};`,
    ].join(' ');
    expect(inputStyleVars(tokens)).toBe(expected);
  });

  it('every dimension var carries the px unit (a dropped/mutated unit is caught)', () => {
    const css = inputStyleVars(tokens);
    for (const name of [
      'hit-target',
      'height',
      'padding-inline',
      'padding-block',
      'font-size',
      'line-height',
    ]) {
      expect(css).toMatch(new RegExp(`--eden-input-${name}: \\d+px;`));
    }
  });

  it('the color vars carry oklch(...) values and there is no hex literal anywhere', () => {
    const css = inputStyleVars(tokens);
    expect(css).toContain('--eden-input-fg: oklch(');
    expect(css).toContain('--eden-input-bg: oklch(');
    expect(css).toContain('--eden-input-border-invalid: oklch(');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});

describe('Input.svelte — the real native field (token binding + a11y states)', () => {
  it('renders a real <input> with role "textbox" and the standalone aria-label name', () => {
    const { getByRole } = render(Input, {
      props: { 'aria-label': 'Email address', placeholder: 'you@example.com' },
    });
    const el = getByRole('textbox', { name: 'Email address' }) as HTMLInputElement;
    expect(el.tagName).toBe('INPUT');
    expect(el.placeholder).toBe('you@example.com');
  });

  it('binds the derived --eden-input-* vars into the element inline style', () => {
    const theme = generateTheme(C21_SEED);
    const { getByRole } = render(Input, { props: { 'aria-label': 'Name', theme } });
    const el = getByRole('textbox', { name: 'Name' });
    const tokens = deriveInputTokens(theme);
    expect(el.getAttribute('style')).toContain(`--eden-input-fg: ${tokens.foreground}`);
    expect(el.getAttribute('style')).toContain(`--eden-input-bg: ${tokens.background}`);
  });

  it('the invalid state sets aria-invalid and the data-invalid styling hook', () => {
    const { getByRole } = render(Input, { props: { 'aria-label': 'Code', invalid: true } });
    const el = getByRole('textbox', { name: 'Code' });
    expect(el.getAttribute('aria-invalid')).toBe('true');
    expect(el.hasAttribute('data-invalid')).toBe(true);
  });

  it('a valid (default) field has NO aria-invalid and NO data-invalid hook', () => {
    const { getByRole } = render(Input, { props: { 'aria-label': 'Plain' } });
    const el = getByRole('textbox', { name: 'Plain' });
    expect(el.getAttribute('aria-invalid')).toBeNull();
    expect(el.hasAttribute('data-invalid')).toBe(false);
  });

  it('forwards disabled to the native element (the rendered input is disabled)', () => {
    const { getByRole } = render(Input, { props: { 'aria-label': 'Off', disabled: true } });
    const el = getByRole('textbox', { name: 'Off' }) as HTMLInputElement;
    expect(el.disabled).toBe(true);
  });

  it('passes through id + aria-describedby (the Field wiring hooks)', () => {
    const { getByRole } = render(Input, {
      props: { 'aria-label': 'Wired', id: 'fld-1', 'aria-describedby': 'err-1' },
    });
    const el = getByRole('textbox', { name: 'Wired' });
    expect(el.id).toBe('fld-1');
    expect(el.getAttribute('aria-describedby')).toBe('err-1');
  });

  it('reflects an initial bound value', () => {
    const { getByRole } = render(Input, { props: { 'aria-label': 'Pre', value: 'hello' } });
    expect((getByRole('textbox', { name: 'Pre' }) as HTMLInputElement).value).toBe('hello');
  });
});

describe('Textarea.svelte — the real native multi-line field (shares the Input tokens)', () => {
  it('renders a real <textarea> with role "textbox", the rows attribute, and the aria-label', () => {
    const { getByRole } = render(Textarea, {
      props: { 'aria-label': 'Message', rows: 5, placeholder: 'Type…' },
    });
    const el = getByRole('textbox', { name: 'Message' }) as HTMLTextAreaElement;
    expect(el.tagName).toBe('TEXTAREA');
    expect(el.rows).toBe(5);
    expect(el.placeholder).toBe('Type…');
  });

  it('binds the SAME derived --eden-input-* vars (one concept, one home with Input)', () => {
    const theme = generateTheme(C21_SEED);
    const { getByRole } = render(Textarea, { props: { 'aria-label': 'Body', theme } });
    const el = getByRole('textbox', { name: 'Body' });
    const tokens = deriveInputTokens(theme);
    expect(el.getAttribute('style')).toContain(`--eden-input-bg: ${tokens.background}`);
  });

  it('the invalid state sets aria-invalid and the data-invalid styling hook', () => {
    const { getByRole } = render(Textarea, { props: { 'aria-label': 'Bad', invalid: true } });
    const el = getByRole('textbox', { name: 'Bad' });
    expect(el.getAttribute('aria-invalid')).toBe('true');
    expect(el.hasAttribute('data-invalid')).toBe(true);
  });

  it('forwards disabled and passes through id + aria-describedby (the Field wiring hooks)', () => {
    const { getByRole } = render(Textarea, {
      props: { 'aria-label': 'W', disabled: true, id: 'ta-1', 'aria-describedby': 'err-2' },
    });
    const el = getByRole('textbox', { name: 'W' }) as HTMLTextAreaElement;
    expect(el.disabled).toBe(true);
    expect(el.id).toBe('ta-1');
    expect(el.getAttribute('aria-describedby')).toBe('err-2');
  });
});
