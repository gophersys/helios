<script lang="ts">
  import { onMount } from 'svelte';
  import type { TelemetryManifest, TimeRange, StepInfo } from './time-context';

  interface LiveTest {
    name: string;
    module: string | null;
    status: 'queued' | 'running' | 'passed' | 'failed' | 'skipped';
    durationS: number | null;
    errorMessage: string | null;
    measurements: Record<string, unknown> | null;
    logOutput: string | null;
    expanded: boolean;
  }

  interface Props {
    manifest: TelemetryManifest;
    liveTests: LiveTest[];
    selectedRange: TimeRange | null;
    onRangeChange?: (range: TimeRange | null) => void;
  }

  let { manifest, liveTests, selectedRange = $bindable(null), onRangeChange }: Props = $props();

  let canvas: HTMLCanvasElement;
  let containerEl: HTMLElement;
  let labelsEl: HTMLElement;
  let w = $state(600);
  let h = $state(48);
  let dpr = 1;

  const pad = { left: 48, right: 48, top: 4, bottom: 4 };

  // Interaction state
  let dragging = $state<'left' | 'right' | 'body' | null>(null);
  let dragStartX = 0;
  let dragStartRange: TimeRange | null = null;

  // Derived timeline bounds
  const timeStart = $derived(manifest.startedAt ?? 0);
  const timeEnd = $derived(manifest.finishedAt ?? (manifest.startedAt ?? 0));
  const timeDuration = $derived(Math.max(timeEnd - timeStart, 1));

  // Map steps to their test status
  function getStepStatus(step: StepInfo): string {
    // Try to find a matching liveTest by name and module
    const match = liveTests.find(
      (t) => t.name === step.name && (t.module === step.module || (!t.module && !step.module))
    );
    return match?.status ?? step.status ?? 'queued';
  }

  function statusColor(status: string): string {
    switch (status) {
      case 'passed': return '#22c55e';
      case 'failed': return '#ef4444';
      case 'running': return '#3b82f6';
      case 'skipped': return '#6b7280';
      default: return '#4b5563';
    }
  }

  function statusColorFaint(status: string): string {
    switch (status) {
      case 'passed': return 'rgba(34, 197, 94, 0.15)';
      case 'failed': return 'rgba(239, 68, 68, 0.15)';
      case 'running': return 'rgba(59, 130, 246, 0.15)';
      case 'skipped': return 'rgba(107, 114, 128, 0.10)';
      default: return 'rgba(75, 85, 99, 0.10)';
    }
  }

  function timeToX(t: number): number {
    const plotW = w - pad.left - pad.right;
    return pad.left + ((t - timeStart) / timeDuration) * plotW;
  }

  function xToTime(x: number): number {
    const plotW = w - pad.left - pad.right;
    return timeStart + ((x - pad.left) / plotW) * timeDuration;
  }

  function formatElapsed(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }

  function draw() {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    const barY = pad.top;
    const barH = h - pad.top - pad.bottom;
    const plotW = w - pad.left - pad.right;

    // Background track
    ctx.fillStyle = '#161b22';
    ctx.beginPath();
    ctx.roundRect(pad.left, barY, plotW, barH, 4);
    ctx.fill();

    // Draw step segments
    for (const step of manifest.steps) {
      const status = getStepStatus(step);
      const x1 = Math.max(timeToX(step.startedAt), pad.left);
      const x2 = Math.min(timeToX(step.finishedAt), pad.left + plotW);
      if (x2 <= x1) continue;

      ctx.fillStyle = statusColor(status);
      ctx.globalAlpha = 0.7;
      ctx.beginPath();
      ctx.roundRect(x1 + 0.5, barY + 1, Math.max(x2 - x1 - 1, 2), barH - 2, 2);
      ctx.fill();
      ctx.globalAlpha = 1;
    }

    // Draw gap regions (between steps) as darker
    // Already covered by background track

    // Draw selection overlay
    if (selectedRange) {
      const sx1 = Math.max(timeToX(selectedRange.start), pad.left);
      const sx2 = Math.min(timeToX(selectedRange.end), pad.left + plotW);

      // Dim everything outside selection
      ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
      if (sx1 > pad.left) {
        ctx.fillRect(pad.left, barY, sx1 - pad.left, barH);
      }
      if (sx2 < pad.left + plotW) {
        ctx.fillRect(sx2, barY, pad.left + plotW - sx2, barH);
      }

      // Selection border
      ctx.strokeStyle = '#58a6ff';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.roundRect(sx1, barY, sx2 - sx1, barH, 2);
      ctx.stroke();

      // Handles
      const handleW = 4;
      const handleH = barH * 0.6;
      const handleY = barY + (barH - handleH) / 2;
      ctx.fillStyle = '#58a6ff';
      // Left handle
      ctx.beginPath();
      ctx.roundRect(sx1 - handleW / 2, handleY, handleW, handleH, 2);
      ctx.fill();
      // Right handle
      ctx.beginPath();
      ctx.roundRect(sx2 - handleW / 2, handleY, handleW, handleH, 2);
      ctx.fill();
    }

    // Time labels at start and end
    ctx.font = '10px ui-monospace, monospace';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#6b7280';
    ctx.textAlign = 'right';
    ctx.fillText(formatElapsed(0), pad.left - 6, barY + barH / 2);
    ctx.textAlign = 'left';
    ctx.fillText(formatElapsed(timeDuration), pad.left + plotW + 6, barY + barH / 2);

    ctx.restore();
  }

  // Redraw on any relevant change
  $effect(() => {
    // Touch reactive deps
    void manifest;
    void liveTests;
    void selectedRange;
    void w;
    void h;
    draw();
  });

  function hitTest(clientX: number): { type: 'left-handle' | 'right-handle' | 'body' | 'step'; step?: StepInfo } | null {
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const x = (clientX - rect.left);

    // Check selection handles first
    if (selectedRange) {
      const sx1 = timeToX(selectedRange.start);
      const sx2 = timeToX(selectedRange.end);
      if (Math.abs(x - sx1) < 8) return { type: 'left-handle' };
      if (Math.abs(x - sx2) < 8) return { type: 'right-handle' };
      if (x >= sx1 && x <= sx2) return { type: 'body' };
    }

    // Check steps
    const t = xToTime(x);
    for (const step of manifest.steps) {
      if (t >= step.startedAt && t <= step.finishedAt) {
        return { type: 'step', step };
      }
    }
    return null;
  }

  function onPointerDown(e: PointerEvent) {
    const hit = hitTest(e.clientX);
    if (!hit) return;

    if (hit.type === 'left-handle' && selectedRange) {
      dragging = 'left';
      dragStartX = e.clientX;
      dragStartRange = { ...selectedRange };
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    } else if (hit.type === 'right-handle' && selectedRange) {
      dragging = 'right';
      dragStartX = e.clientX;
      dragStartRange = { ...selectedRange };
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    } else if (hit.type === 'body' && selectedRange) {
      dragging = 'body';
      dragStartX = e.clientX;
      dragStartRange = { ...selectedRange };
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    } else if (hit.type === 'step' && hit.step) {
      // Click step to select/deselect
      const step = hit.step;
      if (
        selectedRange &&
        Math.abs(selectedRange.start - step.startedAt) < 0.5 &&
        Math.abs(selectedRange.end - step.finishedAt) < 0.5
      ) {
        // Same step clicked again — clear selection
        selectedRange = null;
        onRangeChange?.(null);
      } else {
        selectedRange = { start: step.startedAt, end: step.finishedAt };
        onRangeChange?.(selectedRange);
      }
    }
  }

  function onPointerMove(e: PointerEvent) {
    if (!dragging || !dragStartRange) return;
    const rect = canvas.getBoundingClientRect();
    const dx = e.clientX - dragStartX;
    const plotW = w - pad.left - pad.right;
    const dt = (dx / plotW) * timeDuration;

    if (dragging === 'left') {
      const newStart = Math.max(timeStart, Math.min(dragStartRange.start + dt, dragStartRange.end - 1));
      selectedRange = { start: newStart, end: dragStartRange.end };
      onRangeChange?.(selectedRange);
    } else if (dragging === 'right') {
      const newEnd = Math.min(timeEnd, Math.max(dragStartRange.end + dt, dragStartRange.start + 1));
      selectedRange = { start: dragStartRange.start, end: newEnd };
      onRangeChange?.(selectedRange);
    } else if (dragging === 'body') {
      const rangeDur = dragStartRange.end - dragStartRange.start;
      let newStart = dragStartRange.start + dt;
      let newEnd = dragStartRange.end + dt;
      // Clamp
      if (newStart < timeStart) { newStart = timeStart; newEnd = timeStart + rangeDur; }
      if (newEnd > timeEnd) { newEnd = timeEnd; newStart = timeEnd - rangeDur; }
      selectedRange = { start: newStart, end: newEnd };
      onRangeChange?.(selectedRange);
    }
  }

  function onPointerUp(e: PointerEvent) {
    if (dragging) {
      dragging = null;
      dragStartRange = null;
    }
  }

  // Cursor style
  function updateCursor(e: MouseEvent) {
    if (!canvas) return;
    const hit = hitTest(e.clientX);
    if (hit?.type === 'left-handle' || hit?.type === 'right-handle') {
      canvas.style.cursor = 'ew-resize';
    } else if (hit?.type === 'body') {
      canvas.style.cursor = 'grab';
    } else if (hit?.type === 'step') {
      canvas.style.cursor = 'pointer';
    } else {
      canvas.style.cursor = 'default';
    }
  }

  function updateCanvasSize() {
    if (!containerEl) return;
    const r = containerEl.getBoundingClientRect();
    w = Math.max(Math.floor(r.width), 200);
    h = 48;
    dpr = typeof window !== 'undefined' ? (window.devicePixelRatio || 1) : 1;
    if (canvas) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
    }
    draw();
  }

  // Build step label data for HTML overlay
  const stepLabels = $derived.by(() => {
    if (!manifest.steps.length) return [];
    const plotW = w - pad.left - pad.right;
    return manifest.steps.map((step) => {
      const x1 = timeToX(step.startedAt);
      const x2 = timeToX(step.finishedAt);
      const stepW = x2 - x1;
      // Only show label if segment is wide enough
      if (stepW < 20) return null;
      // Short name: strip test_ prefix, truncate
      let label = step.name.replace(/^test_/, '');
      const maxChars = Math.floor(stepW / 6);
      if (label.length > maxChars) label = label.slice(0, maxChars - 1) + '\u2026';
      return { x: x1, w: stepW, label, status: getStepStatus(step) };
    }).filter(Boolean) as { x: number; w: number; label: string; status: string }[];
  });

  onMount(() => {
    const ro = new ResizeObserver(() => updateCanvasSize());
    ro.observe(containerEl);
    updateCanvasSize();
    return () => ro.disconnect();
  });
</script>

<div class="rounded-lg border border-border bg-surface-0 overflow-hidden mb-2">
  <div bind:this={containerEl} class="relative" style="height: 48px;">
    <canvas
      bind:this={canvas}
      class="block absolute inset-0 touch-none"
      onpointermove={(e) => { onPointerMove(e); updateCursor(e); }}
      onpointerdown={onPointerDown}
      onpointerup={onPointerUp}
    ></canvas>
    <!-- Step labels overlay -->
    <div class="absolute inset-0 pointer-events-none" style="padding-left: {pad.left}px; padding-right: {pad.right}px;">
      <div class="relative h-full">
        {#each stepLabels as sl (sl.label + sl.x)}
          <span
            class="absolute text-2xs font-mono truncate text-center leading-none"
            style="left: {sl.x - pad.left}px; width: {sl.w}px; top: 50%; transform: translateY(-50%); color: {statusColor(sl.status)}; opacity: 0.9;"
          >
            {sl.label}
          </span>
        {/each}
      </div>
    </div>
  </div>
</div>
