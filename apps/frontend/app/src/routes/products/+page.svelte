<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Plus, Trash2, GitBranch, ExternalLink, Search } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import { PageHeader, ErrorAlert, EmptyState, LoadingState, ConfirmDeleteDialog } from '$lib/components/ui';
  import FilterBar from '$lib/components/ui/filter-bar.svelte';
  import FilterSelect from '$lib/components/ui/filter-select.svelte';
  import Pagination from '$lib/components/ui/pagination.svelte';
  import ProductCreationWizard from '$lib/components/products/product-creation-wizard.svelte';
  import type { Product } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('products:manage'));

  let products = $state<Product[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Filters
  let searchQuery = $state('');
  let statusFilter = $state<'all' | 'active' | 'inactive'>('all');

  // Pagination
  let currentPage = $state(1);
  const pageSize = 20;

  // Delete confirmation
  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  // Wizard state
  let showWizard = $state(false);

  // Stage config
  const stageLabels = ['SM', 'DR', 'IN', 'RG', 'FU'];
  const stageNames = ['Smoke', 'Driver', 'Integration', 'Regression', 'FUOTA'];
  const stageColors: Record<number, string> = {
    1: 'bg-blue-400', 2: 'bg-cyan-400', 3: 'bg-amber-400', 4: 'bg-purple-400', 5: 'bg-red-400',
  };

  // Filtered products
  const filteredProducts = $derived.by(() => {
    let result = products;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter((p) => p.name.toLowerCase().includes(q));
    }
    if (statusFilter === 'active') {
      result = result.filter((p) => p.active);
    } else if (statusFilter === 'inactive') {
      result = result.filter((p) => !p.active);
    }
    return result;
  });

  const totalPages = $derived(Math.max(1, Math.ceil(filteredProducts.length / pageSize)));
  const paginatedProducts = $derived(
    filteredProducts.slice((currentPage - 1) * pageSize, currentPage * pageSize)
  );

  // Reset page when filters change
  $effect(() => {
    searchQuery;
    statusFilter;
    currentPage = 1;
  });

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
      fetchProducts();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete';
    }
  }
</script>

