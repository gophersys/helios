<script lang="ts">
  import { Loader2 } from 'lucide-svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import { type RunExecutionContext, getRunExecutionContext } from './run-execution-context.svelte';
  import RunExecutionHeader from './run-execution-header.svelte';
  import SlotNavigator from './slot-navigator.svelte';
  import SlotExecutionView from './slot-execution-view.svelte';
  import CancelRunDialog from './cancel-run-dialog.svelte';
  import type { Snippet } from 'svelte';

  let {
    ctx,
    headerExtra,
    aboveExecution,
  }: {
    ctx: RunExecutionContext;
    headerExtra?: Snippet;
    aboveExecution?: Snippet;
  } = $props();

  // Remove max-w-7xl from parent content wrapper for full viewport width
  function fullWidth(node: HTMLElement) {
    const parent = node.closest('.max-w-7xl');
    if (parent) {
      parent.classList.remove('max-w-7xl');
      parent.classList.add('max-w-full');
    }
    return {
      destroy() {
        if (parent) {
          parent.classList.remove('max-w-full');
          parent.classList.add('max-w-7xl');
        }
      }
    };
  }

  const activeSlot = $derived(ctx.activeSlot);

  // Auto-select first stage when stages appear
  $effect(() => {
    void activeSlot?.stages;
    ctx.autoSelectStage();
  });

  // Auto-focus on running test when it first appears
  $effect(() => {
    void activeSlot?.liveTests;
    void ctx.run;
    ctx.tryInitialFocus();
  });

  // Fetch telemetry manifest when run finishes
  $effect(() => {
    void ctx.run;
    // Triggers _checkTelemetryFetch via _fetchRun
  });

  // Handle selectedRange changes for auto-expand
  $effect(() => {
    void activeSlot?.selectedRange;
    ctx.handleRangeChange();
  });

  // Escape key: clear time range selection + re-enable auto-follow
  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && activeSlot?.selectedRange) {
      activeSlot.selectedRange = null;
      activeSlot.autoFollow = true;

      const running = activeSlot.liveTests.find(t => t.status === 'running');
      if (running) {
        if (running.module && running.module !== activeSlot.selectedStage) {
          activeSlot.selectedStage = running.module;
        }
        for (const t of activeSlot.liveTests) {
          t.expanded = (t.name === running.name && t.module === running.module);
        }
        activeSlot.liveTests = activeSlot.liveTests;
      }

      e.preventDefault();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<svelte:head>
  <title>{ctx.runTitle} — Concord</title>
</svelte:head>

<div class="animate-fade-in" use:fullWidth>
  {#if ctx.loading}
    <LoadingState message="Loading run..." />
  {:else if ctx.error && !ctx.run}
    <ErrorAlert message={ctx.error} />
  {:else if ctx.run}
    <ErrorAlert message={ctx.error} />

    <!-- Shared header (back, title, status, timeline, counts, cancel) -->
    <RunExecutionHeader extra={headerExtra} />

    <!-- Optional domain-specific content above execution view -->
    {#if aboveExecution}
      {@render aboveExecution()}
    {/if}

    <!-- Slot navigator (auto-hidden for single target) -->
    {#if ctx.isMultiSlot}
      <SlotNavigator
        slots={ctx.slotTabs}
        activeIndex={ctx.activeSlotIdx}
        onSelect={(idx) => { ctx.activeSlotIdx = idx; }}
      />
    {/if}

    <!-- Slot execution view -->
    {#if activeSlot}
      <SlotExecutionView
        slot={activeSlot}
        productName={ctx.productName}
        boardRevision={ctx.boardRevision}
        firmwareVersion={ctx.firmwareVersion}
        slotLabel={ctx.isMultiSlot ? `Slot ${activeSlot.slotIndex + 1}` : (activeSlot.serialNumber || '')}
        socLabels={ctx.socLabels}
        isLive={ctx.isActive}
      />
    {:else}
      <div class="flex items-center justify-center h-64 text-text-tertiary text-sm">
        No test data yet. Waiting for test runner...
      </div>
    {/if}

    <CancelRunDialog />
  {/if}
</div>
