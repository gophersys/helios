<script lang="ts">
  import { Cpu, Pencil, Trash2, ChevronDown } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import type { InventoryComponent, InventoryRevision } from '$lib/types/models';
  import { getCategoryDisplayName } from '$lib/constants/inventory';

  interface Props {
    component: InventoryComponent;
    canManage: boolean;
    onEdit: (c: InventoryComponent) => void;
    onDelete: (id: string) => void;
    onSelect: (c: InventoryComponent) => void;
  }

  let { component, canManage, onEdit, onDelete, onSelect }: Props = $props();

  let revDropdown = $state(false);
  let selectedRev = $state<InventoryRevision | null>(null);

  const revisions = $derived(component.revisions || []);

  $effect(() => {
    selectedRev = revisions[0] || null;
  });

  function handleRevisionSelect(rev: InventoryRevision) {
    selectedRev = rev;
    revDropdown = false;
  }
</script>

<svelte:window onclick={() => (revDropdown = false)} />

<div
  role="button"
  tabindex="0"
  onclick={() => onSelect(component)}
  onkeydown={(e) => e.key === 'Enter' && onSelect(component)}
  class="card card-interactive group relative flex flex-col overflow-hidden"
>
  <!-- Hero image -->
  <div class="flex h-36 items-center justify-center bg-surface-2">
    {#if component.imageUrl}
      <img
        src={component.imageUrl}
        alt={component.name}
        class="h-full w-full object-contain p-3"
      />
    {:else}
      <Cpu size={32} strokeWidth={1} class="text-text-tertiary opacity-40" />
    {/if}
  </div>

  <!-- Body -->
  <div class="flex flex-1 flex-col p-3.5">
    <div class="mb-1 flex items-center gap-2">
      <h3 class="truncate text-sm font-semibold text-text-primary">
        {component.name}
      </h3>
      <span class="shrink-0 rounded-full bg-accent-muted px-2 py-0.5 text-2xs font-medium text-accent">
        {getCategoryDisplayName(component.category)}
      </span>
    </div>
    <div class="mb-2 text-2xs text-text-tertiary">
      {component.manufacturer} &middot; {component.partNumber}
    </div>

    <!-- Revision selector -->
    {#if revisions.length > 0}
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="relative mt-auto" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
        <button
          onclick={(e) => { e.stopPropagation(); revDropdown = !revDropdown; }}
          class="flex w-full items-center justify-between rounded-lg border border-border bg-surface-0 px-2.5 py-1.5 text-2xs text-text-secondary hover:border-text-tertiary"
        >
          <span class="flex items-center gap-1.5">
            <span class="font-medium">{selectedRev?.version || revisions[0].version}</span>
            <StatusBadge status={(selectedRev || revisions[0]).status} />
          </span>
          <ChevronDown size={16} />
        </button>

        {#if revDropdown}
          <div
            class="fixed inset-0 z-10"
            onclick={(e) => { e.stopPropagation(); revDropdown = false; }}
            onkeydown={(e) => e.key === 'Escape' && (revDropdown = false)}
            role="button"
            tabindex="-1"
          ></div>
          <div class="absolute left-0 right-0 top-full z-20 mt-1 max-h-48 overflow-y-auto rounded-lg border border-border bg-surface-1 py-1 shadow-card">
            {#each revisions as rev (rev.id)}
              <button
                onclick={(e) => { e.stopPropagation(); handleRevisionSelect(rev); }}
                class="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-2xs hover:bg-surface-2"
              >
                <span class="font-medium text-text-primary">{rev.version}</span>
                <StatusBadge status={rev.status} />
                {#if rev.releaseNotes}
                  <span class="ml-auto truncate text-text-tertiary">{rev.releaseNotes}</span>
                {/if}
              </button>
            {/each}
          </div>
        {/if}
      </div>
    {:else}
      <div class="mt-auto text-2xs text-text-tertiary">No revisions</div>
    {/if}
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
        onclick={() => onEdit(component)}
        class="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-text-primary"
        title="Edit"
        aria-label="Edit"
      >
        <Pencil size={16} />
      </button>
      <button
        onclick={() => onDelete(component.id)}
        class="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-error"
        title="Delete"
        aria-label="Delete"
      >
        <Trash2 size={16} />
      </button>
    </div>
  {/if}
</div>
