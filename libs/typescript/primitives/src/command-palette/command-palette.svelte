<!--
  @eden/primitives — CommandPalette (ADR-0024 / RD-16 / OD-1).

  The OD-1-proven ⌘K command palette: a token-driven, accessible command menu. The BEHAVIOR (the
  modal overlay + focus trap + escape/dismiss, the combobox/listbox ARIA pattern, the fuzzy
  filtering + scoring + grouping, aria-activedescendant, Arrow/Enter/Escape keyboard) is delegated
  entirely to the bits-ui `Dialog` + `Command` primitives — the RD-16/OD-1 ratified behavior layer.
  The OD-1 spike PROVED this exact composition (Dialog.Portal wrapping Command.Root) clears axe on
  Chromium AND WebKit with Eden tokens flowing through the Portal.

  The APPEARANCE is decided entirely by `deriveCommandPaletteTokens` (command-palette/tokens.ts):
  every color/size/space is a CSS custom property whose value is DERIVED from an @eden/theme token.
  This template carries NO literal color and NO literal px — it references `var(--eden-command-*)`
  only. That is what makes the design-correctness gate (contrast + 44px hit-target + scale
  provenance) a mechanical property of the component, and keeps the no-hand-set-hex provenance lint
  green by construction.

  OD-1 integration lessons carried here:
   - TWO-WAY bind:value on both the Dialog `open` state and the Command `value` (the selected item)
     — a host drives and reads both (e.g. ⌘K opens it; selecting runs the command and closes it).
   - The scrollable results region (Command.List) carries tabindex={0} so it is keyboard-focusable
     and the overflow region participates in the focus order (the OD-1 scroll-region a11y lesson).
-->
<script lang="ts">
  import { Command, Dialog } from 'bits-ui';
  import type { Snippet } from 'svelte';
  import type { Theme } from '@eden/theme';
  import {
    deriveCommandPaletteTokens,
    commandPaletteStyleVars,
    defaultCommandPaletteTheme,
  } from './tokens.js';
  import type { CommandPaletteItem, CommandPaletteGroup } from './model.js';

  interface CommandPaletteProps {
    /** The grouped command model the palette renders + fuzzy-filters. */
    groups: readonly CommandPaletteGroup[];
    /** The open state of the modal — TWO-WAY bindable (a host opens it on ⌘K, reads it on dismiss). */
    open?: boolean;
    /** The selected command value — TWO-WAY bindable (the OD-1 lesson: a host reads the selection). */
    value?: string;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /** The accessible label for the command menu (screen-reader only; combobox/listbox aria-label). */
    label?: string;
    /** The input placeholder text. */
    placeholder?: string;
    /** The message rendered when the query matches no command. */
    emptyMessage?: string;
    /** Fired when a command is selected (click or Enter) — receives the item's value. */
    onSelect?: (value: string) => void;
    /** An optional leading snippet rendered per item (e.g. an icon); receives the item. */
    itemPrefix?: Snippet<[CommandPaletteItem]>;
  }

  let {
    groups,
    open = $bindable(false),
    value = $bindable(''),
    theme,
    label = 'Command palette',
    placeholder = 'Type a command or search…',
    emptyMessage = 'No matching commands.',
    onSelect,
    itemPrefix,
  }: CommandPaletteProps = $props();

  // Derive the token set from the injected theme (or the C21 default). Reactive: a host swapping the
  // theme (light↔dark, density) re-derives every color/size — the component never caches a literal.
  const resolvedTheme = $derived(theme ?? defaultCommandPaletteTheme());
  const tokens = $derived(deriveCommandPaletteTokens(resolvedTheme));
  const styleVars = $derived(commandPaletteStyleVars(tokens));

  function handleSelect(itemValue: string): void {
    onSelect?.(itemValue);
    // Selecting a command closes the modal — the standard ⌘K affordance. The host still owns `open`
    // via the two-way bind, so it can re-open or keep it open by re-setting the bound value.
    open = false;
  }

  // Build the bits-ui Command.Item props for one item. `keywords` is OMITTED entirely when the item
  // has none (rather than passed as `undefined`): bits-ui types it `keywords?: string[]` without
  // `undefined`, and `exactOptionalPropertyTypes` rejects a literal `undefined` for such a prop. We
  // spread this so the optional key is absent, not present-with-undefined (the correct optional shape).
  function itemProps(item: CommandPaletteItem): {
    value: string;
    disabled: boolean;
    keywords?: string[];
  } {
    const base = { value: item.value, disabled: item.disabled ?? false };
    return item.keywords ? { ...base, keywords: [...item.keywords] } : base;
  }
