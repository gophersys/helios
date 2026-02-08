<script lang="ts">
  import { Cpu, Package, Pencil, Trash2 } from 'lucide-svelte';
  import type { Product } from '$lib/types/models';

  interface Props {
    product: Product;
    canManage: boolean;
    onEdit: (p: Product) => void;
    onDelete: (id: string) => void;
    onSelect: (p: Product) => void;
  }

  let { product, canManage, onEdit, onDelete, onSelect }: Props = $props();

  const chipsets = $derived(product.chipsets || []);
</script>

<div
  role="button"
  tabindex="0"
  onclick={() => onSelect(product)}
  onkeydown={(e) => e.key === 'Enter' && onSelect(product)}
  class="card card-interactive group relative flex flex-col overflow-hidden"
>
  <!-- Hero -->
  <div class="flex h-36 flex-col items-center justify-center gap-2 bg-surface-2">
    <Package size={32} strokeWidth={1} class="text-text-tertiary opacity-40" />
    {#if chipsets.length > 0}
      <div class="flex flex-wrap justify-center gap-1.5">
        {#each chipsets as c}
          <span class="inline-flex items-center gap-1 rounded-full bg-accent/10 px-2 py-0.5 text-2xs font-medium text-accent">
            <Cpu size={12} />
            {c}
          </span>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Body -->
  <div class="flex flex-1 flex-col p-3.5">
    <div class="mb-1 flex items-center gap-2">
      <h3 class="truncate text-sm font-semibold text-text-primary">
        {product.name}
      </h3>
      <span
        class={[
          'inline-flex items-center rounded-full px-1.5 py-0.5 text-2xs font-medium',
          product.active
            ? 'bg-success-muted text-success'
            : 'bg-surface-2 text-text-tertiary'
        ].join(' ')}
      >
        {product.active ? 'Active' : 'Inactive'}
      </span>
    </div>
    {#if product.description}
      <p class="mb-2 text-2xs text-text-tertiary line-clamp-2">
        {product.description}
      </p>
    {/if}

    <div class="mt-auto flex gap-3 text-2xs text-text-tertiary">
      <span>{product.boardRevisionCount ?? 0} board rev{(product.boardRevisionCount ?? 0) !== 1 ? 's' : ''}</span>
      <span>{product.firmwareAppCount ?? 0} fw app{(product.firmwareAppCount ?? 0) !== 1 ? 's' : ''}</span>
      <span>{product.firmwareBuildCount ?? 0} build{(product.firmwareBuildCount ?? 0) !== 1 ? 's' : ''}</span>
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
        onclick={() => onEdit(product)}
        class="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-text-primary"
        title="Edit"
        aria-label="Edit"
      >
        <Pencil size={16} />
      </button>
      <button
        onclick={() => onDelete(product.id)}
        class="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-error"
        title="Delete"
        aria-label="Delete"
      >
        <Trash2 size={16} />
      </button>
    </div>
  {/if}
</div>
