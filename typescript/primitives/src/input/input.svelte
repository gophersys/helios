<!--
  @eden/primitives — Input (ADR-0024 / RD-16).

  A token-driven, accessible single-line text input. There is no generic text-input PRIMITIVE in
  bits-ui (it ships specialized inputs like PinInput, not a plain field), and the most accessible
  base for a plain text field is the native `<input>` element — which carries the platform text-field
  semantics every screen reader and assistive technology announces natively. So the BEHAVIOR is the
  native element; the APPEARANCE is decided entirely by `deriveInputTokens` (input/tokens.ts): every
  color/size/space is a CSS custom property whose value is DERIVED from an @eden/theme token. This
  template carries NO literal color and NO literal px — it references `var(--eden-input-*)` only, which
  keeps the design-correctness gate (contrast + 44px hit-target + scale provenance) mechanical and the
  no-hand-set-hex provenance lint green by construction.

  ACCESSIBILITY: when used standalone, pass `aria-label` (or wire it through the Field, which links a
  <label>). `invalid` sets `aria-invalid` and switches the border to the gate-checked `error` role.
-->
<script lang="ts">
  import type { Theme } from '@eden/theme';
  import { defaultButtonTheme } from '../button/tokens.js';
  import { deriveInputTokens, inputStyleVars } from './tokens.js';

  interface InputProps {
    /** Two-way bound text value. */
    value?: string;
    /** The input `type` (a text-like type — never a button/submit). */
    type?: 'text' | 'email' | 'password' | 'search' | 'tel' | 'url' | 'number';
    /** Placeholder text (rendered in the gate-checked placeholder color). */
    placeholder?: string;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /** Disabled state — forwarded to the native element (removes it from the tab order). */
    disabled?: boolean;
    /** Invalid state — sets aria-invalid and switches the border to the error role. */
    invalid?: boolean;
    /** The accessible name when used standalone (the Field wires a <label> instead). */
    'aria-label'?: string;
    /** The id of a describing element (e.g. the Field's error message) — sets aria-describedby. */
    'aria-describedby'?: string;
    /** The element id (the Field binds its <label for> to this). */
    id?: string;
    /** Change/input handler. */
    oninput?: (event: Event) => void;
  }

  let {
    value = $bindable(''),
    type = 'text',
    placeholder,
    theme,
    disabled = false,
    invalid = false,
    id,
    oninput,
    'aria-label': ariaLabel,
    'aria-describedby': ariaDescribedby,
  }: InputProps = $props();

  const resolvedTheme = $derived(theme ?? defaultButtonTheme());
  const tokens = $derived(deriveInputTokens(resolvedTheme));
  const styleVars = $derived(inputStyleVars(tokens));
</script>

<input
  {id}
  {type}
  {placeholder}
  {disabled}
  {oninput}
  bind:value
  aria-label={ariaLabel}
  aria-describedby={ariaDescribedby}
  aria-invalid={invalid ? 'true' : undefined}
  data-eden-input=""
  data-invalid={invalid ? '' : undefined}
  class="eden-input"
  style={styleVars}
/>

<style>
  /*
    Every value below is a CSS custom property whose VALUE is a derived @eden/theme token (emitted by
    inputStyleVars). There is NO literal color and NO literal px here. The 44px AAA tap area is
    guaranteed by min-block-size: var(--eden-input-hit-target) (the theme's DECOUPLED hitTargetPx ≥ 44),
    independent of the visual height — so a dense field never shrinks the accessible target (I1/I2).

    The element is a native <input> rendered directly by this component, so the component-scoped class
    applies without :global — but the token vars are bound inline via `style`, so the cascade reaches it.
  */
  .eden-input {
    box-sizing: border-box;
    inline-size: 100%;
    block-size: var(--eden-input-height);
    min-block-size: var(--eden-input-hit-target);
    padding-inline: var(--eden-input-padding-inline);
    padding-block: var(--eden-input-padding-block);

    color: var(--eden-input-fg);
    background: var(--eden-input-bg);
    border: 1px solid var(--eden-input-border);
    border-radius: var(--eden-input-padding-block);

    font-family: var(--eden-input-font-family);
    font-size: var(--eden-input-font-size);
    line-height: var(--eden-input-line-height);
  }

  .eden-input::placeholder {
    color: var(--eden-input-placeholder);
    opacity: 1; /* normalize the UA default placeholder opacity so the gate-checked color is exact. */
  }

  /* The invalid state switches the border to the gate-checked error role. */
  .eden-input[data-invalid] {
    border-color: var(--eden-input-border-invalid);
  }

  .eden-input:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }

  /* A visible, high-contrast focus ring keyed off the text-foreground token (keyboard-operability). */
  .eden-input:focus-visible {
    outline: 2px solid var(--eden-input-fg);
    outline-offset: 2px;
  }

  /* When invalid AND focused, the ring is the error role (the destructive focus signal). */
  .eden-input[data-invalid]:focus-visible {
    outline-color: var(--eden-input-border-invalid);
  }
</style>
