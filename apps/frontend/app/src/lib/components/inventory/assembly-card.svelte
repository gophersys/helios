<script lang="ts">
  import { Boxes, Pencil, Trash2, ChevronDown } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import type { Assembly, AssemblyRevision } from '$lib/types/models';

  interface Props {
    assembly: Assembly;
    canManage: boolean;
    onEdit: (a: Assembly) => void;
    onDelete: (id: string) => void;
    onSelect: (a: Assembly) => void;
  }

  let { assembly, canManage, onEdit, onDelete, onSelect }: Props = $props();

  let revDropdown = $state(false);
  let selectedRev = $state<AssemblyRevision | null>(null);

  const revisions = $derived(assembly.revisions || []);

  $effect(() => {
    selectedRev = revisions[0] || null;
  });

  const currentBom = $derived(selectedRev?.bom || []);

  function handleRevisionSelect(rev: AssemblyRevision) {
    selectedRev = rev;
    revDropdown = false;
  }
</script>

<svelte:window onclick={() => (revDropdown = false)} />

<div
  role="button"
  tabindex="0"
  onclick={() => onSelect(assembly)}
  onkeydown={(e) => e.key === 'Enter' && onSelect(assembly)}
  class="card card-interactive group relative flex flex-col overflow-hidden"
>
  <!-- Hero image -->
  <div class="flex h-36 items-center justify-center bg-surface-2">
    {#if assembly.imageUrl}
      <img
        src={assembly.imageUrl}
        alt={assembly.name}
        class="h-full w-full object-contain p-3"
      />
    {:else}
      <Boxes size={32} strokeWidth={1} class="text-text-tertiary opacity-40" />
    {/if}
  </div>

  <!-- Body -->
  <div class="flex flex-1 flex-col p-3.5">
    <h3 class="mb-1 truncate text-sm font-semibold text-text-primary">
      {assembly.name}
    </h3>
    {#if assembly.description}
      <div class="mb-2 text-2xs text-text-tertiary line-clamp-2">
        {assembly.description}
      </div>
    {/if}

    <!-- Revision selector -->
    {#if revisions.length > 0}
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="relative" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
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
              </button>
            {/each}
          </div>
        {/if}
      </div>
    {:else}
      <div class="text-2xs text-text-tertiary">No revisions</div>
    {/if}

    <!-- BOM list -->
    {#if currentBom.length > 0}
      <div class="mt-2 space-y-0.5">
        {#each currentBom as item (item.id)}
          <div class="text-2xs text-text-secondary">
            {item.quantity}x
            {item.inventoryRevision?.component?.name || 'Unknown'}
            <span class="text-text-tertiary">
              ({item.inventoryRevision?.version || '?'})
            </span>
          </div>
        {/each}
      </div>
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
        onclick={() => onEdit(assembly)}
        class="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-text-primary"
        title="Edit"
        aria-label="Edit"
      >
        <Pencil size={16} />
      </button>
      <button
        onclick={() => onDelete(assembly.id)}
        class="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-error"
        title="Delete"
        aria-label="Delete"
      >
        <Trash2 size={16} />
      </button>
    </div>
  {/if}
</div>
