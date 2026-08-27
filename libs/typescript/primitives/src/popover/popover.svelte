<!--
  @eden/primitives — Popover (ADR-0024 / RD-16 / OD-1).

  A token-driven, accessible popover (a non-modal floating surface anchored to a trigger). The
  BEHAVIOR — anchored positioning (Floating UI), focus management, Escape-to-close, outside-click
  dismissal, focus return to the trigger — is delegated entirely to the bits-ui `Popover` primitive
  (the RD-16/OD-1 ratified behavior layer). The APPEARANCE is decided by `deriveOverlayTokens`
  (overlay/tokens.ts): every color/size/space is a CSS custom property whose value is DERIVED from an
  @eden/theme token. This template carries NO literal color and NO literal px — it references
  `var(--eden-overlay-*)` only.

  THE PORTAL CONTRACT (OD-1): the Content renders into `Popover.Portal` (host `document.body`), so the
  tokens are bound as an inline `style` ON the portaled Content element itself (bits-ui spreads
  `style` onto the rendered node; the `--eden-overlay-*` custom properties inherit to the portaled
  subtree). That seam carries Eden tokens THROUGH the Portal — the a11y lane proves the portaled
  content's computed colors equal the resolved tokens on Chromium AND WebKit.
-->
<script lang="ts">
  import { Popover as BitsPopover } from 'bits-ui';
  import type { Snippet } from 'svelte';
  import type { Theme } from '@eden/theme';
  import { deriveOverlayTokens, overlayStyleVars, defaultOverlayTheme } from '../overlay/tokens.js';

  interface PopoverProps {
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /** Controlled open state (bindable); omit for uncontrolled. */
    open?: boolean;
    /** Open-state change handler. */
    onOpenChange?: (open: boolean) => void;
    /** The trigger content (the control that opens the popover). */
    trigger: Snippet;
    /** The popover body content (rendered inside the floating panel). */
    children: Snippet;
  }

  // onOpenChange defaults to a no-op (see Dialog) so the forwarded value is always a function.
  let {
    theme,
    open = $bindable(false),
    onOpenChange = () => undefined,
    trigger,
    children,
  }: PopoverProps = $props();

  // The popover floats at the dropdown layer (non-modal anchored surface). Reactive re-derivation.
  const resolvedTheme = $derived(theme ?? defaultOverlayTheme());
  const styleVars = $derived(overlayStyleVars(deriveOverlayTokens('dropdown', resolvedTheme)));
</script>

<BitsPopover.Root bind:open {onOpenChange}>
  <BitsPopover.Trigger class="eden-overlay-trigger">
    {@render trigger()}
  </BitsPopover.Trigger>

  <BitsPopover.Portal>
    <BitsPopover.Content
      class="eden-popover-content"
      style={styleVars}
      data-eden-overlay="popover"
      sideOffset={8}
    >
      <div class="eden-popover-body">
        {@render children()}
      </div>
    </BitsPopover.Content>
  </BitsPopover.Portal>
</BitsPopover.Root>

<style>
  /*
    Token-driven, no literals. `:global` is the deliberate scope: the Content is produced INSIDE the
    bits-ui Portal (document.body), so the component-scoped hash is not on it; `eden-popover-content`
    is the stable join key. The panel paints the derived surface and floats at the dropdown z rung.
  */
  :global(.eden-popover-content) {
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
  }

  :global(.eden-popover-body) {
    color: var(--eden-overlay-on-surface);
  }

  :global(.eden-popover-content:focus-visible) {
    outline: 2px solid var(--eden-overlay-on-surface);
    outline-offset: 2px;
  }
</style>
