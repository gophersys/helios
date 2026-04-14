<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Plus, Trash2, Archive, GitBranch, CircuitBoard } from 'lucide-svelte';
  import LinkChip from '$lib/components/ui/link-chip.svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import { PageHeader, ErrorAlert, EmptyState, LoadingState } from '$lib/components/ui';
  import FilterBar from '$lib/components/ui/filter-bar.svelte';
  import FilterSelect from '$lib/components/ui/filter-select.svelte';
  import FilterSearch from '$lib/components/ui/filter-search.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import Pagination from '$lib/components/ui/pagination.svelte';
  import SelectionBar from '$lib/components/ui/selection-bar.svelte';
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
  let statusFilter = $state<'all' | 'ACTIVE' | 'ARCHIVED'>('all');

  // Pagination
  let currentPage = $state(1);
  const pageSize = 20;

  // Selection + batch
  let selectedIds = $state<Set<string>>(new Set());
  let batchLoading = $state(false);
  let confirmBatchDelete = $state(false);

  // Wizard state
  let showWizard = $state(false);

  // Filtered products
  const filteredProducts = $derived.by(() => {
    let result = products;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter((p) => p.name.toLowerCase().includes(q));
    }
    if (statusFilter !== 'all') {
      result = result.filter((p) => p.status === statusFilter);
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

  // Selection helpers
  function toggleItem(id: string) {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    selectedIds = next;
  }
  function selectAll() { selectedIds = new Set(paginatedProducts.map(p => p.id)); }
  function clearSelection() { selectedIds = new Set(); confirmBatchDelete = false; }

  async function batchAction(action: 'archive' | 'delete') {
    if (selectedIds.size === 0) return;
    if (action === 'delete' && !confirmBatchDelete) { confirmBatchDelete = true; return; }
    confirmBatchDelete = false;
    batchLoading = true;
    error = null;
    try {
      const res = await api.post<ApiResponse<any>>('/v2/products/batch', {
        action, ids: [...selectedIds],
      });
      const result = res.data;
      if (result.failed?.length > 0) {
        error = `${result.succeeded.length} ${action}d, ${result.failed.length} failed: ${result.failed[0].reason}`;
      }
      selectedIds = new Set();
      fetchProducts();
    } catch (err: any) {
      error = err instanceof Error ? err.message : `Batch ${action} failed`;
    } finally { batchLoading = false; }
  }

  function getRevisions(p: Product) {
    return ((p as any).revisions || []) as Array<{ version: string; status: string }>;
  }

  onMount(() => {
    if (!auth.hasPermission('products:view')) {
      goto('/');
      return;
    }
    fetchProducts();
  });
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
          onchange={(v) => { statusFilter = v as 'all' | 'ACTIVE' | 'ARCHIVED'; }}
          options={[
            { value: 'all', label: 'All Status' },
            { value: 'ACTIVE', label: 'Active' },
            { value: 'ARCHIVED', label: 'Archived' },
          ]}
        />
      {/snippet}
      <span class="ml-auto text-2xs text-text-tertiary shrink-0">
        {filteredProducts.length} product{filteredProducts.length !== 1 ? 's' : ''}
      </span>
    </FilterBar>

    <!-- Selection bar -->
    {#if canManage}
      <SelectionBar
        selectedCount={selectedIds.size}
        totalCount={paginatedProducts.length}
        onSelectAll={selectAll}
        onClearSelection={clearSelection}
        actions={[
          { label: 'Archive', icon: Archive, variant: 'ghost' as const, loading: batchLoading, onclick: () => batchAction('archive') },
          { label: 'Delete', icon: Trash2, variant: 'danger' as const, loading: batchLoading, onclick: () => batchAction('delete') },
        ]}
      />
    {/if}

    <!-- Inline delete confirmation -->
    {#if confirmBatchDelete}
      <div class="mb-3 flex items-center gap-3 rounded-lg border border-error/30 bg-error-muted px-4 py-2.5">
        <span class="text-sm text-text-primary">
          Permanently delete {selectedIds.size} product{selectedIds.size !== 1 ? 's' : ''}? This cannot be undone.
        </span>
        <div class="ml-auto flex items-center gap-2">
          <button onclick={() => { confirmBatchDelete = false; }} class="btn btn-sm btn-ghost">Cancel</button>
          <button onclick={() => batchAction('delete')} class="btn btn-sm btn-danger">Confirm Delete</button>
        </div>
      </div>
    {/if}

    <!-- Product table -->
    {#if filteredProducts.length === 0}
      <EmptyState message={searchQuery || statusFilter !== 'all' ? 'No products match your filters.' : 'No products yet.'} />
    {:else}
      <div class="table-wrapper">
        <table class="table">
          <thead>
            <tr>
              {#if canManage}
                <th class="table-header w-10">
                  <input
                    type="checkbox"
                    checked={selectedIds.size > 0 && selectedIds.size === paginatedProducts.length}
                    indeterminate={selectedIds.size > 0 && selectedIds.size < paginatedProducts.length}
                    onchange={() => selectedIds.size === paginatedProducts.length ? clearSelection() : selectAll()}
                    class="h-4 w-4 rounded border-border text-accent focus:ring-accent"
                  />
                </th>
              {/if}
              <th class="table-header">Name</th>
              <th class="table-header">Status</th>
              <th class="table-header">Boards</th>
              <th class="table-header">Revisions</th>
            </tr>
          </thead>
          <tbody>
            {#each paginatedProducts as p (p.id)}
              {@const revisions = getRevisions(p)}
              <tr
                class="table-row cursor-pointer"
                class:opacity-60={p.status === 'ARCHIVED'}
                onclick={() => goto(`/products/${p.id}`)}
              >
                {#if canManage}
                  <td class="table-cell w-10" onclick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(p.id)}
                      onchange={() => toggleItem(p.id)}
                      class="h-4 w-4 rounded border-border text-accent focus:ring-accent"
                    />
                  </td>
                {/if}
                <td class="table-cell">
                  <span class="font-medium text-text-primary">{p.name}</span>
                  {#if p.description}
                    <p class="text-2xs text-text-tertiary mt-0.5 truncate max-w-xs">{p.description}</p>
                  {/if}
                  <div class="flex flex-wrap gap-1 mt-1">
                    {#if p.fwRepoSlug}
                      <LinkChip icon={GitBranch} href="https://bitbucket.org/corekinect/{p.fwRepoSlug}" external>{p.fwRepoSlug}</LinkChip>
                    {/if}
                    <LinkChip icon={CircuitBoard}>{revisions.length} revision{revisions.length !== 1 ? 's' : ''}</LinkChip>
                  </div>
                </td>
                <td class="table-cell">
                  <StatusBadge status={p.status} />
                </td>
                <td class="table-cell">
                  <span class="text-text-secondary">{(p as any).boards?.length ?? 0}</span>
                </td>
                <td class="table-cell">
                  {#if revisions.length > 0}
                    <div class="flex gap-1 flex-wrap">
                      {#each revisions as rev}
                        <span class="badge {rev.status === 'ACTIVE' ? 'badge-accent' : 'badge-neutral'} font-mono">
                          {rev.version.toUpperCase()}
                        </span>
                      {/each}
                    </div>
                  {:else}
                    <span class="text-text-tertiary">—</span>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
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
  {/if}
</div>
