<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import { ErrorAlert, LoadingState } from '$lib/components/ui';
  import SessionHeader from '$lib/components/manufacturing/session-header.svelte';
  import PanelRunner from '$lib/components/manufacturing/panel-runner.svelte';
  import PanelResultsGrid from '$lib/components/manufacturing/panel-results-grid.svelte';
  import PanelHistory from '$lib/components/manufacturing/panel-history.svelte';
  import {
    subscribeManufacturingRun,
    disconnectRunSocket,
  } from '$lib/services/websocket';
  import type { ManufacturingSessionDetail, TestRun, RunTarget, TestExecution } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  const auth = getAuth();
  const canRun = $derived(auth.hasPermission('manufacturing:run'));
  const sessionId = $derived($page.params.id);

  let session = $state<ManufacturingSessionDetail | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let unsubscribeRun: (() => void) | null = null;

  // The active or most recent pending run (current panel being tested)
  const activeRun = $derived(
    (session?.runs || []).find((r: TestRun) => r.status === 'ACTIVE' || r.status === 'PENDING')
  );

  // Completed runs (not including active/pending)
  const completedRuns = $derived(
    (session?.runs || []).filter((r: TestRun) => r.status !== 'ACTIVE' && r.status !== 'PENDING')
  );

  async function fetchSession() {
    error = null;
    try {
      const res = await apiFetch<ApiResponse<ManufacturingSessionDetail>>(
        `/v2/manufacturing/sessions/${sessionId}`
      );
      session = res.data;

      // Also fetch results if available
      try {
        const resultsRes = await apiFetch<ApiResponse<any>>(
          `/v2/manufacturing/sessions/${sessionId}/results`
        );
        const resultsData = (resultsRes as any).data;
        if (resultsData?.runs) {
          session = { ...session!, runs: resultsData.runs };
        }
      } catch {
        // Results endpoint may not exist yet; that's fine
      }
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load session';
    } finally {
      loading = false;
    }
  }

  function subscribeToRun(runId: string) {
    // Unsubscribe from any previous run
    if (unsubscribeRun) {
      unsubscribeRun();
      unsubscribeRun = null;
    }

    unsubscribeRun = subscribeManufacturingRun(
      runId,
      {
        onRunStart() {
          // Update the run status to ACTIVE in local state
          if (!session?.runs) return;
          const run = session.runs.find((r: TestRun) => r.id === runId);
          if (run) {
            run.status = 'ACTIVE';
            session = { ...session! };
          }
        },

        onTargetStart(data) {
          if (!session?.runs) return;
          const run = session.runs.find((r: TestRun) => r.id === runId);
          if (!run?.targets) return;

          const target = run.targets.find((t: RunTarget) => t.id === data.targetId);
          if (target) {
            target.status = 'RUNNING';
            target.serialNumber = data.serialNumber || target.serialNumber;
            target.startedAt = new Date().toISOString();
            session = { ...session! };
          }
        },

        onExecutionResult(data) {
          if (!session?.runs) return;
          const run = session.runs.find((r: TestRun) => r.id === runId);
          if (!run?.targets) return;

          // Find the target that owns this execution (try explicit targetId first)
          let target: RunTarget | undefined;
          if (data.targetId) {
            target = run.targets.find((t: RunTarget) => t.id === data.targetId);
          }
          // Fallback: find any running target
          if (!target) {
            target = run.targets.find((t: RunTarget) => t.status === 'RUNNING');
          }
          if (!target) return;

          // Update or add execution record
          if (!target.executions) target.executions = [];
          const existingExec = target.executions.find((e: TestExecution) => e.name === data.name);
          if (existingExec) {
            existingExec.status = data.passed ? 'PASSED' : 'FAILED';
            existingExec.durationMs = data.durationMs;
            existingExec.errorMessage = data.errorMessage;
          } else {
            target.executions = [...target.executions, {
              id: `ws-${Date.now()}`,
              targetId: target.id,
              executionIndex: target.executions.length,
              name: data.name,
              status: data.passed ? 'PASSED' : 'FAILED',
              durationMs: data.durationMs,
              errorMessage: data.errorMessage,
              createdAt: new Date().toISOString(),
            } as TestExecution];
          }
          session = { ...session! };
        },

        onTargetResult(data) {
          if (!session?.runs) return;
          const run = session.runs.find((r: TestRun) => r.id === runId);
          if (!run?.targets) return;

          const target = run.targets.find((t: RunTarget) => t.id === data.targetId);
          if (target) {
            target.status = data.status as RunTarget['status'];
            target.completedAt = new Date().toISOString();
            target.durationMs = data.durationMs;
            session = { ...session! };
          }
        },

        onRunFinish(data) {
          if (!session?.runs) return;
          const run = session.runs.find((r: TestRun) => r.id === runId);
          if (run) {
            run.status = data.status as TestRun['status'];
            run.passedCount = data.passed;
            run.failedCount = data.failed;
            run.completedCount = data.total;
            run.durationMs = data.durationMs ?? undefined;
            session = { ...session! };
          }
          // Refresh full data from server to pick up accurate aggregates
          fetchSession();
        },
      },
      (errMsg) => {
        console.error('Manufacturing run WebSocket error:', errMsg);
      }
    );
  }

  function setupWebSocket() {
    if (!session?.runs) return;
    // Find the latest active or pending run to subscribe to
    const run = session.runs.find(
      (r: TestRun) => r.status === 'ACTIVE' || r.status === 'PENDING'
    );
    if (run) {
      subscribeToRun(run.id);
    }
  }

  async function handleRunPanel(qrCode: string) {
    error = null;
    try {
      const res = await api.post(`/v2/manufacturing/sessions/${sessionId}/runs`, { qrCode });
      await fetchSession();
      // Subscribe to the newly created run
      const newRun = (session?.runs || []).find(
        (r: TestRun) => r.status === 'ACTIVE' || r.status === 'PENDING'
      );
      if (newRun) {
        subscribeToRun(newRun.id);
      }
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to run panel';
    }
  }

  async function handleEndSession() {
    error = null;
    try {
      await api.post(`/v2/manufacturing/sessions/${sessionId}/end`);
      await fetchSession();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to end session';
    }
  }

  onMount(() => {
    if (!auth.hasPermission('manufacturing:view')) {
      goto('/');
      return;
    }
    fetchSession().then(() => {
      if (session?.status === 'ACTIVE') {
        setupWebSocket();
      }
    });
  });

  onDestroy(() => {
    if (unsubscribeRun) unsubscribeRun();
    disconnectRunSocket();
  });
