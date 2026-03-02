<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { beforeNavigate, goto } from '$app/navigation';
  import { page } from '$app/stores';
  import {
    ArrowLeft,
    Ban,
    CheckCircle2,
    Clock,
    Cpu,
    GitCompareArrows,
    Play,
    XCircle,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import type { ValidationRun, ValidationExecution } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import { formatTimeAgo, formatDateTime, formatDuration } from '$lib/utils/formatting';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';

  const auth = getAuth();
  const runId = $derived($page.params.id);

  let run = $state<ValidationRun | null>(null);
  let executions = $state<ValidationExecution[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let cancelling = $state(false);
  let triggering = $state(false);
  let showTrigger = $state(false);
  let triggerFwVersion = $state('');
  let pollInterval: ReturnType<typeof setInterval> | null = null;

  const isActive = $derived(run?.status === 'ACTIVE');

  const progressPct = $derived.by(() => {
    if (!run || !run.targetCount) return 0;
    return Math.round((run.completedCount / run.targetCount) * 100);
  });

  const durationMs = $derived.by(() => {
    if (!run?.startedAt) return null;
    const start = new Date(run.startedAt).getTime();
    const end = run.finishedAt ? new Date(run.finishedAt).getTime() : Date.now();
    return end - start;
  });

  const serialNumber = $derived(
    (run?.config as Record<string, unknown> | null)?.serialNumber as string | undefined
  );

  const firmwareVariant = $derived(
    (run?.config as Record<string, unknown> | null)?.firmwareVariant as string | undefined
  );

  async function fetchRun(): Promise<void> {
    try {
      const res = await apiFetch<ApiResponse<ValidationRun>>(`/v2/validation/runs/${runId}`);
      run = res.data;
      executions = res.data.executions ?? [];
      error = null;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load run';
    } finally {
      loading = false;
    }
  }

  async function cancelRun(): Promise<void> {
    if (!confirm('Cancel this validation run? Queued tests will not be executed.')) return;
    cancelling = true;
    try {
      await api.post(`/v2/validation/runs/${runId}/cancel`);
      await fetchRun();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to cancel run';
    } finally {
      cancelling = false;
    }
  }

  async function triggerRun(): Promise<void> {
    if (!triggerFwVersion.trim()) return;
    triggering = true;
    try {
      await api.post(`/v2/validation/runs/${runId}/trigger`, {
        firmwareVersion: triggerFwVersion.trim(),
      });
      showTrigger = false;
      triggerFwVersion = '';
      await fetchRun();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to trigger run';
    } finally {
      triggering = false;
    }
  }

  function cleanup(): void {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.Validation.View')) {
      goto('/');
      return;
    }
    fetchRun();

    pollInterval = setInterval(() => {
      if (run?.status === 'ACTIVE') fetchRun();
    }, 5000);
  });

  onDestroy(cleanup);
  beforeNavigate(cleanup);
</script>

