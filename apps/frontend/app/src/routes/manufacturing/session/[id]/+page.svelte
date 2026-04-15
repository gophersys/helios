<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { ArrowLeft, Search, Loader2, ServerCrash, RefreshCw } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import { ErrorAlert, EmptyState, LoadingState, Modal, ConfirmDeleteDialog, StatusBadge } from '$lib/components/ui';
  import SessionHeader from '$lib/components/manufacturing/session-header.svelte';
  import PanelGridView from '$lib/components/manufacturing/panel-grid-view.svelte';
  import ScanPanelModal from '$lib/components/manufacturing/scan-panel-modal.svelte';
  import SlotNavigator from '$lib/components/execution/slot-navigator.svelte';
  import SlotExecutionView from '$lib/components/execution/slot-execution-view.svelte';
  import { SlotContext } from '$lib/components/execution/slot-context.svelte';
  import {
    subscribeManufacturingRun,
    subscribeRunWithLogs,
    getRunSocket,
    disconnectRunSocket,
  } from '$lib/services/websocket';
  import { formatTimeAgo, formatDuration } from '$lib/utils/formatting';
  import { reportValidationError } from '$lib/stores/error-reporter.svelte';
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

  // ── Run history filter ─────────────────────────────────────
  let runStatusFilter = $state('all');
  let runSearch = $state('');

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
  // Fixture slot info from session snapshot (MTIB node names for the scan modal)
  const fixtureSlots = $derived.by(() => {
    const snapshot = (session?.config as Record<string, any>)?.fixtureSnapshot;
    if (!snapshot?.slots) return [];
    return (snapshot.slots as any[]).map((s: any) => ({
      slotIndex: s.slotIndex as number,
      nodeName: s.nodeName as string | undefined,
      nodeHostname: s.nodeHostname as string | undefined,
      label: s.label as string | undefined,
    }));
  });

  // ── Session-level computed values ──────────────────────────
  const allRuns = $derived(session?.runs || []);

  // A run that's either executing or waiting to execute
  const activeRun = $derived(
    allRuns.find((r: TestRun) => r.status === 'ACTIVE' || r.status === 'PENDING')
  );

  // Only truly executing (blocks end session)
  const runningRun = $derived(
    allRuns.find((r: TestRun) => r.status === 'ACTIVE')
  );

  const latestRun = $derived(
    allRuns.length > 0 ? allRuns[allRuns.length - 1] : undefined
  );

  // Runner deployment state — gates scanning until runner is connected
  const runnerStatus = $derived(session?.runnerStatus || null);
  const isDeploying = $derived(
    session?.status === 'ACTIVE' && (
      !runnerStatus || runnerStatus === 'DEPLOYING' || runnerStatus === 'CHECKING_MTIBS'
    )
  );
  const runnerFailed = $derived(
    session?.status === 'ACTIVE' && runnerStatus === 'ERROR'
  );
  const runnerReady = $derived(
    runnerStatus === 'READY' || runnerStatus === 'RUNNING'
  );
  let deployTimedOut = $state(false);
  const checkingMtibs = $derived(runnerStatus === 'CHECKING_MTIBS');
  const deployingRunner = $derived(runnerStatus === 'DEPLOYING');
  const mtibsDone = $derived(deployingRunner || !runnerStatus);

  // Deployment polling + timeout
  let deployPollTimer: ReturnType<typeof setInterval> | null = null;
  let deployTimeoutTimer: ReturnType<typeof setTimeout> | null = null;
  let deployElapsed = $state(0);
  let deployElapsedTimer: ReturnType<typeof setInterval> | null = null;

  const DEPLOY_TIMEOUT_S = 120;
  const DEPLOY_POLL_S = 5;

  function startDeploymentWatcher() {
    stopDeploymentWatcher();
    deployElapsed = 0;
    deployTimedOut = false;

    // Tick elapsed counter every second
    deployElapsedTimer = setInterval(() => { deployElapsed++; }, 1000);

    // Poll session every 5s to catch status changes WebSocket might miss
    deployPollTimer = setInterval(async () => {
      if (!isDeploying) { stopDeploymentWatcher(); return; }
      await fetchSession();
    }, DEPLOY_POLL_S * 1000);

    // Timeout after 120s
    deployTimeoutTimer = setTimeout(() => {
      if (isDeploying) {
        deployTimedOut = true;
        stopDeploymentWatcher();
        reportValidationError({
          message: `Manufacturing runner deployment timed out after ${DEPLOY_TIMEOUT_S}s`,
          details: `Session ${sessionId} — runner did not send READY heartbeat within the timeout window`,
          entityType: 'ManufacturingSession',
          entityId: sessionId,
        });
      }
    }, DEPLOY_TIMEOUT_S * 1000);
  }

  function stopDeploymentWatcher() {
    if (deployPollTimer) { clearInterval(deployPollTimer); deployPollTimer = null; }
    if (deployTimeoutTimer) { clearTimeout(deployTimeoutTimer); deployTimeoutTimer = null; }
    if (deployElapsedTimer) { clearInterval(deployElapsedTimer); deployElapsedTimer = null; }
  }

  // Start/stop watcher based on deployment state
  $effect(() => {
    if (isDeploying && !deployPollTimer) {
      startDeploymentWatcher();
    } else if (!isDeploying && deployPollTimer) {
      stopDeploymentWatcher();
    }
  });

  // Report runner failure to error reporter
  $effect(() => {
    if (runnerFailed) {
      reportValidationError({
        message: 'Manufacturing runner deployment failed',
        details: `Session ${sessionId} — runner status is ERROR. Container may have crashed.`,
        entityType: 'ManufacturingSession',
        entityId: sessionId,
      });
    }
  });

  // Filtered run history
  const filteredRuns = $derived.by(() => {
    let runs = [...allRuns];
    if (runStatusFilter !== 'all') {
      runs = runs.filter(r => r.status === runStatusFilter);
    }
    if (runSearch.trim()) {
      const q = runSearch.trim().toLowerCase();
      runs = runs.filter(r =>
        (r.panelIdentifier || '').toLowerCase().includes(q) ||
        (r.name || '').toLowerCase().includes(q) ||
        r.id.toLowerCase().includes(q)
      );
    }
    // Latest first
    runs.sort((a, b) => new Date(b.createdAt || 0).getTime() - new Date(a.createdAt || 0).getTime());
    return runs;
  });

  const runStatusOptions = $derived.by(() => {
    const statuses = new Set(allRuns.map(r => r.status));
    return ['all', ...Array.from(statuses)];
  });

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
    const newRun = allRuns.find(
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

  // ── Panel/standalone click handlers ────────────────────────

  function handleSlotClick(slotIndex: number) {
    // If there's an active or latest run with this target, navigate to run detail
    const run = activeRun || latestRun;
    if (!run) return;
    const target = (run.targets || []).find((t: RunTarget) => t.slotIndex === slotIndex);
    if (target) {
      goto(`/manufacturing/session/${sessionId}/run/${run.id}`);
    }
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

  async function retryDeployment() {
    error = null;
    try {
      await api.post(`/v2/manufacturing/sessions/${sessionId}/redeploy-runner`);
      await fetchSession();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to redeploy runner';
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
    stopDeploymentWatcher();
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
      <!-- Session info card -->
      <SessionHeader
        {session}
        canManage={canRun}
        activeRunExists={!!runningRun}
        onEndSession={() => { showEndConfirm = true; }}
        onArchive={() => { showArchiveConfirm = true; }}
        onDelete={() => { showDeleteConfirm = true; }}
      />

      {#if session.status === 'ARCHIVED'}
        <div class="mb-4 rounded-lg border border-warning/30 bg-warning-muted px-4 py-3 text-sm text-warning">
          This session is archived.
        </div>
      {/if}

      <!-- ── Runner deployment gate (ACTIVE sessions only) ── -->
      {#if isDeploying && !deployTimedOut}
        <div class="card card-lg mb-6">
          <div class="flex flex-col items-center justify-center py-8 text-center">
            <Loader2 size={28} class="text-accent animate-spin mb-4" />
            <h3 class="text-sm font-semibold text-text-primary mb-1">
              {checkingMtibs ? 'Verifying Hardware' : 'Deploying Test Runner'}
            </h3>
            <p class="text-sm text-text-secondary max-w-md mb-4">
              {checkingMtibs
                ? 'Checking that all MTIB servers on the fixture nodes are healthy and reachable.'
                : 'Starting the runner container, downloading the test package, and connecting to hardware.'}
            </p>

            <!-- Progress steps driven by actual status -->
            <div class="w-full max-w-xs space-y-2 text-left mb-4">
              <div class="flex items-center gap-2 text-xs">
                <span class="inline-block h-1.5 w-1.5 rounded-full {mtibsDone ? 'bg-success' : 'bg-text-tertiary animate-pulse'}"></span>
                <span class="{checkingMtibs || mtibsDone ? 'text-text-primary' : 'text-text-tertiary'}">Verifying MTIB health</span>
              </div>
              <div class="flex items-center gap-2 text-xs">
                <span class="inline-block h-1.5 w-1.5 rounded-full {!deployingRunner && !checkingMtibs && deployElapsed > 5 ? 'bg-text-tertiary animate-pulse' : deployingRunner ? 'bg-text-tertiary animate-pulse' : mtibsDone ? 'bg-success' : 'bg-surface-3'}"></span>
                <span class="{mtibsDone ? 'text-text-primary' : 'text-text-tertiary'}">Deploying test runner</span>
              </div>
              <div class="flex items-center gap-2 text-xs">
                <span class="inline-block h-1.5 w-1.5 rounded-full {!runnerStatus && deployElapsed > 10 ? 'bg-text-tertiary animate-pulse' : 'bg-surface-3'}"></span>
                <span class="{!runnerStatus && deployElapsed > 10 ? 'text-text-primary' : 'text-text-tertiary'}">Connecting to hardware + WebSocket</span>
              </div>
            </div>

            <div class="text-2xs text-text-tertiary tabular-nums">
              {deployElapsed}s elapsed {#if deployElapsed > 30}&middot; this is taking longer than usual{/if}
            </div>
          </div>
        </div>
      {:else if runnerFailed || deployTimedOut}
        <div class="card card-lg mb-6">
          <div class="flex flex-col items-center justify-center py-8 text-center">
            <ServerCrash size={28} class="text-error mb-4" />
            <h3 class="text-sm font-semibold text-text-primary mb-1">
              {deployTimedOut ? 'Runner Deployment Timed Out' : 'Runner Deployment Failed'}
            </h3>
            <p class="text-sm text-text-secondary max-w-md mb-4">
              {#if deployTimedOut}
                The runner did not report ready within {DEPLOY_TIMEOUT_S}s. The container may still be starting, or it crashed during boot.
              {:else}
                The test runner container failed to start. Check that Docker is available, the test package exists, and the container image is built.
              {/if}
            </p>
            <div class="flex items-center gap-2">
              <button onclick={retryDeployment} class="btn btn-sm btn-primary">
                <RefreshCw size={14} />
                Retry Deployment
              </button>
              <button onclick={() => { showEndConfirm = true; }} class="btn btn-sm btn-ghost">
                End Session
              </button>
            </div>
          </div>
        </div>
      {:else}
        <!-- Panel widget + run history (runner ready or session not active) -->
        <PanelGridView
          {panelRows}
          {panelCols}
          {hasStandaloneSlot}
          targets={activeRun?.targets ?? latestRun?.targets ?? []}
          scannable={canRun && session.status === 'ACTIVE' && runnerReady && !runningRun}
          onScanPanel={() => openScanModal('panel')}
          onScanStandalone={() => openScanModal('standalone')}
          onSlotClick={handleSlotClick}
        />
      {/if}

      <!-- Run History (always visible) -->
      <div class="mt-6">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-sm font-semibold text-text-primary">
            Run History
          </h2>
          <span class="text-2xs text-text-tertiary">{filteredRuns.length} run{filteredRuns.length !== 1 ? 's' : ''}</span>
        </div>

        {#if allRuns.length > 0}
          <!-- Filter bar -->
          <div class="flex items-center gap-2 mb-3">
            <span class="text-xs text-text-secondary">Status:</span>
            <select bind:value={runStatusFilter} class="input input-sm w-auto">
              {#each runStatusOptions as opt}
                <option value={opt}>{opt === 'all' ? 'All' : opt}</option>
              {/each}
            </select>
            <div class="relative flex-1 max-w-xs">
              <Search size={14} class="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary" />
              <input
                type="text"
                bind:value={runSearch}
                placeholder="Search runs..."
                class="input input-sm pl-9"
              />
            </div>
          </div>

          <!-- Run list table -->
          {#if filteredRuns.length === 0}
            <EmptyState message="No runs match your filters." />
          {:else}
            <div class="overflow-hidden rounded-lg border border-border">
              <table class="w-full">
                <thead>
                  <tr class="border-b border-border bg-surface-2">
                    <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Panel</th>
                    <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Slot Results</th>
                    <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Duration</th>
                    <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">When</th>
                    <th class="px-4 py-2.5 text-right text-2xs font-medium uppercase tracking-wider text-text-tertiary">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {#each filteredRuns as run (run.id)}
                    <tr
                      class="border-b border-border-subtle last:border-0 hover:bg-surface-2 transition-colors cursor-pointer"
                      onclick={() => goto(`/manufacturing/session/${sessionId}/run/${run.id}`)}
                    >
                      <td class="px-4 py-3">
                        <span class="text-sm font-medium text-text-primary">
                          {run.panelIdentifier || run.name || run.id.slice(0, 8)}
                        </span>
                      </td>
                      <td class="px-4 py-3">
                        <div class="flex items-center gap-1.5 flex-wrap">
                          {#if run.targets?.length}
                            {#each [...(run.targets as RunTarget[])].sort((a, b) => a.slotIndex - b.slotIndex) as target (target.id)}
                              <span
                                class="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-2xs font-mono font-medium
                                  {target.status === 'PASSED' ? 'bg-success-muted text-success' :
                                   target.status === 'FAILED' || target.status === 'ERROR' ? 'bg-error-muted text-error' :
                                   target.status === 'RUNNING' ? 'bg-accent-muted text-accent' :
                                   'bg-surface-2 text-text-tertiary'}"
                                title="Slot {target.slotIndex + 1}: {target.status}"
                              >
                                {target.serialNumber || `S${target.slotIndex + 1}`}
                              </span>
                            {/each}
                          {:else}
                            <span class="text-text-tertiary text-sm">—</span>
                          {/if}
                        </div>
                      </td>
                      <td class="px-4 py-3">
                        <span class="text-sm tabular-nums text-text-secondary">
                          {run.durationMs ? formatDuration(run.durationMs) : '—'}
                        </span>
                      </td>
                      <td class="px-4 py-3">
                        <span class="text-sm text-text-tertiary">
                          {run.createdAt ? formatTimeAgo(run.createdAt) : '—'}
                        </span>
                      </td>
                      <td class="px-4 py-3 text-right">
                        {#if run.status === 'COMPLETED' && !run.failedCount}
                          <span class="badge badge-success">PASSED</span>
                        {:else}
                          <StatusBadge status={run.status} />
                        {/if}
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        {:else if session.status === 'ACTIVE'}
          <EmptyState message="Click the panel above to scan and begin manufacturing." />
        {:else}
          <EmptyState message="No runs were recorded during this session." />
        {/if}
      </div>
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
  {fixtureSlots}
  runType={scanRunType}
  onClose={() => { scanModalOpen = false; }}
  onStarted={handleRunStarted}
/>

<!-- End session confirmation -->
<Modal open={showEndConfirm} title="End Manufacturing Session?" onclose={() => { showEndConfirm = false; }} size="sm">
  <div class="space-y-3">
    <p class="text-sm text-text-secondary">
      This will finalize the session. No more panels can be scanned after ending.
    </p>
    {#if allRuns.some(r => r.status === 'PENDING')}
      <p class="text-sm text-warning">
        {allRuns.filter(r => r.status === 'PENDING').length} pending run(s) will be cancelled.
      </p>
    {/if}
    <p class="text-sm text-text-secondary">
      The fixture will be unlocked and the test runner will be stopped.
    </p>
  </div>
  {#snippet footer()}
    <button onclick={() => { showEndConfirm = false; }} class="btn btn-sm btn-ghost">Cancel</button>
    <button onclick={() => { showEndConfirm = false; handleEndSession(); }} class="btn btn-sm btn-danger">End Session</button>
  {/snippet}
</Modal>

<!-- Archive confirmation modal -->
<Modal open={showArchiveConfirm} title="Archive Session?" onclose={() => { showArchiveConfirm = false; }} size="sm">
  <p class="text-sm text-text-secondary">
    Archiving hides this session from default views. You can still find it using the Archived status filter.
  </p>
  {#snippet footer()}
    <button onclick={() => { showArchiveConfirm = false; }} disabled={archiving} class="btn btn-sm btn-ghost">Cancel</button>
    <button onclick={handleArchive} disabled={archiving} class="btn btn-sm bg-warning-muted text-warning hover:bg-warning/20">
      {archiving ? 'Archiving...' : 'Archive Session'}
    </button>
  {/snippet}
</Modal>

<!-- Delete confirmation dialog -->
<ConfirmDeleteDialog
  open={showDeleteConfirm}
  resourceType="session"
  resourceName={session?.id || ''}
  loading={deleting}
  onConfirm={handleDelete}
  onCancel={() => { showDeleteConfirm = false; }}
/>
