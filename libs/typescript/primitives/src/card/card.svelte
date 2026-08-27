<!--
  @eden/primitives — Card (ADR-0024 / doc 17 §4 molecules).

  The surface molecule: a panel with optional `header` / `body` / `footer` slots, in a `raised` (the
  `raised` shadow) or `flat` (outlined, no shadow) variant. The radius is EXACTLY the theme's
  `surface` radius and the raised elevation is EXACTLY the theme's `raised` shadow (doc 17 §4's two
  explicit Card rulings). Renders a plain `<section>` (a generic grouping container); a host that
  needs a labelled region passes `aria-label`.

  The APPEARANCE is decided entirely by `deriveCardTokens` (card/tokens.ts): every colour/size/space/
  shadow is a CSS custom property whose value is DERIVED from an @eden/theme token. This template
  carries NO literal colour and NO literal px — it references `var(--eden-card-*)` only.
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { Theme } from '@eden/theme';
  import { defaultButtonTheme } from '../button/tokens.js';
  import { deriveCardTokens, cardStyleVars, type CardVariant } from './tokens.js';

  interface CardProps {
    /** `raised` (the `raised` shadow) or `flat` (an outlined surface, no shadow). */
    variant?: CardVariant;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /** An accessible label for the card region (optional; makes it a labelled landmark when set). */
    'aria-label'?: string;
    /** The header slot — a title row, actions (optional). */
    header?: Snippet;
    /** The body slot — the card's main content (optional; a card may be header/footer only). */
    body?: Snippet;
    /** The footer slot — actions, metadata (optional). */
    footer?: Snippet;
  }

  let {
    variant = 'raised',
    theme,
    'aria-label': ariaLabel,
    header,
    body,
    footer,
  }: CardProps = $props();

  const resolvedTheme = $derived(theme ?? defaultButtonTheme());
  const tokens = $derived(deriveCardTokens(variant, resolvedTheme));
  const styleVars = $derived(cardStyleVars(tokens));
</script>

<section
  class="eden-card"
  data-eden-card=""
  data-variant={variant}
  aria-label={ariaLabel}
  style={styleVars}
>
  {#if header}
    <header class="eden-card-header">{@render header()}</header>
  {/if}
  {#if body}
    <div class="eden-card-body">{@render body()}</div>
  {/if}
  {#if footer}
    <footer class="eden-card-footer">{@render footer()}</footer>
  {/if}
</section>

<style>
  /*
    Every value below is a CSS custom property whose VALUE is a derived @eden/theme token (emitted by
    cardStyleVars). There is NO literal colour and NO literal px here. The radius is the `surface`
    radius and (for the raised variant) the shadow is the `raised` elevation — doc 17 §4.
  */
  .eden-card {
    display: flex;
    flex-direction: column;
    gap: var(--eden-card-gap);

    box-sizing: border-box;
    padding: var(--eden-card-padding);

    color: var(--eden-card-fg);
    background: var(--eden-card-bg);
    border: 1px solid var(--eden-card-border);
    border-radius: var(--eden-card-radius);
    box-shadow: var(--eden-card-shadow);

    font-family: var(--eden-card-font-family);
    font-size: var(--eden-card-font-size);
    line-height: var(--eden-card-line-height);
  }

  .eden-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--eden-card-gap);
    /* the header is set off from the body by the same outline hairline the card edge uses */
    padding-block-end: var(--eden-card-gap);
    border-block-end: 1px solid var(--eden-card-border);
  }

  .eden-card-footer {
    display: flex;
    align-items: center;
    gap: var(--eden-card-gap);
    padding-block-start: var(--eden-card-gap);
    border-block-start: 1px solid var(--eden-card-border);
  }
</style>
