<script lang="ts">
  // UsageDock — the COMPACT, docked usage + cost widget that replaces the big in-column UsageMeter.
  // It pins to the bottom-right corner (fixed, just under modals) and shows the live session ledger:
  // model · cost in the header, with a collapsible compact breakdown (↑in ↓out · cache · turns ·
  // tools) and a thin context gauge against a nominal 200k window. Collapsed it is a single pill
  // (model · cost). Every value is token-driven off the generated @eden/theme; pointer-events live
  // only on the panel so it never blocks the chat column behind it.
  import type { Meter } from '$lib/gateway/session.svelte';
  import { formatCost } from '$lib/gateway/session.svelte';
  import type { Theme } from '@eden/theme';

  // theme is accepted for parity with the other chat chrome; every visual is token-driven, so it
  // is intentionally unused (the underscore-alias convention used across the chat components).
  let { meter, theme: _theme }: { meter: Meter; theme?: Theme } = $props();

  let expanded = $state(true);

  // Nominal context window for the gauge (claude family ≈ 200k); a proportion, not an enforced
  // limit. "Context used" ≈ the input + cached tokens the conversation carries.
  const CONTEXT_WINDOW = 200_000;
  const contextUsed = $derived(
    meter.inputTokens + meter.cacheReadTokens + meter.cacheCreationTokens,
  );
  const contextPct = $derived(Math.min(100, Math.round((contextUsed / CONTEXT_WINDOW) * 100)));
  const cost = $derived(formatCost(meter.costMicros));
  const cacheTokens = $derived(meter.cacheReadTokens + meter.cacheCreationTokens);

  function compact(n: number): string {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
    return `${n}`;
  }
</script>

<aside
  class="dock"
  class:dock--collapsed={!expanded}
  data-testid="usage-dock"
  data-expanded={expanded}
  data-context-pct={contextPct}
  aria-label="session usage and cost"
>
  <button
    type="button"
    class="dock__head"
    data-testid="usage-dock-toggle"
    aria-expanded={expanded}
    onclick={() => (expanded = !expanded)}
  >
    {#if meter.model}
      <code class="dock__model" data-testid="usage-dock-model">{meter.model}</code>
    {:else}
      <code class="dock__model dock__model--empty">usage</code>
    {/if}
    <span class="dock__sep" aria-hidden="true">·</span>
    <span class="dock__cost" data-testid="usage-dock-cost">{cost}</span>
    <span class="dock__chevron" class:dock__chevron--open={expanded} aria-hidden="true">⌃</span>
  </button>

  {#if expanded}
    <div class="dock__body" data-testid="usage-dock-body">
      <div class="dock__tokens" title="input / output tokens">
        <span class="up">↑{compact(meter.inputTokens)}</span>
        <span class="down">↓{compact(meter.outputTokens)}</span>
        {#if cacheTokens > 0}
          <span class="dock__sep" aria-hidden="true">·</span>
          <span class="cache" title="cache read + write">⟲{compact(cacheTokens)}</span>
        {/if}
      </div>

      <div class="dock__metrics">
        <span class="dock__metric" title="turns">
          <span class="dock__icon" aria-hidden="true">⟳</span>
          <span data-testid="usage-dock-turns">{meter.turns.toLocaleString()}</span>
          <span class="dock__unit">turns</span>
        </span>
        <span class="dock__metric" title="tool uses">
          <span class="dock__icon" aria-hidden="true">⚒</span>
          <span data-testid="usage-dock-tools">{meter.toolUses.toLocaleString()}</span>
          <span class="dock__unit">tools</span>
        </span>
      </div>

      <div class="dock__gauge" title="context window used (nominal 200k)">
        <div class="dock__gauge-fill" style="inline-size: {contextPct}%"></div>
        <span class="dock__gauge-label" data-testid="usage-dock-context">{contextPct}% ctx</span>
      </div>
    </div>
  {/if}
</aside>

<style>
  .dock {
    position: fixed;
    inset-block-end: var(--space-4, 16px);
    inset-inline-end: var(--space-4, 16px);
    z-index: calc(var(--z-modal, 1000) - 1);
    inline-size: 220px;
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
    padding: var(--space-2, 8px) var(--space-3, 12px);
    background: var(--eden-app-panel-bg);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 8px);
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
    font-variant-numeric: tabular-nums;
    pointer-events: auto;
  }
  .dock--collapsed {
    inline-size: auto;
    max-inline-size: 220px;
    padding-block: var(--space-1, 4px);
  }

  .dock__head {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    margin: 0;
    padding: 0;
    border: 0;
    background: none;
    color: inherit;
    font: inherit;
    text-align: start;
    cursor: pointer;
    inline-size: 100%;
  }
  .dock__model {
    color: var(--eden-app-fg);
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .dock__model--empty {
    color: var(--eden-app-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .dock__cost {
    color: var(--color-primary);
    font-weight: 600;
  }
  .dock__chevron {
    margin-inline-start: auto;
    color: var(--eden-app-muted);
    transition: transform 160ms ease-out;
    transform: rotate(180deg);
  }
  .dock__chevron--open {
    transform: rotate(0deg);
    color: var(--eden-app-accent);
  }

  .dock__body {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
    border-block-start: 1px solid var(--eden-app-line);
    padding-block-start: var(--space-2, 8px);
  }
  .dock__tokens {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
  }
  .dock__tokens .up {
    color: color-mix(in oklab, var(--color-info) 80%, var(--eden-app-fg));
  }
  .dock__tokens .down {
    color: var(--eden-app-fg);
  }
  .dock__tokens .cache {
    opacity: 0.7;
  }

  .dock__metrics {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2, 8px);
  }
  .dock__metric {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    color: var(--eden-app-fg);
    font-weight: 600;
  }
  .dock__icon {
    color: var(--eden-app-accent);
    font-weight: 400;
  }
  .dock__unit {
    color: var(--eden-app-muted);
    font-weight: 400;
    opacity: 0.7;
  }

  .dock__gauge {
    position: relative;
    block-size: var(--space-4, 16px);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 4px);
    overflow: hidden;
    display: flex;
    align-items: center;
  }
  .dock__gauge-fill {
    position: absolute;
    inset-block: 0;
    inset-inline-start: 0;
    background: color-mix(in oklab, var(--eden-app-accent) 24%, transparent);
    transition: inline-size 360ms cubic-bezier(0.22, 1, 0.36, 1);
  }
  .dock__gauge-label {
    position: relative;
    margin-inline: auto;
    color: var(--eden-app-fg);
  }

  .dock__sep {
    opacity: 0.4;
  }

  @media (prefers-reduced-motion: reduce) {
    .dock__chevron,
    .dock__gauge-fill {
      transition: none;
    }
  }
</style>
