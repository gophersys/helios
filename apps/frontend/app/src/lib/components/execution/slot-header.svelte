<script lang="ts">
  import { CheckCircle2, Loader2, WifiOff, XCircle } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import TimelineWidget from '$lib/components/validation/timeline-widget.svelte';
  import { formatDuration } from '$lib/utils/formatting';
  import { getSlotContext } from './slot-context.svelte';

  let {
    productName = '',
    boardRevision = '',
    firmwareVersion = '',
    slotLabel = '',
    isLive = false,
  }: {
    productName?: string;
    boardRevision?: string;
    firmwareVersion?: string;
    slotLabel?: string;
    isLive?: boolean;
  } = $props();

  const ctx = getSlotContext();

  const durationMs = $derived.by(() => {
    const tests = ctx.liveTests;
    const firstStart = tests.reduce((min, t) => {
      if (t.startedAtMs && (min === 0 || t.startedAtMs < min)) return t.startedAtMs;
      return min;
    }, 0);
    if (!firstStart) return null;
    if (ctx.liveFinished) {
      const totalS = tests.reduce((sum, t) => sum + (t.durationS || 0), 0);
      return totalS * 1000;
    }
    return ctx.nowMs - firstStart;
  });
</script>

<div class="mb-3">
  <!-- Top row: product info + status -->
  <div class="flex items-center justify-between gap-4 mb-2">
    <div class="flex items-center gap-3 min-w-0">
      <!-- Product + revision -->
      <div class="flex items-center gap-2 text-sm">
        {#if productName}
          <span class="font-semibold text-text-primary">{productName}</span>
        {/if}
        {#if boardRevision}
          <span class="text-text-tertiary">{boardRevision}</span>
        {/if}
        {#if firmwareVersion}
          <span class="font-mono text-2xs text-text-tertiary bg-surface-2 px-1.5 py-0.5 rounded">
            v{firmwareVersion}
          </span>
        {/if}
      </div>

      <!-- Slot + serial -->
      {#if slotLabel || ctx.serialNumber}
        <span class="text-text-tertiary">·</span>
        {#if slotLabel}
          <span class="text-sm text-text-secondary">{slotLabel}</span>
        {/if}
        {#if ctx.serialNumber}
          <span class="font-mono text-2xs text-text-tertiary">{ctx.serialNumber}</span>
        {/if}
      {/if}
    </div>

    <div class="flex items-center gap-3 shrink-0">
      <!-- Connection status -->
      {#if !ctx.connected && isLive}
        <div class="flex items-center gap-1.5 text-warning text-2xs">
          <WifiOff size={12} />
          <span>Reconnecting...</span>
        </div>
      {/if}

      <!-- Live indicator -->
      {#if isLive && ctx.liveRunning}
        <div class="flex items-center gap-1.5">
          <span class="relative flex h-2 w-2">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2 w-2 bg-accent"></span>
          </span>
          <span class="text-2xs text-accent font-medium">LIVE</span>
        </div>
      {/if}

      <!-- Status badge -->
      <StatusBadge status={ctx.status} />
    </div>
  </div>

  <!-- Counts + duration row -->
  <div class="flex items-center gap-4 text-xs text-text-secondary">
    <div class="flex items-center gap-3">
      {#if ctx.livePassedCount > 0}
        <span class="flex items-center gap-1">
          <CheckCircle2 size={12} class="text-success" />
          <span class="font-medium text-text-primary">{ctx.livePassedCount}</span>
        </span>
      {/if}
      {#if ctx.liveFailedCount > 0}
        <span class="flex items-center gap-1 text-error">
          <XCircle size={12} />
          <span class="font-medium">{ctx.liveFailedCount}</span>
        </span>
      {/if}
      {#if ctx.liveSkippedCount > 0}
        <span class="text-text-tertiary">{ctx.liveSkippedCount} skipped</span>
      {/if}
      <span class="text-text-tertiary">
        / {ctx.liveTests.length} total
      </span>
    </div>

    {#if durationMs}
      <span class="tabular-nums text-text-tertiary">{formatDuration(durationMs)}</span>
    {/if}
  </div>

  <!-- Timeline widget -->
  {#if ctx.activeManifest}
    <div class="mt-2">
      <TimelineWidget
        manifest={ctx.activeManifest}
        liveTests={ctx.liveTests}
        bind:selectedRange={ctx.selectedRange}
        interactive={ctx.analysisMode}
      />
    </div>
  {/if}
</div>
