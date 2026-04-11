<script lang="ts">
  import { onMount } from 'svelte';
  import { Loader2, Package } from 'lucide-svelte';
  import RevisionAssetsPanel from './revision-assets-panel.svelte';
  import { listStageConfigs } from '$lib/services/stages';
  import type { Product } from '$lib/types/models';
  import type { ProductStageConfig } from '$lib/types/stages';

  interface Props {
    product: Product;
    canManage: boolean;
    onRefresh: () => void;
    selectedRevisionId?: string | null;
  }

  let { product, canManage, onRefresh, selectedRevisionId }: Props = $props();

  let stageConfigs = $state<ProductStageConfig[]>([]);
  let loading = $state(true);

  const revisions = $derived(
    (product.boards || [])
      .flatMap((b) => b.revisions || [])
      .filter((r) => r.status === 'ACTIVE')
  );

  const selectedRevision = $derived(
    revisions.find((r) => r.id === selectedRevisionId) ?? revisions[0] ?? null
  );

  onMount(async () => {
    try {
      stageConfigs = await listStageConfigs(product.id);
    } catch {
      stageConfigs = [];
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
    <Package size={32} class="mx-auto text-text-tertiary mb-3 opacity-50" />
    <p class="text-sm text-text-secondary">No active board revisions.</p>
    <p class="text-2xs text-text-tertiary mt-1">Add a board revision in the Hardware tab first.</p>
  </div>
{:else}
  <!-- Selected revision panel -->
  {#if selectedRevision}
    {#key selectedRevision.id}
      <RevisionAssetsPanel
        productId={product.id}
        revision={selectedRevision}
        {stageConfigs}
        {canManage}
        {onRefresh}
      />
    {/key}
  {/if}
{/if}
