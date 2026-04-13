<script lang="ts">
  import { QrCode, LayoutGrid, Loader2 } from 'lucide-svelte';
  import Modal from '$lib/components/ui/modal.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import { api } from '$lib/api';
  import type { ApiResponse } from '$lib/types';

  let {
    open = false,
    sessionId,
    panelRows = 1,
    panelCols = 1,
    hasStandaloneSlot = false,
    runType = 'panel',
    onClose,
    onStarted,
  }: {
    open?: boolean;
    sessionId: string;
    panelRows?: number;
    panelCols?: number;
    hasStandaloneSlot?: boolean;
    runType?: 'panel' | 'standalone';
    onClose?: () => void;
    onStarted?: (runId: string) => void;
  } = $props();

  let snrInput = $state('');
  let resolving = $state(false);
  let starting = $state(false);
  let error = $state<string | null>(null);
  let resolvedSlots = $state<{ slotIndex: number; serialNumber: string }[]>([]);
  let resolved = $state(false);

  const panelSlotCount = $derived(panelRows * panelCols);
  const isStandalone = $derived(runType === 'standalone');
  const canResolve = $derived(!resolving && snrInput.trim().length > 0 && !resolved);
  const canStart = $derived(!starting && (isStandalone ? snrInput.trim().length > 0 : resolved && resolvedSlots.length > 0));

  const title = $derived(isStandalone ? 'Scan Standalone' : 'Scan Panel');

  async function handleResolve() {
    if (!canResolve) return;
    resolving = true;
    error = null;
    try {
      const res = await api.post<ApiResponse<{ slots: { slotIndex: number; serialNumber: string }[] }>>(
        `/v2/manufacturing/sessions/${sessionId}/resolve-panel`,
        { snr: snrInput.trim() }
      );
      resolvedSlots = (res as any).data?.slots || [];
      resolved = true;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to resolve panel SNRs';
    } finally {
      resolving = false;
    }
  }

  async function handleStart() {
    if (!canStart) return;
    starting = true;
    error = null;
    try {
      const body: Record<string, unknown> = {
        qrCode: snrInput.trim(),
        runType,
      };
      if (!isStandalone && resolvedSlots.length > 0) {
        body.slotSnrs = resolvedSlots;
      }
      const res = await api.post<ApiResponse<{ id: string }>>(
        `/v2/manufacturing/sessions/${sessionId}/runs`,
        body,
      );
      const runId = (res as any).data?.id;
      resetState();
      onStarted?.(runId);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to start run';
    } finally {
      starting = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      if (!resolved && !isStandalone) {
        handleResolve();
      } else {
        handleStart();
      }
    }
  }

  function resetState() {
    snrInput = '';
    resolvedSlots = [];
    resolved = false;
    error = null;
    resolving = false;
    starting = false;
  }

  function handleClose() {
    resetState();
    onClose?.();
  }
</script>

<Modal {open} {title} onclose={handleClose} size="md">
  <div class="space-y-4">
    <!-- SNR input -->
    <div class="space-y-1.5">
      <label class="form-label">Serial Number</label>
      <div class="relative">
        <QrCode size={14} class="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary" />
        <!-- svelte-ignore a11y_autofocus -->
        <input
          type="text"
          bind:value={snrInput}
          onkeydown={handleKeydown}
          placeholder="Scan or type SNR..."
          disabled={resolved}
          autofocus
          class="input input-md pl-9 w-full"
        />
      </div>
    </div>

    <!-- Error -->
    {#if error}
      <p class="text-sm text-error bg-error-muted rounded-lg px-3 py-2">{error}</p>
    {/if}

    <!-- Resolved panel grid (panel mode only) -->
    {#if !isStandalone && resolved && resolvedSlots.length > 0}
      <div class="rounded-lg border border-border bg-surface-0 p-3">
        <div class="flex items-center gap-2 mb-2">
          <LayoutGrid size={14} class="text-text-tertiary" />
          <span class="text-2xs font-semibold text-text-tertiary uppercase tracking-wider">
            Resolved — {resolvedSlots.length} SNRs
          </span>
        </div>
        <div
          class="grid gap-1.5 mx-auto"
          style="grid-template-columns: repeat({panelCols}, minmax(0, 1fr)); max-width: {Math.min(panelCols * 100, 400)}px;"
        >
          {#each resolvedSlots as slot (slot.slotIndex)}
            <div class="flex flex-col items-center justify-center rounded-lg border border-border bg-surface-2 p-2 text-center min-h-12">
              <span class="text-2xs font-semibold text-text-primary">{slot.slotIndex + 1}</span>
              <span class="text-2xs font-mono text-text-secondary truncate max-w-full">{slot.serialNumber}</span>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Standalone confirmation -->
    {#if isStandalone && snrInput.trim()}
      <div class="rounded-lg border border-warning/30 bg-warning-muted/30 p-3">
        <p class="text-sm text-text-primary">
          Standalone run for SNR: <span class="font-mono font-medium">{snrInput.trim()}</span>
        </p>
      </div>
    {/if}
  </div>

  {#snippet footer()}
    <button onclick={handleClose} class="btn btn-sm btn-ghost" disabled={resolving || starting}>
      Cancel
    </button>

    {#if !isStandalone && !resolved}
      <button onclick={handleResolve} disabled={!canResolve} class="btn btn-sm btn-secondary">
        {#if resolving}
          <Loader2 size={14} class="animate-spin" />
          Resolving...
        {:else}
          Resolve
        {/if}
      </button>
    {:else}
      <button onclick={handleStart} disabled={!canStart} class="btn btn-sm btn-primary">
        {#if starting}
          <Loader2 size={14} class="animate-spin" />
          Starting...
        {:else}
          Start Run
        {/if}
      </button>
    {/if}
  {/snippet}
</Modal>
