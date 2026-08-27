<!--
  @eden/primitives — Button (ADR-0024 / RD-16 / OD-1).

  A token-driven, accessible button. The BEHAVIOR (focus management, disabled semantics, the
  render-as-link / render-as-button polymorphism, the data-attribute state hooks) is delegated to
  the bits-ui `Button` primitive — the RD-16/OD-1 ratified behavior layer. The APPEARANCE is
  decided entirely by `deriveButtonTokens` (button/tokens.ts): every color/size/space is a CSS
  custom property whose value is DERIVED from an @eden/theme token. This template carries NO literal
  color and NO literal px — it references `var(--eden-button-*)` only. That is what makes the
  design-correctness gate (contrast + 44px hit-target + scale provenance) a mechanical property of
  the component, and what keeps the no-hand-set-hex provenance lint green by construction.
-->
<script lang="ts">
  import { Button as BitsButton } from 'bits-ui';
  import type { Snippet } from 'svelte';
  import type { Theme } from '@eden/theme';
  import {
    deriveButtonTokens,
    buttonStyleVars,
    defaultButtonTheme,
    type ButtonVariant,
  } from './tokens.js';

  interface ButtonProps {
    /** The visual variant — a SELECTION of a theme role pair (primary / secondary / ghost). */
    variant?: ButtonVariant;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /** Disabled state — forwarded to the bits-ui primitive (sets aria-disabled + blocks activation). */
    disabled?: boolean;
    /** A `type` for the rendered <button> (defaults to "button" — never an accidental form submit). */
    type?: 'button' | 'submit' | 'reset';
    /** The activation handler. */
    onclick?: (event: MouseEvent) => void;
    /** The label content. */
    children: Snippet;
  }

  let {
    variant = 'primary',
    theme,
    disabled = false,
    type = 'button',
    onclick,
    children,
  }: ButtonProps = $props();

  // Derive the token set from the injected theme (or the C21 default). Reactive: a host swapping the
  // theme (light↔dark, density) re-derives every color/size — the component never caches a literal.
  const resolvedTheme = $derived(theme ?? defaultButtonTheme());
  const tokens = $derived(deriveButtonTokens(variant, resolvedTheme));
  const styleVars = $derived(buttonStyleVars(tokens));
</script>

<BitsButton.Root
  {type}
  {disabled}
  {onclick}
  data-eden-button=""
  data-variant={variant}
  class="eden-button"
  style={styleVars}
>
  {@render children()}
</BitsButton.Root>

<style>
  /*
    Every value below is a CSS custom property whose VALUE is a derived @eden/theme token (emitted by
    buttonStyleVars). There is NO literal color and NO literal px here — the provenance lint and the
    design-correctness gate both rely on that. The 44px AAA tap area is guaranteed by min-block-size:
    var(--eden-button-hit-target) (the theme's DECOUPLED hitTargetPx ≥ 44), independent of the visual
    height — so a dense visual box never shrinks the accessible target (I1/I2, ADR-0024).

    `:global(.eden-button)` — the element rendered by `<BitsButton.Root class="eden-button">` is
    produced INSIDE the bits-ui component, so Svelte's component-scoped hash is not on it; the
    namespaced `eden-button` class is the stable join key and `:global` is the correct, deliberate
    scope so these token-driven rules reliably reach the rendered button (the a11y lane proves the
    computed colors equal the resolved tokens through the real browser).
  */
  :global(.eden-button) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--eden-button-gap);

    box-sizing: border-box;
    block-size: var(--eden-button-height);
    /* the hard a11y constraint: the tap area never falls below the theme's decoupled hit target. */
    min-block-size: var(--eden-button-hit-target);
    min-inline-size: var(--eden-button-hit-target);
    padding-inline: var(--eden-button-padding-inline);
    padding-block: var(--eden-button-padding-block);

    color: var(--eden-button-fg);
    background: var(--eden-button-bg);
    border: 1px solid var(--eden-button-border);
    border-radius: var(--eden-button-padding-block);

    font-family: var(--eden-button-font-family);
    font-size: var(--eden-button-font-size);
    line-height: var(--eden-button-line-height);
    font-weight: 500;

    cursor: pointer;
    user-select: none;
    -webkit-user-select: none;
  }

  :global(.eden-button:disabled) {
    cursor: not-allowed;
    opacity: 0.5;
  }

  /* A visible, high-contrast focus ring keyed off the foreground token (keyboard-operability). */
  :global(.eden-button:focus-visible) {
    outline: 2px solid var(--eden-button-fg);
    outline-offset: 2px;
  }
</style>
