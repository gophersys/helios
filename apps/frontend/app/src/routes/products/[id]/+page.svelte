<script lang="ts">
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch } from '$lib/api';
  import ProductDetail from '$lib/components/products/product-detail.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import type { Product } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('products:manage'));
  const productId = $derived(page.params.id);

  let product = $state<Product | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  async function fetchProduct() {
    try {
      const res = await apiFetch<ApiResponse<Product>>(`/v2/products/${productId}`);
      product = res.data;
      error = null;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load product';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('products:view')) {
      goto('/');
      return;
    }
    fetchProduct();
  });
</script>

<svelte:head>
  <title>{product?.name ?? 'Product'} — Concord</title>
</svelte:head>

{#if loading}
  <LoadingState message="Loading product..." />
{:else if error}
  <div class="animate-fade-in">
    <ErrorAlert message={error} />
  </div>
{:else if product}
  <ProductDetail
    {product}
    {canManage}
    onBack={() => goto('/products')}
    onRefresh={fetchProduct}
  />
{/if}
