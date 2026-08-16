<script lang="ts">
  import {
    ArrowLeft,
    Ban,
    CheckCircle2,
    Clock,
    Loader2,
    SkipForward,
    XCircle,
  } from 'lucide-svelte';
  import { goto } from '$app/navigation';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import TimelineWidget from '$lib/components/validation/timeline-widget.svelte';
  import { formatDuration } from '$lib/utils/formatting';
  import { getRunContext } from './run-context.svelte';

  const ctx = getRunContext();
</script>

{#if ctx.run}
  <!-- Compact header bar: back + title + status + counts + duration in 1 row -->
  <div class="flex items-center gap-2 mb-2 px-3 py-1.5 rounded-lg bg-surface-1 border border-border">
    <button onclick={() => goto('/validation/runs')} class="text-text-tertiary hover:text-text-primary transition-colors shrink-0" title="Back to runs">
      <ArrowLeft size={14} />
    </button>
    <div class="w-px h-4 bg-border"></div>
    <h1 class="text-sm font-semibold text-text-primary truncate">{ctx.run.name}</h1>
    <StatusBadge status={ctx.run.status} />
    {#if ctx.liveRunning && ctx.run.status === 'ACTIVE'}
      <span class="inline-flex items-center gap-1 rounded-full bg-success-muted px-2 py-0.5 text-2xs font-medium text-success shrink-0">
        <span class="relative flex h-1.5 w-1.5">
          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75"></span>
          <span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-success"></span>
        </span>
        LIVE
      </span>
    {/if}

    <!-- Separator -->
    <div class="w-px h-4 bg-border"></div>

    <!-- Metadata -->
    <div class="flex items-center gap-3 text-xs text-text-tertiary">
      {#if ctx.run.product}
        <span>{ctx.run.product.name}</span>
      {/if}
      {#if ctx.serialNumber}
        <span class="font-mono">{ctx.serialNumber}</span>
      {/if}
      {#if ctx.imageTag}
        <span class="font-mono text-2xs bg-surface-2 px-1.5 py-0.5 rounded" title="Validation image tag">{ctx.imageTag}</span>
      {/if}
    </div>

    <!-- Timeline (inline in header — live mode grows dynamically, analysis mode shows full run) -->
    {#if ctx.activeManifest}
      <div class="flex-3 min-w-48 rounded border border-border bg-surface-0 px-1.5 py-0.5 overflow-visible relative z-20">
        <TimelineWidget
          manifest={ctx.activeManifest}
          liveTests={ctx.liveTests}
          bind:selectedRange={ctx.selectedRange}
          interactive={!ctx.isActive}
        />
      </div>
    {/if}

    <!-- Counts + Duration pinned to the right -->
    <div class="flex items-center gap-3 text-xs text-text-secondary shrink-0 ml-auto">
      <span class="flex items-center gap-1">
        <CheckCircle2 size={12} class="text-success" />
        {ctx.livePassedCount}
      </span>
      <span class="flex items-center gap-1">
        <XCircle size={12} class="{ctx.liveFailedCount > 0 ? 'text-error' : 'text-text-tertiary'}" />
        {ctx.liveFailedCount}
      </span>
      <span class="flex items-center gap-1">
        <SkipForward size={12} class="text-text-tertiary" />
        {ctx.liveSkippedCount}
      </span>
      <div class="w-px h-4 bg-border"></div>
      <span class="flex items-center gap-1 text-text-tertiary tabular-nums">
        <Clock size={12} />
        {#if ctx.isActive && ctx.run?.startedAt}
          {formatDuration(ctx.nowMs - new Date(ctx.run.startedAt).getTime())}
        {:else if ctx.liveSummary?.durationS}
          {formatDuration(ctx.liveSummary.durationS * 1000)}
        {:else if ctx.durationMs !== null}
          {formatDuration(ctx.durationMs)}
        {:else}
          —
        {/if}
      </span>
    </div>

    <!-- Cancel button -->
    {#if ctx.isActive}
      <button
        onclick={() => { ctx.confirmCancel = true; }}
        class="shrink-0 flex items-center gap-1.5 rounded-lg border border-error/30 bg-error/10 px-3 py-1.5 text-xs font-medium text-error hover:bg-error/20 transition-colors"
      >
        <Ban size={12} />
        Cancel Run
      </button>
    {/if}
  </div>
{/if}
