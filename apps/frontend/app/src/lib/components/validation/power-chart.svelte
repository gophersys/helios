<script lang="ts">
  import { onMount } from 'svelte';
  import { Activity } from 'lucide-svelte';
  import type { PowerSample } from './types';

  interface Props {
    samples: PowerSample[];
    chgSamples: PowerSample[];
    windowSeconds?: number;
  }

  let { samples, chgSamples, windowSeconds = 60 }: Props = $props();

  let canvas: HTMLCanvasElement;
  let containerEl: HTMLElement;
  let w = $state(400);
  let h = $state(180);
  let dpr = 1;

  // Track data version to know when to redraw
  let lastDrawnSamplesLen = 0;
  let lastDrawnChgLen = 0;
  let lastDrawnW = 0;
  let lastDrawnH = 0;
  let rafId: number | null = null;

  const pad = { top: 8, right: 8, bottom: 22, left: 38 };

  function formatTime(posixS: number): string {
    return new Date(posixS * 1000).toISOString().slice(11, 19);
  }

  function drawChart() {
    if (!canvas || samples.length < 2) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Compute window
    const tMax = samples[samples.length - 1].t;
    const tMin0 = tMax - windowSeconds;
    const windowSamples = samples.filter(s => s.t >= tMin0);
    if (windowSamples.length < 2) return;

    const chgWindow = chgSamples.filter(s => s.t >= windowSamples[0].t && s.t <= tMax);

    const allMA = windowSamples.map(s => s.mA);
    if (chgWindow.length > 0) allMA.push(...chgWindow.map(s => s.mA));

    const minMA = 0;
    const maxMA = Math.max(120, ...allMA) * 1.1;
    const rangeMA = Math.max(maxMA - minMA, 1);
    const tMin = windowSamples[0].t;
    const tRange = Math.max(tMax - tMin, 1);

    const pw = w - pad.left - pad.right;
    const ph = h - pad.top - pad.bottom;

    // Clear
    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    // Background
    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, w, h);

    // Grid lines
    ctx.strokeStyle = '#1e2a3a';
    ctx.lineWidth = 0.5;

    // Horizontal grid
    ctx.beginPath();
    ctx.moveTo(pad.left, pad.top);
    ctx.lineTo(pad.left + pw, pad.top);
    ctx.stroke();

    ctx.setLineDash([2, 2]);
    ctx.beginPath();
    ctx.moveTo(pad.left, pad.top + ph / 2);
    ctx.lineTo(pad.left + pw, pad.top + ph / 2);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.beginPath();
    ctx.moveTo(pad.left, pad.top + ph);
    ctx.lineTo(pad.left + pw, pad.top + ph);
    ctx.stroke();

    // Vertical grid + X-axis labels
    ctx.setLineDash([2, 2]);
    ctx.font = '7px sans-serif';
    ctx.fillStyle = '#6b7280';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    for (const frac of [0, 0.25, 0.5, 0.75, 1]) {
      const tickT = tMin + tRange * frac;
      const tickX = pad.left + pw * frac;
      ctx.beginPath();
      ctx.moveTo(tickX, pad.top);
      ctx.lineTo(tickX, pad.top + ph);
      ctx.stroke();
      ctx.fillText(formatTime(tickT), tickX, h - 12);
    }
    ctx.setLineDash([]);

    // Y-axis labels
    ctx.textAlign = 'end';
    ctx.textBaseline = 'top';
    ctx.font = '8px sans-serif';
    ctx.fillStyle = '#6b7280';
    ctx.fillText(maxMA.toFixed(0), pad.left - 4, pad.top);
    ctx.fillText(((maxMA + minMA) / 2).toFixed(0), pad.left - 4, pad.top + ph / 2 - 3);
    ctx.fillText(minMA.toFixed(0), pad.left - 4, pad.top + ph - 3);

    // mA rotated label
    ctx.save();
    ctx.translate(8, pad.top + ph / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center';
    ctx.font = '7px sans-serif';
    ctx.fillText('mA', 0, 0);
    ctx.restore();

    // Helper: map sample to canvas coords
    function toX(t: number) { return pad.left + ((t - tMin) / tRange) * pw; }
    function toY(mA: number) { return pad.top + ph - ((mA - minMA) / rangeMA) * ph; }

    // Fill under DUT curve
    if (windowSamples.length > 1) {
      ctx.beginPath();
      ctx.moveTo(toX(windowSamples[0].t), pad.top + ph);
      for (const s of windowSamples) {
        ctx.lineTo(toX(s.t), toY(s.mA));
      }
      ctx.lineTo(toX(windowSamples[windowSamples.length - 1].t), pad.top + ph);
      ctx.closePath();
      ctx.fillStyle = 'rgba(34,211,238,0.08)';
      ctx.fill();

      // DUT line (cyan)
      ctx.beginPath();
      ctx.moveTo(toX(windowSamples[0].t), toY(windowSamples[0].mA));
      for (let j = 1; j < windowSamples.length; j++) {
        ctx.lineTo(toX(windowSamples[j].t), toY(windowSamples[j].mA));
      }
      ctx.strokeStyle = '#22d3ee';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    // Charger line (orange)
    if (chgWindow.length > 1) {
      ctx.beginPath();
      ctx.moveTo(toX(chgWindow[0].t), toY(chgWindow[0].mA));
      for (let j = 1; j < chgWindow.length; j++) {
        ctx.lineTo(toX(chgWindow[j].t), toY(chgWindow[j].mA));
      }
      ctx.strokeStyle = '#fb923c';
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.8;
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // Legend
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = '#22d3ee';
    ctx.beginPath();
    ctx.moveTo(pad.left, h - 18);
    ctx.lineTo(pad.left + 12, h - 18);
    ctx.stroke();

    ctx.font = '6px sans-serif';
    ctx.fillStyle = '#6b7280';
    ctx.textAlign = 'start';
    ctx.textBaseline = 'middle';
    ctx.fillText('DUT', pad.left + 15, h - 18);

    ctx.strokeStyle = '#fb923c';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad.left + 35, h - 18);
    ctx.lineTo(pad.left + 47, h - 18);
    ctx.stroke();

    ctx.fillText('CHG', pad.left + 50, h - 18);

    ctx.restore();
  }

  function rafLoop() {
    const needsRedraw =
      samples.length !== lastDrawnSamplesLen ||
      chgSamples.length !== lastDrawnChgLen ||
      w !== lastDrawnW ||
      h !== lastDrawnH;

    if (needsRedraw) {
      lastDrawnSamplesLen = samples.length;
      lastDrawnChgLen = chgSamples.length;
      lastDrawnW = w;
      lastDrawnH = h;
      drawChart();
    }
    rafId = requestAnimationFrame(rafLoop);
  }

  function updateCanvasSize() {
    if (!canvas || !containerEl) return;
    const r = containerEl.getBoundingClientRect();
    w = Math.max(Math.floor(r.width), 100);
    h = Math.max(Math.floor(r.height), 80);
    dpr = window.devicePixelRatio || 1;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    // Force redraw on resize
    lastDrawnW = 0;
  }

  onMount(() => {
    dpr = window.devicePixelRatio || 1;

    const ro = new ResizeObserver(() => {
      updateCanvasSize();
    });
    ro.observe(containerEl);
    updateCanvasSize();

    rafId = requestAnimationFrame(rafLoop);

    return () => {
      ro.disconnect();
      if (rafId !== null) cancelAnimationFrame(rafId);
    };
  });
</script>

<div class="rounded-lg border border-border bg-surface-0 overflow-hidden flex flex-col h-full">
  <div class="flex items-center gap-2 px-3 py-1.5 border-b border-border bg-surface-1 flex-shrink-0">
    <Activity size={12} class="text-accent" />
    <span class="text-xs font-medium text-text-primary">Power</span>
    {#if samples.length > 0}
      {@const last = samples[samples.length - 1]}
      {@const lastChg = chgSamples.length > 0 ? chgSamples[chgSamples.length - 1] : null}
      <span class="ml-auto text-2xs font-mono">
        <span class="text-cyan-400">{last.mA.toFixed(1)}</span>
        {#if lastChg}<span class="text-text-tertiary"> / </span><span class="text-orange-400">{lastChg.mA.toFixed(1)}</span>{/if}
        <span class="text-text-tertiary"> mA</span>
      </span>
    {:else}
      <span class="ml-auto text-2xs text-text-tertiary">No data</span>
    {/if}
  </div>
  <div bind:this={containerEl} class="bg-[#0d1117] flex-1 overflow-hidden relative">
    {#if samples.length > 1}
      <canvas bind:this={canvas} class="block absolute inset-0"></canvas>
    {:else}
      <div class="w-full h-full flex items-center justify-center">
        <div class="text-center">
          <Activity size={24} class="mx-auto text-text-tertiary opacity-20 mb-2" />
          <div class="text-xs text-text-tertiary">Waiting for power data</div>
          <div class="text-2xs text-text-tertiary mt-1 opacity-60">Streams when DUT is powered</div>
        </div>
      </div>
    {/if}
  </div>
</div>
