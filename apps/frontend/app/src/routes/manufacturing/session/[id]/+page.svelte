<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { ArrowLeft, Archive, Trash2, QrCode } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import { ErrorAlert, EmptyState, LoadingState, Modal, ConfirmDeleteDialog, StatusBadge } from '$lib/components/ui';
  import SessionHeader from '$lib/components/manufacturing/session-header.svelte';
  import PanelGridView from '$lib/components/manufacturing/panel-grid-view.svelte';
  import ScanPanelModal from '$lib/components/manufacturing/scan-panel-modal.svelte';
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

  // ── Scan modal state ───────────────────────────────────────
  let scanModalOpen = $state(false);
  let scanRunType = $state<'panel' | 'standalone'>('panel');

  // ── Detail view state ──────────────────────────────────────
  let detailRunId = $state<string | null>(null);
  let detailSlots = $state<SlotContext[]>([]);
  let detailActiveSlot = $state(0);
  let detailUnsubscribe: (() => void) | null = null;

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

  // ── Fixture-derived values ─────────────────────────────────
  const panelRows = $derived(session?.fixture?.panelRows ?? 1);
  const panelCols = $derived(session?.fixture?.panelCols ?? 1);
  const hasStandaloneSlot = $derived(
    !!(session?.fixture?.metadata as Record<string, unknown> | null)?.hasStandaloneSlot
  );

  // ── Session-level computed values ──────────────────────────
  const activeRun = $derived(
    (session?.runs || []).find((r: TestRun) => r.status === 'ACTIVE' || r.status === 'PENDING')
  );

  const latestRun = $derived(
    (session?.runs || []).length > 0
      ? (session?.runs || [])[(session?.runs || []).length - 1]
      : undefined
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

  // ── Scan modal ─────────────────────────────────────────────

  function openScanModal(type: 'panel' | 'standalone') {
    scanRunType = type;
    scanModalOpen = true;
  }

  async function handleRunStarted(runId: string) {
    scanModalOpen = false;
    await fetchSession();
    const newRun = (session?.runs || []).find(
      (r: TestRun) => r.status === 'ACTIVE' || r.status === 'PENDING'
    );
    if (newRun) {
      subscribeToRun(newRun.id);
    }
  }

  // ── Detail view: open/close ────────────────────────────────

  async function openSlotDetail(run: TestRun, targetSlotIndex: number = 0) {
    closeSlotDetail();

    detailRunId = run.id;
    detailActiveSlot = 0;

    const boardRev = run.boardRevision || session?.fixture;
    detailSocLabels = (boardRev as any)?.socs || [];
    detailProductName = run.product?.name || session?.product?.name || '';
    detailBoardRevision = (boardRev as any)?.version || '';
    detailFirmwareVersion = run.assetSet?.version || session?.assetSet?.version || '';

    try {
      const res = await apiFetch<ApiResponse<TestRun>>(`/v2/runs/${run.id}`);
      const fullRun = res.data;

      const targets = fullRun.targets || [];
      const slots: SlotContext[] = [];
      for (const target of targets) {
        const slot = new SlotContext(target.id, target.slotIndex, target.serialNumber || '');
        slot.hydrateFromTarget(target);
        slot.startClock();
        slots.push(slot);
      }
      detailSlots = slots;

      const clickedIdx = slots.findIndex(s => s.slotIndex === targetSlotIndex);
      if (clickedIdx >= 0) detailActiveSlot = clickedIdx;

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
            if (activeSlot) activeSlot.handleLogChunk(data);
          },
          onTelemetry: (data) => {
            if (activeSlot) activeSlot.handleTelemetry(data);
          },
          onRunFinish: () => {
            for (const slot of detailSlots) {
              slot.handleRunFinish();
            }
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

  async function handleEndSession() {
    error = null;
    try {
      await api.post(`/v2/manufacturing/sessions/${sessionId}/end`);
      await fetchSession();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to end session';
    }
  }

  // ── Archive / Delete ───────────────────────────────────────
  let showArchiveConfirm = $state(false);
  let showDeleteConfirm = $state(false);
  let showEndConfirm = $state(false);
  let archiving = $state(false);
  let deleting = $state(false);

  async function handleArchive() {
    archiving = true;
    error = null;
    try {
      await api.post(`/v2/manufacturing/sessions/${sessionId}/archive`);
      showArchiveConfirm = false;
      await fetchSession();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to archive session';
    } finally {
      archiving = false;
    }
  }

  async function handleDelete() {
    deleting = true;
    error = null;
    try {
      await api.delete(`/v2/manufacturing/sessions/${sessionId}`);
      showDeleteConfirm = false;
      goto('/manufacturing');
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete session';
    } finally {
      deleting = false;
    }
  }

  function handleSelectUnit(run: TestRun, target: RunTarget) {
    openSlotDetail(run, target.slotIndex);
  }

  function handleSlotClick(slotIndex: number) {
    if (!activeRun) return;
    const target = (activeRun.targets || []).find((t: RunTarget) => t.slotIndex === slotIndex);
    if (target) {
      openSlotDetail(activeRun, slotIndex);
    }
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
      <div class="mb-4">
        <button
          onclick={closeSlotDetail}
          class="btn btn-ghost btn-sm"
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

    <!-- ── Session View ──────────────────────────────────── -->
    {:else}
      <SessionHeader {session} />

      {#if session.status === 'ARCHIVED'}
        <div class="mb-4 rounded-lg border border-warning/30 bg-warning-muted px-4 py-3 text-sm text-warning">
          This session is archived.
        </div>
      {/if}

      <!-- Panel Grid + Scan Controls -->
      <div class="mb-6 space-y-4">
        <!-- Scan action buttons -->
        {#if canRun && session.status === 'ACTIVE'}
          <div class="flex items-center gap-2">
            <button onclick={() => openScanModal('panel')} class="btn btn-md btn-primary">
              <QrCode size={16} />
              Scan Panel
            </button>
            {#if hasStandaloneSlot}
              <button onclick={() => openScanModal('standalone')} class="btn btn-md btn-ghost">
                Scan Standalone
              </button>
            {/if}
            <div class="ml-auto">
              <button
                onclick={() => { showEndConfirm = true; }}
                disabled={!!activeRun}
                class="btn btn-sm btn-secondary"
              >
                End Session
              </button>
            </div>
          </div>
        {/if}

        <!-- Live panel grid -->
        <PanelGridView
          {panelRows}
          {panelCols}
          {hasStandaloneSlot}
          targets={activeRun?.targets ?? latestRun?.targets ?? []}
          onSlotClick={handleSlotClick}
        />
      </div>

      <!-- Archive / Delete buttons -->
      {#if canRun && (session.status === 'COMPLETED' || session.status === 'CANCELLED')}
        <div class="mb-4 flex items-center gap-2">
          <button
            onclick={() => { showArchiveConfirm = true; }}
            class="btn btn-sm bg-warning-muted text-warning hover:bg-warning/20"
          >
            <Archive size={14} />
            Archive Session
          </button>
        </div>
      {/if}

      {#if canRun && session.status === 'ARCHIVED'}
        <div class="mb-4 flex items-center gap-2">
          <button
            onclick={() => { showDeleteConfirm = true; }}
            class="btn btn-sm btn-danger"
          >
            <Trash2 size={14} />
            Delete Session
          </button>
        </div>
      {/if}

      <!-- Run History -->
      {#if (session.runs || []).length > 0}
        <div>
          <h2 class="text-sm font-semibold text-text-primary mb-3">
            Run History ({(session.runs || []).length})
          </h2>
          <div class="space-y-2">
            {#each (session.runs || []) as run (run.id)}
              <a
                href="/manufacturing/session/{session.id}/run/{run.id}"
                class="card card-sm block transition-colors hover:bg-surface-2/50"
              >
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-3">
                    <span class="text-xs font-medium text-text-primary">
                      {run.panelIdentifier || run.name || run.id.slice(0, 8)}
                    </span>
                    <span class="text-2xs text-text-tertiary">
                      {run.passedCount}/{run.targetCount} passed
                    </span>
                  </div>
                  <div class="flex items-center gap-2">
                    {#if run.durationMs}
                      <span class="text-2xs tabular-nums text-text-tertiary">
                        {Math.round(run.durationMs / 1000)}s
                      </span>
                    {/if}
                    <StatusBadge status={run.status} />
                  </div>
                </div>
              </a>
            {/each}
          </div>
        </div>
      {:else if session.status === 'ACTIVE'}
        <EmptyState message="Scan a panel QR code to begin manufacturing." />
      {:else}
        <EmptyState message="No runs were recorded during this session." />
      {/if}
    {/if}
  {/if}
</div>

<!-- Scan Panel Modal -->
<ScanPanelModal
  open={scanModalOpen}
  {sessionId}
  {panelRows}
  {panelCols}
  {hasStandaloneSlot}
  runType={scanRunType}
  onClose={() => { scanModalOpen = false; }}
  onStarted={handleRunStarted}
/>

<!-- End session confirmation -->
<Modal open={showEndConfirm} title="End Manufacturing Session?" onclose={() => { showEndConfirm = false; }} size="sm">
  <p class="text-sm text-text-secondary">
    This will finalize the session. No more panels can be run after ending.
  </p>
  {#snippet footer()}
    <button
      onclick={() => { showEndConfirm = false; }}
      class="btn btn-sm btn-ghost"
    >
      Cancel
    </button>
    <button
      onclick={() => { showEndConfirm = false; handleEndSession(); }}
      class="btn btn-sm btn-danger"
    >
      End Session
    </button>
  {/snippet}
</Modal>

<!-- Archive confirmation modal -->
<Modal open={showArchiveConfirm} title="Archive Session?" onclose={() => { showArchiveConfirm = false; }} size="sm">
  <p class="text-sm text-text-secondary">
    Archiving hides this session from default views. You can still find it using the Archived status filter.
  </p>
  {#snippet footer()}
    <button
      onclick={() => { showArchiveConfirm = false; }}
      disabled={archiving}
      class="btn btn-sm btn-ghost"
    >
      Cancel
    </button>
    <button
      onclick={handleArchive}
      disabled={archiving}
      class="btn btn-sm bg-warning-muted text-warning hover:bg-warning/20"
    >
      {archiving ? 'Archiving...' : 'Archive Session'}
    </button>
  {/snippet}
</Modal>

<!-- Delete confirmation dialog (type-to-confirm) -->
<ConfirmDeleteDialog
  open={showDeleteConfirm}
  resourceType="session"
  resourceName={session?.id || ''}
  loading={deleting}
  onConfirm={handleDelete}
  onCancel={() => { showDeleteConfirm = false; }}
/>
