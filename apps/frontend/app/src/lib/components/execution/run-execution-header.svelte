<script lang="ts">
  import {
    ArrowLeft,
    Ban,
    CheckCircle2,
    Clock,
    SkipForward,
    XCircle,
  } from 'lucide-svelte';
  import { goto } from '$app/navigation';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import TimelineWidget from '$lib/components/validation/timeline-widget.svelte';
  import { formatDuration } from '$lib/utils/formatting';
  import { getRunExecutionContext } from './run-execution-context.svelte';
  import type { Snippet } from 'svelte';

  let {
    extra,
  }: {
    extra?: Snippet;
  } = $props();

  const ctx = getRunExecutionContext();

  // Use the active slot for per-slot stats + timeline
  const slot = $derived(ctx.activeSlot);
</script>

{#if ctx.run}
  <div class="flex items-center gap-2 mb-2 px-3 py-1.5 rounded-lg bg-surface-1 border border-border">
    <!-- Back button -->
    <button
      onclick={() => goto(ctx.config.backPath)}
      class="text-text-tertiary hover:text-text-primary transition-colors shrink-0"
      title={ctx.config.backLabel}
    >
      <ArrowLeft size={14} />
    </button>
    <div class="w-px h-4 bg-border"></div>

    <!-- Run title + status -->
    <h1 class="text-sm font-semibold text-text-primary truncate">{ctx.runTitle}</h1>
    <StatusBadge status={ctx.run.status} />

    <!-- LIVE indicator — based on run status, not active slot's running state.
         In multi-slot runs, tests execute sequentially so individual slots may be idle. -->
    {#if ctx.isActive}
      <span class="inline-flex items-center gap-1 rounded-full bg-success-muted px-2 py-0.5 text-2xs font-medium text-success shrink-0">
        <span class="relative flex h-1.5 w-1.5">
          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75"></span>
          <span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-success"></span>
        </span>
        LIVE
      </span>
    {/if}

    <div class="w-px h-4 bg-border"></div>

    <!-- Metadata -->
    <div class="flex items-center gap-3 text-xs text-text-tertiary">
      {#if ctx.productName}
        <span>{ctx.productName}</span>
      {/if}
      {#if slot?.serialNumber}
        <span class="font-mono">{slot.serialNumber}</span>
      {/if}
      {#if ctx.firmwareVersion}
        <span class="font-mono text-2xs bg-surface-2 px-1.5 py-0.5 rounded">v{ctx.firmwareVersion}</span>
      {/if}
    </div>

    <!-- Timeline (interactive in analysis mode) -->
    {#if slot?.activeManifest}
      <div class="flex-3 min-w-48 rounded border border-border bg-surface-0 px-1.5 py-0.5 overflow-visible relative z-20">
        <TimelineWidget
          manifest={slot.activeManifest}
          liveTests={slot.liveTests}
          bind:selectedRange={slot.selectedRange}
          interactive={!ctx.isActive}
        />
      </div>
    {/if}

    <!-- Counts + Duration -->
    <div class="flex items-center gap-3 text-xs text-text-secondary shrink-0 ml-auto">
      <span class="flex items-center gap-1">
        <CheckCircle2 size={12} class="text-success" />
        {ctx.totalPassed}
      </span>
      <span class="flex items-center gap-1">
        <XCircle size={12} class="{ctx.totalFailed > 0 ? 'text-error' : 'text-text-tertiary'}" />
        {ctx.totalFailed}
      </span>
      <span class="flex items-center gap-1">
        <SkipForward size={12} class="text-text-tertiary" />
        {ctx.totalSkipped}
      </span>
      <div class="w-px h-4 bg-border"></div>
      <span class="flex items-center gap-1 text-text-tertiary tabular-nums">
        <Clock size={12} />
        {#if ctx.durationMs !== null}
          {formatDuration(ctx.durationMs)}
        {:else}
          —
        {/if}
      </span>
    </div>

    <!-- Extension slot (validation: trigger/simulate buttons) -->
    {#if extra}
      {@render extra()}
    {/if}

    <!-- Cancel button -->
    {#if ctx.isActive}
      <button
        onclick={() => { ctx.confirmCancel = true; }}
        class="shrink-0 flex items-center gap-1.5 rounded-lg border border-error/30 bg-error/10 px-3 py-1.5 text-xs font-medium text-error hover:bg-error/20 transition-colors"
      >
        <Ban size={12} />
        Cancel
      </button>
    {/if}
  </div>
{/if}
