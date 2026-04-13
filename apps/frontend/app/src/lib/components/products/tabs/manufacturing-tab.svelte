<script lang="ts">
  import { Factory } from 'lucide-svelte';
  import ProductStages from '../product-stages.svelte';
  import TestAppStatusCard from '../test-app-status-card.svelte';
  import TestPackageList from '../test-package-list.svelte';
  import FixtureDesignsSection from '../fixture-designs-section.svelte';
  import type { Product } from '$lib/types/models';

  interface Props {
    product: Product;
    canManage: boolean;
    onRefresh: () => void;
    selectedRevisionId?: string | null;
  }

  let { product, canManage, onRefresh, selectedRevisionId }: Props = $props();

  const revisions = $derived(
    (product.boards || [])
      .flatMap((b) => b.revisions || [])
      .filter((r) => r.status === 'ACTIVE')
  );

  const selectedRevision = $derived(
    revisions.find((r) => r.id === selectedRevisionId) ?? revisions[0] ?? null
  );
</script>

<!-- Test App section -->
<div class="card card-md mb-6">
  <h3 class="text-sm font-semibold text-text-primary mb-3">Manufacturing Test App</h3>
  <TestAppStatusCard status={product.testAppStatus?.manufacturing ?? null} type="MANUFACTURING" />
  <TestPackageList productId={product.id} packageType="MANUFACTURING" {onRefresh} />
  <FixtureDesignsSection type="MANUFACTURING" />
</div>

{#if revisions.length === 0}
  <div class="text-center py-8">
    <Factory size={32} class="mx-auto text-text-tertiary mb-3 opacity-50" />
    <p class="text-sm text-text-secondary">No active board revisions.</p>
    <p class="text-2xs text-text-tertiary mt-1">Add a board revision in the Hardware tab first.</p>
  </div>
{:else}
  {#if selectedRevision}
    <ProductStages
      productId={product.id}
      productSlug={product.slug ?? ''}
      productName={product.name}
      {revisions}
      fwRepoSlug={product.mfgFwRepoSlug ?? product.fwRepoSlug ?? ''}
      stageType="MANUFACTURING"
      boardRevisionId={selectedRevision.id}
      {canManage}
      {onRefresh}
    />
  {/if}
{/if}
