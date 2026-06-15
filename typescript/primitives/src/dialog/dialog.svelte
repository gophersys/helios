<!--
  @eden/primitives — Dialog (ADR-0024 / RD-16 / OD-1).

  A token-driven, accessible modal dialog. The BEHAVIOR — focus trap, Escape-to-close, the LIFO
  unwind of NESTED dialogs (the OD-1 spike proved nested Dialog/LIFO + ⌘K cleared axe on Chromium
  AND WebKit with Eden tokens through the Portal), the scroll lock, focus return to the trigger — is
  delegated entirely to the bits-ui `Dialog` primitive (the RD-16/OD-1 ratified behavior layer). The
  APPEARANCE is decided by `deriveOverlayTokens` (overlay/tokens.ts): every color/size/space is a CSS
  custom property whose value is DERIVED from an @eden/theme token. This template carries NO literal
  color and NO literal px — it references `var(--eden-overlay-*)` only.

  THE PORTAL CONTRACT (OD-1): the Content (and the scrim Overlay) render into `Dialog.Portal`, whose
  host is `document.body` — OUTSIDE this component's DOM subtree. So the tokens are bound as an inline
  `style` ON the portaled Overlay and Content elements themselves (bits-ui spreads `style` onto the
  rendered node, and the `--eden-overlay-*` custom properties inherit to the whole portaled subtree).
  That is the seam that carries Eden tokens THROUGH the Portal — the half of the OD-1 proof this
  template owns; the a11y lane proves the portaled content's computed colors equal the resolved tokens.
-->
<script lang="ts">
  import { Dialog as BitsDialog } from 'bits-ui';
  import type { Snippet } from 'svelte';
  import type { Theme } from '@eden/theme';
  import { deriveOverlayTokens, overlayStyleVars, defaultOverlayTheme } from '../overlay/tokens.js';

  interface DialogProps {
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /** Controlled open state (bindable); omit for uncontrolled. */
    open?: boolean;
    /** Open-state change handler (fires on every open/close, incl. Escape and outside-click). */
    onOpenChange?: (open: boolean) => void;
    /** The accessible dialog title (rendered into `Dialog.Title`, announced by the SR). */
    title: string;
    /** Optional supporting description (rendered into `Dialog.Description`). */
    description?: string;
    /** The trigger content (the control that opens the dialog). */
    trigger: Snippet;
    /** The dialog body content (rendered inside the focus-trapped panel). */
    children: Snippet;
  }

  // onOpenChange defaults to a no-op so the value forwarded to bits-ui is always a function (under
  // exactOptionalPropertyTypes an explicit `undefined` is not assignable to OnChangeFn<boolean>); a
  // caller's handler replaces it. bind:open still propagates the state to a caller's bound variable.
  let {
    theme,
    open = $bindable(false),
    onOpenChange = () => undefined,
    title,
    description,
    trigger,
    children,
  }: DialogProps = $props();

  // Derive the modal-layer overlay tokens from the injected theme (or the C21 default). Reactive: a
  // host swapping the theme (light↔dark, density) re-derives every color/size — never a cached literal.
  const resolvedTheme = $derived(theme ?? defaultOverlayTheme());
  const styleVars = $derived(overlayStyleVars(deriveOverlayTokens('modal', resolvedTheme)));
</script>

<BitsDialog.Root bind:open {onOpenChange}>
  <BitsDialog.Trigger class="eden-overlay-trigger">
    {@render trigger()}
  </BitsDialog.Trigger>

  <BitsDialog.Portal>
    <!-- The scrim Overlay and the panel Content both carry the token style so they render THROUGH
         the portal with Eden tokens (OD-1). The Overlay paints the derived scrim; the Content the
         derived surface. -->
    <BitsDialog.Overlay class="eden-dialog-overlay" style={styleVars} />
    <BitsDialog.Content class="eden-dialog-content" style={styleVars} data-eden-overlay="dialog">
      <BitsDialog.Title class="eden-dialog-title">{title}</BitsDialog.Title>
      {#if description}
        <BitsDialog.Description class="eden-dialog-description"
          >{description}</BitsDialog.Description
        >
      {/if}
      <div class="eden-dialog-body">
        {@render children()}
      </div>
      <BitsDialog.Close class="eden-overlay-close" aria-label="Close dialog">×</BitsDialog.Close>
    </BitsDialog.Content>
  </BitsDialog.Portal>
</BitsDialog.Root>

<style>
  /*
    Every value below is a CSS custom property whose VALUE is a derived @eden/theme token (emitted by
    overlayStyleVars and bound onto the portaled element). There is NO literal color and NO literal px
    here. `:global(...)` is the deliberate, correct scope: the Overlay/Content elements are produced
    INSIDE the bits-ui Portal (document.body), so Svelte's component-scoped hash is not on them; the
    namespaced `eden-dialog-*` classes are the stable join keys.

    The 44px AAA tap area on the close control is guaranteed by min-block/inline-size:
    var(--eden-overlay-hit-target) (the theme's DECOUPLED hitTargetPx ≥ 44), independent of the visual
    glyph — a dense visual box never shrinks the accessible target (I1/I2, ADR-0024).
  */
  :global(.eden-dialog-overlay) {
    position: fixed;
    inset: 0;
    z-index: var(--eden-overlay-z);
    background: var(--eden-overlay-scrim);
  }

  :global(.eden-dialog-content) {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    /* one layer above the scrim — the same modal rung, stacked after it in the portal DOM order. */
    z-index: var(--eden-overlay-z);

    box-sizing: border-box;
    min-inline-size: var(--eden-overlay-hit-target);
    max-inline-size: 90vw;
    padding: var(--eden-overlay-padding);

    color: var(--eden-overlay-on-surface);
    background: var(--eden-overlay-surface);
    border: 1px solid var(--eden-overlay-outline);
    border-radius: var(--eden-overlay-radius);
    box-shadow: var(--eden-overlay-shadow);

    font-family: var(--eden-overlay-font-family);
    font-size: var(--eden-overlay-font-size);
    line-height: var(--eden-overlay-line-height);

    display: flex;
    flex-direction: column;
    gap: var(--eden-overlay-gap);
  }

  :global(.eden-dialog-title) {
    margin: 0;
    color: var(--eden-overlay-on-surface);
    font-size: var(--eden-overlay-font-size);
    font-weight: 600;
  }

  :global(.eden-dialog-description) {
    margin: 0;
    color: var(--eden-overlay-on-surface);
  }

  :global(.eden-dialog-body) {
    color: var(--eden-overlay-on-surface);
  }

  :global(.eden-overlay-close) {
    position: absolute;
    top: var(--eden-overlay-gap);
    right: var(--eden-overlay-gap);

    display: inline-flex;
    align-items: center;
    justify-content: center;
    box-sizing: border-box;
    min-block-size: var(--eden-overlay-hit-target);
    min-inline-size: var(--eden-overlay-hit-target);

    color: var(--eden-overlay-on-surface);
    background: var(--eden-overlay-surface);
    border: 1px solid var(--eden-overlay-outline);
    border-radius: var(--eden-overlay-radius);
    cursor: pointer;
  }

  :global(.eden-dialog-content:focus-visible),
  :global(.eden-overlay-close:focus-visible) {
    outline: 2px solid var(--eden-overlay-on-surface);
    outline-offset: 2px;
  }
</style>
