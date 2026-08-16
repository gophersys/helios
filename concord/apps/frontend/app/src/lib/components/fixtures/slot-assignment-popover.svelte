<script lang="ts">
  import { Server, Loader2, Check, X as XIcon, Trash2 } from 'lucide-svelte';
  import Modal from '$lib/components/ui/modal.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import type { FixtureSlot, ConcordNode } from '$lib/types/models';

  let {
    open,
    slot,
    availableNodes,
    canManage,
    locked = false,
    onClose,
    onAssign,
    onUnassign,
  }: {
    open: boolean;
    slot: FixtureSlot | null;
    availableNodes: ConcordNode[];
    canManage: boolean;
    locked?: boolean;
    onClose: () => void;
    onAssign: (slotId: string, nodeId: string) => Promise<void> | void;
    onUnassign: (slotId: string) => Promise<void> | void;
  } = $props();

  let selectedNodeId = $state('');
  let busy = $state(false);

  $effect(() => {
    if (!open) {
      selectedNodeId = '';
      busy = false;
    }
  });

  async function handleAssign() {
    if (!slot || !selectedNodeId) return;
    busy = true;
    try {
      await onAssign(slot.id, selectedNodeId);
      onClose();
    } finally {
      busy = false;
    }
  }

  async function handleUnassign() {
    if (!slot) return;
    busy = true;
    try {
      await onUnassign(slot.id);
      onClose();
    } finally {
      busy = false;
    }
  }

  const filteredNodes = $derived(
    slot && slot.nodeId
      ? availableNodes.filter((n) => n.id !== slot.nodeId)
      : availableNodes
  );

  const nodeOptions = $derived(
    filteredNodes.map((n) => ({ value: n.id, label: `${n.name} (${n.hostname})` }))
  );
</script>

<Modal
  open={open && !!slot}
  size="md"
  title={slot ? `Slot ${slot.slotIndex + 1}${slot.label ? ' · ' + slot.label : ''}` : 'Slot'}
  onclose={onClose}
>
  {#if slot}
    <div class="space-y-4">
      <!-- Current assignment summary -->
      <div class="rounded-lg border border-border bg-surface-1 p-3">
        <div class="flex items-center gap-2 text-2xs uppercase tracking-wider text-text-tertiary mb-2">
          <Server size={12} /> Current Assignment
        </div>
        {#if slot.node}
          <div class="flex items-center justify-between gap-2">
            <div class="min-w-0">
              <p class="text-sm font-medium text-text-primary truncate">{slot.node.name}</p>
              <p class="text-2xs font-mono text-text-tertiary truncate">{slot.node.hostname}</p>
              {#if slot.mtibStatus?.reason}
                <p class="text-2xs text-text-tertiary mt-1">{slot.mtibStatus.reason}</p>
              {/if}
            </div>
            <!-- Use the per-slot mtibStatus label so the panel tile and
                 the modal always show the same state (READY, DEPLOYING,
                 NOT_DEPLOYED, …). Falls back to the 3-value summary on
                 ``node.status`` when mtibStatus isn't loaded. -->
            <StatusBadge status={slot.mtibStatus?.state ?? slot.node.status} />
          </div>
        {:else}
          <p class="text-sm text-text-tertiary">No node assigned.</p>
        {/if}
      </div>

      {#if canManage}
        {#if locked}
          <p class="text-2xs text-warning">Fixture is locked by an active session — assignments cannot change.</p>
        {:else}
          <!-- Assign / change -->
          <div class="space-y-2">
            <label class="block text-2xs font-medium text-text-secondary">
              {slot.node ? 'Change to' : 'Assign'}
            </label>
            <Select
              bind:value={selectedNodeId}
              placeholder={availableNodes.length === 0 ? 'No nodes available' : 'Select node...'}
              options={nodeOptions}
              compact
            />
            <div class="flex items-center justify-between gap-2 pt-1">
              {#if slot.node}
                <button
                  onclick={handleUnassign}
                  disabled={busy}
                  class="btn btn-sm btn-ghost text-error"
                >
                  {#if busy}<Loader2 size={14} class="animate-spin" />{:else}<Trash2 size={14} />{/if}
                  Unassign
                </button>
              {:else}
                <span></span>
              {/if}
              <div class="flex items-center gap-2">
                <button onclick={onClose} class="btn btn-sm btn-ghost" disabled={busy}>
                  <XIcon size={14} /> Cancel
                </button>
                <button
                  onclick={handleAssign}
                  disabled={busy || !selectedNodeId}
                  class="btn btn-sm btn-primary"
                >
                  {#if busy}<Loader2 size={14} class="animate-spin" />{:else}<Check size={14} />{/if}
                  {slot.node ? 'Change' : 'Assign'}
                </button>
              </div>
            </div>
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</Modal>
