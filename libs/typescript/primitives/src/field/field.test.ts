/**
 * Field — unit + component render (the application-logic correctness dimension, ADR-0024).
 *
 * Two layers: (1) the pure token-derivation contract (deriveFieldTokens / fieldStyleVars) asserted
 * directly, and (2) the REAL Svelte 5 component rendered through @testing-library/svelte — proving
 * the a11y WIRING is correct: the `<label for>` targets the control id, an error links via
 * aria-describedby + marks the control aria-invalid + announces via role="alert", and a valid field
 * renders no error node and leaves the control valid. The control is supplied as a snippet that
 * consumes the wiring props (the same contract Input/Textarea honor).
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { createRawSnippet, type Snippet } from 'svelte';
import { generateTheme, C21_SEED } from '@eden/theme';
import Field from './field.svelte';
import { deriveFieldTokens, fieldStyleVars } from './tokens.js';

/**
 * A control snippet that renders a native <input> consuming the Field's wiring props — exactly the
 * contract Input/Textarea honor (id / aria-describedby / aria-invalid). Lets the test assert the
 * Field's relationship semantics without coupling to the Input component's internals.
 */
interface ControlWiring {
  readonly id: string;
  readonly describedby: string | undefined;
  readonly invalid: boolean;
}

function controlSnippet(): Snippet<[ControlWiring]> {
  return createRawSnippet((props: () => ControlWiring) => {
    const p = props();
    return {
      render: () => {
        const describedby = p.describedby ? ` aria-describedby="${p.describedby}"` : '';
        const invalid = p.invalid ? ` aria-invalid="true"` : '';
        return `<input type="text" id="${p.id}"${describedby}${invalid} />`;
      },
    };
  }) as unknown as Snippet<[ControlWiring]>;
}

describe('deriveFieldTokens — the pure derivation contract', () => {
  const theme = generateTheme(C21_SEED);

  it('selects the label/error/surface roles (on-surface label, error message, surface background)', () => {
    const t = deriveFieldTokens(theme);
    expect(t.labelOklch).toEqual(theme.roles.onSurface.value);
    expect(t.errorOklch).toEqual(theme.roles.error.value);
    expect(t.surfaceOklch).toEqual(theme.roles.surface.value);
  });

  it('derives the label type from the `label` typography role and the gap from the inset', () => {
    const t = deriveFieldTokens(theme);
    const labelRole = theme.typography.find((r) => r.name === 'label')!;
    expect(t.labelFontSizePx).toBe(labelRole.fontSizePx);
    expect(t.labelFontFamily).toBe(labelRole.fontFamily);
    expect(t.gapPx).toBe(theme.controlGeometry.insetPx);
  });

  it('falls back to the body role size when there is no `label` typography role', () => {
    const noLabel = { ...theme, typography: theme.typography.filter((r) => r.name !== 'label') };
    const body = noLabel.typography.find((r) => r.name === 'body')!;
    expect(deriveFieldTokens(noLabel).labelFontSizePx).toBe(body.fontSizePx);
  });

  it('falls back to the control font size + `inherit` family when typography is empty (fully total)', () => {
    const noType = { ...theme, typography: [] };
    const t = deriveFieldTokens(noType);
    expect(t.labelFontSizePx).toBe(theme.controlGeometry.fontSizePx);
    expect(t.labelLineHeightPx).toBe(theme.controlGeometry.lineHeightPx);
    expect(t.labelFontFamily).toBe('inherit');
  });
});

describe('fieldStyleVars — the CSS custom-property emission', () => {
  const tokens = deriveFieldTokens(generateTheme(C21_SEED));

  it('emits the EXACT complete declaration string — every var name mapped to its own token', () => {
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-field-label: ${tokens.label};`,
      `--eden-field-error: ${tokens.error};`,
      `--eden-field-surface: ${tokens.surface};`,
      `--eden-field-gap: ${px(tokens.gapPx)};`,
      `--eden-field-label-font-size: ${px(tokens.labelFontSizePx)};`,
      `--eden-field-label-line-height: ${px(tokens.labelLineHeightPx)};`,
      `--eden-field-label-font-family: ${tokens.labelFontFamily};`,
    ].join(' ');
    expect(fieldStyleVars(tokens)).toBe(expected);
  });

  it('the color vars carry oklch(...) values and there is no hex literal anywhere', () => {
    const css = fieldStyleVars(tokens);
    expect(css).toContain('--eden-field-label: oklch(');
    expect(css).toContain('--eden-field-error: oklch(');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});

describe('Field.svelte — the a11y wiring (label/for, describedby, invalid, role=alert)', () => {
  it('binds the <label for> to the control id (the visible label IS the accessible name)', () => {
    const { getByText, getByRole } = render(Field, {
      props: { label: 'Email', control: controlSnippet() },
    });
    const labelEl = getByText('Email') as HTMLLabelElement;
    const control = getByRole('textbox', { name: 'Email' });
    expect(labelEl.tagName).toBe('LABEL');
    expect(labelEl.getAttribute('for')).toBe(control.id);
    expect(control.id).toBeTruthy();
  });

  it('a VALID field renders no error node and leaves the control valid', () => {
    const { queryByRole, getByRole } = render(Field, {
      props: { label: 'Name', control: controlSnippet() },
    });
    expect(queryByRole('alert')).toBeNull();
    const control = getByRole('textbox', { name: 'Name' });
    expect(control.getAttribute('aria-invalid')).toBeNull();
    expect(control.getAttribute('aria-describedby')).toBeNull();
  });

  it('an ERROR links the message via aria-describedby, marks the control invalid, and announces it', () => {
    const { getByRole } = render(Field, {
      props: { label: 'Code', error: 'Required', control: controlSnippet() },
    });
    const alert = getByRole('alert');
    expect(alert.textContent).toBe('Required');
    const control = getByRole('textbox', { name: 'Code' });
    expect(control.getAttribute('aria-invalid')).toBe('true');
    // the describedby points AT the error message element (the relationship is real, not dangling).
    expect(control.getAttribute('aria-describedby')).toBe(alert.id);
    expect(alert.id).toBeTruthy();
  });

  it('binds the derived --eden-field-* vars into the group inline style', () => {
    const theme = generateTheme(C21_SEED);
    const { getByText } = render(Field, {
      props: { label: 'Styled', theme, control: controlSnippet() },
    });
    const group = getByText('Styled').closest('.eden-field');
    expect(group).not.toBeNull();
    const tokens = deriveFieldTokens(theme);
    expect(group!.getAttribute('style')).toContain(`--eden-field-label: ${tokens.label}`);
    expect(group!.getAttribute('style')).toContain(`--eden-field-error: ${tokens.error}`);
  });

  it('two Fields on a page get DISTINCT ids (no aria-describedby collision)', () => {
    const a = render(Field, { props: { label: 'A', error: 'x', control: controlSnippet() } });
    const b = render(Field, { props: { label: 'B', error: 'y', control: controlSnippet() } });
    const idA = a.getByRole('textbox', { name: 'A' }).id;
    const idB = b.getByRole('textbox', { name: 'B' }).id;
    expect(idA).not.toBe(idB);
  });
});
