<script lang="ts">
  import { onMount } from 'svelte';
  import { FlaskConical } from 'lucide-svelte';
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
    (product.boards || []).flatMap((b) => b.revisions || [])
  );

  const activeRevisions = $derived(
    revisions.filter((r) => r.status === 'ACTIVE')
  );

  const selectedRevision = $derived(
    activeRevisions.find((r) => r.id === selectedRevId) ?? activeRevisions[0] ?? null
  );

  onMount(() => {
    if (activeRevisions.length > 0 && !selectedRevId) {
      selectedRevId = activeRevisions[0].id;
    }
  });
</script>

<!-- Test App section -->
<div class="rounded-xl border border-border bg-surface-1 p-5 mb-6">
  <h3 class="text-sm font-semibold text-text-primary mb-3">Validation Test App</h3>
  <TestAppStatusCard status={product.testAppStatus?.validation ?? null} type="VALIDATION" />
  <TestPackageList productId={product.id} packageType="VALIDATION" {onRefresh} />
</div>

{#if activeRevisions.length === 0}
  <div class="text-center py-8">
    <FlaskConical size={32} class="mx-auto text-text-tertiary mb-3 opacity-50" />
    <p class="text-sm text-text-secondary">No active board revisions.</p>
    <p class="text-2xs text-text-tertiary mt-1">Add a board revision in the Hardware tab first.</p>
  </div>
{:else}
  <!-- Revision subtabs -->
  <div class="flex gap-1 border-b border-border mb-4 mt-4">
    {#each activeRevisions as rev}
      <button
        onclick={() => selectedRevId = rev.id}
        class="px-3 py-2 text-sm font-medium transition-colors border-b-2 -mb-px
          {(selectedRevision?.id === rev.id) ? 'border-accent text-accent' : 'border-transparent text-text-tertiary hover:text-text-secondary'}"
      >
        {rev.version}
        <span class="text-2xs text-text-tertiary ml-1">{rev.ckBoardsName}</span>
      </button>
    {/each}
  </div>

  {#if selectedRevision}
    <ProductStages
      productId={product.id}
      productName={product.name}
      {revisions}
      boardRevisionId={selectedRevision.id}
      fwRepoSlug={product.fwRepoSlug ?? ''}
      {canManage}
      {onRefresh}
    />
  {/if}
{/if}
