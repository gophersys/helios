<script lang="ts">
  import { Server, Pencil, Trash2, HeartPulse, Wrench } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import type { ConcordNode } from '$lib/types/models';

  let { node, canManage, onEdit, onDelete, onHealthCheck }: {
    node: ConcordNode;
    canManage: boolean;
    onEdit: (node: ConcordNode) => void;
    onDelete: (id: string) => void;
    onHealthCheck: (id: string) => void;
  } = $props();

  const statusDot = $derived(
    node.status === 'ONLINE' ? 'bg-success' :
    node.status === 'MAINTENANCE' ? 'bg-warning' :
    node.status === 'ERROR' ? 'bg-error' :
    'bg-text-tertiary'
  );
</script>

<div class="card card-interactive group relative flex flex-col overflow-hidden">
  <!-- Hero -->
  <div class="flex h-28 flex-col items-center justify-center gap-2 bg-surface-2">
    <Server size={28} strokeWidth={1} class="text-text-tertiary opacity-40" />
    <StatusBadge status={node.type} />
  </div>

  <!-- Body -->
  <div class="flex flex-1 flex-col p-3.5">
    <div class="mb-1 flex items-center gap-2">
      <span class="h-2 w-2 shrink-0 rounded-full {statusDot}"></span>
      <h3 class="truncate text-sm font-semibold text-text-primary">
        {node.name}
      </h3>
      <StatusBadge status={node.status} />
    </div>

    <div class="mt-1 space-y-0.5 text-2xs text-text-tertiary">
      <p class="truncate">Host: <span class="text-text-secondary">{node.hostname}</span></p>
      {#if node.ipAddress}
        <p>IP: <span class="text-text-secondary">{node.ipAddress}</span></p>
      {/if}
      {#if node.hardwareRevision}
        <p>HW Rev: <span class="text-text-secondary">{node.hardwareRevision}</span></p>
      {/if}
    </div>

    {#if node.fixtureSlot}
      <div class="mt-2 flex items-center gap-1.5 text-2xs">
        <Wrench size={12} class="text-accent" />
        <span class="text-text-secondary">
          {node.fixtureSlot.fixtureName || 'Fixture'} — Slot {node.fixtureSlot.slotIndex}
        </span>
      </div>
    {/if}
  </div>

  <!-- Actions -->
  {#if canManage}
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div
      role="group"
      class="absolute right-2 top-2 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
    >
      <button
        onclick={() => onHealthCheck(node.id)}
        class="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-success"
        title="Health check"
        aria-label="Health check"
      >
        <HeartPulse size={16} />
      </button>
      <button
        onclick={() => onEdit(node)}
        class="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-text-primary"
        title="Edit"
        aria-label="Edit"
      >
        <Pencil size={16} />
      </button>
      <button
        onclick={() => onDelete(node.id)}
        class="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-error"
        title="Delete"
        aria-label="Delete"
      >
        <Trash2 size={16} />
      </button>
    </div>
  {/if}
</div>
