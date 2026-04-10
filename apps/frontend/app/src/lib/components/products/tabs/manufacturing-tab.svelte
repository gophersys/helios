<script lang="ts">
  import ProductStages from '../product-stages.svelte';
  import TestAppStatusCard from '../test-app-status-card.svelte';
  import TestPackageList from '../test-package-list.svelte';
  import type { Product } from '$lib/types/models';

  interface Props {
    product: Product;
    canManage: boolean;
    onRefresh: () => void;
  }

  let { product, canManage, onRefresh }: Props = $props();

  let selectedRevId = $state<string | null>(null);

  const revisions = $derived(
    (product.boards || [])
      .flatMap((b) => b.revisions || [])
      .filter((r) => r.status === 'ACTIVE')
  );

  const selectedRevision = $derived(
    revisions.find((r) => r.id === selectedRevId) ?? revisions[0] ?? null
  );
</script>

<TestAppStatusCard status={product.testAppStatus?.manufacturing ?? null} type="MANUFACTURING" />

{#if revisions.length === 0}
  <div class="text-center py-8">
    <p class="text-sm text-text-secondary">No active board revisions.</p>
    <p class="text-2xs text-text-tertiary mt-1">Add a board revision in the Hardware tab first.</p>
  </div>
{:else}
  <!-- Revision subtabs -->
  <div class="flex gap-1 border-b border-border mb-4">
    {#each revisions as rev}
      <button
        onclick={() => selectedRevId = rev.id}
        class="px-3 py-2 text-sm font-medium transition-colors border-b-2 -mb-px
          {selectedRevision?.id === rev.id ? 'border-accent text-accent' : 'border-transparent text-text-tertiary hover:text-text-secondary'}"
      >
        {rev.version}
        <span class="text-2xs text-text-tertiary ml-1">{rev.ckBoardsName}</span>
      </button>
    {/each}
  </div>

  {#if selectedRevision}
    <TestPackageList productId={product.id} packageType="MANUFACTURING" boardRevisionId={selectedRevision.id} />
    <ProductStages
      productId={product.id}
      productName={product.name}
      {revisions}
      fwRepoSlug={product.mfgFwRepoSlug ?? product.fwRepoSlug ?? ''}
      stageType="MANUFACTURING"
      boardRevisionId={selectedRevision.id}
      emptyLabel="Manufacturing not configured"
      enableLabel="Enable Manufacturing"
      {onRefresh}
    />
  {/if}
{/if}
