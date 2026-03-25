<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { beforeNavigate, goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { Loader2 } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import { createRunContext } from '$lib/components/validation/run-context.svelte';
  import RunHeader from '$lib/components/validation/run-header.svelte';
  import StageSidebar from '$lib/components/validation/stage-sidebar.svelte';
  import TestList from '$lib/components/validation/test-list.svelte';
  import ChartPanel from '$lib/components/validation/chart-panel.svelte';
  import UartPanel from '$lib/components/validation/uart-panel.svelte';
  import ResizeLayout from '$lib/components/validation/resize-layout.svelte';
  import CancelDialog from '$lib/components/validation/cancel-dialog.svelte';

  const auth = getAuth();
  const runId = $derived($page.params.id);

  // Svelte action: removes max-w-7xl from the parent content wrapper
  // so this page can use the full viewport width for UART/power panels
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

  // Create and provide RunContext to all children via setContext
  const ctx = createRunContext(runId);

  // Auto-select first stage when stages appear
  $effect(() => {
    void ctx.stages;
    ctx.autoSelectStage();
  });

  // Auto-focus on running test when it first appears
  $effect(() => {
    void ctx.liveTests;
    void ctx.run;
    ctx.tryInitialFocus();
  });

  // Fetch telemetry manifest when run finishes or page loads for a completed run
  $effect(() => {
    void ctx.run;
    ctx.checkTelemetryFetch();
  });

  // Handle selectedRange changes for auto-expand
  $effect(() => {
    void ctx.selectedRange;
    ctx.handleRangeChange();
  });

  // Escape key: clear time range selection + re-enable auto-follow to running test
  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && ctx.selectedRange) {
      ctx.selectedRange = null;
      ctx.autoFollow = true;
      // Snap back to the running test if there is one
      const running = ctx.liveTests.find(t => t.status === 'running');
      if (running) {
        if (running.module && running.module !== ctx.selectedStage) {
          ctx.selectedStage = running.module;
        }
        for (const t of ctx.liveTests) {
          t.expanded = (t.name === running.name && t.module === running.module);
        }
        ctx.liveTests = ctx.liveTests;
        setTimeout(() => {
          const el = document.querySelector(`[data-test-name="${running.name}"][data-test-module="${running.module}"]`) as HTMLElement;
          if (el) {
            const panel = el.closest('[class*="overflow-y-auto"], [class*="overflow-auto"]') as HTMLElement;
            if (panel) {
              const pr = panel.getBoundingClientRect();
              const er = el.getBoundingClientRect();
              panel.scrollTo({ top: panel.scrollTop + (er.top - pr.top - pr.height * 0.15), behavior: 'smooth' });
            }
          }
        }, 50);
      }
      e.preventDefault();
    }
  }

  onMount(() => {
    if (!auth.hasPermission('validation:view')) {
      goto('/');
      return;
    }
    ctx.subscribe();
  });

  function cleanup() {
    ctx.destroy();
  }

  onDestroy(cleanup);
  beforeNavigate(cleanup);
</script>

<svelte:window onkeydown={handleKeydown} />

<svelte:head>
  <title>{ctx.run?.name ?? 'Run'} — Validation — Concord</title>
</svelte:head>

<div class="animate-fade-in" use:fullWidth>
  {#if ctx.loading}
    <LoadingState message="Loading run..." />
  {:else if ctx.error && !ctx.run}
    <ErrorAlert message={ctx.error} />
  {:else if ctx.run}
    <ErrorAlert message={ctx.error} />

    <RunHeader />

    <!-- Main layout: Top row (stages+tests+charts) -> resize -> UART bottom -->
    {#if ctx.liveTests.length > 0 || ctx.buildJobs.length > 0}
    <div class="flex flex-col relative" data-resize-container style="height: calc(100vh - 90px);">
      <!-- Telemetry loading overlay (analysis mode) -->
      {#if ctx.telemetryLoading && ctx.analysisMode}
        <div class="absolute inset-0 z-20 flex items-center justify-center bg-surface-0/60 backdrop-blur-sm rounded-lg">
          <div class="flex flex-col items-center gap-3">
            <Loader2 size={28} class="text-accent animate-spin" />
            <span class="text-sm text-text-secondary font-medium">Loading telemetry data...</span>
          </div>
        </div>
      {/if}

      <!-- Top row: stages + test steps + telemetry charts -->
      <div class="flex overflow-hidden" style="flex: 0 0 {ctx.topPanelHeight}%;">
        <!-- Stage sidebar -->
        <div class="flex-shrink-0 overflow-y-auto" style="width: {ctx.sidebarWidth}px;">
          <StageSidebar />
        </div>

        <!-- Vertical drag bar: sidebar <-> test steps -->
        <ResizeLayout
          orientation="horizontal"
          initialSize={192}
          minSize={120}
          maxSize={400}
          bind:size={ctx.sidebarWidth}
          bind:resizing={ctx.vResizing as any}
        />

        <!-- Center panel: Test list or build logs for selected stage -->
        <div class="flex-1 min-w-0 overflow-y-auto">
          <TestList />
        </div>

        <!-- Vertical drag bar: test steps <-> charts (xl only) -->
        <div class="hidden xl:flex">
          <ResizeLayout
            orientation="horizontal"
            initialSize={576}
            minSize={300}
            maxSize={800}
            inverted={true}
            bind:size={ctx.chartsWidth}
            bind:resizing={ctx.vResizing as any}
          />
        </div>

        <!-- Telemetry charts (right side of top row) -->
        <div class="flex-shrink-0 hidden xl:flex flex-col gap-2" style="width: {ctx.chartsWidth}px;">
          <ChartPanel />
        </div>
      </div><!-- end top row -->

      <!-- Horizontal resize bar between top panel and UART -->
      <ResizeLayout
        orientation="vertical"
        initialSize={50}
        minSize={15}
        maxSize={80}
        bind:size={ctx.topPanelHeight}
        bind:resizing={ctx.resizing}
      />

      <!-- UART Terminals (full width bottom, resizable) -->
      <div class="flex-1 min-h-0 overflow-hidden">
        <UartPanel />
      </div>
    </div><!-- end main layout -->
    {/if}
  {/if}

  <CancelDialog />
</div>
