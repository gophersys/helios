<script lang="ts">
  import { Plus, Trash2 } from 'lucide-svelte';
  import type { InventoryRevisionOption } from '$lib/types/models';

  interface BomEntry {
    inventoryRevisionId: string;
    quantity: number;
  }

  interface Props {
    bom: BomEntry[];
    onchange: (bom: BomEntry[]) => void;
    availableRevisions: InventoryRevisionOption[];
  }

  let { bom, onchange, availableRevisions }: Props = $props();

  let searchTerm = $state('');

  import { getCategoryDisplayName } from '$lib/constants/inventory';

  // Group revisions by component for display
  interface GroupedRevision {
    componentName: string;
    category: string;
    revisions: InventoryRevisionOption[];
  }

  const grouped = $derived.by(() => {
    const groups: Record<string, GroupedRevision> = {};
    for (const rev of availableRevisions) {
      const key = rev.componentId;
      if (!groups[key]) {
        groups[key] = {
          componentName: rev.componentName,
          category: rev.category,
          revisions: [],
        };
      }
      groups[key].revisions.push(rev);
    }
    return groups;
  });

  const selectedIds = $derived(new Set(bom.map((b) => b.inventoryRevisionId)));

  const filteredGroups = $derived.by(() => {
    if (!searchTerm) return Object.entries(grouped);
    const term = searchTerm.toLowerCase();
    return Object.entries(grouped).filter(([, group]) =>
      group.componentName.toLowerCase().includes(term) ||
      group.category.toLowerCase().includes(term) ||
      group.revisions.some((r) => r.version.toLowerCase().includes(term))
    );
  });

  function addItem(revisionId: string) {
    if (!selectedIds.has(revisionId)) {
      onchange([...bom, { inventoryRevisionId: revisionId, quantity: 1 }]);
    }
  }

  function removeItem(revisionId: string) {
    onchange(bom.filter((b) => b.inventoryRevisionId !== revisionId));
  }

  function updateQuantity(revisionId: string, quantity: number) {
    onchange(
      bom.map((b) =>
        b.inventoryRevisionId === revisionId
          ? { ...b, quantity: Math.max(1, quantity) }
          : b
      )
    );
  }

  function getRevisionLabel(revisionId: string): string {
    const rev = availableRevisions.find((r) => r.id === revisionId);
    return rev ? `${rev.componentName} (${rev.version})` : revisionId;
  }
</script>

<div>
  <span class="mb-1.5 block text-2xs font-medium text-text-tertiary">
    Bill of Materials
  </span>

  <!-- Current BOM items -->
  {#if bom.length > 0}
    <div class="mb-3 space-y-1.5">
      {#each bom as item (item.inventoryRevisionId)}
        <div class="flex items-center gap-2 rounded-lg border border-border bg-surface-0 px-3 py-2">
          <span class="flex-1 text-xs text-text-primary">
            {getRevisionLabel(item.inventoryRevisionId)}
          </span>
          <input
            type="number"
            min="1"
            value={item.quantity}
            onchange={(e) => updateQuantity(item.inventoryRevisionId, parseInt((e.target as HTMLInputElement).value) || 1)}
            class="w-16 rounded border border-border bg-surface-1 px-2 py-1 text-center text-xs text-text-primary focus:border-accent focus:outline-none"
          />
          <button
            type="button"
            onclick={() => removeItem(item.inventoryRevisionId)}
            class="rounded p-1 text-text-tertiary hover:text-error"
            title="Remove"
            aria-label="Remove"
          >
            <Trash2 size={16} />
          </button>
        </div>
      {/each}
    </div>
  {/if}

  <!-- Add component search -->
  <div class="rounded-lg border border-border bg-surface-0">
    <div class="p-2">
      <input
        type="text"
        placeholder="Search components..."
        bind:value={searchTerm}
        class="w-full rounded border border-border bg-surface-1 px-2.5 py-1.5 text-xs text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
      />
    </div>
    <div class="max-h-48 overflow-y-auto border-t border-border">
      {#if filteredGroups.length === 0}
        <div class="px-3 py-4 text-center text-2xs text-text-tertiary">
          No components found
        </div>
      {:else}
        {#each filteredGroups as [compId, group] (compId)}
          <div>
            <div class="sticky top-0 bg-surface-2 px-3 py-1.5 text-2xs font-semibold text-text-secondary">
              {group.componentName}
              <span class="ml-1.5 font-normal text-text-tertiary">
                {getCategoryDisplayName(group.category)}
              </span>
            </div>
            {#each group.revisions as rev (rev.id)}
              {@const isSelected = selectedIds.has(rev.id)}
              <button
                type="button"
                disabled={isSelected}
                onclick={() => addItem(rev.id)}
                class={[
                  'flex w-full items-center gap-2 px-3 py-1.5 text-left text-2xs',
                  isSelected
                    ? 'bg-accent-muted text-text-tertiary'
                    : 'hover:bg-surface-2 text-text-primary'
                ].join(' ')}
              >
                <Plus size={12} class={isSelected ? 'opacity-30' : 'text-accent'} />
                <span class="font-medium">{rev.version}</span>
                <span class="text-text-tertiary">{rev.status}</span>
                {#if isSelected}
                  <span class="ml-auto text-2xs text-accent">Added</span>
                {/if}
              </button>
            {/each}
          </div>
        {/each}
      {/if}
    </div>
  </div>
</div>
