<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { ArrowLeft } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import { ErrorAlert, LoadingState } from '$lib/components/ui';
  import SessionHeader from '$lib/components/manufacturing/session-header.svelte';
  import PanelRunner from '$lib/components/manufacturing/panel-runner.svelte';
  import PanelResultsGrid from '$lib/components/manufacturing/panel-results-grid.svelte';
  import PanelHistory from '$lib/components/manufacturing/panel-history.svelte';
  import SlotNavigator from '$lib/components/execution/slot-navigator.svelte';
  import SlotExecutionView from '$lib/components/execution/slot-execution-view.svelte';
  import { SlotContext } from '$lib/components/execution/slot-context.svelte';
  import {
    subscribeManufacturingRun,
    subscribeRunWithLogs,
    getRunSocket,
    disconnectRunSocket,
  } from '$lib/services/websocket';
  import type { ManufacturingSession, TestRun, RunTarget, TestExecution } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  const auth = getAuth();
  const canRun = $derived(auth.hasPermission('manufacturing:run'));
  const sessionId = $derived($page.params.id);

  let session = $state<ManufacturingSession | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let unsubscribeRun: (() => void) | null = null;
  let unsubscribeRunnerStatus: (() => void) | null = null;

  // ── Detail view state ──────────────────────────────────────
  // When a user clicks a unit card, we open the full execution view
  // for that run's slots. The test keeps running in K8s regardless
  // of whether this view is open.
  let detailRunId = $state<string | null>(null);
  let detailSlots = $state<SlotContext[]>([]);
  let detailActiveSlot = $state(0);
  let detailUnsubscribe: (() => void) | null = null;

  // Hardware info for dynamic UART labels
  let detailSocLabels = $state<string[]>([]);
  let detailProductName = $state('');
  let detailBoardRevision = $state('');
  let detailFirmwareVersion = $state('');

  const activeSlot = $derived(detailSlots[detailActiveSlot] || null);

  const slotTabs = $derived(detailSlots.map(s => ({
    index: s.slotIndex,
    label: `Slot ${s.slotIndex + 1}`,
    serialNumber: s.serialNumber || undefined,
    status: s.status,
  })));

  // ── Session-level computed values ──────────────────────────
  const activeRun = $derived(
    (session?.runs || []).find((r: TestRun) => r.status === 'ACTIVE' || r.status === 'PENDING')
  );

  const completedRuns = $derived(
    (session?.runs || []).filter((r: TestRun) => r.status !== 'ACTIVE' && r.status !== 'PENDING')
  );

  // ── Data fetching ──────────────────────────────────────────

  async function fetchSession() {
    error = null;
    try {
      const res = await apiFetch<ApiResponse<ManufacturingSession>>(
        `/v2/manufacturing/sessions/${sessionId}`
      );
      session = res.data;

      try {
        const resultsRes = await apiFetch<ApiResponse<any>>(
          `/v2/manufacturing/sessions/${sessionId}/results`
        );
        const resultsData = (resultsRes as any).data;
        if (resultsData?.runs) {
          session = { ...session!, runs: resultsData.runs };
        }
      } catch {
        // Results endpoint may not exist yet
      }
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load session';
    } finally {
      loading = false;
    }
  }

  // ── Detail view: open/close ────────────────────────────────

  async function openSlotDetail(run: TestRun, targetSlotIndex: number = 0) {
    // Clean up previous detail subscription
    closeSlotDetail();

    detailRunId = run.id;
    detailActiveSlot = 0;

    // Extract hardware info from run or session
    const boardRev = run.boardRevision || session?.fixture?.boardRevision;
    detailSocLabels = boardRev?.socs || [];
    detailProductName = run.product?.name || session?.product?.name || '';
    detailBoardRevision = boardRev?.version || '';
    detailFirmwareVersion = run.assetSet?.version || session?.assetSet?.version || '';

    // Fetch full run detail to get targets with executions and steps
    try {
      const res = await apiFetch<ApiResponse<TestRun>>(`/v2/runs/${run.id}`);
      const fullRun = res.data;

      // Create SlotContext per target
      const targets = fullRun.targets || [];
      const slots: SlotContext[] = [];
      for (const target of targets) {
        const slot = new SlotContext(target.id, target.slotIndex, target.serialNumber || '');
        slot.hydrateFromTarget(target);
        slot.startClock();
        slots.push(slot);
      }
      detailSlots = slots;

      // Set active slot to the one the user clicked
      const clickedIdx = slots.findIndex(s => s.slotIndex === targetSlotIndex);
      if (clickedIdx >= 0) detailActiveSlot = clickedIdx;

      // Subscribe to live events if run is active
      if (fullRun.status === 'ACTIVE' || fullRun.status === 'PENDING') {
        detailUnsubscribe = subscribeRunWithLogs(run.id, {
          onTestStart: (data) => {
            const slot = _findSlotByTargetId(data.targetId);
            if (slot) slot.handleTestStart(data);
          },
          onTestResult: (data) => {
            const slot = _findSlotByTargetId(data.targetId);
            if (slot) slot.handleTestResult(data);
          },
          onLogChunk: (data) => {
            // Route to active slot (UART data doesn't have targetId)
            if (activeSlot) activeSlot.handleLogChunk(data);
          },
          onTelemetry: (data) => {
            // Route telemetry to active slot
            if (activeSlot) activeSlot.handleTelemetry(data);
          },
          onRunFinish: () => {
            for (const slot of detailSlots) {
              slot.handleRunFinish();
            }
            // Refresh session data
            fetchSession();
          },
        });
      }
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load run details';
    }
  }

  function closeSlotDetail() {
    if (detailUnsubscribe) {
      detailUnsubscribe();
      detailUnsubscribe = null;
    }
    for (const slot of detailSlots) {
      slot.destroy();
    }
    detailSlots = [];
    detailRunId = null;
    detailActiveSlot = 0;
  }

  function _findSlotByTargetId(targetId?: string): SlotContext | undefined {
    if (!targetId) return detailSlots[detailActiveSlot];
    return detailSlots.find(s => s.targetId === targetId) || detailSlots[detailActiveSlot];
  }

  // ── Session-level WebSocket ────────────────────────────────

  function subscribeToRun(runId: string) {
    if (unsubscribeRun) {
      unsubscribeRun();
      unsubscribeRun = null;
    }

    unsubscribeRun = subscribeManufacturingRun(
      runId,
      {
        onRunStart() {
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

          let target: RunTarget | undefined;
          if (data.targetId) {
            target = run.targets.find((t: RunTarget) => t.id === data.targetId);
          }
          if (!target) {
            target = run.targets.find((t: RunTarget) => t.status === 'RUNNING');
          }
          if (!target) return;

          if (!target.executions) target.executions = [];
          const existingExec = target.executions.find((e: TestExecution) => e.name === data.name);
          if (existingExec) {
            existingExec.status = data.passed ? 'PASSED' : 'FAILED';
            existingExec.durationMs = data.durationMs;
            existingExec.errorMessage = data.errorMessage;
            existingExec.measurements = data.measurements ?? undefined;
          } else {
            target.executions = [...target.executions, {
              id: `ws-${Date.now()}`,
              targetId: target.id,
              executionIndex: target.executions.length,
              name: data.name,
              status: data.passed ? 'PASSED' : 'FAILED',
              durationMs: data.durationMs,
              errorMessage: data.errorMessage,
              measurements: data.measurements ?? undefined,
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
    const run = session.runs.find(
      (r: TestRun) => r.status === 'ACTIVE' || r.status === 'PENDING'
    );
    if (run) {
      subscribeToRun(run.id);
    }
  }

  function subscribeToRunnerStatus() {
    if (unsubscribeRunnerStatus) {
      unsubscribeRunnerStatus();
      unsubscribeRunnerStatus = null;
    }

    const socket = getRunSocket();
    if (!socket) return;

    const handler = (data: { sessionId: string; runnerStatus: string; timestamp?: string }) => {
      if (data.sessionId === sessionId && session) {
        session = { ...session, runnerStatus: data.runnerStatus, runnerLastHeartbeat: data.timestamp };
      }
    };

    socket.on('manufacturing_runner_status', handler);
    unsubscribeRunnerStatus = () => { socket.off('manufacturing_runner_status', handler); };
  }

  async function handleRunPanel(qrCode: string) {
    error = null;
    try {
      await api.post(`/v2/manufacturing/sessions/${sessionId}/runs`, { qrCode });
      await fetchSession();
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

  function handleSelectUnit(run: TestRun, target: RunTarget) {
    openSlotDetail(run, target.slotIndex);
  }

  // Svelte action: remove max-w constraint for full-width layout
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

  onMount(() => {
    if (!auth.hasPermission('manufacturing:view')) {
      goto('/');
      return;
    }
    fetchSession().then(() => {
      if (session?.status === 'ACTIVE') {
        setupWebSocket();
        subscribeToRunnerStatus();
      }
    });
  });

  onDestroy(() => {
    if (unsubscribeRun) unsubscribeRun();
    if (unsubscribeRunnerStatus) unsubscribeRunnerStatus();
    closeSlotDetail();
    disconnectRunSocket();
  });
</script>

<svelte:head>
  <title>{session?.product?.name || 'Session'} — Manufacturing — Concord</title>
</svelte:head>

<div class="animate-fade-in" use:fullWidth>
  {#if loading}
    <LoadingState message="Loading session..." />
  {:else if error && !session}
    <ErrorAlert message={error} />
  {:else if session}
    <ErrorAlert message={error} />

    <!-- ── Detail View (slot execution) ──────────────────── -->
    {#if detailRunId && activeSlot}
      <div class="mb-3">
        <button
          onclick={closeSlotDetail}
          class="flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
        >
          <ArrowLeft size={16} />
          Back to session
        </button>
      </div>

      <SlotNavigator
        slots={slotTabs}
        activeIndex={detailActiveSlot}
        onSelect={(idx) => { detailActiveSlot = idx; }}
      />

      <SlotExecutionView
        slot={activeSlot}
        productName={detailProductName}
        boardRevision={detailBoardRevision}
        firmwareVersion={detailFirmwareVersion}
        slotLabel={`Slot ${activeSlot.slotIndex + 1}`}
        socLabels={detailSocLabels}
        isLive={!activeSlot.liveFinished}
      />

    <!-- ── Session View (panels + unit grid) ─────────────── -->
    {:else}
      <SessionHeader {session} />

      <PanelRunner
        {session}
        {canRun}
        onRunPanel={handleRunPanel}
        onEndSession={handleEndSession}
      />

      {#if activeRun}
        <div class="mb-6">
          <h2 class="text-sm font-semibold text-text-primary mb-3">Active Panel</h2>
          <PanelResultsGrid
            panel={activeRun}
            onSelectUnit={(target) => handleSelectUnit(activeRun, target)}
          />
        </div>
      {/if}

      {#if completedRuns.length > 0}
        <div>
          <h2 class="text-sm font-semibold text-text-primary mb-3">
            Panel History ({completedRuns.length})
          </h2>
          <PanelHistory panels={completedRuns} onSelectUnit={(panel, target) => handleSelectUnit(panel, target)} />
        </div>
      {/if}

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
  {/if}
</div>
