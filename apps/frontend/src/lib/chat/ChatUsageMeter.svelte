<script lang="ts">
  // The live usage + cost meter on the design system: the @eden/primitives UsageMeter progress bar
  // (tokens used against a budget, with the cost readout + a tier accent) over the full four-token
  // breakdown + per-model attribution. It updates live as `usage` ticks arrive and reconciles
  // against the authoritative terminal ledger. This is the point of the demo: SEE the backend
  // accounting move in real time — every value token-driven off the generated @eden/theme.
  import { UsageMeter } from '@eden/primitives';
  import type { Theme } from '@eden/theme';
  import { formatCost, type Meter } from '$lib/gateway/session.svelte';

  let { meter, theme }: { meter: Meter; theme: Theme } = $props();

  // The meter shows total tokens used against a soft display budget so the bar has a proportion to
  // fill (the gateway does not enforce a hard budget in the dev plane). The cost is the integer-
  // micros readout formatted to dollars (no float drift).
  const DISPLAY_BUDGET = 200_000;
  const used = $derived(meter.inputTokens + meter.outputTokens);
  const cost = $derived(formatCost(meter.costMicros));
</script>

<section class="meter" aria-label="usage and cost meter">
  <header class="meter__head">
    <span class="meter__eyebrow">usage · cost</span>
    {#if meter.model}
      <code class="meter__model" data-testid="meter-model">{meter.model}</code>
    {/if}
  </header>

  <UsageMeter {used} budget={DISPLAY_BUDGET} {cost} unit="tokens" {theme} />

  <dl class="meter__grid">
    <div class="meter__cell">
      <dt>cost</dt>
      <dd class="meter__cost" data-testid="meter-cost">{cost}</dd>
    </div>
    <div class="meter__cell">
      <dt>input</dt>
      <dd data-testid="meter-input">{meter.inputTokens.toLocaleString()}</dd>
    </div>
    <div class="meter__cell">
      <dt>output</dt>
      <dd data-testid="meter-output">{meter.outputTokens.toLocaleString()}</dd>
    </div>
    <div class="meter__cell">
      <dt>cache read</dt>
      <dd>{meter.cacheReadTokens.toLocaleString()}</dd>
    </div>
    <div class="meter__cell">
      <dt>cache write</dt>
      <dd>{meter.cacheCreationTokens.toLocaleString()}</dd>
    </div>
    <div class="meter__cell">
      <dt>turns</dt>
      <dd>{meter.turns.toLocaleString()}</dd>
    </div>
    <div class="meter__cell">
      <dt>tool uses</dt>
      <dd>{meter.toolUses.toLocaleString()}</dd>
    </div>
  </dl>
</section>

<style>
  .meter {
    display: flex;
    flex-direction: column;
    gap: var(--space-3, 12px);
    padding: var(--space-4, 16px);
    border-radius: var(--eden-app-radius, 8px);
    background: var(--eden-app-panel-bg);
    border: 1px solid var(--eden-app-panel-line);
  }
  .meter__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2, 8px);
  }
  .meter__eyebrow {
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--eden-app-muted);
  }
  .meter__model {
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    color: var(--color-primary);
  }
  .meter__grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-2, 8px) var(--space-4, 16px);
    margin: 0;
  }
  .meter__cell {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-2, 8px);
    border-block-end: 1px dotted var(--eden-app-line);
    padding-block-end: var(--space-1, 4px);
  }
  .meter__cell dt {
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .meter__cell dd {
    margin: 0;
    font-family: var(--font-code);
    font-size: var(--font-size-label, 13px);
    font-weight: 600;
    color: var(--eden-app-fg);
    font-variant-numeric: tabular-nums;
  }
  .meter__cell dd.meter__cost {
    color: var(--color-primary);
  }
</style>
