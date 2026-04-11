<script lang="ts">
  import { QrCode, Play, Square } from 'lucide-svelte';
  import Modal from '$lib/components/ui/modal.svelte';
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
  <div class="card card-sm mb-4">
    <div class="flex items-center gap-3">
      <div class="relative flex-1">
        <QrCode size={14} class="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary" />
        <input
          type="text"
          bind:value={qrInput}
          onkeydown={handleKeydown}
          placeholder="Scan or enter panel QR code"
          disabled={panelRunning || !sessionActive}
          class="input input-md pl-9"
        />
      </div>

      <button
        onclick={handleRunPanel}
        disabled={!canSubmit}
        class="btn btn-sm btn-primary"
      >
        <Play size={14} />
        {submitting ? 'Starting...' : 'Run Panel'}
      </button>

      <button
        onclick={() => { showEndConfirm = true; }}
        disabled={panelRunning}
        class="btn btn-sm btn-secondary"
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
<Modal open={showEndConfirm} title="End Manufacturing Session?" onclose={() => { showEndConfirm = false; }} size="sm">
  <p class="text-2xs text-text-secondary">
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
      onclick={handleEndSession}
      class="btn btn-sm btn-danger"
    >
      End Session
    </button>
  {/snippet}
</Modal>
