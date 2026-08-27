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
  import CancelDialog from '$lib/components/validation/cancel-dialog.svelte';
  import SlotExecutionView from '$lib/components/execution/slot-execution-view.svelte';

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

  // Create and provide RunContext to all children via setContext.
  // svelte-ignore state_referenced_locally
  const ctx = createRunContext(runId!);

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

  // Escape key: clear time range selection + re-enable auto-follow
  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && ctx.selectedRange) {
      ctx.selectedRange = null;
      ctx.autoFollow = true;
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

  // Get or create SlotContext for the shared execution view
  const slotCtx = $derived(ctx.slotCtx);

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

    <!-- Run-level header (cancel, trigger, demo — validation-specific) -->
    <RunHeader />

    <!-- Shared execution view (test list + charts + UART) -->
    {#if slotCtx && (ctx.liveTests.length > 0 || ctx.buildJobs.length > 0)}
      <SlotExecutionView
        slot={slotCtx}
        productName={ctx.run.product?.name ?? ''}
        boardRevision={ctx.run.boardRevision?.version ?? ''}
        firmwareVersion={ctx.imageTag ?? ''}
        slotLabel={ctx.serialNumber ?? ''}
        socLabels={ctx.socLabels}
        isLive={ctx.isActive}
      />
    {/if}
  {/if}

  <CancelDialog />
</div>
