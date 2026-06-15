<!--
  @eden/primitives — DropdownMenu (ADR-0024 / RD-16 / OD-1).

  A token-driven, accessible dropdown menu. The BEHAVIOR — the `menu`/`menuitem` ARIA roles, roving
  arrow-key navigation, typeahead, Escape-to-close, outside-click dismissal, focus return to the
  trigger — is delegated entirely to the bits-ui `DropdownMenu` primitive (the RD-16/OD-1 ratified
  behavior layer). The APPEARANCE is decided by `deriveOverlayTokens` (overlay/tokens.ts): every
  color/size/space is a CSS custom property whose value is DERIVED from an @eden/theme token. This
  template carries NO literal color and NO literal px — it references `var(--eden-overlay-*)` only.

  THE PORTAL CONTRACT (OD-1): the Content renders into `DropdownMenu.Portal` (host `document.body`),
  so the tokens are bound as an inline `style` ON the portaled Content element; the `--eden-overlay-*`
  custom properties inherit to the menu and every item. The a11y lane proves the portaled menu's
  computed colors equal the resolved tokens — and every item clears the 44px tap floor — on both engines.

  A menu's items are data, not arbitrary markup, so the component takes an `items` array (each a
  `{ label, onSelect, disabled? }`) and renders the bits-ui `Item` for each — keeping the menu's a11y
  contract (one menuitem per row, the selection wired to bits-ui's keyboard+pointer activation) intact.
-->
<script lang="ts">
  import { DropdownMenu as BitsMenu } from 'bits-ui';
  import type { Snippet } from 'svelte';
  import type { Theme } from '@eden/theme';
  import { deriveOverlayTokens, overlayStyleVars, defaultOverlayTheme } from '../overlay/tokens.js';
  import type { DropdownMenuItem } from './types.js';

  interface DropdownMenuProps {
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /** Controlled open state (bindable); omit for uncontrolled. */
    open?: boolean;
    /** Open-state change handler. */
    onOpenChange?: (open: boolean) => void;
    /** The menu rows. */
    items: readonly DropdownMenuItem[];
    /** The trigger content (the control that opens the menu). */
    trigger: Snippet;
  }

  // onOpenChange defaults to a no-op (see Dialog) so the forwarded value is always a function.
  let {
    theme,
    open = $bindable(false),
    onOpenChange = () => undefined,
    items,
    trigger,
  }: DropdownMenuProps = $props();

  // The menu floats at the dropdown layer. Reactive re-derivation when the host swaps the theme.
  const resolvedTheme = $derived(theme ?? defaultOverlayTheme());
  const styleVars = $derived(overlayStyleVars(deriveOverlayTokens('dropdown', resolvedTheme)));
</script>

<BitsMenu.Root bind:open {onOpenChange}>
  <BitsMenu.Trigger class="eden-overlay-trigger">
    {@render trigger()}
  </BitsMenu.Trigger>

  <BitsMenu.Portal>
    <BitsMenu.Content
      class="eden-menu-content"
      style={styleVars}
      data-eden-overlay="dropdown-menu"
      sideOffset={8}
    >
      {#each items as item (item.label)}
        <BitsMenu.Item
          class="eden-menu-item"
          disabled={item.disabled ?? false}
          onSelect={item.onSelect}
        >
          {item.label}
        </BitsMenu.Item>
      {/each}
    </BitsMenu.Content>
  </BitsMenu.Portal>
</BitsMenu.Root>

<style>
  /*
    Token-driven, no literals. `:global` is the deliberate scope: the Content/Items are produced
    INSIDE the bits-ui Portal (document.body); `eden-menu-*` are the stable join keys. Every menu item
    meets the 44px AAA tap floor via min-block-size: var(--eden-overlay-hit-target) — a dense visual
    row never shrinks the accessible target (I1/I2, ADR-0024).
  */
  :global(.eden-menu-content) {
    z-index: var(--eden-overlay-z);
    box-sizing: border-box;
    min-inline-size: var(--eden-overlay-hit-target);
    max-inline-size: 90vw;
    padding: var(--eden-overlay-gap);

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

  :global(.eden-menu-item) {
    display: flex;
    align-items: center;
    box-sizing: border-box;
    min-block-size: var(--eden-overlay-hit-target);
    padding-inline: var(--eden-overlay-padding);

    color: var(--eden-overlay-on-surface);
    background: var(--eden-overlay-surface);
    border-radius: var(--eden-overlay-radius);
    cursor: pointer;
    user-select: none;
    -webkit-user-select: none;
  }

  :global(.eden-menu-item[data-disabled]) {
    cursor: not-allowed;
    opacity: 0.5;
  }

  :global(.eden-menu-item[data-highlighted]),
  :global(.eden-menu-item:focus-visible) {
    outline: 2px solid var(--eden-overlay-on-surface);
    outline-offset: -2px;
  }
</style>
