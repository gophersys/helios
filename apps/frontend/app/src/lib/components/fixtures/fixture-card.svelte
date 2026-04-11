<script lang="ts">
  import { Wrench, Pencil, Trash2 } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import type { Fixture } from '$lib/types/models';

  let { fixture, canManage, onEdit, onDelete, onSelect }: {
    fixture: Fixture;
    canManage: boolean;
    onEdit: (f: Fixture) => void;
    onDelete: (id: string) => void;
    onSelect: (f: Fixture) => void;
  } = $props();

  const slotCount = $derived(fixture.slotCount ?? fixture.slots?.length ?? 0);
  const assignedCount = $derived(fixture.slots?.filter(s => s.nodeId).length ?? 0);
</script>

<div
  role="button"
  tabindex="0"
  onclick={() => onSelect(fixture)}
  onkeydown={(e) => e.key === 'Enter' && onSelect(fixture)}
  class="card card-interactive group relative flex flex-col overflow-hidden"
>
  <!-- Hero -->
  <div class="flex h-32 flex-col items-center justify-center gap-2 bg-surface-2">
    <Wrench size={28} strokeWidth={1} class="text-text-tertiary opacity-40" />
    <StatusBadge status={fixture.type} />
  </div>

  <!-- Body -->
  <div class="flex flex-1 flex-col p-3.5">
    <div class="mb-1 flex items-center gap-2">
      <h3 class="truncate text-sm font-semibold text-text-primary">
        {fixture.name}
      </h3>
      <span
        class={[
          'inline-flex items-center rounded-full px-1.5 py-0.5 text-2xs font-medium',
          fixture.active
            ? 'bg-success-muted text-success'
            : 'bg-surface-2 text-text-tertiary'
        ].join(' ')}
      >
        {fixture.active ? 'Active' : 'Inactive'}
      </span>
    </div>

    {#if fixture.productName}
      <p class="text-2xs text-text-tertiary">Product: <span class="text-text-secondary">{fixture.productName}</span></p>
    {/if}

    {#if fixture.description}
      <p class="mt-1 text-2xs text-text-tertiary line-clamp-2">{fixture.description}</p>
    {/if}

    <!-- Slot dots -->
    <div class="mt-auto pt-2">
      <div class="flex items-center gap-1">
        <span class="text-2xs text-text-tertiary mr-1">{assignedCount}/{slotCount} slots</span>
        {#each Array(slotCount) as _, i}
          <span
            class={[
              'h-2.5 w-2.5 rounded-full',
              fixture.slots && fixture.slots[i]?.nodeId ? 'bg-success' : 'bg-surface-3'
            ].join(' ')}
          ></span>
        {/each}
      </div>
    </div>
  </div>

  <!-- Edit/delete -->
  {#if canManage}
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div
      role="group"
      class="absolute right-2 top-2 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
    >
      <button
        onclick={() => onEdit(fixture)}
        class="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur-sm hover:text-text-primary"
        title="Edit"
        aria-label="Edit"
      >
        <Pencil size={16} />
      </button>
      <button
        onclick={() => onDelete(fixture.id)}
        class="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur-sm hover:text-error"
        title="Delete"
        aria-label="Delete"
      >
        <Trash2 size={16} />
      </button>
    </div>
  {/if}
</div>
