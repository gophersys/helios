<script lang="ts">
  import { onMount } from 'svelte';
  import type { TelemetryManifest, TimeRange, StepInfo } from './time-context';

  interface LiveTest {
    name: string;
    module: string | null;
    status: 'queued' | 'running' | 'passed' | 'failed' | 'skipped';
    [key: string]: unknown;
  }

  interface Props {
    manifest: TelemetryManifest;
    liveTests: LiveTest[];
    selectedRange: TimeRange | null;
    interactive?: boolean;
  }

  let { manifest, liveTests, selectedRange = $bindable(null), interactive = true }: Props = $props();

  let canvas: HTMLCanvasElement;
  let containerEl: HTMLElement;
  let w = $state(300);
  const h = 24;
  let dpr = 1;

  // Tooltip
  let tooltip = $state<{ x: number; text: string } | null>(null);

  const timeStart = $derived(manifest.startedAt ?? 0);
  const timeEnd = $derived(manifest.finishedAt ?? (manifest.startedAt ?? 0));
  const timeDuration = $derived(Math.max(timeEnd - timeStart, 1));

  function getStepStatus(step: StepInfo): string {
    const match = liveTests.find(t => t.name === step.name && t.module === step.module);
    return match?.status ?? step.status ?? 'queued';
  }

  // Use different hues per module for visual grouping
  const moduleColors: Record<string, string> = {};
  const hues = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#06b6d4'];
  let hueIdx = 0;
  function moduleColor(module: string | null): string {
    const key = module || '_default';
    if (!moduleColors[key]) {
      moduleColors[key] = hues[hueIdx % hues.length];
      hueIdx++;
    }
    return moduleColors[key];
  }

  function statusColor(status: string, module: string | null): string {
    if (status === 'failed') return '#ef4444';
    if (status === 'skipped') return '#4b5563';
    return moduleColor(module);
  }

  function timeToX(t: number): number {
    return ((t - timeStart) / timeDuration) * w;
  }

  function xToTime(x: number): number {
    return timeStart + (x / w) * timeDuration;
  }

  function draw() {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    // Background track
    ctx.fillStyle = '#1e2a3a';
    ctx.beginPath();
    ctx.roundRect(0, 4, w, h - 8, 3);
    ctx.fill();

    // Step segments
    for (const step of manifest.steps) {
      const status = getStepStatus(step);
      const x1 = Math.max(timeToX(step.startedAt), 0);
      const x2 = Math.min(timeToX(step.finishedAt), w);
      if (x2 <= x1 + 0.5) continue;

      ctx.fillStyle = statusColor(status, step.module);
      ctx.globalAlpha = 0.8;
      ctx.beginPath();
      ctx.roundRect(x1 + 0.5, 5, Math.max(x2 - x1 - 1, 1.5), h - 10, 2);
      ctx.fill();
      ctx.globalAlpha = 1;
    }

    // Selection overlay
    if (selectedRange) {
      const sx1 = Math.max(timeToX(selectedRange.start), 0);
      const sx2 = Math.min(timeToX(selectedRange.end), w);

      // Dim outside
      ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
      if (sx1 > 0) ctx.fillRect(0, 4, sx1, h - 8);
      if (sx2 < w) ctx.fillRect(sx2, 4, w - sx2, h - 8);

      // Selection border
      ctx.strokeStyle = '#58a6ff';
      ctx.lineWidth = 1;
      ctx.strokeRect(sx1, 4, sx2 - sx1, h - 8);
    }

    ctx.restore();
  }

  // Redraw when data changes. In live mode, manifest changes every second
  // (nowMs ticks). Throttle redraws to avoid interfering with hover/click.
  let _lastDrawTime = 0;
  $effect(() => {
    void manifest; void liveTests; void selectedRange; void w;
    const now = Date.now();
    // In live mode (manifest changes frequently), limit redraws to 2/sec
    // unless selectedRange changed or width changed
    if (now - _lastDrawTime < 400 && !selectedRange) {
      // Skip this redraw, schedule one soon
      const timer = setTimeout(() => { _lastDrawTime = Date.now(); draw(); }, 400);
      return () => clearTimeout(timer);
    }
    _lastDrawTime = now;
    draw();
  });

  function onClick(e: MouseEvent) {
    if (!interactive) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const t = xToTime(x);

    for (const step of manifest.steps) {
      if (t >= step.startedAt && t <= step.finishedAt) {
        if (selectedRange && Math.abs(selectedRange.start - step.startedAt) < 0.5 && Math.abs(selectedRange.end - step.finishedAt) < 0.5) {
          selectedRange = null;
        } else {
          selectedRange = { start: step.startedAt, end: step.finishedAt };
        }
        return;
      }
    }
    selectedRange = null;
  }

  function onHover(e: MouseEvent) {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const t = xToTime(x);

    for (const step of manifest.steps) {
      if (t >= step.startedAt && t <= step.finishedAt) {
        const dur = step.finishedAt - step.startedAt;
        const m = Math.floor(dur / 60);
        const s = Math.floor(dur % 60);
        tooltip = {
          x: e.clientX - rect.left,
          text: `${step.module ? step.module + ' → ' : ''}${step.name} (${m}m ${s}s)`,
        };
        canvas.style.cursor = 'pointer';
        return;
      }
    }
    tooltip = null;
    canvas.style.cursor = 'default';
  }

  function onLeave() {
    tooltip = null;
  }

  function updateSize() {
    if (!containerEl) return;
    w = Math.max(Math.floor(containerEl.getBoundingClientRect().width), 100);
    dpr = typeof window !== 'undefined' ? (window.devicePixelRatio || 1) : 1;
    if (canvas) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
    }
    draw();
  }

  onMount(() => {
    const ro = new ResizeObserver(() => updateSize());
    ro.observe(containerEl);
    updateSize();
    return () => ro.disconnect();
  });
</script>

<div class="flex items-center gap-1.5 min-w-0" style="height: {h}px;">
  <span class="text-2xs font-mono text-text-tertiary shrink-0">{timeStart ? new Date(timeStart * 1000).toISOString().slice(11, 19) : ''}</span>
  <div bind:this={containerEl} class="relative flex-1 min-w-0" style="height: {h}px;">
    <canvas
      bind:this={canvas}
      class="block absolute inset-0 touch-none"
      onclick={onClick}
      onmousemove={onHover}
      onmouseleave={onLeave}
    ></canvas>
    {#if tooltip}
      <div
        class="absolute bottom-full mb-1 px-2 py-1 rounded bg-surface-2 border border-border text-2xs text-text-primary whitespace-nowrap pointer-events-none z-50"
        style="left: {Math.min(tooltip.x, w - 150)}px; transform: translateX(-50%);"
      >
        {tooltip.text}
      </div>
    {/if}
  </div>
  <span class="text-2xs font-mono text-text-tertiary shrink-0">{timeEnd ? new Date(timeEnd * 1000).toISOString().slice(11, 19) : ''}</span>
  {#if selectedRange}
    <button
      onclick={() => { selectedRange = null; }}
      class="shrink-0 flex items-center gap-1 rounded px-2 py-0.5 text-2xs transition-all whitespace-nowrap
        bg-accent/15 border border-accent/40 text-accent hover:bg-accent/25 cursor-pointer"
      title="Clear selection (Esc)"
    >Clear ✕</button>
  {/if}
</div>
