<script lang="ts">
  import { onMount } from 'svelte';
  import { Loader2 } from 'lucide-svelte';
  import RevisionAssetsPanel from './revision-assets-panel.svelte';
  import { listStageConfigs } from '$lib/services/stages';
  import type { Product, BoardRevision } from '$lib/types/models';
  import type { ProductStageConfig } from '$lib/types/stages';

  interface Props {
    product: Product;
    canManage: boolean;
  }

  let { product, canManage }: Props = $props();

  let stageConfigs = $state<ProductStageConfig[]>([]);
  let loading = $state(true);
  let selectedRevId = $state<string | null>(null);

  const revisions = $derived(
    (product.boards || [])
      .flatMap((b) => b.revisions || [])
      .filter((r) => r.status === 'ACTIVE')
  );

  const selectedRevision = $derived(
    revisions.find((r) => r.id === selectedRevId) ?? revisions[0] ?? null
  );

  onMount(async () => {
    try {
      stageConfigs = await listStageConfigs(product.id);
    } catch {
      stageConfigs = [];
    }
    if (revisions.length > 0 && !selectedRevId) {
      selectedRevId = revisions[0].id;
    }
    loading = false;
  });
</script>

{#if loading}
  <div class="flex items-center gap-2 justify-center py-8 text-sm text-text-tertiary">
    <Loader2 size={16} class="animate-spin" /> Loading...
  </div>
{:else if revisions.length === 0}
  <div class="text-center py-8">
    <p class="text-sm text-text-secondary">No active board revisions.</p>
    <p class="text-2xs text-text-tertiary mt-1">Add a board revision in the Hardware tab first.</p>
  </div>
{:else}
  <!-- Revision tabs -->
  <div class="flex gap-1 border-b border-border mb-4">
    {#each revisions as rev}
      <button
        onclick={() => selectedRevId = rev.id}
        class="px-3 py-2 text-sm font-medium transition-colors border-b-2 -mb-px
          {selectedRevId === rev.id ? 'border-accent text-accent' : 'border-transparent text-text-tertiary hover:text-text-secondary'}"
      >
        {rev.version}
        <span class="text-2xs text-text-tertiary ml-1">{rev.ckBoardsName}</span>
      </button>
    {/each}
  </div>

  <!-- Selected revision panel -->
  {#if selectedRevision}
    {#key selectedRevision.id}
      <RevisionAssetsPanel
        productId={product.id}
        revision={selectedRevision}
        {stageConfigs}
        {canManage}
      />
    {/key}
  {/if}
{/if}