</script>

<svelte:head>
  <title>{session?.product?.name || 'Session'} — Manufacturing — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  {#if loading}
    <LoadingState message="Loading session..." />
  {:else if error && !session}
    <ErrorAlert message={error} />
  {:else if session}
    <ErrorAlert message={error} />

    <SessionHeader {session} />

    <!-- Panel Runner (input + controls) -->
    <PanelRunner
      {session}
      {canRun}
      onRunPanel={handleRunPanel}
      onEndSession={handleEndSession}
    />

    <!-- Active Run (current panel) -->
    {#if activeRun}
      <div class="mb-6">
        <h2 class="text-sm font-semibold text-text-primary mb-3">Active Panel</h2>
        <PanelResultsGrid panel={activeRun} />
      </div>
    {/if}

    <!-- Run History (completed panels) -->
    {#if completedRuns.length > 0}
      <div>
        <h2 class="text-sm font-semibold text-text-primary mb-3">
          Panel History ({completedRuns.length})
        </h2>
        <PanelHistory panels={completedRuns} />
      </div>
    {/if}

    <!-- Empty state when no runs at all -->
    {#if !activeRun && completedRuns.length === 0}
      <div class="rounded-xl border border-border bg-surface-1 p-8 text-center">
        <p class="text-sm text-text-tertiary">
          {#if session.status === 'ACTIVE'}
            Scan a panel QR code to begin manufacturing.
          {:else}
            No panels were run during this session.
          {/if}
        </p>
      </div>
    {/if}
  {/if}
</div>