<svelte:head>
  <title>{run?.name ?? 'Run'} — Validation — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <!-- Back link -->
  <button
    onclick={() => goto('/validation/runs')}
    class="flex items-center gap-1 text-xs text-text-tertiary hover:text-text-primary transition-colors mb-3"
  >
    <ArrowLeft size={14} />
    Validation Runs
  </button>

  {#if loading}
    <LoadingState message="Loading run..." />
  {:else if error && !run}
    <ErrorAlert message={error} />
  {:else if run}
    <ErrorAlert message={error} />

    <!-- Header -->
    <div class="flex items-start justify-between gap-4 mb-6">
      <div>
        <div class="flex items-center gap-3">
          <h1 class="text-lg font-semibold text-text-primary">{run.name}</h1>
          <StatusBadge status={run.status} />
        </div>
        <div class="mt-1 flex items-center gap-4 text-xs text-text-tertiary">
          {#if run.product}
            <span>{run.product.name}</span>
          {/if}
          {#if serialNumber}
            <span class="font-mono">{serialNumber}</span>
          {/if}
          {#if firmwareVariant}
            <span class="capitalize">{firmwareVariant}</span>
          {/if}
          {#if run.createdBy}
            <span>by {run.createdBy.name}</span>
          {/if}
        </div>
      </div>

      <div class="flex items-center gap-2">
        <button
          onclick={() => goto(`/validation/runs/compare?a=${runId}&b=`)}
          class="btn btn-sm flex items-center gap-1.5"
        >
          <GitCompareArrows size={14} />
          Compare...
        </button>
        {#if isActive && auth.hasPermission('Concord.Admin.Validation.Manage')}
          <button
            onclick={() => { showTrigger = !showTrigger; }}
            class="btn btn-sm btn-primary flex items-center gap-1.5"
          >
            <Play size={14} />
            Trigger Run
          </button>
          <button
            onclick={cancelRun}
            disabled={cancelling}
            class="btn btn-sm btn-danger flex items-center gap-1.5"
          >
            <Ban size={14} />
            {cancelling ? 'Cancelling...' : 'Cancel Run'}
          </button>
        {/if}
      </div>
    </div>

    <!-- Trigger form -->
    {#if showTrigger}
      <div class="card mb-4">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-medium text-text-primary">Trigger K8s Validation Job</h3>
          <button onclick={() => { showTrigger = false; }} class="text-text-tertiary hover:text-text-primary text-xs">
            Cancel
          </button>
        </div>
        <form onsubmit={(e) => { e.preventDefault(); triggerRun(); }} class="flex items-end gap-3">
          <div class="flex-1">
            <label for="fw-version" class="mb-1 block text-2xs font-medium text-text-tertiary">Firmware Version</label>
            <input
              id="fw-version"
              bind:value={triggerFwVersion}
              placeholder="e.g. 0.1.12"
              required
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
            />
          </div>
          <button type="submit" disabled={triggering || !triggerFwVersion.trim()} class="btn btn-sm btn-primary">
            {triggering ? 'Triggering...' : 'Trigger'}
          </button>
        </form>
      </div>
    {/if}

    <!-- Stats cards -->
    <div class="grid grid-cols-2 gap-3 sm:grid-cols-4 mb-6">
      <div class="card card-sm">
        <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Progress</div>
        <div class="mt-1 text-xl font-semibold tabular-nums text-text-primary">
          {run.completedCount}<span class="text-sm text-text-tertiary">/{run.targetCount}</span>
        </div>
        {#if run.targetCount > 0}
          <div class="mt-2 h-1.5 w-full rounded-full bg-surface-2">
            <div
              class="h-1.5 rounded-full transition-all duration-500 {run.failedCount > 0 ? 'bg-warning' : 'bg-success'}"
              style:width="{progressPct}%"
            ></div>
          </div>
        {/if}
      </div>

      <div class="card card-sm">
        <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Passed</div>
        <div class="mt-1 flex items-center gap-1.5">
          <CheckCircle2 size={18} class="text-success" />
          <span class="text-xl font-semibold tabular-nums text-text-primary">{run.passedCount}</span>
        </div>
      </div>

      <div class="card card-sm">
        <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Failed</div>
        <div class="mt-1 flex items-center gap-1.5">
          <XCircle size={18} class={run.failedCount > 0 ? 'text-error' : 'text-text-tertiary'} />
          <span class="text-xl font-semibold tabular-nums text-text-primary">{run.failedCount}</span>
        </div>
      </div>

      <div class="card card-sm">
        <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Duration</div>
        <div class="mt-1 flex items-center gap-1.5">
          <Clock size={18} class="text-text-tertiary" />
          <span class="text-xl font-semibold tabular-nums text-text-primary">
            {durationMs !== null ? formatDuration(durationMs) : '—'}
          </span>
        </div>
      </div>
    </div>

    <!-- Devices -->
    {#if run.devices && run.devices.length > 0}
      <div class="mb-6">
        <h2 class="mb-3 text-sm font-medium text-text-primary">Devices</h2>
        <div class="flex flex-wrap gap-2">
          {#each run.devices as device (device.id)}
            <div class="card card-sm flex items-center gap-2">
              <Cpu size={14} class="text-text-tertiary" />
              <span class="font-mono text-xs text-text-primary">{device.serialNumber}</span>
              <StatusBadge status={device.status} />
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Test executions -->
    <div>
      <h2 class="mb-3 text-sm font-medium text-text-primary">
        Test Executions
        <span class="text-text-tertiary font-normal">({executions.length})</span>
      </h2>

      {#if executions.length === 0}
        <div class="card card-sm text-center text-sm text-text-tertiary">
          No test executions yet.
        </div>
      {:else}
        <div class="table-wrapper">
          <table class="table">
            <thead>
              <tr class="border-b border-border">
                <th class="table-header">Test</th>
                <th class="table-header">Category</th>
                <th class="table-header">Status</th>
                <th class="table-header text-right">Results</th>
                <th class="table-header text-right">Started</th>
              </tr>
            </thead>
            <tbody>
              {#each executions as exec (exec.id)}
                <tr class="table-row">
                  <td class="table-cell font-medium text-text-primary">
                    {exec.test?.name ?? exec.testId}
                  </td>
                  <td class="table-cell text-text-secondary">
                    {exec.test?.category ?? '—'}
                  </td>
                  <td class="table-cell">
                    <StatusBadge status={exec.status} />
                  </td>
                  <td class="table-cell text-right tabular-nums text-text-secondary">
                    {#if exec.resultCount !== undefined}
                      {exec.resultsPassed ?? 0}/{exec.resultCount}
                    {:else if exec.results}
                      {exec.results.filter(r => r.passed).length}/{exec.results.length}
                    {:else}
                      —
                    {/if}
                  </td>
                  <td class="table-cell text-right text-text-tertiary">
                    {#if exec.startedAt}
                      <span title={formatDateTime(exec.startedAt)}>
                        {formatTimeAgo(exec.startedAt)}
                      </span>
                    {:else}
                      —
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>

    <!-- Notes -->
    {#if run.notes}
      <div class="mt-6">
        <h2 class="mb-2 text-sm font-medium text-text-primary">Notes</h2>
        <div class="card card-sm text-sm text-text-secondary whitespace-pre-wrap">{run.notes}</div>
      </div>
    {/if}

    <!-- Metadata footer -->
    <div class="mt-6 flex items-center gap-4 text-2xs text-text-tertiary">
      <span>Created {formatDateTime(run.createdAt)}</span>
      {#if run.finishedAt}
        <span>Finished {formatDateTime(run.finishedAt)}</span>
      {/if}
      <span class="font-mono">{run.id}</span>
    </div>
  {/if}
</div>
