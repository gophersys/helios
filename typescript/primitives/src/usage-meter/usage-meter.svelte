<!--
  @eden/primitives — UsageMeter (ADR-0024 / RD-16). Surfaces an agent run's token usage + cost against
  a budget: a numeric readout and a proportional bar that shifts colour as the budget is approached.
  The APPEARANCE is decided entirely by deriveUsageMeterTokens (usage-meter/tokens.ts) and the meter
  MATH by usageFraction/usageTier/barWidthPercent — every colour/size/space is a CSS custom property
  whose value is DERIVED from an @eden/theme token; this template references var(--eden-usage-meter-*)
  only and carries NO literal colour and NO literal px (the bar width % is a derived value, not a literal).

  Semantics: the bar is a real role="progressbar" with aria-valuenow/min/max and an aria-valuetext that
  speaks the human readout, so assistive tech announces the usage; the tier is conveyed by BOTH colour
  AND the readout text (over budget says so in words — never colour alone, WCAG 1.4.1).
-->
<script lang="ts">
  import type { Theme } from '@eden/theme';
  import { generateTheme, C21_SEED } from '@eden/theme';
  import {
    deriveUsageMeterTokens,
    usageMeterStyleVars,
    usageFraction,
    usageTier,
    barWidthPercent,
  } from './tokens.js';

  interface UsageMeterProps {
    /** Tokens used so far in the run. */
    used: number;
    /** The token budget for the run. */
    budget: number;
    /** An optional human cost readout (e.g. `$0.42`) rendered as the caption detail. */
    cost?: string;
    /** A unit word for the readout (defaults to `tokens`). */
    unit?: string;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
  }

  let { used, budget, cost, unit = 'tokens', theme }: UsageMeterProps = $props();

  const resolvedTheme = $derived(theme ?? generateTheme(C21_SEED));
  const fraction = $derived(usageFraction(used, budget));
  const tier = $derived(usageTier(fraction));
  const tokens = $derived(deriveUsageMeterTokens(tier, resolvedTheme));
  const styleVars = $derived(usageMeterStyleVars(tokens));
  const fillWidth = $derived(barWidthPercent(fraction));
  const percentLabel = $derived(`${String(Math.round(fraction * 100))}%`);
  const tierWord = $derived(
    tier === 'over' ? 'over budget' : tier === 'near' ? 'near budget' : 'within budget',
  );
  const valueText = $derived(
    `${String(used)} of ${String(budget)} ${unit} (${percentLabel}, ${tierWord})`,
  );
</script>

<!-- role="group" (not a <section> landmark) so multiple meters on a page do not collide as
     non-unique landmarks; the group is named, and the progressbar carries its OWN accessible name. -->
<div
  class="eden-usage-meter"
  data-eden-usage-meter=""
  data-tier={tier}
  role="group"
  aria-label="Usage and cost"
  style={styleVars}
>
  <div class="eden-usage-meter-readout">
    <span class="eden-usage-meter-primary">{used} / {budget} {unit}</span>
    <span class="eden-usage-meter-tier">{tierWord}</span>
  </div>
  <div
    class="eden-usage-meter-track"
    role="progressbar"
    aria-label="Token usage"
    aria-valuenow={Math.round(fraction * 100)}
    aria-valuemin={0}
    aria-valuemax={100}
    aria-valuetext={valueText}
  >
    <div class="eden-usage-meter-fill" style={`inline-size: ${fillWidth};`}></div>
  </div>
  {#if cost}
    <span class="eden-usage-meter-cost">{cost}</span>
  {/if}
</div>

<style>
  .eden-usage-meter {
    display: flex;
    flex-direction: column;
    gap: var(--eden-usage-meter-gap);
    box-sizing: border-box;
    padding: var(--eden-usage-meter-padding);
    border-radius: var(--eden-usage-meter-radius);
    color: var(--eden-usage-meter-fg);
    background: var(--eden-usage-meter-bg);
    border: 1px solid var(--eden-usage-meter-track);
    font-size: var(--eden-usage-meter-readout-size);
    line-height: var(--eden-usage-meter-readout-line-height);
    font-family: var(--eden-usage-meter-readout-family);
  }

  .eden-usage-meter-readout {
    display: flex;
    justify-content: space-between;
    gap: var(--eden-usage-meter-gap);
  }

  .eden-usage-meter-primary {
    font-weight: 600;
  }

  /* The tier word carries the fill accent AND the word — colour is never the only signal. */
  .eden-usage-meter-tier {
    color: var(--eden-usage-meter-fill);
    font-weight: 600;
  }

  .eden-usage-meter-track {
    inline-size: 100%;
    block-size: var(--eden-usage-meter-track-height);
    background: var(--eden-usage-meter-track);
    border-radius: var(--eden-usage-meter-radius);
    overflow: hidden;
  }

  .eden-usage-meter-fill {
    block-size: 100%;
    background: var(--eden-usage-meter-fill);
    /* inline-size is the derived bar-width percentage (a computed value, not a literal). */
  }

  .eden-usage-meter-cost {
    font-size: var(--eden-usage-meter-caption-size);
    opacity: 0.85;
  }
</style>
