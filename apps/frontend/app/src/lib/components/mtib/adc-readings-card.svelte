<script lang="ts">
  import type { AdcReading } from '$lib/types/mtib';
  import { mtibObservabilityStore } from '$lib/stores/mtib-observability.svelte';
  import { onMount, onDestroy } from 'svelte';
  import { Download } from 'lucide-svelte';

  let { nodeId, channels }: { nodeId: string; channels?: number[] } = $props();

  // Track min/max values per channel
  let channelStats = $state<Map<number, { min: number; max: number; current: number }>>(new Map());
  let updateCount = $state(0);
  let startTime = $state(Date.now());

  onMount(() => {
    mtibObservabilityStore.subscribe(nodeId, ['adc']);
  });

  onDestroy(() => {
    mtibObservabilityStore.unsubscribe();
  });

  // Update stats when readings change
  $effect(() => {
    if (mtibObservabilityStore.adcReadings) {
      const readings = channels
        ? mtibObservabilityStore.adcReadings.filter(r => channels.includes(r.channel))
        : mtibObservabilityStore.adcReadings;

      readings.forEach(reading => {
        const existing = channelStats.get(reading.channel);
        if (existing) {
          channelStats.set(reading.channel, {
            min: Math.min(existing.min, reading.voltage_v),
            max: Math.max(existing.max, reading.voltage_v),
            current: reading.voltage_v
          });
        } else {
          channelStats.set(reading.channel, {
            min: reading.voltage_v,
            max: reading.voltage_v,
            current: reading.voltage_v
          });
        }
      });

      updateCount++;
    }
  });

  // Format voltage with 3 decimal places
  function formatVoltage(v: number): string {
    return v.toFixed(3);
  }

  // Calculate percentage for progress bar (0-5V range)
  function getPercentage(voltage: number): number {
    return Math.min(100, Math.max(0, (voltage / 5.0) * 100));
  }

  // Export to CSV
  function exportCsv(): void {
    if (!mtibObservabilityStore.adcReadings) return;

    const readings = channels
      ? mtibObservabilityStore.adcReadings.filter(r => channels.includes(r.channel))
      : mtibObservabilityStore.adcReadings;

    const csvRows = ['Channel,Voltage (V),Min (V),Max (V)'];
    readings.forEach(reading => {
      const stats = channelStats.get(reading.channel);
      if (stats) {
        csvRows.push(`${reading.channel},${stats.current},${stats.min},${stats.max}`);
      }
    });

    const csv = csvRows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `adc-readings-${nodeId}-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // Calculate update rate
  function getUpdateRate(): string {
    if (updateCount === 0) return '0 Hz';
    const elapsed = (Date.now() - startTime) / 1000;
    const rate = updateCount / elapsed;
    return rate >= 1 ? `${rate.toFixed(1)} Hz` : `${(rate * 1000).toFixed(0)} mHz`;
  }
</script>

<div class="bg-surface-1 border border-surface-2 rounded-lg p-4">
  <div class="flex items-center justify-between mb-4">
    <div>
      <h3 class="text-lg font-semibold text-text-primary">ADC Readings</h3>
      {#if mtibObservabilityStore.isConnected && updateCount > 0}
        <p class="text-xs text-text-secondary mt-0.5">Update rate: {getUpdateRate()}</p>
      {/if}
    </div>
    <div class="flex items-center gap-3">
      {#if mtibObservabilityStore.isConnected}
        <div class="flex items-center gap-2">
          <div class="w-2 h-2 rounded-full bg-success animate-pulse"></div>
          <span class="text-sm text-text-secondary">Live</span>
        </div>
      {/if}
      {#if mtibObservabilityStore.adcReadings}
        <button
          class="p-2 text-text-secondary hover:text-accent hover:bg-surface-2 rounded-md transition-colors"
          onclick={exportCsv}
          aria-label="Export to CSV"
          title="Export to CSV"
        >
          <Download size={18} />
        </button>
      {/if}
    </div>
  </div>

  {#if mtibObservabilityStore.error}
    <div class="rounded-md bg-error-muted border border-error p-4">
      <p class="text-sm text-error font-medium">Error</p>
      <p class="text-sm text-text-secondary mt-1">{mtibObservabilityStore.error}</p>
      <button
        class="mt-3 px-3 py-1.5 text-sm font-medium text-error border border-error rounded-md hover:bg-error hover:text-white transition-colors"
        onclick={() => mtibObservabilityStore.subscribe(nodeId, ['adc'])}
        aria-label="Retry connection"
      >
        Retry
      </button>
    </div>
  {:else if mtibObservabilityStore.adcReadings}
    {@const readings = channels
      ? mtibObservabilityStore.adcReadings.filter(r => channels.includes(r.channel))
      : mtibObservabilityStore.adcReadings}

    {#if readings.length === 0}
      <div class="text-center py-8 text-text-secondary">
        <p>No ADC channels available</p>
      </div>
    {:else}
      <div class="space-y-4">
        {#each readings as reading (reading.channel)}
          {@const stats = channelStats.get(reading.channel)}
          {#if stats}
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <span class="text-sm font-medium text-text-primary">Channel {reading.channel}</span>
                <span class="text-sm font-mono font-semibold text-accent">{formatVoltage(stats.current)}V</span>
              </div>

              <!-- Progress bar -->
              <div class="relative h-6 bg-surface-2 rounded-md overflow-hidden">
                <div
                  class="absolute left-0 top-0 h-full bg-accent transition-all duration-150"
                  style="width: {getPercentage(stats.current)}%"
                  role="progressbar"
                  aria-valuenow={stats.current}
                  aria-valuemin={0}
                  aria-valuemax={5}
                  aria-label="Channel {reading.channel} voltage"
                ></div>
                <div class="absolute inset-0 flex items-center justify-center">
                  <span class="text-xs font-mono text-text-primary mix-blend-difference">
                    {formatVoltage(stats.current)}V
                  </span>
                </div>
              </div>

              <!-- Min/Max indicators -->
              <div class="flex items-center justify-between text-xs text-text-secondary">
                <span>Min: <span class="font-mono">{formatVoltage(stats.min)}V</span></span>
                <span>Max: <span class="font-mono">{formatVoltage(stats.max)}V</span></span>
              </div>
            </div>
          {/if}
        {/each}
      </div>
    {/if}
  {:else}
    <!-- Loading skeleton -->
    <div class="space-y-4">
      {#each Array(4) as _, i}
        <div class="space-y-2 animate-pulse">
          <div class="flex items-center justify-between">
            <div class="h-4 w-20 bg-surface-3 rounded"></div>
            <div class="h-4 w-16 bg-surface-3 rounded"></div>
          </div>
          <div class="h-6 bg-surface-3 rounded-md"></div>
          <div class="flex items-center justify-between">
            <div class="h-3 w-16 bg-surface-3 rounded"></div>
            <div class="h-3 w-16 bg-surface-3 rounded"></div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
