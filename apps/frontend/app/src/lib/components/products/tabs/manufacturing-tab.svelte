<script lang="ts">
  import ProductStages from '../product-stages.svelte';
  import TestAppStatusCard from '../test-app-status-card.svelte';
  import type { Product } from '$lib/types/models';

  interface Props {
    product: Product;
    canManage: boolean;
    onRefresh: () => void;
  }

  let { product, canManage, onRefresh }: Props = $props();

  const revisions = $derived(
    (product.boards || []).flatMap((b) => b.revisions || [])
  );
</script>

<TestAppStatusCard status={product.testAppStatus?.manufacturing ?? null} type="MANUFACTURING" />

<ProductStages
  productId={product.id}
  productName={product.name}
  {revisions}
  fwRepoSlug={product.mfgFwRepoSlug ?? product.fwRepoSlug ?? ''}
  stageType="MANUFACTURING"
  emptyLabel="Manufacturing not configured"
  enableLabel="Enable Manufacturing"
  {onRefresh}
/>
