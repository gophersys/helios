<script lang="ts">
  // The CONTEXT / observability bar — the second status line under the activity bar, modeled on
  // Claude Code's bottom chrome: model · context-window gauge · token usage (↑in ↓out · cache) ·
  // cost · live turns · live tool-uses. Every value updates in REAL TIME off the reducer's meter
  // (turns/tool-uses now tick live, not only at terminal) and the counters FLASH on change. Fully
  // token-driven from the generated @eden/theme.
  import type { Meter } from '$lib/gateway/session.svelte';
  import { formatCost } from '$lib/gateway/session.svelte';
  import type { Theme } from '@eden/theme';

  let { meter }: { meter: Meter; theme?: Theme } = $props();

  // Nominal context window for the gauge (claude family ≈ 200k); the gauge is a proportion, not an
  // enforced limit. "Context used" ≈ the input + cached tokens the conversation carries.
  const CONTEXT_WINDOW = 200_000;
  const contextUsed = $derived(
    meter.inputTokens + meter.cacheReadTokens + meter.cacheCreationTokens,
  );
  const contextPct = $derived(Math.min(100, Math.round((contextUsed / CONTEXT_WINDOW) * 100)));
  const cost = $derived(formatCost(meter.costMicros));

  function compact(n: number): string {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
    return `${n}`;
  }
</script>

<div
  class="contextbar"
  data-testid="agent-context"
  data-turns={meter.turns}
  data-tool-uses={meter.toolUses}
  data-context-pct={contextPct}
  aria-label="agent context and usage"
>
  {#if meter.model}
    <code class="contextbar__model" data-testid="context-model">{meter.model}</code>
  {/if}

  <!-- context-window gauge (animated width) -->
  <div class="contextbar__gauge" title="context window used (nominal)">
    <div class="contextbar__gauge-fill" style="inline-size: {contextPct}%"></div>
    <span class="contextbar__gauge-label" data-testid="context-window">{contextPct}% ctx</span>
  </div>

  <span class="contextbar__sep" aria-hidden="true">·</span>

  <!-- token usage -->
  <span class="contextbar__tokens" title="input / output / cached tokens">
    <span class="up">↑{compact(meter.inputTokens)}</span>
    <span class="down">↓{compact(meter.outputTokens)}</span>
    {#if meter.cacheReadTokens > 0}<span class="cache">⟲{compact(meter.cacheReadTokens)}</span>{/if}
  </span>

  <span class="contextbar__sep" aria-hidden="true">·</span>
  <span class="contextbar__cost" data-testid="context-cost">{cost}</span>

  <span class="contextbar__sep" aria-hidden="true">·</span>
  <!-- live turns + tool-uses: the {#key} blocks replay the flash animation each time the count changes -->
  <span class="contextbar__metric" title="turns">
    <span class="contextbar__icon" aria-hidden="true">⟳</span>
    {#key meter.turns}<span class="flash" data-testid="context-turns">{meter.turns}</span>{/key}
    <span class="contextbar__unit">turns</span>
  </span>
  <span class="contextbar__metric" title="tool uses">
    <span class="contextbar__icon" aria-hidden="true">⚒</span>
    {#key meter.toolUses}<span class="flash" data-testid="context-tools">{meter.toolUses}</span
      >{/key}
    <span class="contextbar__unit">tools</span>
  </span>
</div>

<style>
  .contextbar {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    padding: var(--space-1, 4px) var(--space-3, 12px);
    border-block-start: 1px solid var(--eden-app-line);
    background: var(--eden-app-rail-bg);
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
    font-variant-numeric: tabular-nums;
    overflow-x: auto;
    white-space: nowrap;
  }
  .contextbar__model {
    color: var(--eden-app-fg);
    font-weight: 600;
  }
  .contextbar__gauge {
    position: relative;
    inline-size: 92px;
    block-size: var(--space-4, 16px);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 4px);
    overflow: hidden;
    flex: none;
    display: flex;
    align-items: center;
  }
  .contextbar__gauge-fill {
    position: absolute;
    inset-block: 0;
    inset-inline-start: 0;
    background: color-mix(in oklab, var(--eden-app-accent) 24%, transparent);
    transition: inline-size 360ms cubic-bezier(0.22, 1, 0.36, 1);
  }
  .contextbar__gauge-label {
    position: relative;
    margin-inline: auto;
    font-size: 10px;
    color: var(--eden-app-fg);
  }
  .contextbar__tokens {
    display: inline-flex;
    gap: var(--space-2, 8px);
  }
  .contextbar__tokens .up {
    color: color-mix(in oklab, var(--color-info) 80%, var(--eden-app-fg));
  }
  .contextbar__tokens .down {
    color: var(--eden-app-fg);
  }
  .contextbar__tokens .cache {
    opacity: 0.7;
  }
  .contextbar__cost {
    color: var(--eden-app-fg);
  }
  .contextbar__sep {
    opacity: 0.4;
  }
  .contextbar__metric {
    display: inline-flex;
    align-items: center;
    gap: 3px;
  }
  .contextbar__icon {
    color: var(--eden-app-accent);
  }
  .contextbar__unit {
    opacity: 0.6;
  }
  .flash {
    display: inline-block;
    color: var(--eden-app-fg);
    font-weight: 600;
    animation: contextbar-flash 600ms ease-out;
  }
  @keyframes contextbar-flash {
    0% {
      color: var(--eden-app-accent);
      transform: translateY(-2px) scale(1.25);
    }
    100% {
      color: var(--eden-app-fg);
      transform: none;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .contextbar__gauge-fill {
      transition: none;
    }
    .flash {
      animation: none;
    }
  }
</style>
