<script lang="ts">
  import type { GpioState } from '$lib/types/mtib';
  import { mtibObservabilityStore } from '$lib/stores/mtib-observability.svelte';
  import { onMount, onDestroy } from 'svelte';

  let { nodeId }: { nodeId: string } = $props();

  onMount(() => {
    mtibObservabilityStore.subscribe(nodeId, ['gpio']);
  });

  onDestroy(() => {
    mtibObservabilityStore.unsubscribe();
  });

  // Format pin number (P0.00, P0.01, etc.)
  function formatPin(pin: number): string {
    return `P0.${pin.toString().padStart(2, '0')}`;
  }
</script>

<div class="bg-surface-1 border border-surface-2 rounded-lg p-4" aria-live="polite">
  <div class="flex items-center justify-between mb-4">
    <h3 class="text-lg font-semibold text-text-primary">GPIO State</h3>
    {#if mtibObservabilityStore.isConnected}
      <div class="flex items-center gap-2">
        <div class="w-2 h-2 rounded-full bg-success animate-pulse"></div>
        <span class="text-sm text-text-secondary">Live</span>
      </div>
    {/if}
  </div>

  {#if mtibObservabilityStore.error}
    <div class="rounded-md bg-error-muted border border-error p-4">
      <p class="text-sm text-error font-medium">Error</p>
      <p class="text-sm text-text-secondary mt-1">{mtibObservabilityStore.error}</p>
      <button
        class="mt-3 px-3 py-1.5 text-sm font-medium text-error border border-error rounded-md hover:bg-error hover:text-white transition-colors"
        onclick={() => mtibObservabilityStore.subscribe(nodeId, ['gpio'])}
        aria-label="Retry connection"
      >
        Retry
      </button>
    </div>
  {:else if mtibObservabilityStore.gpioStates}
    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
      {#each mtibObservabilityStore.gpioStates as gpio (gpio.pin)}
        <div
          class="flex flex-col items-center justify-center p-3 rounded-md border transition-all duration-150"
          class:bg-success={gpio.value}
          class:border-success={gpio.value}
          class:bg-surface-2={!gpio.value}
          class:border-surface-2={!gpio.value}
          role="status"
          aria-label="{formatPin(gpio.pin)} {gpio.direction} {gpio.value ? 'HIGH' : 'LOW'}"
        >
          <span class="text-xs font-mono font-semibold text-text-primary mb-1">
            {formatPin(gpio.pin)}
          </span>
          <span class="text-2xs font-mono text-text-secondary mb-2">
            {gpio.direction}
          </span>
          <div class="flex items-center gap-1">
            <div
              class="w-3 h-3 rounded-full transition-colors"
              class:bg-white={gpio.value}
              class:bg-text-tertiary={!gpio.value}
              aria-hidden="true"
            ></div>
            <span class="text-xs font-semibold" class:text-white={gpio.value} class:text-text-secondary={!gpio.value}>
              {gpio.value ? 'HIGH' : 'LOW'}
            </span>
          </div>
        </div>
      {/each}
    </div>
  {:else}
    <!-- Loading skeleton -->
    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
      {#each Array(12) as _, i}
        <div class="flex flex-col items-center justify-center p-3 rounded-md border border-surface-2 bg-surface-2 animate-pulse">
          <div class="h-3 w-12 bg-surface-3 rounded mb-1"></div>
          <div class="h-2 w-16 bg-surface-3 rounded mb-2"></div>
          <div class="h-4 w-14 bg-surface-3 rounded"></div>
        </div>
      {/each}
    </div>
  {/if}
</div>