<svelte:head>
  <title>Products — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6 flex items-start justify-between">
    <PageHeader
      title="Products"
      description="Manage products, firmware stages, and builds."
    />
    {#if canManage && !showWizard}
      <button
        onclick={() => { showWizard = true; }}
        class="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
      >
        <Plus size={16} />
        New Product
      </button>
    {/if}
  </div>

  {#if loading}
    <LoadingState message="Loading products..." />
  {:else}
    <ErrorAlert message={error} />

    {#if showWizard && canManage}
      <div class="mb-4">
        <ProductCreationWizard
          onCreated={() => { showWizard = false; fetchProducts(); }}
          onCancel={() => { showWizard = false; }}
        />
      </div>
    {/if}

    <!-- Filter bar -->
    <FilterBar>
      <div class="relative flex-1">
        <Search size={14} class="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary" />
        <input
          type="text"
          placeholder="Search products..."
          bind:value={searchQuery}
          class="w-full rounded-lg border border-border bg-surface-0 py-2 pl-9 pr-3 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
        />
      </div>
      <FilterSelect
        label="Status"
        value={statusFilter}
        onchange={(v) => { statusFilter = v as 'all' | 'active' | 'inactive'; }}
        options={[
          { value: 'all', label: 'All Status' },
          { value: 'active', label: 'Active' },
          { value: 'inactive', label: 'Inactive' },
        ]}
      />
    </FilterBar>

    <!-- Product list -->
    {#if filteredProducts.length === 0}
      <EmptyState message={searchQuery || statusFilter !== 'all' ? 'No products match your filters' : 'No products yet'} />
    {:else}
      <div class="mt-4 rounded-xl border border-border bg-surface-1 overflow-hidden">
        {#each paginatedProducts as p (p.id)}
          {@const revisions = (p as any).revisions || []}
          {@const stages = (p as any).stageConfigs || []}
          <div
            role="button"
            tabindex="0"
            onclick={() => goto(`/products/${p.id}`)}
            onkeydown={(e) => e.key === 'Enter' && goto(`/products/${p.id}`)}
            class="group flex items-center gap-4 px-4 py-3 border-b border-border-subtle hover:bg-surface-2/50 cursor-pointer transition-colors last:border-b-0"
          >
            <!-- Left: Name + description -->
            <div class="min-w-0 flex-1">
              <div class="font-semibold text-sm text-text-primary">{p.name}</div>
              {#if p.description}
                <p class="text-2xs text-text-tertiary truncate">{p.description}</p>
              {/if}
            </div>

            <!-- Center: Revisions -->
            {#if revisions.length > 0}
              <div class="hidden sm:flex flex-wrap gap-1 shrink-0">
                {#each revisions as rev}
                  <span class="inline-flex items-center rounded bg-surface-2 px-1.5 py-0.5 font-mono text-2xs {rev.status === 'ACTIVE' ? 'text-text-primary' : 'text-text-tertiary line-through'}">
                    {rev.version.toUpperCase()}
                  </span>
                {/each}
              </div>
            {/if}

            <!-- Center: Repo links -->
            {#if p.fwRepoSlug || p.mfgFwRepoSlug}
              <div class="hidden md:flex gap-1.5 shrink-0">
                {#if p.fwRepoSlug}
                  <a
                    href="https://bitbucket.org/corekinect/{p.fwRepoSlug}"
                    target="_blank" rel="noopener noreferrer"
                    class="inline-flex items-center gap-1 rounded bg-surface-0 px-1.5 py-0.5 font-mono text-2xs text-text-secondary hover:text-accent transition-colors"
                    onclick={(e) => e.stopPropagation()}
                  >
                    <GitBranch size={10} /> {p.fwRepoSlug} <ExternalLink size={8} class="opacity-50" />
                  </a>
                {/if}
                {#if p.mfgFwRepoSlug}
                  <a
                    href="https://bitbucket.org/corekinect/{p.mfgFwRepoSlug}"
                    target="_blank" rel="noopener noreferrer"
                    class="inline-flex items-center gap-1 rounded bg-surface-0 px-1.5 py-0.5 font-mono text-2xs text-text-secondary hover:text-accent transition-colors"
                    onclick={(e) => e.stopPropagation()}
                  >
                    <GitBranch size={10} /> {p.mfgFwRepoSlug} <ExternalLink size={8} class="opacity-50" />
                  </a>
                {/if}
              </div>
            {/if}

            <!-- Right: Stage pills -->
            <div class="hidden sm:flex gap-0.5 shrink-0">
              {#each [1, 2, 3, 4, 5] as stageNum}
                {@const cfg = stages.find((s: any) => s.stage === stageNum)}
                <span
                  class="w-5 h-5 flex items-center justify-center rounded text-[9px] font-bold
                    {cfg?.enabled ? stageColors[stageNum] + ' text-white' : 'bg-surface-2 text-text-tertiary'}"
                  title="{stageNames[stageNum - 1]}: {cfg?.enabled ? 'Enabled' : 'Off'}"
                >
                  {stageLabels[stageNum - 1]}
                </span>
              {/each}
            </div>

            <!-- Right: Status badge -->
            <span class="shrink-0 rounded-full px-1.5 py-0.5 text-2xs font-medium {p.active ? 'bg-success-muted text-success' : 'bg-surface-2 text-text-tertiary'}">
              {p.active ? 'Active' : 'Inactive'}
            </span>

            <!-- Right: Delete button (hover reveal) -->
            {#if canManage}
              <button
                onclick={(e) => { e.stopPropagation(); promptDelete(p.id); }}
                class="shrink-0 rounded-lg p-1.5 text-text-tertiary opacity-0 transition-opacity group-hover:opacity-100 hover:text-error"
                title="Delete" aria-label="Delete {p.name}"
              >
                <Trash2 size={14} />
              </button>
            {/if}
          </div>
        {/each}
      </div>

      {#if totalPages > 1}
        <div class="mt-4">
          <Pagination
            page={currentPage}
            {totalPages}
            onPageChange={(page) => { currentPage = page; }}
          />
        </div>
      {/if}
    {/if}

    <ConfirmDeleteDialog
      open={!!deleteTarget}
      entityType="product"
      entityName={deleteTarget?.name || ''}
      onConfirm={() => { handleDelete(deleteTarget!.id); deleteTarget = null; }}
      onCancel={() => (deleteTarget = null)}
    />
  {/if}
</div>
