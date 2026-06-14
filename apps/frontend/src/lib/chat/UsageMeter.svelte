<script lang="ts">
  // The live usage + cost meter (REQ-0024 token/cost meter). It renders all four token kinds,
  // the per-model attribution, and the cost from the ledger — updating live as `usage` ticks
  // arrive and reconciling against the authoritative terminal ledger. Numbers are tabular so
  // the meter does not jitter as it streams. This is the point of the demo: SEE the backend
  // accounting move in real time.
  import { formatCost, type Meter } from '$lib/gateway/session.svelte';

  let { meter }: { meter: Meter } = $props();
</script>

<section class="meter panel" aria-label="usage and cost meter">
  <header class="meter__head">
    <span class="eyebrow">usage · cost</span>
    {#if meter.model}
      <span class="chip chip--info" data-testid="meter-model">{meter.model}</span>
    {/if}
  </header>

  <div class="meter__cost" data-testid="meter-cost">{formatCost(meter.costMicros)}</div>

  <dl class="meter__grid">
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
    padding: 1rem 1.1rem;
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
  }
  .meter__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
  }
  .eyebrow {
    font-family: var(--font-code);
    font-size: var(--type-micro);
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
  }
  .meter__cost {
    font-family: var(--font-code);
    font-size: 1.6rem;
    font-weight: 650;
    color: var(--accent);
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.01em;
  }
  .meter__grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.55rem 1rem;
    margin: 0;
  }
  .meter__cell {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.5rem;
    border-bottom: 1px dotted var(--line);
    padding-bottom: 0.25rem;
  }
  .meter__cell dt {
    font-size: var(--type-micro);
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .meter__cell dd {
    margin: 0;
    font-family: var(--font-code);
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--fg);
    font-variant-numeric: tabular-nums;
  }
</style>
