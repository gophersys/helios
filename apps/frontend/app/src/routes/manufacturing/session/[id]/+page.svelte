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
    subscribeManufacturingSession,
    disconnectManufacturingSocket,
  } from '$lib/services/websocket';
  import type { ManufacturingSessionDetail, ManufacturingPanel, ManufacturingUnit, ManufacturingStage } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  const auth = getAuth();
  const canRun = $derived(auth.hasPermission('manufacturing:run'));
  const sessionId = $derived($page.params.id);

  let session = $state<ManufacturingSessionDetail | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let unsubscribe: (() => void) | null = null;

  // Completed panels (not including active)
  const completedPanels = $derived(
    (session?.panels || []).filter((p) => p.status !== 'RUNNING')
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
        const resultsRes = await apiFetch<ApiResponse<{ panels: ManufacturingPanel[] }>>(
          `/v2/manufacturing/sessions/${sessionId}/results`
        );
        const panelsData = (resultsRes as any).data;
        if (panelsData?.panels) {
          session = { ...session!, panels: panelsData.panels };
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

  async function handleRunPanel(qrCode: string) {
    error = null;
    try {
      await api.post(`/v2/manufacturing/sessions/${sessionId}/panels`, { qrCode });
      await fetchSession();
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

  function setupWebSocket() {
    if (!sessionId) return;

    unsubscribe = subscribeManufacturingSession(
      sessionId,
      {
        onUnitStart(data) {
          if (!session?.activePanel) return;
          // Add or update unit in the active panel
          const panel = session.activePanel;
          const existingIdx = panel.units.findIndex((u) => u.slotIndex === data.slotIndex);
          const newUnit: ManufacturingUnit = {
            id: `temp-${data.slotIndex}`,
            panelId: data.panelId,
            slotIndex: data.slotIndex,
            slotLabel: data.slotLabel,
            serialNumber: data.serialNumber,
            status: 'RUNNING',
            stages: [],
            errorMessage: null,
            startedAt: new Date().toISOString(),
            finishedAt: null,
          };
          if (existingIdx >= 0) {
            panel.units[existingIdx] = newUnit;
          } else {
            panel.units = [...panel.units, newUnit];
          }
          session = { ...session! };
        },

        onStageResult(data) {
          if (!session?.activePanel) return;
          const panel = session.activePanel;
          const unit = panel.units.find((u) => u.slotIndex === data.slotIndex);
          if (unit) {
            const stageUpdate: ManufacturingStage = {
              type: data.stage as ManufacturingStage['type'],
              status: data.status as ManufacturingStage['status'],
              durationMs: data.durationMs,
              errorMessage: data.errorMessage,
            };
            const existingStageIdx = unit.stages.findIndex((s) => s.type === data.stage);
            if (existingStageIdx >= 0) {
              unit.stages[existingStageIdx] = stageUpdate;
            } else {
              unit.stages = [...unit.stages, stageUpdate];
            }
            session = { ...session! };
          }
        },

        onUnitResult(data) {
          if (!session?.activePanel) return;
          const panel = session.activePanel;
          const unit = panel.units.find((u) => u.slotIndex === data.slotIndex);
          if (unit) {
            unit.status = data.status as ManufacturingUnit['status'];
            unit.serialNumber = data.serialNumber || unit.serialNumber;
            unit.errorMessage = data.errorMessage;
            unit.finishedAt = new Date().toISOString();
            session = { ...session! };
          }
        },

        onPanelComplete(data) {
          if (!session) return;
          // Update session counts
          session = {
            ...session,
            passCount: session.passCount + data.passCount,
            failCount: session.failCount + data.failCount,
            panelCount: session.panelCount + 1,
          };
          // Refresh full data from the server
          fetchSession();
        },
      },
      (errMsg) => {
        console.error('Manufacturing WebSocket error:', errMsg);
      }
    );
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
    if (unsubscribe) unsubscribe();
    disconnectManufacturingSocket();
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

    <!-- Active Panel -->
    {#if session.activePanel}
      <div class="mb-6">
        <h2 class="text-sm font-semibold text-text-primary mb-3">Active Panel</h2>
        <PanelResultsGrid panel={session.activePanel} />
      </div>
    {/if}

    <!-- Panel History -->
    {#if completedPanels.length > 0}
      <div>
        <h2 class="text-sm font-semibold text-text-primary mb-3">
          Panel History ({completedPanels.length})
        </h2>
        <PanelHistory panels={completedPanels} />
      </div>
    {/if}

    <!-- Empty state when no panels at all -->
    {#if !session.activePanel && completedPanels.length === 0}
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
