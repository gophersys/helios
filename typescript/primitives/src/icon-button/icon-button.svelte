<!--
  @eden/primitives — IconButton (ADR-0024 / RD-16 / OD-1).

  A token-driven, accessible icon-only button — a SQUARE Button whose content is a single glyph.
  The BEHAVIOR is delegated to the bits-ui `Button` primitive (the RD-16/OD-1 ratified behavior
  layer). The APPEARANCE is decided entirely by `deriveIconButtonTokens` (icon-button/tokens.ts):
  every color/size is a CSS custom property whose value is DERIVED from an @eden/theme token. This
  template carries NO literal color and NO literal px — it references `var(--eden-icon-button-*)`
  only, which keeps the design-correctness gate (contrast + 44px hit-target + scale provenance)
  mechanical and the no-hand-set-hex provenance lint green by construction.

  ACCESSIBILITY: an icon-only control has no visible text, so a `label` is REQUIRED and bound to
  `aria-label` — the accessible name the screen reader announces and the axe `button-name` rule
  asserts. The square visual box never shrinks the tap area below the theme's 44px AAA hit target.
-->
<script lang="ts">
  import { Button as BitsButton } from 'bits-ui';
  import type { Snippet } from 'svelte';
  import type { Theme } from '@eden/theme';
  import type { ButtonVariant } from '../button/tokens.js';
  import { defaultButtonTheme } from '../button/tokens.js';
  import { deriveIconButtonTokens, iconButtonStyleVars } from './tokens.js';

  interface IconButtonProps {
    /** The accessible name — REQUIRED (an icon-only control has no visible text). Sets aria-label. */
    label: string;
    /** The visual variant — a SELECTION of a theme role pair (primary / secondary / ghost / danger). */
    variant?: ButtonVariant;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /** Disabled state — forwarded to the bits-ui primitive (sets aria-disabled + blocks activation). */
    disabled?: boolean;
    /** A `type` for the rendered <button> (defaults to "button" — never an accidental form submit). */
    type?: 'button' | 'submit' | 'reset';
    /** The activation handler. */
    onclick?: (event: MouseEvent) => void;
    /** The icon glyph (an inline SVG snippet). */
    children: Snippet;
  }

  let {
    label,
    variant = 'primary',
    theme,
    disabled = false,
    type = 'button',
    onclick,
    children,
  }: IconButtonProps = $props();

  const resolvedTheme = $derived(theme ?? defaultButtonTheme());
  const tokens = $derived(deriveIconButtonTokens(variant, resolvedTheme));
  const styleVars = $derived(iconButtonStyleVars(tokens));
</script>

<BitsButton.Root
  {type}
  {disabled}
  {onclick}
  aria-label={label}
  data-eden-icon-button=""
  data-variant={variant}
  class="eden-icon-button"
  style={styleVars}
>
  {@render children()}
</BitsButton.Root>

<style>
  /*
    Every value below is a CSS custom property whose VALUE is a derived @eden/theme token (emitted by
    iconButtonStyleVars). There is NO literal color and NO literal px here. The square edge is the
    visual component height; the 44px AAA tap area is guaranteed by min-block-size/min-inline-size:
    var(--eden-icon-button-hit-target) (the theme's DECOUPLED hitTargetPx ≥ 44), independent of the
    visual size — so a dense visual box never shrinks the accessible target (I1/I2, ADR-0024).

    `:global(.eden-icon-button)` — the element is rendered INSIDE the bits-ui component, so Svelte's
    component-scoped hash is not on it; the namespaced class is the stable join key and `:global` is
    the deliberate scope so these token-driven rules reach the rendered button.
  */
  :global(.eden-icon-button) {
    display: inline-flex;
    align-items: center;
    justify-content: center;

    box-sizing: border-box;
    block-size: var(--eden-icon-button-size);
    inline-size: var(--eden-icon-button-size);
    /* the hard a11y constraint: the tap area never falls below the theme's decoupled hit target. */
    min-block-size: var(--eden-icon-button-hit-target);
    min-inline-size: var(--eden-icon-button-hit-target);

    color: var(--eden-icon-button-fg);
    background: var(--eden-icon-button-bg);
    border: 1px solid var(--eden-icon-button-border);
    border-radius: 50%;

    cursor: pointer;
    user-select: none;
    -webkit-user-select: none;
  }

  /* The glyph is sized from the theme's icon-size token (a scale value, not eyeballed). */
  :global(.eden-icon-button :where(svg, img)) {
    inline-size: var(--eden-icon-button-icon-size);
    block-size: var(--eden-icon-button-icon-size);
    display: block;
  }

  :global(.eden-icon-button:disabled) {
    cursor: not-allowed;
    opacity: 0.5;
  }

  /* A visible, high-contrast focus ring keyed off the foreground token (keyboard-operability). */
  :global(.eden-icon-button:focus-visible) {
    outline: 2px solid var(--eden-icon-button-fg);
    outline-offset: 2px;
  }
</style>
