<script lang="ts">
  import { onMount } from 'svelte';
  import { Cpu } from 'lucide-svelte';
  import type { AccelSample } from './types';

  interface Props {
    samples: AccelSample[];
    windowSeconds?: number;
  }

  let { samples, windowSeconds = 60 }: Props = $props();

  let canvas: HTMLCanvasElement;
  let containerEl: HTMLElement;
  let w = $state(400);
  let h = $state(180);
  let dpr = 1;

  let lastDrawnLen = 0;
  let lastDrawnW = 0;
  let lastDrawnH = 0;
  let rafId: number | null = null;

  let mouseX = $state<number | null>(null);
  let lastDrawnMouseX: number | null = null;

  const pad = { top: 8, right: 8, bottom: 22, left: 38 };

  const colors = { x: '#ef4444', y: '#22c55e', z: '#3b82f6' };

  function formatTime(posixS: number): string {
    return new Date(posixS * 1000).toISOString().slice(11, 19);
  }

  function drawChart() {
    if (!canvas || samples.length < 2) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const sorted = [...samples].sort((a, b) => a.t - b.t);
    const tMax = sorted[sorted.length - 1].t;
    const tMin0 = tMax - windowSeconds;
    const windowSamples = sorted.filter(s => s.t >= tMin0);
    if (windowSamples.length < 2) return;

    const tMin = windowSamples[0].t;
    const tRange = tMax - tMin || 1;

    // Find Y range across all axes
    let yMin = Infinity, yMax = -Infinity;
    for (const s of windowSamples) {
      yMin = Math.min(yMin, s.x, s.y, s.z);
      yMax = Math.max(yMax, s.x, s.y, s.z);
    }
    // Add 10% padding
    const yPad = Math.max(Math.abs(yMax - yMin) * 0.1, 0.1);
    yMin -= yPad;
    yMax += yPad;
    const yRange = yMax - yMin || 1;

    const cw = w - pad.left - pad.right;
    const ch = h - pad.top - pad.bottom;

    function tToX(t: number): number { return pad.left + ((t - tMin) / tRange) * cw; }
    function vToY(v: number): number { return pad.top + ch - ((v - yMin) / yRange) * ch; }

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    // Background
    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, w, h);

    // Grid
    ctx.strokeStyle = '#1e2a3a';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const y = pad.top + (ch * i) / 4;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(w - pad.right, y);
      ctx.stroke();
    }
    // Zero line (if visible)
    if (yMin < 0 && yMax > 0) {
      const zeroY = vToY(0);
      ctx.strokeStyle = '#374151';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(pad.left, zeroY);
      ctx.lineTo(w - pad.right, zeroY);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Draw XYZ lines
    for (const [axis, color] of Object.entries(colors) as [keyof typeof colors, string][]) {
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.globalAlpha = 0.9;
      ctx.beginPath();
      let first = true;
      for (const s of windowSamples) {
        const x = tToX(s.t);
        const y = vToY(s[axis]);
        if (first) { ctx.moveTo(x, y); first = false; }
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // Y-axis labels
    ctx.fillStyle = '#6b7280';
    ctx.font = `${9 * dpr / dpr}px monospace`;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let i = 0; i <= 4; i++) {
      const v = yMin + (yRange * (4 - i)) / 4;
      ctx.fillText(v.toFixed(1), pad.left - 4, pad.top + (ch * i) / 4);
    }

    // Y-axis unit
    ctx.save();
    ctx.translate(8, pad.top + ch / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center';
    ctx.fillStyle = '#6b7280';
    ctx.fillText('g', 0, 0);
    ctx.restore();

    // X-axis time labels
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillStyle = '#6b7280';
    for (let i = 0; i <= 4; i++) {
      const t = tMin + (tRange * i) / 4;
      const x = tToX(t);
      ctx.fillText(formatTime(t), x, h - pad.bottom + 4);
    }

    // Cursor crosshair
    if (mouseX !== null && mouseX >= pad.left && mouseX <= w - pad.right) {
      ctx.strokeStyle = '#ffffff40';
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(mouseX, pad.top);
      ctx.lineTo(mouseX, h - pad.bottom);
      ctx.stroke();
      ctx.setLineDash([]);

      // Find nearest sample
      const cursorT = tMin + ((mouseX - pad.left) / cw) * tRange;
      let nearest = windowSamples[0];
      let bestDist = Infinity;
      for (const s of windowSamples) {
        const d = Math.abs(s.t - cursorT);
        if (d < bestDist) { bestDist = d; nearest = s; }
      }

      // Draw dots on each axis
      for (const [axis, color] of Object.entries(colors) as [keyof typeof colors, string][]) {
        const dx = tToX(nearest.t);
        const dy = vToY(nearest[axis]);
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(dx, dy, 3, 0, Math.PI * 2);
        ctx.fill();
      }

      // Tooltip
      const tooltipX = mouseX < w / 2 ? mouseX + 10 : mouseX - 130;
      const tooltipY = pad.top + 4;
      ctx.fillStyle = 'rgba(30, 42, 58, 0.92)';
      ctx.beginPath();
      ctx.roundRect(tooltipX, tooltipY, 120, 56, 4);
      ctx.fill();

      ctx.font = `${9}px monospace`;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      ctx.fillStyle = '#9ca3af';
      ctx.fillText(formatTime(nearest.t), tooltipX + 6, tooltipY + 4);
      ctx.fillStyle = colors.x;
      ctx.fillText(`X: ${nearest.x.toFixed(3)}g`, tooltipX + 6, tooltipY + 17);
      ctx.fillStyle = colors.y;
      ctx.fillText(`Y: ${nearest.y.toFixed(3)}g`, tooltipX + 6, tooltipY + 30);
      ctx.fillStyle = colors.z;
      ctx.fillText(`Z: ${nearest.z.toFixed(3)}g`, tooltipX + 6, tooltipY + 43);
    }

    ctx.restore();
  }

  function tick() {
    const needsRedraw =
      samples.length !== lastDrawnLen ||
      w !== lastDrawnW ||
      h !== lastDrawnH ||
      mouseX !== lastDrawnMouseX;

    if (needsRedraw) {
      drawChart();
      lastDrawnLen = samples.length;
      lastDrawnW = w;
      lastDrawnH = h;
      lastDrawnMouseX = mouseX;
    }
    rafId = requestAnimationFrame(tick);
  }

  function updateSize() {
    if (!containerEl) return;
    const rect = containerEl.getBoundingClientRect();
    w = Math.max(Math.floor(rect.width), 100);
    h = Math.max(Math.floor(rect.height), 60);
    dpr = typeof window !== 'undefined' ? (window.devicePixelRatio || 1) : 1;
    if (canvas) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
    }
  }

  onMount(() => {
    const ro = new ResizeObserver(() => updateSize());
    ro.observe(containerEl);
    updateSize();
    rafId = requestAnimationFrame(tick);
    return () => {
      ro.disconnect();
      if (rafId) cancelAnimationFrame(rafId);
    };
  });
</script>

<div class="rounded-lg border border-border bg-surface-0 overflow-hidden flex flex-col h-full">
  <div class="flex items-center gap-2 px-3 py-1.5 border-b border-border bg-surface-1 flex-shrink-0">
    <Cpu size={12} class="text-accent" />
    <span class="text-xs font-medium text-text-primary">Accelerometer</span>
    <div class="ml-auto flex items-center gap-2 text-2xs">
      <span class="flex items-center gap-1"><span class="inline-block w-2 h-0.5 rounded" style="background: {colors.x}"></span> X</span>
      <span class="flex items-center gap-1"><span class="inline-block w-2 h-0.5 rounded" style="background: {colors.y}"></span> Y</span>
      <span class="flex items-center gap-1"><span class="inline-block w-2 h-0.5 rounded" style="background: {colors.z}"></span> Z</span>
      <span class="text-text-tertiary ml-1">{samples.length > 0 ? `${samples.length}` : ''}</span>
    </div>
  </div>
  <div bind:this={containerEl} class="bg-[#0d1117] flex-1 overflow-hidden relative">
    {#if samples.length > 1}
      <canvas
        bind:this={canvas}
        class="block absolute inset-0 touch-none"
        onmousemove={(e) => { mouseX = e.clientX - containerEl.getBoundingClientRect().left; }}
        onmouseleave={() => { mouseX = null; }}
      ></canvas>
    {:else}
      <div class="w-full h-full flex items-center justify-center">
        <div class="text-center">
          <Cpu size={24} class="mx-auto text-text-tertiary opacity-20 mb-2" />
          <div class="text-xs text-text-tertiary">Waiting for accelerometer data</div>
          <div class="text-2xs text-text-tertiary mt-1 opacity-60">XYZ from LIS2DE12 sensor</div>
        </div>
      </div>
    {/if}
  </div>
</div>
