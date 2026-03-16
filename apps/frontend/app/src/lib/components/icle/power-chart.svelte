<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { Download } from 'lucide-svelte';
  import type { IclePowerReading } from '$lib/types/icle';

  let { readings, deviceId }: { readings: IclePowerReading[]; deviceId: string } = $props();

  let canvasVoltage: HTMLCanvasElement | null = $state(null);
  let canvasCurrent: HTMLCanvasElement | null = $state(null);
  let canvasPower: HTMLCanvasElement | null = $state(null);

  // Redraw charts when readings change
  $effect(() => {
    if (readings.length > 0) {
      drawCharts();
    }
  });

  function drawCharts(): void {
    drawChart(canvasVoltage, 'voltage_mv', 'Voltage (mV)', 0, 5000);
    drawChart(canvasCurrent, 'current_ma', 'Current (mA)', 0, 500);
    drawChart(canvasPower, 'power_mw', 'Power (mW)', 0, 2500);
  }

  function drawChart(
    canvas: HTMLCanvasElement | null,
    metric: keyof IclePowerReading,
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
    const padding = { top: 25, right: 10, bottom: 25, left: 50 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // Clear canvas
    ctx.fillStyle = getComputedStyle(canvas).getPropertyValue('background-color') || '#1a1a1a';
    ctx.fillRect(0, 0, width, height);

    // Get text color from CSS variable
    const textColor = getComputedStyle(document.documentElement)
      .getPropertyValue('--text-secondary')
      .trim() || '#999';

    const gridColor = getComputedStyle(document.documentElement)
      .getPropertyValue('--border')
      .trim() || '#333';

    // Draw grid lines
    ctx.strokeStyle = gridColor;
    ctx.lineWidth = 0.5;
    const ySteps = 5;
    for (let i = 0; i <= ySteps; i++) {
      const y = padding.top + (chartHeight * i) / ySteps;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(padding.left + chartWidth, y);
      ctx.stroke();
    }

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
    ctx.font = '10px monospace';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let i = 0; i <= ySteps; i++) {
      const y = padding.top + (chartHeight * i) / ySteps;
      const value = maxY - ((maxY - minY) * i) / ySteps;
      ctx.fillText(value.toFixed(0), padding.left - 5, y);
    }

    // Draw chart title
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(label, padding.left, 5);

    // No data check
    if (readings.length < 2) {
      ctx.fillStyle = textColor;
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('Waiting for data...', width / 2, height / 2);
      return;
    }

    // Calculate time window
    const startTime = readings[0].timestamp;
    const endTime = readings[readings.length - 1].timestamp;
    const timeWindow = Math.max(endTime - startTime, 1000); // at least 1 second

    // Draw data line
    const accentColor = getComputedStyle(document.documentElement)
      .getPropertyValue('--accent')
      .trim() || '#3b82f6';

    ctx.strokeStyle = accentColor;
    ctx.lineWidth = 1.5;
    ctx.beginPath();

    readings.forEach((reading, i) => {
      const value = reading[metric] as number;
      const time = reading.timestamp - startTime;
      const x = padding.left + (time / timeWindow) * chartWidth;
      const y = padding.top + chartHeight - (((value - minY) / (maxY - minY)) * chartHeight);

      if (i === 0) {
        ctx.moveTo(x, Math.max(padding.top, Math.min(padding.top + chartHeight, y)));
      } else {
        ctx.lineTo(x, Math.max(padding.top, Math.min(padding.top + chartHeight, y)));
      }
    });

    ctx.stroke();

    // Draw current value
    const lastReading = readings[readings.length - 1];
    const lastValue = lastReading[metric] as number;
    ctx.fillStyle = accentColor;
    ctx.font = 'bold 12px monospace';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'top';
    ctx.fillText(lastValue.toFixed(1), width - 5, 5);
  }

  function exportCsv(): void {
    const csvRows = ['Timestamp,Voltage (mV),Current (mA),Power (mW)'];
    readings.forEach((r) => {
      csvRows.push(`${r.timestamp},${r.voltage_mv},${r.current_ma},${r.power_mw}`);
    });

    const csv = csvRows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `icle-power-${deviceId}-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // Redraw on window resize
  function handleResize() {
    drawCharts();
  }

  onMount(() => {
    window.addEventListener('resize', handleResize);
  });

  onDestroy(() => {
    window.removeEventListener('resize', handleResize);
  });
</script>

<div class="card p-4">
  <div class="flex items-center justify-between mb-4">
    <div>
      <h3 class="text-sm font-semibold text-text-primary">Power Monitor</h3>
      <p class="text-2xs text-text-tertiary">Real-time power measurements</p>
    </div>
    <div class="flex items-center gap-3">
      {#if readings.length > 0}
        <div class="flex items-center gap-2">
          <div class="w-2 h-2 rounded-full bg-success animate-pulse"></div>
          <span class="text-2xs text-text-secondary">Live</span>
        </div>
        <button
          class="p-1.5 text-text-secondary hover:text-accent hover:bg-surface-2 rounded-md transition-colors"
          onclick={exportCsv}
          aria-label="Export to CSV"
          title="Export to CSV"
        >
          <Download size={16} />
        </button>
      {/if}
    </div>
  </div>

  <div class="space-y-3">
    <!-- Voltage chart -->
    <canvas
      bind:this={canvasVoltage}
      class="w-full bg-surface-0 rounded-md border border-border"
      style="height: 120px;"
      aria-label="Voltage chart"
    ></canvas>

    <!-- Current chart -->
    <canvas
      bind:this={canvasCurrent}
      class="w-full bg-surface-0 rounded-md border border-border"
      style="height: 120px;"
      aria-label="Current chart"
    ></canvas>

    <!-- Power chart -->
    <canvas
      bind:this={canvasPower}
      class="w-full bg-surface-0 rounded-md border border-border"
      style="height: 120px;"
      aria-label="Power chart"
    ></canvas>
  </div>

  <!-- Current readings summary -->
  {#if readings.length > 0}
    {@const latest = readings[readings.length - 1]}
    <div class="grid grid-cols-3 gap-3 mt-4">
      <div class="rounded-lg bg-surface-1 p-3 text-center">
        <p class="text-lg font-bold text-text-primary tabular-nums">{latest.voltage_mv.toFixed(0)}</p>
        <p class="text-2xs text-text-tertiary">mV</p>
      </div>
      <div class="rounded-lg bg-surface-1 p-3 text-center">
        <p class="text-lg font-bold text-text-primary tabular-nums">{latest.current_ma.toFixed(1)}</p>
        <p class="text-2xs text-text-tertiary">mA</p>
      </div>
      <div class="rounded-lg bg-surface-1 p-3 text-center">
        <p class="text-lg font-bold text-accent tabular-nums">{latest.power_mw.toFixed(1)}</p>
        <p class="text-2xs text-text-tertiary">mW</p>
      </div>
    </div>
  {/if}
</div>
