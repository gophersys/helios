<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Plus } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import { PageHeader, ErrorAlert, EmptyState, LoadingState, ConfirmDeleteDialog } from '$lib/components/ui';
  import ProductCard from '$lib/components/products/product-card.svelte';
  import ProductDetail from '$lib/components/products/product-detail.svelte';
  import ProductCreationWizard from '$lib/components/products/product-creation-wizard.svelte';
  import ChipsetManagement from '$lib/components/products/chipset-management.svelte';
  import { useChipsets } from '$lib/hooks/use-chipsets.svelte';
  import type { Product } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  type TopTab = 'products' | 'chipsets';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('products:manage'));

  let topTab = $state<TopTab>('products');
  let products = $state<Product[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Delete confirmation
  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  // Detail state
  let selectedProduct = $state<Product | null>(null);

  // Wizard state
  let showWizard = $state(false);

  // Chipset state
  const chipsetState = useChipsets();

  async function fetchProducts() {
    try {
      const res = await apiFetch<ApiResponse<{ data: Product[] }>>('/v2/products');
      const payload = res.data;
      products = Array.isArray(payload) ? payload : (payload as { data: Product[] }).data || [];
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load products';
    } finally {
      loading = false;
    }
  }

  async function fetchDetail(id: string) {
    try {
      const res = await apiFetch<ApiResponse<Product>>(`/v2/products/${id}`);
      selectedProduct = res.data;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load product';
    }
  }

  onMount(() => {
    if (!auth.hasPermission('products:view')) {
      goto('/');
      return;
    }
    fetchProducts();
  });

  function promptDelete(id: string) {
    const target = products.find((p) => p.id === id);
    deleteTarget = { id, name: target?.name || '' };
  }

  async function handleDelete(id: string) {
    error = null;
    try {
      await api.delete(`/v2/products/${id}`);
      if (selectedProduct?.id === id) selectedProduct = null;
      fetchProducts();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete';
    }
  }

  const topTabs: { key: TopTab; label: string }[] = [
    { key: 'products', label: 'Products' },
    { key: 'chipsets', label: 'Chipsets' },
  ];
</script>

<svelte:head>
  <title>Products — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="Products"
      description="Manage products, firmware stages, and chipsets."
    />
  </div>

  {#if loading}
    <LoadingState message="Loading products..." />
  {:else if selectedProduct}
    <ProductDetail
      product={selectedProduct}
      chipsets={chipsetState.data}
      {canManage}
      onBack={() => (selectedProduct = null)}
      onRefresh={() => fetchDetail(selectedProduct!.id)}
    />
  {:else}
    <!-- Top-level tabs -->
    <div class="mb-5 flex gap-1 border-b border-border">
      {#each topTabs as tab}
        <button
          onclick={() => (topTab = tab.key)}
          class={[
            'px-4 py-2 text-sm font-medium transition-colors',
            topTab === tab.key
              ? 'border-b-2 border-accent text-accent'
              : 'text-text-tertiary hover:text-text-secondary'
          ].join(' ')}
        >
          {tab.label}
        </button>
      {/each}
    </div>

    {#if topTab === 'products'}
      <ErrorAlert message={error} />

      <!-- Add button -->
      {#if canManage && !showWizard}
        <div class="mb-4 flex justify-end">
          <button
            onclick={() => { showWizard = true; }}
            class="flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover"
          >
            <Plus size={16} />
            New Product
          </button>
        </div>
      {/if}

      {#if showWizard && canManage}
        <div class="mb-4">
          <ProductCreationWizard
            onCreated={() => { showWizard = false; fetchProducts(); }}
            onCancel={() => { showWizard = false; }}
          />
        </div>
      {/if}

      <!-- Grid -->
      {#if products.length === 0}
        <EmptyState message="No products yet" />
      {:else}
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {#each products as p (p.id)}
            <ProductCard
              product={p}
              {canManage}
              onDelete={promptDelete}
              onSelect={(prod) => fetchDetail(prod.id)}
            />
          {/each}
        </div>
      {/if}

      <ConfirmDeleteDialog
        open={!!deleteTarget}
        entityType="product"
        entityName={deleteTarget?.name || ''}
        onConfirm={() => { handleDelete(deleteTarget!.id); deleteTarget = null; }}
        onCancel={() => (deleteTarget = null)}
      />
    {/if}

    {#if topTab === 'chipsets'}
      <div class="card card-md">
        {#if chipsetState.loading}
          <LoadingState message="Loading chipsets..." />
        {:else if chipsetState.error}
          <ErrorAlert message={chipsetState.error} />
        {:else}
          <ChipsetManagement
            chipsets={chipsetState.data}
            {canManage}
            onRefresh={() => chipsetState.fetch()}
          />
        {/if}
      </div>
    {/if}
  {/if}
</div>
