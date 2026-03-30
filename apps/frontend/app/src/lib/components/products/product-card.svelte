<script lang="ts">
  import { Package, Trash2, Cpu, Layers } from 'lucide-svelte';
  import type { Product } from '$lib/types/models';

  interface Props {
    product: Product;
    canManage: boolean;
    onDelete: (id: string) => void;
    onSelect: (p: Product) => void;
  }

  let { product, canManage, onDelete, onSelect }: Props = $props();
</script>

<div
  role="button"
  tabindex="0"
  onclick={() => onSelect(product)}
  onkeydown={(e) => e.key === 'Enter' && onSelect(product)}
  class="card card-interactive group relative flex flex-col overflow-hidden"
>
  <div class="p-4">
    <!-- Header -->
    <div class="flex items-center justify-between mb-2">
      <div class="flex items-center gap-2.5">
        <div class="flex items-center justify-center w-9 h-9 rounded-lg bg-accent/10">
          <Package size={18} class="text-accent" />
        </div>
        <div>
          <h3 class="text-sm font-semibold text-text-primary">{product.name}</h3>
          <span class="text-2xs font-mono text-text-tertiary">{product.slug || '—'}</span>
        </div>
      </div>
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
      <p class="text-2xs text-text-tertiary mb-3 line-clamp-2">{product.description}</p>
    {/if}

    <!-- Targets -->
    {#if product.targets && product.targets.length > 0}
      <div class="flex flex-wrap gap-1.5 mb-3">
        {#each product.targets as target}
          <span class="inline-flex items-center gap-1 rounded-full bg-accent/10 px-2 py-0.5 text-2xs font-mono text-accent">
            <Cpu size={10} />
            {target.soc}
            <span class="text-accent/60">#{target.appId}</span>
          </span>
        {/each}
      </div>
    {/if}

    <!-- Stats -->
    <div class="flex gap-4 text-2xs text-text-tertiary">
      <div class="flex items-center gap-1">
        <Layers size={12} />
        <span><strong class="text-text-secondary">{product.boardCount ?? 0}</strong> board{(product.boardCount ?? 0) !== 1 ? 's' : ''}</span>
      </div>
      <div class="flex items-center gap-1">
        <Cpu size={12} />
        <span><strong class="text-text-secondary">{product.firmwareBuildCount ?? 0}</strong> build{(product.firmwareBuildCount ?? 0) !== 1 ? 's' : ''}</span>
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
        onclick={() => onDelete(product.id)}
        class="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-error"
        title="Delete"
        aria-label="Delete"
      >
        <Trash2 size={14} />
      </button>
    </div>
  {/if}
</div>
