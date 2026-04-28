<script lang="ts">
  import { goto } from '$app/navigation';
  import { Play } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import SessionStartDialog from '$lib/components/manufacturing/session-start-dialog.svelte';
  import type { ManufacturingFixture } from '$lib/types/models';

  let {
    fixture,
    canRun = false,
  }: {
    fixture: ManufacturingFixture;
    canRun?: boolean;
  } = $props();

  let showStartDialog = $state(false);
</script>

<div class="card card-sm card-interactive">
  <div class="flex items-start justify-between gap-3">
    <div class="min-w-0 flex-1">
      <h3 class="text-sm font-semibold text-text-primary">{fixture.name}</h3>
      {#if fixture.productName}
        <p class="text-2xs text-text-tertiary mt-0.5">{fixture.productName}</p>
      {/if}
      {#if fixture.description}
        <p class="text-2xs text-text-tertiary mt-1 truncate">{fixture.description}</p>
      {/if}
    </div>
    <StatusBadge status={fixture.assignable ? 'READY' : (fixture.lockState ?? 'FREE')} />
  </div>

  <div class="mt-3 flex items-center justify-between">
    <span class="text-2xs text-text-secondary">
      {fixture.slotCount} {fixture.slotCount === 1 ? 'slot' : 'slots'}
    </span>

    <div class="flex items-center gap-2">
      {#if fixture.activeSessionId}
        <button
          onclick={() => goto(`/manufacturing/session/${fixture.activeSessionId}`)}
          class="text-2xs font-medium text-accent hover:text-accent-hover transition-colors"
        >
          View active session
        </button>
      {:else if canRun && fixture.assignable}
        <button
          onclick={() => showStartDialog = true}
          class="btn btn-sm btn-primary text-2xs"
        >
          <Play size={12} />
          New Session
        </button>
      {/if}
    </div>
  </div>
</div>

{#if showStartDialog}
  <SessionStartDialog
    open={true}
    productId={fixture.productId}
    onClose={() => showStartDialog = false}
    onStarted={() => goto(`/manufacturing/sessions`)}
  />
{/if}
