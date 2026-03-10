<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { apiFetch } from '$lib/api';
  import {
    AlertCircle,
    Loader2,
    ZoomIn,
    ZoomOut,
    Maximize2,
    RefreshCw,
  } from 'lucide-svelte';

  // Props
  interface Props {
    runId: string;
    testName: string;
  }

  let { runId, testName }: Props = $props();

  // Power sample structure (matches binary format)
  interface PowerSample {
    timestamp_ms: number;
    voltage_mv: number;
    current_ma: number;
    power_mw: number;
  }

  interface PowerHeader {
    magic: string;
    version: number;
    sample_rate_hz: number;
    channel_count: number;
    sample_count: number;
    start_time_ms: number;
  }

  // State
  let samples = $state<PowerSample[]>([]);
  let header = $state<PowerHeader | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let svgContainer = $state<SVGSVGElement | null>(null);

  // View state
  let viewMode = $state<'voltage' | 'current' | 'power'>('current');
  let zoomLevel = $state(1);
  let panOffset = $state(0);

  // Chart dimensions
  const chartHeight = 200;
  const chartPadding = { top: 20, right: 40, bottom: 30, left: 50 };

  // Derived chart data
  const chartWidth = $derived(800 * zoomLevel);

  const visibleSamples = $derived.by(() => {
    if (samples.length === 0) return [];
    const startIdx = Math.floor(panOffset / zoomLevel);
    const visibleCount = Math.ceil(800 / zoomLevel);
    return samples.slice(startIdx, startIdx + visibleCount);
  });

  const dataRange = $derived.by(() => {
    if (samples.length === 0) return { min: 0, max: 100 };

    let values: number[];
    switch (viewMode) {
      case 'voltage':
        values = samples.map(s => s.voltage_mv);
        break;
      case 'current':
        values = samples.map(s => s.current_ma);
        break;
      case 'power':
        values = samples.map(s => s.power_mw);
        break;
    }

    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = (max - min) * 0.1 || 10;

    return {
      min: Math.max(0, min - padding),
      max: max + padding,
    };
  });

  const timeRange = $derived.by(() => {
    if (samples.length === 0) return { min: 0, max: 1000 };
    return {
      min: samples[0].timestamp_ms,
      max: samples[samples.length - 1].timestamp_ms,
    };
  });

  // Generate SVG path for the chart
  const chartPath = $derived.by(() => {
    if (samples.length === 0) return '';

    const innerWidth = chartWidth - chartPadding.left - chartPadding.right;
    const innerHeight = chartHeight - chartPadding.top - chartPadding.bottom;

    const xScale = (t: number) =>
      chartPadding.left + ((t - timeRange.min) / (timeRange.max - timeRange.min)) * innerWidth;

    const yScale = (v: number) =>
      chartPadding.top + innerHeight - ((v - dataRange.min) / (dataRange.max - dataRange.min)) * innerHeight;

    const getValue = (s: PowerSample): number => {
      switch (viewMode) {
        case 'voltage': return s.voltage_mv;
        case 'current': return s.current_ma;
        case 'power': return s.power_mw;
      }
    };

    const points = samples.map((s, i) => {
      const x = xScale(s.timestamp_ms);
      const y = yScale(getValue(s));
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    });

    return points.join(' ');
  });

  // Y-axis ticks
  const yTicks = $derived.by(() => {
    const tickCount = 5;
    const range = dataRange.max - dataRange.min;
    const step = range / (tickCount - 1);

    return Array.from({ length: tickCount }, (_, i) => {
      const value = dataRange.min + step * i;
      return {
        value,
        y: chartPadding.top + (chartHeight - chartPadding.top - chartPadding.bottom) * (1 - (value - dataRange.min) / range),
      };
    });
  });

  // X-axis ticks
  const xTicks = $derived.by(() => {
    const tickCount = 6;
    const range = timeRange.max - timeRange.min;
    const step = range / (tickCount - 1);
    const innerWidth = chartWidth - chartPadding.left - chartPadding.right;

    return Array.from({ length: tickCount }, (_, i) => {
      const time = timeRange.min + step * i;
      return {
        time,
        x: chartPadding.left + (innerWidth * i) / (tickCount - 1),
        label: (time / 1000).toFixed(1) + 's',
      };
    });
  });

  const unitLabel = $derived.by(() => {
    switch (viewMode) {
      case 'voltage': return 'mV';
      case 'current': return 'mA';
      case 'power': return 'mW';
    }
  });

  const strokeColor = $derived.by(() => {
    switch (viewMode) {
      case 'voltage': return 'var(--color-info)';
      case 'current': return 'var(--color-accent)';
      case 'power': return 'var(--color-success)';
    }
  });

  // Parse binary power.bin file
  function parsePowerBinary(buffer: ArrayBuffer): { header: PowerHeader; samples: PowerSample[] } {
    const view = new DataView(buffer);
    let offset = 0;

    // Read header (assuming fixed format)
    // Magic: 4 bytes "PWRB"
    const magic = String.fromCharCode(
      view.getUint8(offset),
      view.getUint8(offset + 1),
      view.getUint8(offset + 2),
      view.getUint8(offset + 3)
    );
    offset += 4;

    // Version: 2 bytes
    const version = view.getUint16(offset, true);
    offset += 2;

    // Sample rate: 4 bytes
    const sample_rate_hz = view.getUint32(offset, true);
    offset += 4;

    // Channel count: 2 bytes
    const channel_count = view.getUint16(offset, true);
    offset += 2;

    // Sample count: 4 bytes
    const sample_count = view.getUint32(offset, true);
    offset += 4;

    // Start time: 8 bytes
    const start_time_ms = Number(view.getBigUint64(offset, true));
    offset += 8;

    const headerData: PowerHeader = {
      magic,
      version,
      sample_rate_hz,
      channel_count,
      sample_count,
      start_time_ms,
    };

    // Read samples
    // Each sample: timestamp_ms (4), voltage_mv (2), current_ma (2), power_mw (2) = 10 bytes
    const sampleData: PowerSample[] = [];
    const sampleSize = 10;

    for (let i = 0; i < sample_count && offset + sampleSize <= buffer.byteLength; i++) {
      const timestamp_ms = view.getUint32(offset, true);
      offset += 4;
      const voltage_mv = view.getUint16(offset, true);
      offset += 2;
      const current_ma = view.getUint16(offset, true);
      offset += 2;
      const power_mw = view.getUint16(offset, true);
      offset += 2;

      sampleData.push({ timestamp_ms, voltage_mv, current_ma, power_mw });
    }

    return { header: headerData, samples: sampleData };
  }

  // Parse CSV fallback
  function parsePowerCsv(text: string): PowerSample[] {
    const lines = text.trim().split('\n');
    const sampleData: PowerSample[] = [];

    for (let i = 1; i < lines.length; i++) {
      const parts = lines[i].split(',').map(p => parseFloat(p.trim()));
      if (parts.length >= 4) {
        sampleData.push({
          timestamp_ms: parts[0],
          voltage_mv: parts[1],
          current_ma: parts[2],
          power_mw: parts[3],
        });
      }
    }

    return sampleData;
  }

  // Fetch power data
  async function fetchPowerData(): Promise<void> {
    loading = true;
    error = null;

    try {
      // Try binary format first
      const res = await fetch(
        `/v2/validation/runs/${runId}/artifacts/${encodeURIComponent(testName)}/power.bin`
      );

      if (res.ok) {
        const buffer = await res.arrayBuffer();
        const parsed = parsePowerBinary(buffer);
        header = parsed.header;
        samples = parsed.samples;
      } else {
        // Fall back to CSV
        const csvRes = await fetch(
          `/v2/validation/runs/${runId}/artifacts/${encodeURIComponent(testName)}/power.csv`
        );

        if (csvRes.ok) {
          const text = await csvRes.text();
          samples = parsePowerCsv(text);
        } else {
          throw new Error('Power data not available');
        }
      }
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load power data';
      samples = [];
    } finally {
      loading = false;
    }
  }

  function zoomIn(): void {
    zoomLevel = Math.min(zoomLevel * 1.5, 10);
  }

  function zoomOut(): void {
    zoomLevel = Math.max(zoomLevel / 1.5, 1);
  }

  function resetZoom(): void {
    zoomLevel = 1;
    panOffset = 0;
  }

  function handleWheel(e: WheelEvent): void {
    e.preventDefault();
    if (e.ctrlKey || e.metaKey) {
      // Zoom
      if (e.deltaY < 0) {
        zoomIn();
      } else {
        zoomOut();
      }
    } else {
      // Pan
      panOffset = Math.max(0, panOffset + e.deltaX);
    }
  }

  // Statistics
  const stats = $derived.by(() => {
    if (samples.length === 0) return null;

    const voltages = samples.map(s => s.voltage_mv);
    const currents = samples.map(s => s.current_ma);

    return {
      avgVoltage: (voltages.reduce((a, b) => a + b, 0) / voltages.length).toFixed(0),
      avgCurrent: (currents.reduce((a, b) => a + b, 0) / currents.length).toFixed(1),
      maxCurrent: Math.max(...currents).toFixed(1),
      minCurrent: Math.min(...currents).toFixed(1),
      duration: ((timeRange.max - timeRange.min) / 1000).toFixed(2),
    };
  });

  onMount(() => {
    fetchPowerData();
  });
