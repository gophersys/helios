<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { ArrowLeft } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch } from '$lib/api';
  import { ErrorAlert, LoadingState, StatusBadge } from '$lib/components/ui';
  import SlotNavigator from '$lib/components/execution/slot-navigator.svelte';
  import SlotExecutionView from '$lib/components/execution/slot-execution-view.svelte';
  import { SlotContext } from '$lib/components/execution/slot-context.svelte';
  import {
    subscribeRunWithLogs,
  } from '$lib/services/websocket';
  import { formatDuration } from '$lib/utils/formatting';
  import type { TestRun, RunTarget } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  const auth = getAuth();
  const sessionId = $derived($page.params.id);
  const runId = $derived($page.params.runId);

  let run = $state<TestRun | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Slot execution detail
  let slots = $state<SlotContext[]>([]);
  let activeSlotIdx = $state(0);
  let unsubscribe: (() => void) | null = null;

  const activeSlot = $derived(slots[activeSlotIdx] || null);

  const slotTabs = $derived(slots.map((s) => ({
    index: s.slotIndex,
    label: `Slot ${s.slotIndex + 1}`,
    serialNumber: s.serialNumber || undefined,
    status: s.status,
  })));

  // Hardware info for dynamic UART labels
  let socLabels = $state<string[]>([]);
  let productName = $state('');
  let boardRevision = $state('');
  let firmwareVersion = $state('');

  async function fetchRun() {
    error = null;
    try {
      const res = await apiFetch<ApiResponse<TestRun>>(`/v2/runs/${runId}`);
      run = res.data;

      // Extract hardware info
      const rev = run.boardRevision;
      socLabels = rev?.socs || [];
      productName = run.product?.name || '';
      boardRevision = rev?.version || '';
      firmwareVersion = run.assetSet?.version || '';

      // Build slot contexts
      const targets = run.targets || [];
      const built: SlotContext[] = [];
      for (const target of targets) {
        const slot = new SlotContext(target.id, target.slotIndex, target.serialNumber || '');
        slot.hydrateFromTarget(target);
        slot.startClock();
        built.push(slot);
      }
      slots = built;

      // Subscribe to live events if active
      if (run.status === 'ACTIVE' || run.status === 'PENDING') {
        unsubscribe = subscribeRunWithLogs(run.id, {
          onTestStart: (data) => {
            const slot = findSlot(data.targetId);
            if (slot) slot.handleTestStart(data);
          },
          onTestResult: (data) => {
            const slot = findSlot(data.targetId);
            if (slot) slot.handleTestResult(data);
          },
          onLogChunk: (data) => {
            if (activeSlot) activeSlot.handleLogChunk(data);
          },
          onTelemetry: (data) => {
            if (activeSlot) activeSlot.handleTelemetry(data);
          },
          onRunFinish: () => {
            for (const s of slots) s.handleRunFinish();
            fetchRun();
          },
        });
      }
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load run';
    } finally {
      loading = false;
    }
  }

  function findSlot(targetId?: string): SlotContext | undefined {
    if (!targetId) return slots[activeSlotIdx];
    return slots.find((s) => s.targetId === targetId) || slots[activeSlotIdx];
  }

  function getDuration(target: RunTarget): string | null {
    if (!target.startedAt) return null;
    const start = new Date(target.startedAt).getTime();
    const end = target.completedAt ? new Date(target.completedAt).getTime() : Date.now();
    return formatDuration(end - start);
  }

  onMount(() => {
    if (!auth.hasPermission('manufacturing:view')) {
      goto('/');
      return;
    }
    fetchRun();
  });

  onDestroy(() => {
    if (unsubscribe) unsubscribe();
    for (const s of slots) s.destroy();
  });
</script>

<svelte:head>
  <title>Run {run?.panelIdentifier || runId.slice(0, 8)} — Manufacturing — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  {#if loading}
    <LoadingState message="Loading run..." />
  {:else if error && !run}
    <ErrorAlert message={error} />
  {:else if run}
    <ErrorAlert message={error} />

    <!-- Back nav -->
    <button
      onclick={() => goto(`/manufacturing/session/${sessionId}`)}
      class="mb-3 flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
    >
      <ArrowLeft size={14} />
      Back to session
    </button>

    <!-- Run header -->
    <div class="mb-6 flex items-start justify-between gap-4">
      <div>
        <div class="flex items-center gap-3 mb-1">
          <h1 class="text-lg font-semibold text-text-primary">
            {run.panelIdentifier || run.name || `Run ${runId.slice(0, 8)}`}
          </h1>
          <StatusBadge status={run.status} />
        </div>
        <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-secondary">
          <span>Targets: <span class="font-medium text-text-primary">{run.targetCount}</span></span>
          <span>Passed: <span class="font-medium text-success">{run.passedCount}</span></span>
          {#if run.failedCount > 0}
            <span>Failed: <span class="font-medium text-error">{run.failedCount}</span></span>
          {/if}
          {#if run.durationMs}
            <span>Duration: <span class="font-medium text-text-primary tabular-nums">{formatDuration(run.durationMs)}</span></span>
          {/if}
        </div>
      </div>
    </div>

    <!-- Slot execution view -->
    {#if activeSlot}
      <SlotNavigator
        slots={slotTabs}
        activeIndex={activeSlotIdx}
        onSelect={(idx) => { activeSlotIdx = idx; }}
      />

      <SlotExecutionView
        slot={activeSlot}
        {productName}
        {boardRevision}
        {firmwareVersion}
        slotLabel={`Slot ${activeSlot.slotIndex + 1}`}
        {socLabels}
        isLive={!activeSlot.liveFinished}
      />
    {:else}
      <!-- Target list fallback when no slot context is available -->
      <div class="space-y-2">
        <h2 class="text-sm font-semibold text-text-primary mb-3">Targets</h2>
        {#each (run.targets || []) as target (target.id)}
          <div class="card card-sm">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <span class="text-xs font-semibold text-text-primary">Slot {target.slotIndex + 1}</span>
                {#if target.serialNumber}
                  <span class="text-2xs font-mono text-text-tertiary">{target.serialNumber}</span>
                {/if}
              </div>
              <div class="flex items-center gap-2">
                {#if getDuration(target)}
                  <span class="text-2xs tabular-nums text-text-tertiary">{getDuration(target)}</span>
                {/if}
                <StatusBadge status={target.status} />
              </div>
            </div>
            {#if target.errorMessage}
              <p class="mt-2 text-2xs text-error bg-error-muted rounded px-2 py-1 truncate" title={target.errorMessage}>
                {target.errorMessage}
              </p>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>
