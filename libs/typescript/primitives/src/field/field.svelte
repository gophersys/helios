<!--
  @eden/primitives — Field (ADR-0024 / RD-16 / ADR-0004).

  The form Field: a label + control + optional error message, correctly WIRED for accessibility.
  The Field is the a11y composition layer — it generates a stable id, binds the native `<label for>`
  to the control, and, when there is an error, links the message via `aria-describedby` AND marks the
  control `aria-invalid`. The CONTROL is supplied as a snippet that receives the wiring props
  (`{ id, describedby, invalid }`), so the same Field wraps an Input, a Textarea, or any control that
  honors those props — the control stays the ONE home of its own appearance; the Field owns the
  relationship semantics only.

  The APPEARANCE (label color/size, error color, the vertical rhythm) is decided entirely by
  `deriveFieldTokens` (field/tokens.ts): every color/size/space is a CSS custom property whose value
  is DERIVED from an @eden/theme token. This template carries NO literal color and NO literal px — it
  references `var(--eden-field-*)` only, so the design-correctness gate (label + error contrast,
  scale provenance) is mechanical and the no-hand-set-hex provenance lint is green by construction.
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { Theme } from '@eden/theme';
  import { defaultButtonTheme } from '../button/tokens.js';
  import { deriveFieldTokens, fieldStyleVars } from './tokens.js';

  /** The wiring props the Field hands to the control snippet (the accessible relationship). */
  interface FieldControlProps {
    /** The control's element id — the `<label for>` target. */
    readonly id: string;
    /** The error-message element id to set as the control's aria-describedby (when erroring). */
    readonly describedby: string | undefined;
    /** Whether the control is in the invalid state (sets the control's aria-invalid + error border). */
    readonly invalid: boolean;
  }

  interface FieldProps {
    /** The visible label text — bound to the control via `<label for>` (the accessible name). */
    label: string;
    /** The error message; when non-empty the control is marked invalid and described by it. */
    error?: string;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /** A stable id base; defaults to a generated unique id. */
    id?: string;
    /** The control, rendered with the wiring props so it links to this Field's label + error. */
    control: Snippet<[FieldControlProps]>;
  }

  let { label, error, theme, id, control }: FieldProps = $props();

  // A stable, unique id base per component instance — the Svelte 5 `$props.id()` rune (consistent
  // across SSR hydration, no crypto dependency). The control gets `${base}-control` and the error
  // message `${base}-error`, so the `<label for>` and aria-describedby links are exact.
  const uid = $props.id();
  const baseId = $derived(id ?? `eden-field-${uid}`);
  const controlId = $derived(`${baseId}-control`);
  const errorId = $derived(`${baseId}-error`);
  const invalid = $derived(Boolean(error));

  const resolvedTheme = $derived(theme ?? defaultButtonTheme());
  const tokens = $derived(deriveFieldTokens(resolvedTheme));
  const styleVars = $derived(fieldStyleVars(tokens));
</script>

<div class="eden-field" style={styleVars} data-eden-field="">
  <label class="eden-field-label" for={controlId}>{label}</label>

  {@render control({ id: controlId, describedby: invalid ? errorId : undefined, invalid })}

  {#if invalid}
    <p class="eden-field-error" id={errorId} role="alert">{error}</p>
  {/if}
</div>

<style>
  /*
    Every value below is a CSS custom property whose VALUE is a derived @eden/theme token (emitted by
    fieldStyleVars). There is NO literal color and NO literal px here. The vertical rhythm between the
    label, the control, and the error message is a single ramp step (var(--eden-field-gap)).
  */
  .eden-field {
    display: flex;
    flex-direction: column;
    gap: var(--eden-field-gap);
  }

  .eden-field-label {
    color: var(--eden-field-label);
    font-family: var(--eden-field-label-font-family);
    font-size: var(--eden-field-label-font-size);
    line-height: var(--eden-field-label-line-height);
    font-weight: 500;
  }

  .eden-field-error {
    margin: 0;
    color: var(--eden-field-error);
    font-family: var(--eden-field-label-font-family);
    font-size: var(--eden-field-label-font-size);
    line-height: var(--eden-field-label-line-height);
  }
</style>