</script>

<div class="rounded-lg border border-border bg-surface-0 overflow-hidden">
  <!-- Header -->
  <div class="flex items-center justify-between px-3 py-2 border-b border-border bg-surface-1">
    <div class="flex items-center gap-2">
      <span class="text-xs font-medium text-text-primary">Power Profile</span>
      {#if samples.length > 0}
        <span class="text-2xs text-text-tertiary">({samples.length} samples)</span>
      {/if}
    </div>

    <div class="flex items-center gap-1">
      <!-- View mode toggle -->
      <div class="flex items-center rounded-lg bg-surface-2 p-0.5 mr-2">
        <button
          onclick={() => (viewMode = 'voltage')}
          class="px-2 py-1 text-2xs font-medium rounded-md transition-colors {viewMode === 'voltage' ? 'bg-surface-0 text-text-primary shadow-sm' : 'text-text-tertiary hover:text-text-primary'}"
        >
          Voltage
        </button>
        <button
          onclick={() => (viewMode = 'current')}
          class="px-2 py-1 text-2xs font-medium rounded-md transition-colors {viewMode === 'current' ? 'bg-surface-0 text-text-primary shadow-sm' : 'text-text-tertiary hover:text-text-primary'}"
        >
          Current
        </button>
        <button
          onclick={() => (viewMode = 'power')}
          class="px-2 py-1 text-2xs font-medium rounded-md transition-colors {viewMode === 'power' ? 'bg-surface-0 text-text-primary shadow-sm' : 'text-text-tertiary hover:text-text-primary'}"
        >
          Power
        </button>
      </div>

      <button
        onclick={zoomIn}
        class="p-1.5 rounded hover:bg-surface-2 text-text-tertiary hover:text-text-primary transition-colors"
        title="Zoom in"
      >
        <ZoomIn size={14} />
      </button>
      <button
        onclick={zoomOut}
        class="p-1.5 rounded hover:bg-surface-2 text-text-tertiary hover:text-text-primary transition-colors"
        title="Zoom out"
      >
        <ZoomOut size={14} />
      </button>
      <button
        onclick={resetZoom}
        class="p-1.5 rounded hover:bg-surface-2 text-text-tertiary hover:text-text-primary transition-colors"
        title="Reset view"
      >
        <Maximize2 size={14} />
      </button>
      <button
        onclick={fetchPowerData}
        disabled={loading}
        class="p-1.5 rounded hover:bg-surface-2 text-text-tertiary hover:text-text-primary transition-colors disabled:opacity-50"
        title="Refresh"
      >
        <RefreshCw size={14} class={loading ? 'animate-spin' : ''} />
      </button>
    </div>
  </div>

  <!-- Chart -->
  <div class="p-3">
    {#if loading}
      <div class="flex items-center justify-center py-12 text-text-tertiary">
        <Loader2 size={16} class="animate-spin mr-2" />
        Loading power data...
      </div>
    {:else if error}
      <div class="flex items-center gap-2 py-8 justify-center text-error">
        <AlertCircle size={14} />
        <span>{error}</span>
      </div>
    {:else if samples.length === 0}
      <div class="py-8 text-center text-text-tertiary">
        No power data available
      </div>
    {:else}
      <div class="overflow-x-auto" onwheel={handleWheel}>
        <svg
          bind:this={svgContainer}
          width={chartWidth}
          height={chartHeight}
          class="block"
        >
          <!-- Grid lines -->
          {#each yTicks as tick}
            <line
              x1={chartPadding.left}
              y1={tick.y}
              x2={chartWidth - chartPadding.right}
              y2={tick.y}
              stroke="var(--color-border)"
              stroke-width="1"
              stroke-dasharray="2,2"
            />
          {/each}

          <!-- Y-axis labels -->
          {#each yTicks as tick}
            <text
              x={chartPadding.left - 8}
              y={tick.y}
              text-anchor="end"
              alignment-baseline="middle"
              class="text-2xs fill-text-tertiary"
            >
              {tick.value.toFixed(0)}
            </text>
          {/each}

          <!-- X-axis labels -->
          {#each xTicks as tick}
            <text
              x={tick.x}
              y={chartHeight - 8}
              text-anchor="middle"
              class="text-2xs fill-text-tertiary"
            >
              {tick.label}
            </text>
          {/each}

          <!-- Data line -->
          <path
            d={chartPath}
            fill="none"
            stroke={strokeColor}
            stroke-width="1.5"
            stroke-linejoin="round"
            stroke-linecap="round"
          />

          <!-- Y-axis unit label -->
          <text
            x={12}
            y={chartPadding.top + (chartHeight - chartPadding.top - chartPadding.bottom) / 2}
            text-anchor="middle"
            transform="rotate(-90, 12, {chartPadding.top + (chartHeight - chartPadding.top - chartPadding.bottom) / 2})"
            class="text-2xs fill-text-tertiary"
          >
            {unitLabel}
          </text>
        </svg>
      </div>
    {/if}
  </div>

  <!-- Stats footer -->
  {#if stats}
    <div class="flex items-center gap-4 px-3 py-2 border-t border-border bg-surface-1 text-2xs">
      <span class="text-text-tertiary">
        Avg: <span class="text-text-primary font-medium">{stats.avgVoltage}mV</span> / <span class="text-text-primary font-medium">{stats.avgCurrent}mA</span>
      </span>
      <span class="text-text-tertiary">
        Current range: <span class="text-text-primary font-medium">{stats.minCurrent}</span> - <span class="text-text-primary font-medium">{stats.maxCurrent}mA</span>
      </span>
      <span class="text-text-tertiary">
        Duration: <span class="text-text-primary font-medium">{stats.duration}s</span>
      </span>
    </div>
  {/if}
</div>