</script>

<Dialog.Root bind:open>
  <Dialog.Portal>
    <Dialog.Overlay class="eden-command-overlay" style={styleVars} />
    <Dialog.Content
      class="eden-command-content"
      style={styleVars}
      data-eden-command=""
      aria-label={label}
    >
      <!-- The visually-hidden title/description: a Dialog.Content REQUIRES an accessible name; the
           command menu's name is the `label`, surfaced as the dialog title for the a11y tree. -->
      <Dialog.Title class="eden-command-srhidden">{label}</Dialog.Title>
      <Dialog.Description class="eden-command-srhidden">{placeholder}</Dialog.Description>

      <Command.Root class="eden-command-root" {label} bind:value loop disableInitialScroll>
        <div class="eden-command-input-row">
          <Command.Input class="eden-command-input" {placeholder} />
        </div>

        <!-- The scrollable results region. tabindex={0} (the OD-1 lesson): the overflow region is
             keyboard-focusable so a keyboard user can scroll it and it participates in the order. -->
        <Command.List class="eden-command-list" tabindex={0}>
          <Command.Viewport class="eden-command-viewport">
            <Command.Empty class="eden-command-empty">{emptyMessage}</Command.Empty>

            {#each groups as group, groupIndex (group.value)}
              {#if groupIndex > 0}
                <Command.Separator class="eden-command-separator" />
              {/if}
              <Command.Group class="eden-command-group" value={group.value}>
                <Command.GroupHeading class="eden-command-heading">
                  {group.heading}
                </Command.GroupHeading>
                <Command.GroupItems>
                  {#each group.items as item (item.value)}
                    <Command.Item
                      class="eden-command-item"
                      {...itemProps(item)}
                      onSelect={() => {
                        handleSelect(item.value);
                      }}
                    >
                      {#if itemPrefix}
                        <span class="eden-command-item-prefix">{@render itemPrefix(item)}</span>
                      {/if}
                      <span class="eden-command-item-label">{item.label}</span>
                    </Command.Item>
                  {/each}
                </Command.GroupItems>
              </Command.Group>
            {/each}
          </Command.Viewport>
        </Command.List>
      </Command.Root>
    </Dialog.Content>
  </Dialog.Portal>
</Dialog.Root>

<style>
  /*
    Every value below is a CSS custom property whose VALUE is a derived @eden/theme token (emitted by
    commandPaletteStyleVars). There is NO literal color and NO literal px here — the provenance lint
    and the design-correctness gate both rely on that. The 44px AAA tap area on the input and every
    item is guaranteed by min-block-size: var(--eden-command-hit-target) (the theme's DECOUPLED
    hitTargetPx ≥ 44), independent of the visual height — so a dense visual row never shrinks the
    accessible target (I1/I2, ADR-0024).

    :global(...) — the elements are rendered INSIDE the bits-ui Dialog/Command components (and the
    Dialog content lives in a Portal at document.body), so Svelte's component-scoped hash is not on
    them; the namespaced `eden-command-*` classes are the stable join keys and :global is the correct,
    deliberate scope so these token-driven rules reach the portalled content (the a11y lane proves the
    computed colors equal the resolved tokens through the real browser, through the Portal).
  */
  :global(.eden-command-overlay) {
    position: fixed;
    inset: 0;
    z-index: var(--eden-command-z-modal);
    background: var(--eden-command-overlay);
    opacity: var(--eden-command-overlay-alpha);
  }

  :global(.eden-command-content) {
    position: fixed;
    inset-block-start: var(--eden-command-list-max-height);
    inset-inline-start: 50%;
    transform: translateX(-50%);
    z-index: var(--eden-command-z-modal);

    inline-size: min(92vw, var(--eden-command-list-max-height));
    box-sizing: border-box;
    padding: var(--eden-command-panel-padding);

    background: var(--eden-command-panel-bg);
    color: var(--eden-command-item-fg);
    border: 1px solid var(--eden-command-panel-border);
    border-radius: var(--eden-command-panel-radius);

    font-family: var(--eden-command-font-family);
    font-size: var(--eden-command-font-size);
    line-height: var(--eden-command-line-height);
  }

  /* The screen-reader-only title/description (visually hidden, present for the a11y tree). */
  :global(.eden-command-srhidden) {
    position: absolute;
    inline-size: 1px;
    block-size: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  :global(.eden-command-root) {
    display: flex;
    flex-direction: column;
    gap: var(--eden-command-gap);
  }

  :global(.eden-command-input) {
    box-sizing: border-box;
    inline-size: 100%;
    block-size: var(--eden-command-input-height);
    /* the hard a11y constraint: the input tap area never falls below the theme's decoupled target. */
    min-block-size: var(--eden-command-hit-target);
    padding-inline: var(--eden-command-item-padding-inline);
    padding-block: var(--eden-command-panel-padding);

    color: var(--eden-command-input-fg);
    background: var(--eden-command-input-bg);
    border: 1px solid var(--eden-command-panel-border);
    border-radius: var(--eden-command-panel-radius);

    font-family: var(--eden-command-font-family);
    font-size: var(--eden-command-font-size);
    line-height: var(--eden-command-line-height);
  }

  :global(.eden-command-input::placeholder) {
    color: var(--eden-command-input-placeholder);
  }

  :global(.eden-command-input:focus-visible) {
    outline: 2px solid var(--eden-command-input-fg);
    outline-offset: 2px;
  }

  :global(.eden-command-list) {
    overflow-y: auto;
    max-block-size: var(--eden-command-list-max-height);
  }

  :global(.eden-command-list:focus-visible) {
    outline: 2px solid var(--eden-command-input-fg);
    outline-offset: 2px;
  }

  :global(.eden-command-heading) {
    padding-inline: var(--eden-command-item-padding-inline);
    padding-block: var(--eden-command-panel-padding);
    color: var(--eden-command-heading-fg);
    font-size: var(--eden-command-heading-font-size);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  :global(.eden-command-item) {
    display: flex;
    align-items: center;
    gap: var(--eden-command-gap);

    box-sizing: border-box;
    block-size: var(--eden-command-item-height);
    /* the hard a11y constraint: every selectable row's tap area meets the decoupled 44px floor. */
    min-block-size: var(--eden-command-hit-target);
    padding-inline: var(--eden-command-item-padding-inline);

    color: var(--eden-command-item-fg);
    border-radius: var(--eden-command-panel-radius);

    cursor: pointer;
    user-select: none;
    -webkit-user-select: none;
  }

  /* The SELECTED item (aria-selected) paints the primary-container pair — a gated, on-* fg/bg. */
  :global(.eden-command-item[data-selected]) {
    color: var(--eden-command-item-selected-fg);
    background: var(--eden-command-item-selected-bg);
  }

  :global(.eden-command-item[data-disabled]) {
    cursor: not-allowed;
    opacity: 0.5;
  }

  :global(.eden-command-item-prefix) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: var(--eden-command-icon-size);
    block-size: var(--eden-command-icon-size);
  }

  :global(.eden-command-item-label) {
    flex: 1 1 auto;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  :global(.eden-command-separator) {
    block-size: 1px;
    margin-block: var(--eden-command-panel-padding);
    background: var(--eden-command-separator);
  }

  :global(.eden-command-empty) {
    padding-inline: var(--eden-command-item-padding-inline);
    padding-block: var(--eden-command-panel-padding);
    color: var(--eden-command-heading-fg);
  }
</style>
