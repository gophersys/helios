<!--
  @eden/primitives — Chip (ADR-0024 / doc 17 §4 atoms).

  The MONO data chip the Clusters north star reads — an id, a count, a path, a resource name in the
  monospace voice. The `removable` variant carries an inline remove affordance (the filter-chip
  pattern): a real `<button>` (the bits-ui Button behavior layer) with an accessible name, sized to
  the 44px AAA tap floor, firing `onRemove`. The `default` variant is a static data pill.

  The APPEARANCE is decided entirely by `deriveChipTokens` (chip/tokens.ts): every colour/size/space
  is a CSS custom property whose value is DERIVED from an @eden/theme token via the shared
  surface-tokens/chat-surface vocabulary. This template carries NO literal colour and NO literal px —
  it references `var(--eden-chip-*)` only.
-->
<script lang="ts">
  import { Button as BitsButton } from 'bits-ui';
  import type { Snippet } from 'svelte';
  import type { Theme } from '@eden/theme';
  import { defaultButtonTheme } from '../button/tokens.js';
  import { deriveChipTokens, chipStyleVars, type ChipVariant } from './tokens.js';

  interface ChipProps {
    /** `default` (static data chip) or `removable` (renders an inline remove control). */
    variant?: ChipVariant;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /**
     * The accessible label for the remove control (removable variant), e.g. "Remove namespace filter".
     * Required for the removable variant so the control has a real accessible name (never an icon
     * alone). Ignored for the default variant.
     */
    removeLabel?: string;
    /** Fired when the remove control is activated (removable variant). */
    onRemove?: () => void;
    /** The chip content — the mono datum (id / count / path). */
    children: Snippet;
  }

  let {
    variant = 'default',
    theme,
    removeLabel = 'Remove',
    onRemove,
    children,
  }: ChipProps = $props();

  const resolvedTheme = $derived(theme ?? defaultButtonTheme());
  const tokens = $derived(deriveChipTokens(resolvedTheme));
  const styleVars = $derived(chipStyleVars(tokens));
</script>

<span class="eden-chip" data-eden-chip="" data-variant={variant} style={styleVars}>
  <span class="eden-chip-data">{@render children()}</span>
  {#if variant === 'removable'}
    <BitsButton.Root
      type="button"
      class="eden-chip-remove"
      aria-label={removeLabel}
      onclick={() => onRemove?.()}
    >
      <!-- A ×-glyph via CSS (the visible affordance); the accessible name is the aria-label above. -->
      <span aria-hidden="true">&times;</span>
    </BitsButton.Root>
  {/if}
</span>

<style>
  /*
    Every value below is a CSS custom property whose VALUE is a derived @eden/theme token (emitted by
    chipStyleVars). There is NO literal colour and NO literal px here.
  */
  .eden-chip {
    display: inline-flex;
    align-items: center;
    gap: var(--eden-chip-gap);

    box-sizing: border-box;
    padding-inline: var(--eden-chip-padding-inline);
    padding-block: var(--eden-chip-padding-block);

    color: var(--eden-chip-fg);
    background: var(--eden-chip-bg);
    border: 1px solid var(--eden-chip-border);
    border-radius: var(--eden-chip-radius);

    font-family: var(--eden-chip-font-family);
    font-size: var(--eden-chip-font-size);
    line-height: var(--eden-chip-line-height);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }

  .eden-chip-data {
    display: inline-flex;
    align-items: center;
  }

  /*
    The remove control — a real button, sized to the decoupled 44px AAA tap floor (min-*-size), so a
    dense visual chip never shrinks the accessible remove target. `:global` because the element is
    rendered inside the bits-ui Button component (Svelte's component-scoped hash is not on it).
  */
  :global(.eden-chip .eden-chip-remove) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-inline-size: var(--eden-chip-hit-target);
    min-block-size: var(--eden-chip-hit-target);
    /* the visible glyph box is tight; the tap area is the decoupled floor above it */
    inline-size: 1em;
    block-size: 1em;
    margin: 0;
    padding: 0;

    color: inherit;
    background: transparent;
    border: 0;
    border-radius: var(--eden-chip-radius);

    font: inherit;
    line-height: 1;
    cursor: pointer;
  }

  :global(.eden-chip .eden-chip-remove:focus-visible) {
    outline: 2px solid var(--eden-chip-fg);
    outline-offset: 2px;
  }
</style>
