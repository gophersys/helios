<script lang="ts">
  import { QrCode, LayoutGrid, Loader2, Check, AlertTriangle, Fingerprint } from 'lucide-svelte';
  import Modal from '$lib/components/ui/modal.svelte';
  import { api } from '$lib/api';
  import type { ApiResponse } from '$lib/types';

  interface ResolvedSlot {
    slotIndex: number;
    snr: string | null;
    deviceId: string | null;
    label: string;
    coreopsError: string | null;
  }

  interface FixtureSlotInfo {
    slotIndex: number;
    nodeName?: string;
    nodeHostname?: string;
    label?: string;
  }

  let {
    open = false,
    sessionId,
    panelRows = 1,
    panelCols = 1,
    hasStandaloneSlot = false,
    runType = 'panel',
    fixtureSlots = [],
    onClose,
    onStarted,
  }: {
    open?: boolean;
    sessionId: string;
    panelRows?: number;
    panelCols?: number;
    hasStandaloneSlot?: boolean;
    runType?: 'panel' | 'standalone';
    fixtureSlots?: FixtureSlotInfo[];
    onClose?: () => void;
    onStarted?: (runId: string) => void;
  } = $props();

  // Build a lookup: slotIndex → fixture slot info (MTIB node name)
  const fixtureSlotMap = $derived(
    new Map(fixtureSlots.map(s => [s.slotIndex, s]))
  );

  let snrInput = $state('');
  let resolving = $state(false);
  let starting = $state(false);
  let error = $state<string | null>(null);
  let resolvedSlots = $state<ResolvedSlot[]>([]);
  let resolved = $state(false);
  let coreopsAvailable = $state(false);

  const isStandalone = $derived(runType === 'standalone');
  const canResolve = $derived(!resolving && snrInput.trim().length > 0 && !resolved);
  const canStart = $derived(!starting && resolved);
  const hasCoreopsErrors = $derived(resolvedSlots.some(s => s.coreopsError));

  const title = $derived(isStandalone ? 'Scan Standalone' : 'Scan Panel');

  async function handleResolve() {
    if (!canResolve) return;
    resolving = true;
    error = null;
    try {
      const res = await api.post<ApiResponse<{ primarySnr: string; coreopsAvailable: boolean; slots: ResolvedSlot[] }>>(
        `/v2/manufacturing/sessions/${sessionId}/resolve-panel`,
        { snr: snrInput.trim(), runType }
      );
      const data = (res as any).data;
      const allSlots: ResolvedSlot[] = data?.slots || [];

      if (isStandalone) {
        // Standalone: show only the standalone slot
        const panelSlotCount = panelRows * panelCols;
        const standaloneOnly = allSlots.filter(s => s.slotIndex >= panelSlotCount);
        if (standaloneOnly.length === 0) {
          // If no standalone slot returned, create one from the input SNR
          resolvedSlots = [{
            slotIndex: panelSlotCount,
            snr: snrInput.trim(),
            deviceId: data?.slots?.[0]?.deviceId || null,
            label: 'Standalone',
            coreopsError: data?.slots?.[0]?.coreopsError || null,
          }];
        } else {
          resolvedSlots = standaloneOnly;
        }
      } else {
        // Panel: only show grid slots (first rows*cols), not standalone
        const panelSlotCount = panelRows * panelCols;
        const panelOnly = allSlots.filter(s => s.slotIndex < panelSlotCount);

        // If most slots have no SNR, the input was bad
        const slotsWithSnr = panelOnly.filter(s => s.snr);
        if (slotsWithSnr.length === 0) {
          error = 'Could not derive serial numbers from this input. Check the SNR and try again.';
          return;
        }
        if (slotsWithSnr.length < panelOnly.length / 2) {
          error = `Only ${slotsWithSnr.length} of ${panelOnly.length} slots resolved. The SNR may be invalid.`;
          return;
        }

        resolvedSlots = panelOnly;
      }
      coreopsAvailable = data?.coreopsAvailable ?? false;
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
        body.slotSnrs = resolvedSlots.map(s => ({
          slotIndex: s.slotIndex,
          snr: s.snr,
        }));
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
      if (!resolved) {
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
    coreopsAvailable = false;
    error = null;
    resolving = false;
    starting = false;
  }

  function handleClose() {
    resetState();
    onClose?.();
  }

  function handleRescan() {
    snrInput = '';
    resolvedSlots = [];
    resolved = false;
    coreopsAvailable = false;
    error = null;
    focusInput();
  }

  let inputEl: HTMLInputElement;

  function focusInput() {
    requestAnimationFrame(() => {
      inputEl?.focus();
    });
  }

  $effect(() => {
    if (open) focusInput();
  });
</script>

<svelte:window onkeydown={(e) => {
  if (!open || e.key !== 'Enter') return;
  e.preventDefault();
  if (!resolved && canResolve) {
    handleResolve();
  } else if (resolved && canStart) {
    handleStart();
  }
}} />

<Modal {open} {title} onclose={handleClose} size={resolved ? 'lg' : 'md'}>
  <div class="space-y-4">
    <!-- SNR input -->
    <div class="space-y-1.5">
      <label class="form-label">Serial Number</label>
      <div class="relative">
        <QrCode size={14} class="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary" />
        <!-- svelte-ignore a11y_autofocus -->
        <input
          type="text"
          bind:this={inputEl}
          bind:value={snrInput}
          oninput={() => { snrInput = snrInput.toUpperCase(); }}
          onkeydown={handleKeydown}
          placeholder="Scan or type SNR..."
          disabled={resolved}
          autofocus
          class="input input-md pl-9 w-full"
        />
      </div>
      {#if resolved}
        <button onclick={handleRescan} class="btn btn-sm btn-ghost text-accent">
          Scan different panel
        </button>
      {/if}
    </div>

    <!-- Error -->
    {#if error}
      <p class="text-sm text-error bg-error-muted rounded-lg px-3 py-2">{error}</p>
    {/if}

    <!-- Resolved panel grid (panel mode only) -->
    {#if !isStandalone && resolved && resolvedSlots.length > 0}
      <div class="rounded-lg border border-border bg-surface-0 p-4">
        <!-- Header -->
        <div class="flex items-center gap-2 mb-3">
          <LayoutGrid size={14} class="text-accent" />
          <span class="text-2xs font-semibold text-text-primary uppercase tracking-wider">
            Panel Layout
          </span>
          <span class="text-2xs text-text-tertiary ml-auto">
            {resolvedSlots.length} slots &middot; {panelRows}x{panelCols}
          </span>
        </div>

        <!-- Grid matches fixture physical layout -->
        <div
          class="grid gap-2"
          style="grid-template-columns: repeat({panelCols}, minmax(0, 1fr));"
        >
          {#each resolvedSlots as slot (slot.slotIndex)}
            <div
              class="flex flex-col items-center gap-1 rounded-lg border-2 p-3 text-center transition-colors
                {slot.coreopsError
                  ? 'border-warning/50 bg-warning-muted/30'
                  : slot.deviceId
                    ? 'border-success/40 bg-success-muted/30'
                    : 'border-border bg-surface-2'
                }"
            >
              <!-- Slot number -->
              <span class="text-2xs font-semibold text-text-tertiary uppercase tracking-wider">
                {slot.label}
              </span>

              <!-- MTIB node (from fixture snapshot) -->
              {#if fixtureSlotMap.get(slot.slotIndex)?.nodeName}
                <span class="text-2xs text-text-tertiary font-mono">
                  {fixtureSlotMap.get(slot.slotIndex)?.nodeName}
                </span>
              {/if}

              <!-- SNR -->
              <span class="text-sm font-mono font-semibold text-text-primary">
                {slot.snr || '—'}
              </span>

              <!-- Device ID or CoreOps status -->
              {#if slot.deviceId}
                <div class="flex items-center gap-1">
                  <Fingerprint size={10} class="text-success shrink-0" />
                  <span class="text-2xs font-mono text-success break-all">{slot.deviceId}</span>
                </div>
              {:else if slot.coreopsError}
                <div class="flex items-center gap-1">
                  <AlertTriangle size={10} class="text-warning" />
                  <span class="text-2xs text-warning">ID failed</span>
                </div>
              {:else if !coreopsAvailable}
                <span class="text-2xs text-text-tertiary">No CoreOps</span>
              {:else}
                <span class="text-2xs text-text-tertiary">Pending</span>
              {/if}
            </div>
          {/each}
        </div>

        <!-- CoreOps warning -->
        {#if hasCoreopsErrors}
          <p class="mt-3 text-2xs text-warning flex items-center gap-1">
            <AlertTriangle size={12} />
            Some device IDs could not be resolved. Run will continue without them.
          </p>
        {:else if coreopsAvailable && resolvedSlots.every(s => s.deviceId)}
          <p class="mt-3 text-2xs text-success flex items-center gap-1">
            <Check size={12} />
            All device IDs resolved via CoreOps.
          </p>
        {/if}
      </div>
    {/if}

    <!-- Standalone resolved view -->
    {#if isStandalone && resolved && resolvedSlots.length > 0}
      <div class="rounded-lg border border-border bg-surface-0 p-4">
        <div class="flex items-center gap-2 mb-3">
          <LayoutGrid size={14} class="text-accent" />
          <span class="text-2xs font-semibold text-text-primary uppercase tracking-wider">Standalone</span>
        </div>
        <div class="flex justify-center">
          {#each resolvedSlots as slot (slot.slotIndex)}
            <div class="flex flex-col items-center gap-1 rounded-lg border-2 p-4 text-center w-48
              {slot.coreopsError
                ? 'border-warning/50 bg-warning-muted/30'
                : slot.deviceId
                  ? 'border-success/40 bg-success-muted/30'
                  : 'border-border bg-surface-2'
              }">
              <span class="text-2xs font-semibold text-text-tertiary uppercase tracking-wider">{slot.label}</span>
              {#if fixtureSlotMap.get(slot.slotIndex)?.nodeName}
                <span class="text-2xs text-text-tertiary font-mono">{fixtureSlotMap.get(slot.slotIndex)?.nodeName}</span>
              {/if}
              <span class="text-sm font-mono font-semibold text-text-primary">{slot.snr || '—'}</span>
              {#if slot.deviceId}
                <div class="flex items-center gap-1">
                  <Fingerprint size={10} class="text-success shrink-0" />
                  <span class="text-2xs font-mono text-success break-all">{slot.deviceId}</span>
                </div>
              {:else if slot.coreopsError}
                <div class="flex items-center gap-1">
                  <AlertTriangle size={10} class="text-warning" />
                  <span class="text-2xs text-warning">ID pending</span>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>

  {#snippet footer()}
    <button onclick={handleClose} class="btn btn-sm btn-ghost" disabled={resolving || starting}>
      Cancel
    </button>

    {#if !resolved}
      <button onclick={handleResolve} disabled={!canResolve} class="btn btn-sm btn-secondary">
        {#if resolving}
          <Loader2 size={14} class="animate-spin" />
          Verifying...
        {:else}
          Verify
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
