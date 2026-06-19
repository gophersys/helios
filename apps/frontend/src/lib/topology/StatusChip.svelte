<script lang="ts">
  // A status pill: glyph + word (+ optional fraction like "1/12"), tinted from the status role token.
  // The third (text) channel makes the status decodable without the legend. Reused by the Scorecard,
  // namespace cards, the drawer and the table.
  import type { Status } from './contract';
  import { STATUS } from './status';
  import StatusGlyph from './StatusGlyph.svelte';

  let {
    status = 'unknown',
    fraction,
    label,
    size = 'sm',
  }: { status?: Status; fraction?: string; label?: string; size?: 'sm' | 'md' } = $props();
  const spec = $derived(STATUS[status]);
</script>

<span class="chip {size}" style="--tint: var({spec.token})">
  <StatusGlyph {status} size={size === 'md' ? 13 : 11} />
  <span class="word">{label ?? spec.label}</span>
  {#if fraction}<span class="frac">{fraction}</span>{/if}
</span>

<style>
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    border-radius: 999px;
    background: color-mix(in oklab, var(--tint) 12%, var(--eden-app-panel-bg));
    border: 1px solid color-mix(in oklab, var(--tint) 35%, transparent);
    color: color-mix(in oklab, var(--tint) 72%, var(--eden-app-fg));
    font-weight: 600;
    white-space: nowrap;
  }
  .sm {
    padding: 1px 8px 1px 6px;
    font-size: 11px;
  }
  .md {
    padding: 3px 11px 3px 8px;
    font-size: 12.5px;
  }
  .word {
    letter-spacing: 0.01em;
  }
  .frac {
    font-family: var(--font-code);
    font-size: 0.85em;
    opacity: 0.85;
  }
</style>
