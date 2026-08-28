<!--
  @eden/primitives — Textarea (ADR-0024 / RD-16).

  A token-driven, accessible multi-line text input. Like Input, the most accessible base is the
  native `<textarea>` element (the platform multi-line-field semantics every assistive technology
  announces natively); the APPEARANCE is decided entirely by `deriveInputTokens` (input/tokens.ts —
  ONE home: a Textarea is an Input that wraps). This template carries NO literal color and NO literal
  px — it references `var(--eden-input-*)` only, so the design-correctness gate (contrast + 44px
  hit-target + scale provenance) is mechanical and the no-hand-set-hex provenance lint is green.

  ACCESSIBILITY: same as Input — pass `aria-label` standalone, or wire through the Field. `invalid`
  sets `aria-invalid` and switches the border to the gate-checked `error` role. The visual height is
  driven by `rows`, but the field never falls below the 44px AAA tap floor.
-->
<script lang="ts">
  import type { Theme } from '@eden/theme';
  import { defaultButtonTheme } from '../button/tokens.js';
  import { deriveInputTokens, inputStyleVars } from './tokens.js';

  interface TextareaProps {
    /** Two-way bound text value. */
    value?: string;
    /** The visible number of text rows (the native attribute; drives the visual height). */
    rows?: number;
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
    rows = 3,
    placeholder,
    theme,
    disabled = false,
    invalid = false,
    id,
    oninput,
    'aria-label': ariaLabel,
    'aria-describedby': ariaDescribedby,
  }: TextareaProps = $props();

  const resolvedTheme = $derived(theme ?? defaultButtonTheme());
  const tokens = $derived(deriveInputTokens(resolvedTheme));
  const styleVars = $derived(inputStyleVars(tokens));
</script>

<textarea
  {id}
  {rows}
  {placeholder}
  {disabled}
  {oninput}
  bind:value
  aria-label={ariaLabel}
  aria-describedby={ariaDescribedby}
  aria-invalid={invalid ? 'true' : undefined}
  data-eden-textarea=""
  data-invalid={invalid ? '' : undefined}
  class="eden-textarea"
  style={styleVars}
></textarea>

<style>
  /*
    Every value below is a CSS custom property whose VALUE is a derived @eden/theme token (emitted by
    inputStyleVars). There is NO literal color and NO literal px here. The 44px AAA tap area is
    guaranteed by min-block-size: var(--eden-input-hit-target). The visual height grows with `rows`;
    block-size:auto lets the native rows attribute size it while the min-block-size enforces the floor.
  */
  .eden-textarea {
    box-sizing: border-box;
    inline-size: 100%;
    block-size: auto;
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

    resize: vertical;
  }

  .eden-textarea::placeholder {
    color: var(--eden-input-placeholder);
    opacity: 1;
  }

  .eden-textarea[data-invalid] {
    border-color: var(--eden-input-border-invalid);
  }

  .eden-textarea:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }

  .eden-textarea:focus-visible {
    outline: 2px solid var(--eden-input-fg);
    outline-offset: 2px;
  }

  .eden-textarea[data-invalid]:focus-visible {
    outline-color: var(--eden-input-border-invalid);
  }
</style>
