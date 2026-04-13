<script lang="ts">
  import { Package, Trash2, ExternalLink, GitBranch } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import type { Product } from '$lib/types/models';

  interface Props {
    product: Product;
    canManage: boolean;
    onDelete: (id: string) => void;
    onSelect: (p: Product) => void;
  }

  let { product, canManage, onDelete, onSelect }: Props = $props();

  const revisions = $derived((product as any).revisions || []);
</script>

<div
  role="button"
  tabindex="0"
  onclick={() => onSelect(product)}
  onkeydown={(e) => e.key === 'Enter' && onSelect(product)}
  class="card card-interactive group relative flex flex-col overflow-hidden"
>
  <div class="p-4 space-y-3">
    <!-- Header: name + status -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2.5">
        <div class="flex items-center justify-center w-8 h-8 rounded-lg bg-accent/10">
          <Package size={16} class="text-accent" />
        </div>
        <div>
          <h3 class="text-sm font-semibold text-text-primary">{product.name}</h3>
          {#if product.description}
            <p class="text-2xs text-text-tertiary line-clamp-1">{product.description}</p>
          {/if}
        </div>
      </div>
      <StatusBadge status={product.active ? 'ACTIVE' : 'INACTIVE'} />
    </div>

    <!-- Revisions -->
    {#if revisions.length > 0}
      <div class="flex flex-wrap gap-1.5">
        {#each revisions as rev}
          <span class="inline-flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 font-mono text-2xs {rev.status === 'ACTIVE' ? 'text-text-primary' : 'text-text-tertiary line-through'}">
            {rev.version.toUpperCase()}
            <span class="text-text-tertiary">({rev.ckBoardsName})</span>
          </span>
        {/each}
      </div>
    {/if}

    <!-- Repos -->
    {#if product.fwRepoSlug || product.mfgFwRepoSlug}
      <div class="flex flex-wrap gap-2">
        {#if product.fwRepoSlug}
          <a
            href="https://bitbucket.org/corekinect/{product.fwRepoSlug}"
            target="_blank" rel="noopener noreferrer"
            class="inline-flex items-center gap-1 rounded bg-surface-0 px-1.5 py-0.5 font-mono text-2xs text-text-secondary hover:text-accent transition-colors"
            onclick={(e) => e.stopPropagation()}
          >
            <GitBranch size={10} /> {product.fwRepoSlug} <ExternalLink size={8} class="opacity-50" />
          </a>
        {/if}
        {#if product.mfgFwRepoSlug}
          <a
            href="https://bitbucket.org/corekinect/{product.mfgFwRepoSlug}"
            target="_blank" rel="noopener noreferrer"
            class="inline-flex items-center gap-1 rounded bg-surface-0 px-1.5 py-0.5 font-mono text-2xs text-text-secondary hover:text-accent transition-colors"
            onclick={(e) => e.stopPropagation()}
          >
            <GitBranch size={10} /> {product.mfgFwRepoSlug} <ExternalLink size={8} class="opacity-50" />
          </a>
        {/if}
      </div>
    {/if}


    <!-- Stats row -->
    <div class="flex gap-4 text-2xs text-text-tertiary border-t border-border-subtle pt-2">
      <div>
        <strong class="text-text-secondary">{product.assetSetCount ?? 0}</strong> asset sets
      </div>
      <div>
        <strong class="text-text-secondary">{revisions.length}</strong> revision{revisions.length !== 1 ? 's' : ''}
      </div>
      <div>
        <strong class="text-text-secondary">{product.targets?.length ?? 0}</strong> target{(product.targets?.length ?? 0) !== 1 ? 's' : ''}
      </div>
    </div>
  </div>

  <!-- Delete -->
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
        class="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur-sm hover:text-error"
        title="Delete" aria-label="Delete"
      >
        <Trash2 size={14} />
      </button>
    </div>
  {/if}
</div>
