<script lang="ts">
  import { onMount } from 'svelte';
  import { Activity } from 'lucide-svelte';
  import type { PowerSample, JoulescopeSample } from './types';

  interface Props {
    samples: PowerSample[];
    chgSamples: PowerSample[];
    jsSamples?: JoulescopeSample[];
    windowSeconds?: number;
  }

  let { samples, chgSamples, jsSamples = [], windowSeconds = 60 }: Props = $props();

  let canvas: HTMLCanvasElement;
  let containerEl: HTMLElement;
  let w = $state(400);
  let h = $state(180);
  let dpr = 1;

  // Track data version to know when to redraw
  let lastDrawnSamplesLen = 0;
  let lastDrawnChgLen = 0;
  let lastDrawnJsLen = 0;
  let lastDrawnW = 0;
  let lastDrawnH = 0;
  let rafId: number | null = null;

  // Cursor crosshair state
  let mouseX = $state<number | null>(null);
  let lastDrawnMouseX: number | null = null;

  const pad = { top: 8, right: 8, bottom: 22, left: 38 };

  function formatTime(posixS: number): string {
    return new Date(posixS * 1000).toISOString().slice(11, 19);
  }

  function drawChart() {
    if (!canvas || samples.length < 2) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Compute window — ensure samples are time-sorted (backfill + live can mix)
    const sorted = [...samples].sort((a, b) => a.t - b.t);
    const tMax = sorted[sorted.length - 1].t;
    const tMin0 = tMax - windowSeconds;
    const windowSamples = sorted.filter(s => s.t >= tMin0);
    if (windowSamples.length < 2) return;

    const chgSorted = [...chgSamples].sort((a, b) => a.t - b.t);
    const chgWindow = chgSorted.filter(s => s.t >= windowSamples[0].t && s.t <= tMax);

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

    // Joulescope line (green) — plotted in mA scale (uA / 1000) for same Y-axis
    const jsSorted = [...jsSamples].sort((a, b) => a.t - b.t);
    const jsWindow = jsSorted.filter(s => s.t >= (windowSamples[0]?.t ?? tMin0) && s.t <= tMax);
    if (jsWindow.length > 1) {
      ctx.beginPath();
      const jsToMA = (s: JoulescopeSample) => s.uA / 1000; // uA → mA for shared Y-axis
      ctx.moveTo(toX(jsWindow[0].t), toY(jsToMA(jsWindow[0])));
      for (let j = 1; j < jsWindow.length; j++) {
        ctx.lineTo(toX(jsWindow[j].t), toY(jsToMA(jsWindow[j])));
      }
      ctx.strokeStyle = '#4ade80';
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.8;
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // Cursor crosshair
    if (mouseX !== null && mouseX >= pad.left && mouseX <= pad.left + pw) {
      // Vertical dashed line
      ctx.setLineDash([4, 3]);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(mouseX, pad.top);
      ctx.lineTo(mouseX, pad.top + ph);
      ctx.stroke();
      ctx.setLineDash([]);

      // Find nearest time at mouseX
      const cursorT = tMin + ((mouseX - pad.left) / pw) * tRange;

      // Find nearest DUT sample
      let nearestDut: PowerSample | null = null;
      let bestDist = Infinity;
      for (const s of windowSamples) {
        const d = Math.abs(s.t - cursorT);
        if (d < bestDist) { bestDist = d; nearestDut = s; }
      }

      // Find nearest CHG sample
      let nearestChg: PowerSample | null = null;
      bestDist = Infinity;
      for (const s of chgWindow) {
        const d = Math.abs(s.t - cursorT);
        if (d < bestDist) { bestDist = d; nearestChg = s; }
      }

      // Find nearest Joulescope sample
      let nearestJs: JoulescopeSample | null = null;
      bestDist = Infinity;
      for (const s of jsWindow) {
        const d = Math.abs(s.t - cursorT);
        if (d < bestDist) { bestDist = d; nearestJs = s; }
      }

      // Draw intersection dots
      if (nearestDut) {
        const dx = toX(nearestDut.t);
        const dy = toY(nearestDut.mA);
        ctx.beginPath();
        ctx.arc(dx, dy, 3, 0, Math.PI * 2);
        ctx.fillStyle = '#22d3ee';
        ctx.fill();
        ctx.strokeStyle = '#0d1117';
        ctx.lineWidth = 1;
        ctx.stroke();
      }
      if (nearestChg) {
        const cx = toX(nearestChg.t);
        const cy = toY(nearestChg.mA);
        ctx.beginPath();
        ctx.arc(cx, cy, 3, 0, Math.PI * 2);
        ctx.fillStyle = '#fb923c';
        ctx.fill();
        ctx.strokeStyle = '#0d1117';
        ctx.lineWidth = 1;
        ctx.stroke();
      }
      if (nearestJs) {
        const jx = toX(nearestJs.t);
        const jy = toY(nearestJs.uA / 1000);
        ctx.beginPath();
        ctx.arc(jx, jy, 3, 0, Math.PI * 2);
        ctx.fillStyle = '#4ade80';
        ctx.fill();
        ctx.strokeStyle = '#0d1117';
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // Tooltip box
      const tooltipLines: string[] = [];
      tooltipLines.push(formatTime(cursorT));
      if (nearestDut) tooltipLines.push(`DUT: ${nearestDut.mA.toFixed(1)} mA`);
      if (nearestChg) tooltipLines.push(`CHG: ${nearestChg.mA.toFixed(1)} mA`);
      if (nearestJs) tooltipLines.push(`JS: ${nearestJs.uA.toFixed(1)} \u00B5A`);

      const lineH = 16;
      const tooltipPad = 8;
      const tooltipW = 130;
      const tooltipH = tooltipLines.length * lineH + tooltipPad * 2;

      // Position tooltip: prefer right of cursor, flip if near edge
      let tx = mouseX + 10;
      if (tx + tooltipW > w - 4) tx = mouseX - tooltipW - 10;
      let ty = pad.top + 8;

      // Background
      ctx.fillStyle = 'rgba(22, 27, 34, 0.92)';
      ctx.beginPath();
      ctx.roundRect(tx, ty, tooltipW, tooltipH, 4);
      ctx.fill();
      ctx.strokeStyle = 'rgba(48, 54, 61, 0.8)';
      ctx.lineWidth = 0.5;
      ctx.stroke();

      // Text
      ctx.font = '12px monospace';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      for (let i = 0; i < tooltipLines.length; i++) {
        const line = tooltipLines[i];
        if (line.startsWith('DUT:')) ctx.fillStyle = '#22d3ee';
        else if (line.startsWith('CHG:')) ctx.fillStyle = '#fb923c';
        else if (line.startsWith('JS:')) ctx.fillStyle = '#4ade80';
        else ctx.fillStyle = '#9ca3af';
        ctx.fillText(line, tx + tooltipPad, ty + tooltipPad + i * lineH);
      }
    }

    ctx.restore();
  }

  let lastDrawnFirstT = 0;
  let lastDrawnLastT = 0;

  function rafLoop() {
    const firstT = samples.length > 0 ? samples[0].t : 0;
    const lastT = samples.length > 0 ? samples[samples.length - 1].t : 0;
    const needsRedraw =
      samples.length !== lastDrawnSamplesLen ||
      chgSamples.length !== lastDrawnChgLen ||
      jsSamples.length !== lastDrawnJsLen ||
      w !== lastDrawnW ||
      h !== lastDrawnH ||
      mouseX !== lastDrawnMouseX ||
      firstT !== lastDrawnFirstT ||
      lastT !== lastDrawnLastT;

    if (needsRedraw) {
      lastDrawnSamplesLen = samples.length;
      lastDrawnChgLen = chgSamples.length;
      lastDrawnJsLen = jsSamples.length;
      lastDrawnW = w;
      lastDrawnH = h;
      lastDrawnMouseX = mouseX;
      lastDrawnFirstT = firstT;
      lastDrawnLastT = lastT;
      drawChart();
    }
    rafId = requestAnimationFrame(rafLoop);
  }

  function updateCanvasSize() {
    if (!canvas || !containerEl) return;
    const r = containerEl.getBoundingClientRect();
    const newW = Math.floor(r.width);
    const newH = Math.floor(r.height);
    if (newW < 50 || newH < 30) return; // Layout not settled yet
    w = newW;
    h = newH;
    dpr = window.devicePixelRatio || 1;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    lastDrawnW = 0; // Force redraw
  }

  onMount(() => {
    dpr = window.devicePixelRatio || 1;

    const ro = new ResizeObserver(() => updateCanvasSize());
    ro.observe(containerEl);

    updateCanvasSize();
    rafId = requestAnimationFrame(rafLoop);

    return () => {
      ro.disconnect();
      if (rafId !== null) cancelAnimationFrame(rafId);
    };
  });

  function handleMouseMove(e: MouseEvent) {
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    mouseX = e.clientX - rect.left;
  }

  function handleMouseLeave() {
    mouseX = null;
  }
</script>

<div class="rounded-lg border border-border bg-surface-0 overflow-hidden flex flex-col h-full">
  <div class="flex items-center gap-2 px-3 py-1.5 border-b border-border bg-surface-1 shrink-0">
    <Activity size={12} class="text-accent" />
    <span class="text-xs font-medium text-text-primary">Power</span>
    <span class="flex items-center gap-2 ml-1">
      <span class="flex items-center gap-1">
        <span class="inline-block w-3 h-0.5 rounded" style="background: #22d3ee;"></span>
        <span class="text-2xs text-text-tertiary">DUT</span>
      </span>
      <span class="flex items-center gap-1">
        <span class="inline-block w-3 h-0.5 rounded" style="background: #fb923c;"></span>
        <span class="text-2xs text-text-tertiary">CHG</span>
      </span>
      {#if jsSamples.length > 0}
        <span class="flex items-center gap-1">
          <span class="inline-block w-3 h-0.5 rounded" style="background: #4ade80;"></span>
          <span class="text-2xs text-text-tertiary">JS</span>
        </span>
      {/if}
    </span>
    {#if samples.length > 0}
      {@const last = samples[samples.length - 1]}
      {@const lastChg = chgSamples.length > 0 ? chgSamples[chgSamples.length - 1] : null}
      {@const lastJs = jsSamples.length > 0 ? jsSamples[jsSamples.length - 1] : null}
      <span class="ml-auto text-2xs font-mono">
        <span class="text-cyan-400">{last.mA.toFixed(1)}</span>
        {#if lastChg}<span class="text-text-tertiary"> / </span><span class="text-orange-400">{lastChg.mA.toFixed(1)}</span>{/if}
        <span class="text-text-tertiary"> mA</span>
        {#if lastJs}<span class="text-text-tertiary"> | </span><span class="text-green-400">{lastJs.uA.toFixed(1)} &micro;A</span>{/if}
      </span>
    {:else}
      <span class="ml-auto text-2xs text-text-tertiary">No data</span>
    {/if}
  </div>
  <div bind:this={containerEl} class="bg-[#0d1117] flex-1 overflow-hidden relative">
    <canvas bind:this={canvas} class="block absolute inset-0" onmousemove={handleMouseMove} onmouseleave={handleMouseLeave}></canvas>
    {#if samples.length < 2}
      <div class="absolute inset-0 flex items-center justify-center z-10">
        <div class="text-center">
          <Activity size={24} class="mx-auto text-text-tertiary opacity-20 mb-2" />
          <div class="text-xs text-text-tertiary">Waiting for power data</div>
          <div class="text-2xs text-text-tertiary mt-1 opacity-60">Streams when DUT is powered</div>
        </div>
      </div>
    {/if}
  </div>
</div>
