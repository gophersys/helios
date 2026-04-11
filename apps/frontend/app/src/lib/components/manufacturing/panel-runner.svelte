<script lang="ts">
  import { QrCode, Play, Square } from 'lucide-svelte';
  import type { ManufacturingSession } from '$lib/types/models';

  let {
    session,
    canRun = false,
    onRunPanel,
    onEndSession,
  }: {
    session: ManufacturingSession;
    canRun?: boolean;
    onRunPanel?: (qrCode: string) => void;
    onEndSession?: () => void;
  } = $props();

  let qrInput = $state('');
  let submitting = $state(false);
  let showEndConfirm = $state(false);

  const panelRunning = $derived(
    (session.runs || []).some((r) => r.status === 'ACTIVE')
  );
  const sessionActive = $derived(session.status === 'ACTIVE');
  const canSubmit = $derived(
    canRun && sessionActive && !panelRunning && !submitting && qrInput.trim().length > 0
  );

  async function handleRunPanel() {
    if (!canSubmit) return;
    submitting = true;
    try {
      onRunPanel?.(qrInput.trim());
      qrInput = '';
    } finally {
      submitting = false;
    }
  }

  function handleEndSession() {
    showEndConfirm = false;
    onEndSession?.();
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && canSubmit) {
      handleRunPanel();
    }
  }
</script>

{#if canRun && sessionActive}
  <div class="rounded-lg border border-border bg-surface-1 p-4 mb-4">
    <div class="flex items-center gap-3">
      <div class="relative flex-1">
        <QrCode size={14} class="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary" />
        <input
          type="text"
          bind:value={qrInput}
          onkeydown={handleKeydown}
          placeholder="Scan or enter panel QR code"
          disabled={panelRunning || !sessionActive}
          class="w-full rounded-lg border border-border bg-surface-0 py-2 pl-9 pr-3 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none disabled:opacity-50"
        />
      </div>

      <button
        onclick={handleRunPanel}
        disabled={!canSubmit}
        class="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50 transition-colors"
      >
        <Play size={14} />
        {submitting ? 'Starting...' : 'Run Panel'}
      </button>

      <button
        onclick={() => { showEndConfirm = true; }}
        disabled={panelRunning}
        class="flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2 disabled:opacity-50 transition-colors"
      >
        <Square size={14} />
        End Session
      </button>
    </div>

    {#if panelRunning}
      <p class="mt-2 text-2xs text-accent">
        Panel in progress. Waiting for results...
      </p>
    {/if}
  </div>
{/if}

<!-- End session confirmation dialog -->
{#if showEndConfirm}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog">
    <div class="rounded-lg border border-border bg-surface-1 p-6 shadow-lg max-w-sm w-full mx-4">
      <h3 class="text-sm font-semibold text-text-primary mb-2">End Manufacturing Session?</h3>
      <p class="text-2xs text-text-secondary mb-4">
        This will finalize the session. No more panels can be run after ending.
      </p>
      <div class="flex justify-end gap-2">
        <button
          onclick={() => { showEndConfirm = false; }}
          class="rounded-lg px-3 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2"
        >
          Cancel
        </button>
        <button
          onclick={handleEndSession}
          class="rounded-lg bg-error px-3 py-2 text-sm font-medium text-white hover:bg-error/80"
        >
          End Session
        </button>
      </div>
    </div>
  </div>
{/if}
