<!--
  @eden/primitives — Tabs (ADR-0024 / RD-16 / OD-1 · doc 17 §4 molecules).

  A token-driven, accessible segmented view-switcher. The BEHAVIOR — the `tablist`/`tab`/`tabpanel`
  ARIA roles, roving arrow-key focus, the selected-tab state, activation, focus management — is
  delegated entirely to the bits-ui `Tabs` primitive (the RD-16/OD-1 ratified behavior layer; NOT a
  new behavior dep). The APPEARANCE is decided by `deriveTabsTokens` (tabs/tokens.ts): every colour/
  size/space is a CSS custom property whose value is DERIVED from an @eden/theme token. This template
  carries NO literal colour and NO literal px — it references `var(--eden-tabs-*)` only.

  Each tab's PANEL body is supplied via the `panel` snippet, which receives the active tab's value —
  so the same Tabs renders any panel content while the a11y contract (one tabpanel per tab, wired to
  bits-ui's keyboard+pointer selection) stays intact.
-->
<script lang="ts">
  import { Tabs as BitsTabs } from 'bits-ui';
  import type { Snippet } from 'svelte';
  import type { Theme } from '@eden/theme';
  import { defaultButtonTheme } from '../button/tokens.js';
  import { deriveTabsTokens, tabsStyleVars, type Tab } from './tokens.js';

  interface TabsProps {
    /** The tabs to render (each a value + label, optionally disabled). */
    tabs: readonly Tab[];
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /** The selected tab value (bindable); defaults to the first tab. */
    value?: string;
    /** Selection-change handler. */
    onValueChange?: (value: string) => void;
    /** An accessible label for the tablist (recommended so the tab group is named). */
    label?: string;
    /** The panel body for the active tab — receives the active tab's `value`. */
    panel: Snippet<[string]>;
  }

  let {
    tabs,
    theme,
    value = $bindable(tabs[0]?.value ?? ''),
    onValueChange = () => undefined,
    label,
    panel,
  }: TabsProps = $props();

  const resolvedTheme = $derived(theme ?? defaultButtonTheme());
  const styleVars = $derived(tabsStyleVars(deriveTabsTokens(resolvedTheme)));
</script>

<BitsTabs.Root bind:value {onValueChange} class="eden-tabs" style={styleVars}>
  <BitsTabs.List class="eden-tabs-list" aria-label={label}>
    {#each tabs as tab (tab.value)}
      <BitsTabs.Trigger value={tab.value} disabled={tab.disabled} class="eden-tabs-trigger">
        {tab.label}
      </BitsTabs.Trigger>
    {/each}
  </BitsTabs.List>

  {#each tabs as tab (tab.value)}
    <BitsTabs.Content value={tab.value} class="eden-tabs-panel">
      {#if value === tab.value}
        {@render panel(tab.value)}
      {/if}
    </BitsTabs.Content>
  {/each}
</BitsTabs.Root>

<style>
  /*
    Every value below is a CSS custom property whose VALUE is a derived @eden/theme token (emitted by
    tabsStyleVars). There is NO literal colour and NO literal px here. `:global` on the bits-rendered
    nodes: bits-ui produces the List/Trigger/Content elements inside its own components, so the
    component-scoped hash is not on them; the namespaced `eden-tabs-*` classes are the stable join key.
  */
  :global(.eden-tabs) {
    display: flex;
    flex-direction: column;
    gap: var(--eden-tabs-gap);
    color: var(--eden-tabs-inactive);
    background: var(--eden-tabs-surface);
    font-family: var(--eden-tabs-font-family);
    font-size: var(--eden-tabs-font-size);
    line-height: var(--eden-tabs-line-height);
  }

  :global(.eden-tabs-list) {
    display: flex;
    gap: var(--eden-tabs-gap);
    /* the tablist rail: a single outline hairline under the row of triggers */
    border-block-end: 1px solid var(--eden-tabs-rail);
  }

  :global(.eden-tabs-trigger) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    box-sizing: border-box;
    /* the tap area never falls below the decoupled 44px AAA floor */
    min-block-size: var(--eden-tabs-hit-target);
    padding-inline: var(--eden-tabs-padding-inline);
    padding-block: var(--eden-tabs-padding-block);

    color: var(--eden-tabs-inactive);
    background: transparent;
    border: 0;
    /* the active indicator lives on the bottom edge; transparent until selected */
    border-block-end: 2px solid transparent;
    /* pull the indicator down onto the list rail so it reads as one underline */
    margin-block-end: -1px;

    font: inherit;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
  }

  /* bits-ui sets data-state="active" on the selected trigger — the active colour + indicator. */
  :global(.eden-tabs-trigger[data-state='active']) {
    color: var(--eden-tabs-active);
    border-block-end-color: var(--eden-tabs-active);
  }

  :global(.eden-tabs-trigger:disabled) {
    cursor: not-allowed;
    opacity: 0.5;
  }

  :global(.eden-tabs-trigger:focus-visible) {
    outline: 2px solid var(--eden-tabs-active);
    outline-offset: 2px;
  }

  :global(.eden-tabs-panel) {
    color: var(--eden-tabs-fg);
  }
</style>
