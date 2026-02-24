<script lang="ts">
  import type { AnalyzerSample } from '$lib/types/mtib';
  import { analyzerStore } from '$lib/stores/analyzer.svelte';
  import { onMount, onDestroy } from 'svelte';
  import { Download, ZoomIn, ZoomOut, Maximize2 } from 'lucide-svelte';

  let { captureId, channels }: { captureId: string; channels?: number[] } = $props();

  let canvas: HTMLCanvasElement | null = $state(null);
  let zoomLevel = $state(1.0);
  let panOffset = $state(0); // Horizontal pan in pixels
  let isDragging = $state(false);
  let dragStart = $state({ x: 0, offset: 0 });

  const CHANNEL_COLORS = [
    '#3b82f6', // blue
    '#10b981', // green
    '#f59e0b', // amber
    '#ef4444', // red
    '#8b5cf6', // purple
    '#ec4899', // pink
    '#06b6d4', // cyan
    '#84cc16'  // lime
  ];

  const CHANNEL_LABELS = [
    'D0', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7'
  ];

  onMount(() => {
    // Note: capture should already be started by parent component
    // This component just displays the data
  });

  onDestroy(() => {
    // Parent is responsible for stopping capture
  });

  // Redraw when samples change
  $effect(() => {
    if (analyzerStore.samples.length > 0) {
      drawWaveform();
    }
  });

  function drawWaveform(): void {
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
    const padding = { top: 40, right: 10, bottom: 40, left: 80 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // Clear canvas
    ctx.fillStyle = getComputedStyle(canvas).getPropertyValue('background-color') || '#1a1a1a';
    ctx.fillRect(0, 0, width, height);

    const samples = analyzerStore.samples;
    if (samples.length < 2) return;

    // Filter channels if specified
    const visibleChannels = channels || [0, 1, 2, 3, 4, 5, 6, 7];
    const numChannels = visibleChannels.length;
    const channelHeight = chartHeight / numChannels;

    // Get text color from CSS
    const textColor = getComputedStyle(document.documentElement)
      .getPropertyValue('--text-secondary')
      .trim() || '#999';
    const accentColor = getComputedStyle(document.documentElement)
      .getPropertyValue('--accent')
      .trim() || '#3b82f6';

    // Calculate time range
    const startTimeNs = samples[0].timestamp_ns;
    const endTimeNs = samples[samples.length - 1].timestamp_ns;
    const durationNs = endTimeNs - startTimeNs;
    const durationUs = durationNs / 1000;

    // Apply zoom and pan
    const visibleWidth = chartWidth / zoomLevel;
    const maxPan = Math.max(0, chartWidth - visibleWidth);
    panOffset = Math.max(0, Math.min(maxPan, panOffset));

    // Draw channel separators and labels
    ctx.strokeStyle = textColor;
    ctx.lineWidth = 1;
    ctx.font = '12px monospace';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';

    visibleChannels.forEach((channel, i) => {
      const y = padding.top + i * channelHeight;

      // Separator line
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(padding.left + chartWidth, y);
      ctx.stroke();

      // Channel label
      ctx.fillStyle = CHANNEL_COLORS[channel % CHANNEL_COLORS.length];
      ctx.fillText(CHANNEL_LABELS[channel] || `D${channel}`, padding.left - 10, y + channelHeight / 2);
    });

    // Bottom border
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top + chartHeight);
    ctx.lineTo(padding.left + chartWidth, padding.top + chartHeight);
    ctx.stroke();

    // Draw time markers
    ctx.fillStyle = textColor;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    const timeSteps = 10;
    for (let i = 0; i <= timeSteps; i++) {
      const x = padding.left + (chartWidth * i) / timeSteps;
      const timeUs = (durationUs * i) / timeSteps;
      const label = timeUs >= 1000
        ? `${(timeUs / 1000).toFixed(1)}ms`
        : `${timeUs.toFixed(1)}µs`;
      ctx.fillText(label, x, padding.top + chartHeight + 5);
    }

    // Draw waveforms
    visibleChannels.forEach((channel, i) => {
      const y = padding.top + i * channelHeight;
      const highY = y + channelHeight * 0.2;
      const lowY = y + channelHeight * 0.8;

      ctx.strokeStyle = CHANNEL_COLORS[channel % CHANNEL_COLORS.length];
      ctx.lineWidth = 2;
      ctx.beginPath();

      let lastValue = false;
      let lastX = padding.left - panOffset;

      samples.forEach((sample, idx) => {
        const timeNs = sample.timestamp_ns - startTimeNs;
        const timeRatio = timeNs / durationNs;
        const x = padding.left + (timeRatio * chartWidth * zoomLevel) - panOffset;

        // Check if this sample is visible
        if (x < padding.left - 5 || x > padding.left + chartWidth + 5) {
          return;
        }

        const value = (sample.channel_states & (1 << channel)) !== 0;
        const currentY = value ? highY : lowY;

        if (idx === 0) {
          ctx.moveTo(x, currentY);
          lastValue = value;
          lastX = x;
        } else {
          // Draw vertical edge if value changed
          if (value !== lastValue) {
            ctx.lineTo(lastX, lastValue ? highY : lowY);
            ctx.lineTo(lastX, value ? highY : lowY);
            lastValue = value;
          }
          ctx.lineTo(x, currentY);
          lastX = x;
        }
      });

      ctx.stroke();
    });

    // Draw title
    ctx.fillStyle = textColor;
    ctx.font = '14px sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(`Capture: ${captureId.slice(0, 8)}`, padding.left, 10);

    // Draw sample count
    ctx.textAlign = 'right';
    ctx.fillText(`${samples.length} samples | ${durationUs.toFixed(2)}µs`, width - 10, 10);
  }

  function handleZoomIn(): void {
    zoomLevel = Math.min(10, zoomLevel * 1.5);
    drawWaveform();
  }

  function handleZoomOut(): void {
    zoomLevel = Math.max(1, zoomLevel / 1.5);
    panOffset = 0; // Reset pan on zoom out
    drawWaveform();
  }

  function handleResetZoom(): void {
    zoomLevel = 1;
    panOffset = 0;
    drawWaveform();
  }

  function handleMouseDown(e: MouseEvent): void {
    if (zoomLevel > 1) {
      isDragging = true;
      dragStart = { x: e.clientX, offset: panOffset };
    }
  }

  function handleMouseMove(e: MouseEvent): void {
    if (isDragging) {
      const dx = dragStart.x - e.clientX;
      panOffset = dragStart.offset + dx;
      drawWaveform();
    }
  }

  function handleMouseUp(): void {
    isDragging = false;
  }

  function exportVcd(): void {
    const samples = analyzerStore.samples;
    if (samples.length === 0) return;

    const visibleChannels = channels || [0, 1, 2, 3, 4, 5, 6, 7];
    const vcdLines: string[] = [];

    // VCD header
    vcdLines.push('$version MTIB Analyzer $end');
    vcdLines.push('$timescale 1ns $end');
    vcdLines.push('$scope module logic $end');

    // Declare variables
    visibleChannels.forEach(channel => {
      vcdLines.push(`$var wire 1 ${String.fromCharCode(65 + channel)} ${CHANNEL_LABELS[channel]} $end`);
    });

    vcdLines.push('$upscope $end');
    vcdLines.push('$enddefinitions $end');
    vcdLines.push('$dumpvars');

    // Initial values
    visibleChannels.forEach(channel => {
      const value = (samples[0].channel_states & (1 << channel)) !== 0 ? '1' : '0';
      vcdLines.push(`${value}${String.fromCharCode(65 + channel)}`);
    });

    vcdLines.push('$end');

    // Sample data
    samples.forEach(sample => {
      vcdLines.push(`#${sample.timestamp_ns}`);
      visibleChannels.forEach(channel => {
        const value = (sample.channel_states & (1 << channel)) !== 0 ? '1' : '0';
        vcdLines.push(`${value}${String.fromCharCode(65 + channel)}`);
      });
    });

    const vcd = vcdLines.join('\n');
    const blob = new Blob([vcd], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `analyzer-capture-${captureId}-${Date.now()}.vcd`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function exportCsv(): void {
    const samples = analyzerStore.samples;
    if (samples.length === 0) return;

    const visibleChannels = channels || [0, 1, 2, 3, 4, 5, 6, 7];
    const csvRows = ['Time (ns),' + visibleChannels.map(ch => CHANNEL_LABELS[ch]).join(',')];

    samples.forEach(sample => {
      const values = visibleChannels.map(channel => {
        return (sample.channel_states & (1 << channel)) !== 0 ? '1' : '0';
      });
      csvRows.push(`${sample.timestamp_ns},${values.join(',')}`);
    });

    const csv = csvRows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `analyzer-capture-${captureId}-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // Redraw on window resize
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', drawWaveform);
    onDestroy(() => {
      window.removeEventListener('resize', drawWaveform);
    });
  }
</script>

<svelte:window
  onmousemove={handleMouseMove}
  onmouseup={handleMouseUp}
/>

<div class="bg-surface-1 border border-surface-2 rounded-lg p-4">
  <div class="flex items-center justify-between mb-4">
    <div>
      <h3 class="text-lg font-semibold text-text-primary">Waveform Viewer</h3>
      <p class="text-xs text-text-secondary mt-0.5">
        {#if analyzerStore.isCapturing}
          Capturing... ({analyzerStore.totalSamples} samples)
        {:else if analyzerStore.captureComplete}
          Capture complete ({analyzerStore.totalSamples} samples)
        {:else}
          No active capture
        {/if}
      </p>
    </div>
    <div class="flex items-center gap-2">
      {#if analyzerStore.samples.length > 0}
        <!-- Zoom controls -->
        <div class="flex items-center gap-1 border border-surface-2 rounded-md">
          <button
            class="p-1.5 text-text-secondary hover:text-accent hover:bg-surface-2 transition-colors rounded-l-md"
            onclick={handleZoomOut}
            disabled={zoomLevel <= 1}
            aria-label="Zoom out"
            title="Zoom out"
          >
            <ZoomOut size={16} />
          </button>
          <span class="px-2 text-xs font-mono text-text-secondary border-x border-surface-2">
            {zoomLevel.toFixed(1)}x
          </span>
          <button
            class="p-1.5 text-text-secondary hover:text-accent hover:bg-surface-2 transition-colors"
            onclick={handleZoomIn}
            disabled={zoomLevel >= 10}
            aria-label="Zoom in"
            title="Zoom in"
          >
            <ZoomIn size={16} />
          </button>
          <button
            class="p-1.5 text-text-secondary hover:text-accent hover:bg-surface-2 transition-colors rounded-r-md"
            onclick={handleResetZoom}
            disabled={zoomLevel === 1 && panOffset === 0}
            aria-label="Reset zoom"
            title="Reset zoom"
          >
            <Maximize2 size={16} />
          </button>
        </div>

        <!-- Export buttons -->
        <div class="flex items-center gap-1">
          <button
            class="px-3 py-1.5 text-sm font-medium text-text-secondary hover:text-accent hover:bg-surface-2 rounded-md transition-colors flex items-center gap-1.5"
            onclick={exportCsv}
            aria-label="Export to CSV"
          >
            <Download size={14} />
            CSV
          </button>
          <button
            class="px-3 py-1.5 text-sm font-medium text-text-secondary hover:text-accent hover:bg-surface-2 rounded-md transition-colors flex items-center gap-1.5"
            onclick={exportVcd}
            aria-label="Export to VCD"
          >
            <Download size={14} />
            VCD
          </button>
        </div>
      {/if}
    </div>
  </div>

  {#if analyzerStore.error}
    <div class="rounded-md bg-error-muted border border-error p-4">
      <p class="text-sm text-error font-medium">Capture Error</p>
      <p class="text-sm text-text-secondary mt-1">{analyzerStore.error}</p>
    </div>
  {:else if analyzerStore.samples.length > 0}
    <div class="space-y-4">
      <!-- Waveform canvas -->
      <canvas
        bind:this={canvas}
        class="w-full bg-surface-0 rounded-md border border-surface-2"
        class:cursor-grab={zoomLevel > 1 && !isDragging}
        class:cursor-grabbing={isDragging}
        style="height: 400px;"
        onmousedown={handleMouseDown}
        role="img"
        aria-label="Logic analyzer waveform display"
      ></canvas>

      {#if zoomLevel > 1}
        <p class="text-xs text-text-secondary text-center">
          Drag to pan horizontally
        </p>
      {/if}

      <!-- Channel legend -->
      <div class="flex flex-wrap gap-2">
        {#each (channels || [0, 1, 2, 3, 4, 5, 6, 7]) as channel}
          <div class="flex items-center gap-2 px-3 py-1.5 bg-surface-2 border border-surface-2 rounded-md">
            <div
              class="w-3 h-3 rounded-full"
              style="background-color: {CHANNEL_COLORS[channel % CHANNEL_COLORS.length]}"
              aria-hidden="true"
            ></div>
            <span class="text-sm font-mono text-text-primary">{CHANNEL_LABELS[channel]}</span>
          </div>
        {/each}
      </div>
    </div>
  {:else if analyzerStore.isCapturing}
    <!-- Loading state -->
    <div class="flex flex-col items-center justify-center py-16 space-y-4">
      <div class="w-12 h-12 border-4 border-surface-2 border-t-accent rounded-full animate-spin"></div>
      <p class="text-sm text-text-secondary">
        Capturing samples...
      </p>
    </div>
  {:else}
    <!-- Empty state -->
    <div class="text-center py-16 text-text-secondary">
      <p>No capture data available</p>
      <p class="text-xs mt-2">Start a capture to view waveforms</p>
    </div>
  {/if}
</div>
