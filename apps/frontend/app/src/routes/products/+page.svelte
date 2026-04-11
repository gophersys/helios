<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Plus, Trash2, GitBranch, ExternalLink } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import { PageHeader, ErrorAlert, EmptyState, LoadingState, ConfirmDeleteDialog } from '$lib/components/ui';
  import FilterBar from '$lib/components/ui/filter-bar.svelte';
  import FilterSelect from '$lib/components/ui/filter-select.svelte';
  import FilterSearch from '$lib/components/ui/filter-search.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import Pagination from '$lib/components/ui/pagination.svelte';
  import ProductCreationWizard from '$lib/components/products/product-creation-wizard.svelte';
  import type { Product } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import { STAGE_NAMES } from '$lib/types/stages';

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

  function getStageConfigs(p: Product) {
    return ((p as any).stageConfigs || []) as Array<{ stage: number; enabled: boolean; type?: string }>;
  }

  function getRevisions(p: Product) {
    return ((p as any).revisions || []) as Array<{ version: string; status: string }>;
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
        class="btn btn-md btn-primary flex items-center gap-2"
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
      <div class="mb-6">
        <ProductCreationWizard
          onCreated={() => { showWizard = false; fetchProducts(); }}
          onCancel={() => { showWizard = false; }}
        />
      </div>
    {/if}

    <!-- Filter bar -->
    <FilterBar class="mb-4">
      {#snippet filters()}
        <FilterSearch bind:value={searchQuery} placeholder="Search products..." class="w-56" />
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
      {/snippet}
      <span class="ml-auto text-2xs text-text-tertiary shrink-0">
        {filteredProducts.length} product{filteredProducts.length !== 1 ? 's' : ''}
      </span>
    </FilterBar>

    <!-- Product list -->
    {#if filteredProducts.length === 0}
      <EmptyState message={searchQuery || statusFilter !== 'all' ? 'No products match your filters.' : 'No products yet.'} />
    {:else}
      <div class="space-y-3">
        {#each paginatedProducts as p (p.id)}
          {@const revisions = getRevisions(p)}
          {@const stages = getStageConfigs(p)}
          {@const valStages = stages.filter(s => !s.type || s.type === 'VALIDATION')}
          {@const enabledCount = valStages.filter(s => s.enabled).length}

          <div
            role="button"
            tabindex="0"
            onclick={() => goto(`/products/${p.id}`)}
            onkeydown={(e) => e.key === 'Enter' && goto(`/products/${p.id}`)}
            class="group card card-interactive card-md"
          >
            <!-- Row 1: Name + Status -->
            <div class="flex items-start justify-between gap-4">
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-3">
                  <h3 class="text-sm font-semibold text-text-primary">{p.name}</h3>
                  <StatusBadge status={p.active ? 'ACTIVE' : 'INACTIVE'} />
                </div>
                {#if p.description}
                  <p class="text-xs text-text-secondary mt-0.5">{p.description}</p>
                {/if}
              </div>

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

            <!-- Row 2: Metadata -->
            <div class="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2">
              <!-- Hardware revisions -->
              {#if revisions.length > 0}
                <div class="flex items-center gap-2">
                  <span class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Hardware</span>
                  <div class="flex gap-1">
                    {#each revisions as rev}
                      <span class="badge {rev.status === 'ACTIVE' ? 'badge-accent' : 'badge-neutral'} font-mono">
                        {rev.version.toUpperCase()}
                      </span>
                    {/each}
                  </div>
                </div>
              {/if}

              <!-- Repositories -->
              {#if p.fwRepoSlug || p.mfgFwRepoSlug}
                <div class="flex items-center gap-2">
                  <span class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Repos</span>
                  <div class="flex gap-1.5">
                    {#if p.fwRepoSlug}
                      <a
                        href="https://bitbucket.org/corekinect/{p.fwRepoSlug}"
                        target="_blank" rel="noopener noreferrer"
                        class="inline-flex items-center gap-1 rounded-md bg-surface-0 px-2 py-0.5 font-mono text-2xs text-text-secondary hover:text-accent transition-colors"
                        onclick={(e) => e.stopPropagation()}
                      >
                        <GitBranch size={10} />
                        {p.fwRepoSlug}
                        <ExternalLink size={8} class="opacity-40" />
                      </a>
                    {/if}
                    {#if p.mfgFwRepoSlug}
                      <a
                        href="https://bitbucket.org/corekinect/{p.mfgFwRepoSlug}"
                        target="_blank" rel="noopener noreferrer"
                        class="inline-flex items-center gap-1 rounded-md bg-surface-0 px-2 py-0.5 font-mono text-2xs text-text-secondary hover:text-accent transition-colors"
                        onclick={(e) => e.stopPropagation()}
                      >
                        <GitBranch size={10} />
                        {p.mfgFwRepoSlug}
                        <ExternalLink size={8} class="opacity-40" />
                      </a>
                    {/if}
                  </div>
                </div>
              {/if}

              <!-- Validation stages -->
              {#if valStages.length > 0}
                <div class="flex items-center gap-2">
                  <span class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Stages</span>
                  <div class="flex gap-0.5">
                    {#each [1, 2, 3, 4, 5] as stageNum}
                      {@const cfg = valStages.find(s => s.stage === stageNum)}
                      <span
                        class="inline-flex items-center justify-center w-6 h-5 rounded text-[10px] font-semibold
                          {cfg?.enabled ? 'bg-accent-muted text-accent' : 'bg-surface-2 text-text-tertiary'}"
                        title="{STAGE_NAMES['VALIDATION']?.[stageNum] || `Stage ${stageNum}`}: {cfg?.enabled ? 'Enabled' : 'Off'}"
                      >
                        {stageNum}
                      </span>
                    {/each}
                  </div>
                  <span class="text-2xs text-text-tertiary">{enabledCount}/{valStages.length}</span>
                </div>
              {/if}
            </div>
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
