<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Plus, Check } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import { PageHeader, ErrorAlert, EmptyState, LoadingState, ConfirmDeleteDialog, FormCard } from '$lib/components/ui';
  import ProductCard from '$lib/components/products/product-card.svelte';
  import ProductDetail from '$lib/components/products/product-detail.svelte';
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

  // Form state
  let showForm = $state(false);
  let editingId = $state<string | null>(null);
  let formName = $state('');
  let formDescription = $state('');
  let formActive = $state(true);
  let submitting = $state(false);

  // Delete confirmation
  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  // Detail state
  let selectedProduct = $state<Product | null>(null);

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

  function resetForm() {
    formName = '';
    formDescription = '';
    formActive = true;
    editingId = null;
    showForm = false;
  }

  function startEdit(p: Product) {
    formName = p.name;
    formDescription = p.description || '';
    formActive = p.active;
    editingId = p.id;
    showForm = true;
    selectedProduct = null;
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    error = null;
    submitting = true;

    const body = {
      name: formName,
      description: formDescription || null,
      active: formActive,
    };

    try {
      if (editingId) {
        await api.put(`/v2/products/${editingId}`, body);
      } else {
        await api.post('/v2/products', body);
      }
      resetForm();
      fetchProducts();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to save product';
    } finally {
      submitting = false;
    }
  }

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

      {#if showForm && canManage}
        <FormCard title={editingId ? 'Edit product' : 'New product'} onClose={resetForm}>
          <form onsubmit={handleSubmit}>
            <div class="mb-3 grid grid-cols-2 gap-3">
              <label>
                <span class="mb-1 block text-2xs font-medium text-text-tertiary">Name</span>
                <input
                  type="text"
                  required
                  bind:value={formName}
                  placeholder="e.g. Sigma5"
                  class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
              </label>
              <label>
                <span class="mb-1 block text-2xs font-medium text-text-tertiary">Description</span>
                <input
                  type="text"
                  bind:value={formDescription}
                  placeholder="Optional description"
                  class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
              </label>
            </div>
            <div class="mb-4">
              <label class="flex items-center gap-2 text-sm text-text-primary">
                <input
                  type="checkbox"
                  bind:checked={formActive}
                  class="rounded border-border"
                />
                Active
              </label>
            </div>
            <div class="flex gap-2">
              <button
                type="submit"
                disabled={submitting}
                class="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
              >
                <Check size={16} />
                {submitting ? 'Saving...' : editingId ? 'Save changes' : 'Create'}
              </button>
              <button
                type="button"
                onclick={resetForm}
                class="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2"
              >
                Cancel
              </button>
            </div>
          </form>
        </FormCard>
      {/if}

      <!-- Add button -->
      {#if canManage && !showForm}
        <div class="mb-4 flex justify-end">
          <button
            onclick={() => { resetForm(); showForm = true; }}
            class="flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover"
          >
            <Plus size={16} />
            New product
          </button>
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
              onEdit={startEdit}
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
