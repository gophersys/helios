<script lang="ts">
  import { Server } from 'lucide-svelte';
  import Select from '$lib/components/ui/select.svelte';
  import type { FixtureSlot, ConcordNode } from '$lib/types/models';

  let { slot, availableNodes, canManage, onAssign, onUnassign }: {
    slot: FixtureSlot;
    availableNodes: ConcordNode[];
    canManage: boolean;
    onAssign: (slotId: string, nodeId: string) => void;
    onUnassign: (slotId: string) => void;
  } = $props();

  let selectedNodeId = $state('');

  function handleAssign() {
    if (selectedNodeId) {
      onAssign(slot.id, selectedNodeId);
      selectedNodeId = '';
    }
  }
</script>

<tr class="table-row">
  <td class="table-cell font-mono text-text-secondary">{slot.slotIndex}</td>
  <td class="table-cell text-text-secondary">{slot.label || '—'}</td>
  <td class="table-cell">
    {#if slot.node}
      <div class="flex items-center gap-2">
        <Server size={14} class="text-success" />
        <span class="text-sm text-text-primary">{slot.node.name}</span>
        <span class="text-2xs text-text-tertiary">({slot.node.hostname})</span>
        {#if canManage}
          <button
            onclick={() => onUnassign(slot.id)}
            class="ml-2 text-2xs text-error hover:underline"
          >
            Remove
          </button>
        {/if}
      </div>
    {:else if canManage}
      <div class="flex items-center gap-2">
        <Select
          bind:value={selectedNodeId}
          placeholder="Select node..."
          options={availableNodes.map(n => ({ value: n.id, label: `${n.name} (${n.hostname})` }))}
          compact
        />
        <button
          onclick={handleAssign}
          disabled={!selectedNodeId}
          class="btn btn-sm btn-primary"
        >
          Assign
        </button>
      </div>
    {:else}
      <span class="text-2xs text-text-tertiary">Unassigned</span>
    {/if}
  </td>
  <td class="table-cell">
    <span
      class={[
        'inline-flex items-center rounded-full px-1.5 py-0.5 text-2xs font-medium',
        slot.active ? 'bg-success-muted text-success' : 'bg-surface-2 text-text-tertiary'
      ].join(' ')}
    >
      {slot.active ? 'Active' : 'Inactive'}
    </span>
  </td>
</tr>
