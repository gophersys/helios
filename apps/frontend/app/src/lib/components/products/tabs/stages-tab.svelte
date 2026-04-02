<script lang="ts">
  import ProductStages from '../product-stages.svelte';
  import type { Product } from '$lib/types/models';

  interface Props {
    product: Product;
    canManage: boolean;
  }

  let { product, canManage }: Props = $props();

  const revisions = $derived(
    (product.boards || []).flatMap((b) => b.revisions || [])
  );
</script>

<ProductStages
  productId={product.id}
  productName={product.name}
  {revisions}
  fwRepoSlug={product.fwRepoSlug ?? ''}
/>
