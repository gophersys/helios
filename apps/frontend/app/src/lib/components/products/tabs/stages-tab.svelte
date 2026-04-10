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

<TestAppStatusCard status={product.testAppStatus?.validation ?? null} type="VALIDATION" />

<ProductStages
  productId={product.id}
  productName={product.name}
  {revisions}
  fwRepoSlug={product.fwRepoSlug ?? ''}
  {onRefresh}
/>
