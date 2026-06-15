<!--
  @eden/primitives — Tooltip (ADR-0024 / RD-16 / OD-1).

  A token-driven, accessible tooltip (a transient label surface on hover/focus). The BEHAVIOR — the
  open delay, hover/focus triggering, the `aria-describedby` wiring, Escape-to-dismiss, pointer-safe
  hoverable content — is delegated entirely to the bits-ui `Tooltip` primitive (the RD-16/OD-1
  ratified behavior layer); we wrap it in `Tooltip.Provider` so a standalone tooltip works without a
  host provider. The APPEARANCE is decided by `deriveOverlayTokens` (overlay/tokens.ts): every
  color/size/space is a CSS custom property whose value is DERIVED from an @eden/theme token. This
  template carries NO literal color and NO literal px — it references `var(--eden-overlay-*)` only.

  THE PORTAL CONTRACT (OD-1): the Content renders into `Tooltip.Portal` (host `document.body`), so the
  tokens are bound as an inline `style` ON the portaled Content element itself; the `--eden-overlay-*`
  custom properties inherit to the portaled subtree. The a11y lane proves the portaled content's
  computed colors equal the resolved tokens — and that the contrast gate holds — on Chromium AND WebKit.
-->
<script lang="ts">
  import { Tooltip as BitsTooltip } from 'bits-ui';
  import type { Snippet } from 'svelte';
  import type { Theme } from '@eden/theme';
  import { deriveOverlayTokens, overlayStyleVars, defaultOverlayTheme } from '../overlay/tokens.js';

  interface TooltipProps {
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /** Controlled open state (bindable); omit for uncontrolled. */
    open?: boolean;
    /** Open-state change handler. */
    onOpenChange?: (open: boolean) => void;
    /** The open delay, ms (forwarded to the bits-ui provider); defaults to the bits-ui default. */
    delayDuration?: number;
    /** The trigger content (the control the tooltip describes). */
    trigger: Snippet;
    /** The tooltip body content (the transient label). */
    children: Snippet;
  }

  // onOpenChange defaults to a no-op (see Dialog) so the forwarded value is always a function.
  let {
    theme,
    open = $bindable(false),
    onOpenChange = () => undefined,
    delayDuration = 300,
    trigger,
    children,
  }: TooltipProps = $props();

  // The tooltip floats at the highest (tooltip) layer — transient, above dropdowns and modals'
  // anchored siblings. Reactive re-derivation when the host swaps the theme.
  const resolvedTheme = $derived(theme ?? defaultOverlayTheme());
  const styleVars = $derived(overlayStyleVars(deriveOverlayTokens('tooltip', resolvedTheme)));
</script>

<BitsTooltip.Provider {delayDuration}>
  <BitsTooltip.Root bind:open {onOpenChange}>
    <BitsTooltip.Trigger class="eden-overlay-trigger">
      {@render trigger()}
    </BitsTooltip.Trigger>

    <BitsTooltip.Portal>
      <BitsTooltip.Content
        class="eden-tooltip-content"
        style={styleVars}
        data-eden-overlay="tooltip"
        sideOffset={8}
      >
        {@render children()}
      </BitsTooltip.Content>
    </BitsTooltip.Portal>
  </BitsTooltip.Root>
</BitsTooltip.Provider>

<style>
  /*
    Token-driven, no literals. `:global` is the deliberate scope: the Content is produced INSIDE the
    bits-ui Portal (document.body); `eden-tooltip-content` is the stable join key. The label paints
    the derived surface and floats at the tooltip z rung (highest in the ladder).
  */
  :global(.eden-tooltip-content) {
    z-index: var(--eden-overlay-z);
    box-sizing: border-box;
    max-inline-size: 90vw;
    padding-block: var(--eden-overlay-gap);
    padding-inline: var(--eden-overlay-padding);

    color: var(--eden-overlay-on-surface);
    background: var(--eden-overlay-surface);
    border: 1px solid var(--eden-overlay-outline);
    border-radius: var(--eden-overlay-radius);
    box-shadow: var(--eden-overlay-shadow);

    font-family: var(--eden-overlay-font-family);
    font-size: var(--eden-overlay-font-size);
    line-height: var(--eden-overlay-line-height);
  }
</style>
