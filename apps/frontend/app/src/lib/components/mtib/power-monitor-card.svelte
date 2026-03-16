<script lang="ts">
  import type { PowerReading } from '$lib/types/mtib';
  import { mtibObservabilityStore } from '$lib/stores/mtib-observability.svelte';
  import { onMount, onDestroy } from 'svelte';
  import { Download, Eye, EyeOff } from 'lucide-svelte';

  let { nodeId, channels }: { nodeId: string; channels?: number[] } = $props();

  // Ring buffer for chart data (600 samples = 60s at 10Hz)
  const MAX_SAMPLES = 600;
  type ChannelData = {
    voltage: number[];
    current: number[];
    timestamps: number[];
    visible: boolean;
    color: string;
  };
  let channelData = $state<Map<number, ChannelData>>(new Map());
  let startTime = $state<number | null>(null);

  let canvasVoltage: HTMLCanvasElement | null = $state(null);
  let canvasCurrent: HTMLCanvasElement | null = $state(null);

  const CHANNEL_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

  onMount(() => {
    mtibObservabilityStore.subscribe(nodeId, ['power']);
  });

  onDestroy(() => {
    mtibObservabilityStore.unsubscribe();
  });

  // Update chart data when readings arrive
  $effect(() => {
    if (mtibObservabilityStore.powerReadings && mtibObservabilityStore.lastUpdate) {
      if (!startTime) {
        startTime = mtibObservabilityStore.lastUpdate;
      }

      const readings = channels
        ? mtibObservabilityStore.powerReadings.filter(r => channels.includes(r.channel))
        : mtibObservabilityStore.powerReadings;

      const elapsed = (mtibObservabilityStore.lastUpdate - startTime) / 1000; // seconds

      readings.forEach((reading) => {
        let data = channelData.get(reading.channel);
        if (!data) {
          data = {
            voltage: [],
            current: [],
            timestamps: [],
            visible: true,
            color: CHANNEL_COLORS[reading.channel % CHANNEL_COLORS.length]
          };
          channelData.set(reading.channel, data);
        }

        // Add new sample
        data.voltage.push(reading.voltage_v);
        data.current.push(reading.current_ma);
        data.timestamps.push(elapsed);

        // Trim to MAX_SAMPLES (ring buffer)
        if (data.voltage.length > MAX_SAMPLES) {
          data.voltage.shift();
          data.current.shift();
          data.timestamps.shift();
        }
      });

      // Trigger chart redraw
      drawCharts();
    }
  });

  function drawCharts(): void {
    drawChart(canvasVoltage, 'voltage', 'Voltage (V)', 0, 5);
    drawChart(canvasCurrent, 'current', 'Current (mA)', 0, 1000);
  }

  function drawChart(
    canvas: HTMLCanvasElement | null,
    metric: 'voltage' | 'current',
    label: string,
    minY: number,
    maxY: number
  ): void {
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;
    const padding = { top: 30, right: 10, bottom: 30, left: 50 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // Clear canvas
    ctx.fillStyle = getComputedStyle(canvas).getPropertyValue('background-color') || '#1a1a1a';
    ctx.fillRect(0, 0, width, height);

    // Get text color from CSS variable
    const textColor = getComputedStyle(document.documentElement)
      .getPropertyValue('--text-secondary')
      .trim() || '#999';

    // Draw axes
    ctx.strokeStyle = textColor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left, padding.top + chartHeight);
    ctx.lineTo(padding.left + chartWidth, padding.top + chartHeight);
    ctx.stroke();

    // Draw Y-axis labels
    ctx.fillStyle = textColor;
    ctx.font = '11px monospace';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    const ySteps = 5;
    for (let i = 0; i <= ySteps; i++) {
      const y = padding.top + (chartHeight * i) / ySteps;
      const value = maxY - ((maxY - minY) * i) / ySteps;
      ctx.fillText(value.toFixed(1), padding.left - 5, y);
    }

    // Draw X-axis labels (time in seconds)
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    const xSteps = 6;
    const maxTime = 60; // 60 seconds
    for (let i = 0; i <= xSteps; i++) {
      const x = padding.left + (chartWidth * i) / xSteps;
      const time = (maxTime * i) / xSteps;
      ctx.fillText(`${time}s`, x, padding.top + chartHeight + 5);
    }

    // Draw chart title
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(label, padding.left, 5);

    // Draw data lines for each channel
    channelData.forEach((data, channel) => {
      if (!data.visible) return;

      const values = metric === 'voltage' ? data.voltage : data.current;
      if (values.length < 2) return;

      ctx.strokeStyle = data.color;
      ctx.lineWidth = 2;
      ctx.beginPath();

      const timeWindow = 60; // 60 seconds visible
      values.forEach((value, i) => {
        const time = data.timestamps[i];
        const x = padding.left + ((time / timeWindow) * chartWidth);
        const y = padding.top + chartHeight - (((value - minY) / (maxY - minY)) * chartHeight);

        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });

      ctx.stroke();
    });
  }

  function toggleChannel(channel: number): void {
    const data = channelData.get(channel);
    if (data) {
      data.visible = !data.visible;
      drawCharts();
    }
  }

  function exportCsv(): void {
    const csvRows = ['Time (s),Channel,Voltage (V),Current (mA)'];
    channelData.forEach((data, channel) => {
      data.timestamps.forEach((time, i) => {
        csvRows.push(`${time.toFixed(3)},${channel},${data.voltage[i]},${data.current[i]}`);
      });
    });

    const csv = csvRows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `power-readings-${nodeId}-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // Redraw on window resize
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', drawCharts);
    onDestroy(() => {
      window.removeEventListener('resize', drawCharts);
    });
  }
</script>

<div class="bg-surface-1 border border-surface-2 rounded-lg p-4">
  <div class="flex items-center justify-between mb-4">
    <div>
      <h3 class="text-lg font-semibold text-text-primary">Power Monitor</h3>
      <p class="text-xs text-text-secondary mt-0.5">Last 60 seconds</p>
    </div>
    <div class="flex items-center gap-3">
      {#if mtibObservabilityStore.isConnected}
        <div class="flex items-center gap-2">
          <div class="w-2 h-2 rounded-full bg-success animate-pulse"></div>
          <span class="text-sm text-text-secondary">Live</span>
        </div>
      {/if}
      {#if channelData.size > 0}
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
        onclick={() => mtibObservabilityStore.subscribe(nodeId, ['power'])}
        aria-label="Retry connection"
      >
        Retry
      </button>
    </div>
  {:else if mtibObservabilityStore.powerReadings}
    <div class="space-y-4">
      <!-- Channel toggles -->
      <div class="flex flex-wrap gap-2">
        {#each Array.from(channelData.entries()) as [channel, data]}
          <button
            class="flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors border"
            class:bg-surface-2={data.visible}
            class:border-accent={data.visible}
            class:bg-surface-0={!data.visible}
            class:border-surface-2={!data.visible}
            class:text-text-primary={data.visible}
            class:text-text-tertiary={!data.visible}
            onclick={() => toggleChannel(channel)}
            aria-label="Toggle channel {channel} visibility"
            aria-pressed={data.visible}
          >
            {#if data.visible}
              <Eye size={14} />
            {:else}
              <EyeOff size={14} />
            {/if}
            <span
              class="w-3 h-3 rounded-full"
              style="background-color: {data.color}"
              aria-hidden="true"
            ></span>
            <span>Ch {channel}</span>
          </button>
        {/each}
      </div>

      <!-- Voltage chart -->
      <div class="space-y-2">
        <canvas
          bind:this={canvasVoltage}
          class="w-full bg-surface-0 rounded-md border border-surface-2"
          style="height: 200px;"
          aria-label="Voltage chart"
        ></canvas>
      </div>

      <!-- Current chart -->
      <div class="space-y-2">
        <canvas
          bind:this={canvasCurrent}
          class="w-full bg-surface-0 rounded-md border border-surface-2"
          style="height: 200px;"
          aria-label="Current chart"
        ></canvas>
      </div>

      <!-- Current readings table -->
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 pt-2">
        {#each mtibObservabilityStore.powerReadings as reading}
          {@const data = channelData.get(reading.channel)}
          {#if data}
            <div
              class="p-3 rounded-md border transition-all"
              class:border-accent={reading.enabled}
              class:bg-surface-2={reading.enabled}
              class:border-surface-2={!reading.enabled}
              class:bg-surface-0={!reading.enabled}
            >
              <div class="flex items-center gap-2 mb-2">
                <div
                  class="w-2 h-2 rounded-full"
                  style="background-color: {data.color}"
                  aria-hidden="true"
                ></div>
                <span class="text-xs font-semibold text-text-primary">Ch {reading.channel}</span>
              </div>
              <div class="space-y-1">
                <div class="flex justify-between text-xs">
                  <span class="text-text-secondary">Voltage:</span>
                  <span class="font-mono font-semibold text-accent">{reading.voltage_v.toFixed(3)}V</span>
                </div>
                <div class="flex justify-between text-xs">
                  <span class="text-text-secondary">Current:</span>
                  <span class="font-mono font-semibold text-accent">{reading.current_ma.toFixed(1)}mA</span>
                </div>
              </div>
            </div>
          {/if}
        {/each}
      </div>
    </div>
  {:else}
    <!-- Loading skeleton -->
    <div class="space-y-4">
      <div class="flex gap-2">
        {#each Array(4) as _, i}
          <div class="h-8 w-20 bg-surface-3 rounded-md animate-pulse"></div>
        {/each}
      </div>
      <div class="h-48 bg-surface-3 rounded-md animate-pulse"></div>
      <div class="h-48 bg-surface-3 rounded-md animate-pulse"></div>
    </div>
  {/if}
</div>
