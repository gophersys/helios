<!--
  @eden/primitives — StatRow (ADR-0024 / doc 17 §4 molecules).

  The Clusters header number-row: a horizontal run of label-over-value pairs (a bold MONO value over
  a small uppercase overline label). Renders a `<dl>` of `<div>`-wrapped `<dt>`(label)/`<dd>`(value)
  pairs — the semantic description-list structure for label→value data, announced as term/definition
  by assistive tech. The value carries `data-value` for testability.

  The APPEARANCE is decided entirely by `deriveStatRowTokens` (stat-row/tokens.ts): every colour/size/
  space is a CSS custom property whose value is DERIVED from an @eden/theme token. This template
  carries NO literal colour and NO literal px — it references `var(--eden-stat-row-*)` only.
-->
<script lang="ts">
  import type { Theme } from '@eden/theme';
  import { defaultButtonTheme } from '../button/tokens.js';
  import { deriveStatRowTokens, statRowStyleVars, type Stat } from './tokens.js';

  interface StatRowProps {
    /** The label-over-value pairs to render (the Clusters totals). */
    stats: readonly Stat[];
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
  }

  let { stats, theme }: StatRowProps = $props();

  const resolvedTheme = $derived(theme ?? defaultButtonTheme());
  const tokens = $derived(deriveStatRowTokens(resolvedTheme));
  const styleVars = $derived(statRowStyleVars(tokens));
</script>

<dl class="eden-stat-row" data-eden-stat-row="" style={styleVars}>
  {#each stats as stat (stat.label)}
    <div class="eden-stat-row-pair">
      <dd class="eden-stat-row-value" data-value={stat.value}>{stat.value}</dd>
      <dt class="eden-stat-row-label">{stat.label}</dt>
    </div>
  {/each}
</dl>

<style>
  /*
    Every value below is a CSS custom property whose VALUE is a derived @eden/theme token (emitted by
    statRowStyleVars). There is NO literal colour and NO literal px here. The value is the prominent
    MONO number; the label is the quiet uppercase overline (the Clusters `.tot` unit).
  */
  .eden-stat-row {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: var(--eden-stat-row-gap);
    margin: 0;
  }

  .eden-stat-row-pair {
    display: flex;
    flex-direction: column;
    gap: var(--eden-stat-row-pair-gap);
  }

  .eden-stat-row-value {
    margin: 0;
    color: var(--eden-stat-row-value);
    font-family: var(--eden-stat-row-value-font-family);
    font-size: var(--eden-stat-row-value-font-size);
    line-height: var(--eden-stat-row-value-line-height);
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }

  .eden-stat-row-label {
    color: var(--eden-stat-row-label);
    font-family: var(--eden-stat-row-label-font-family);
    font-size: var(--eden-stat-row-label-font-size);
    line-height: var(--eden-stat-row-label-line-height);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
</style>
