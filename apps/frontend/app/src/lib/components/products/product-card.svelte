<script lang="ts">
  import { Package, Trash2, ExternalLink, GitBranch, FlaskConical, Cpu } from 'lucide-svelte';
  import type { Product } from '$lib/types/models';

  interface Props {
    product: Product;
    canManage: boolean;
    onDelete: (id: string) => void;
    onSelect: (p: Product) => void;
  }

  let { product, canManage, onDelete, onSelect }: Props = $props();

  const stageLabels = ['SM', 'SI', 'IN', 'NY', 'FU'];
  const stageColors: Record<number, string> = {
    1: 'bg-blue-400', 2: 'bg-cyan-400', 3: 'bg-amber-400', 4: 'bg-purple-400', 5: 'bg-red-400',
  };

  const revisions = $derived((product as any).revisions || []);
  const stages = $derived((product as any).stageConfigs || []);
  const enabledStages = $derived((product as any).enabledStageCount || 0);
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
      <span class="rounded-full px-1.5 py-0.5 text-2xs font-medium {product.active ? 'bg-success-muted text-success' : 'bg-surface-2 text-text-tertiary'}">
        {product.active ? 'Active' : 'Inactive'}
      </span>
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

    <!-- Validation stages -->
    <div class="flex items-center gap-2">
      <FlaskConical size={12} class="text-text-tertiary shrink-0" />
      {#if stages.length > 0}
        <div class="flex gap-1">
          {#each [1, 2, 3, 4, 5] as stageNum}
            {@const cfg = stages.find((s: any) => s.stage === stageNum)}
            <span
              class="w-6 h-5 flex items-center justify-center rounded text-[9px] font-bold
                {cfg?.enabled ? stageColors[stageNum] + ' text-white' : 'bg-surface-2 text-text-tertiary'}"
              title="{cfg?.name || stageLabels[stageNum-1]}: {cfg?.enabled ? 'Enabled' : 'Disabled'}"
            >
              {stageLabels[stageNum - 1]}
            </span>
          {/each}
        </div>
        <span class="text-2xs text-text-tertiary">{enabledStages}/5</span>
      {:else}
        <span class="text-2xs text-text-tertiary">No stages configured</span>
      {/if}
    </div>

    <!-- Stats row -->
    <div class="flex gap-4 text-2xs text-text-tertiary border-t border-border-subtle pt-2">
      <div>
        <strong class="text-text-secondary">{product.firmwareSetCount ?? 0}</strong> firmware sets
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
    <div
      role="group"
      class="absolute right-2 top-2 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
    >
      <button
        onclick={() => onDelete(product.id)}
        class="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-error"
        title="Delete" aria-label="Delete"
      >
        <Trash2 size={14} />
      </button>
    </div>
  {/if}
</div>
