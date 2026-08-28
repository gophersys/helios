<!--
  @eden/primitives — Divider (ADR-0024 / doc 17 §4 atoms).

  A horizontal/vertical rule, INSET by default (doc 17 §1.6: never a full-bleed page cut). Renders a
  native `<hr>` for the horizontal orientation (the semantic thematic-break element) and a
  `role="separator"` span with `aria-orientation="vertical"` for the vertical one, so the separator
  is announced correctly either way. The `inset={false}` escape hatch exists for the rare full-bleed
  need (a shell chrome edge), but the DEFAULT is inset.

  The APPEARANCE is decided entirely by `deriveDividerTokens` (divider/tokens.ts): the rule colour +
  inset are CSS custom properties whose value is DERIVED from an @eden/theme token. This template
  carries NO literal colour and NO literal px — it references `var(--eden-divider-*)` only.
-->
<script lang="ts">
  import type { Theme } from '@eden/theme';
  import { defaultButtonTheme } from '../button/tokens.js';
  import { deriveDividerTokens, dividerStyleVars, type DividerOrientation } from './tokens.js';

  interface DividerProps {
    /** `horizontal` (a row separator) or `vertical` (a column separator). */
    orientation?: DividerOrientation;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /** Whether the rule is inset off the edges (the DEFAULT; `false` = a deliberate full-bleed edge). */
    inset?: boolean;
  }

  let { orientation = 'horizontal', theme, inset = true }: DividerProps = $props();

  const resolvedTheme = $derived(theme ?? defaultButtonTheme());
  const tokens = $derived(deriveDividerTokens(resolvedTheme));
  const styleVars = $derived(dividerStyleVars(tokens));
</script>

{#if orientation === 'vertical'}
  <span
    class="eden-divider eden-divider-vertical"
    class:inset
    data-eden-divider=""
    data-orientation="vertical"
    role="separator"
    aria-orientation="vertical"
    style={styleVars}
  ></span>
{:else}
  <hr
    class="eden-divider eden-divider-horizontal"
    class:inset
    data-eden-divider=""
    data-orientation="horizontal"
    style={styleVars}
  />
{/if}

<style>
  /*
    Every value below is a CSS custom property whose VALUE is a derived @eden/theme token (emitted by
    dividerStyleVars). There is NO literal colour and NO literal px here (the hairline thickness rides
    a token too). The INSET is the anti-full-bleed default (doc 17 §1.6).
  */
  .eden-divider {
    border: 0;
    background: var(--eden-divider-line);
    flex: none;
  }

  .eden-divider-horizontal {
    block-size: var(--eden-divider-thickness);
    inline-size: auto;
    margin-block: 0;
    margin-inline: 0;
  }

  .eden-divider-horizontal.inset {
    margin-inline: var(--eden-divider-inset);
  }

  .eden-divider-vertical {
    display: inline-block;
    inline-size: var(--eden-divider-thickness);
    block-size: auto;
    align-self: stretch;
  }

  .eden-divider-vertical.inset {
    margin-block: var(--eden-divider-inset);
  }
</style>
