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
  import { actionable } from '$lib/actions/actionable';
  import type { Product } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';


  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('products:manage'));

  type PaginationData = { page: number; limit: number; total: number; pages: number };

  let products = $state<Product[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Filters
  let searchQuery = $state('');
  let statusFilter = $state<'all' | 'ACTIVE' | 'ARCHIVED'>('all');

  // Pagination
  let currentPage = $state(1);
  let pagination = $state<PaginationData>({ page: 1, limit: 25, total: 0, pages: 0 });

  // Selection + batch
  let selectedIds = $state<Set<string>>(new Set());
  let batchLoading = $state(false);
  let confirmBatchDelete = $state(false);

  // Wizard state
  let showWizard = $state(false);

  let searchTimeout: ReturnType<typeof setTimeout> | undefined;
  let debouncedSearch = $state('');

  $effect(() => {
    clearTimeout(searchTimeout);
    const q = searchQuery;
    searchTimeout = setTimeout(() => { debouncedSearch = q; }, 300);
  });

  $effect(() => {
    statusFilter;
    debouncedSearch;
    currentPage = 1;
  });

  $effect(() => {
    const _page = currentPage;
    const _status = statusFilter;
    const _search = debouncedSearch;
    fetchProducts();
  });

  async function fetchProducts() {
    try {
      const params = new URLSearchParams();
      params.set('page', String(currentPage));
      params.set('limit', '25');
      if (statusFilter !== 'all') params.set('status', statusFilter);
      if (debouncedSearch) params.set('search', debouncedSearch);

      const res = await apiFetch<ApiResponse<{ data: Product[]; pagination: PaginationData }>>(
        '/v2/products?' + params.toString()
      );
      products = res.data.data;
      pagination = res.data.pagination;
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
  function selectAll() { selectedIds = new Set(products.map(p => p.id)); }
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
        use:actionable={{ id: 'new-product', label: 'New product' }}
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
        {pagination.total} product{pagination.total !== 1 ? 's' : ''}
      </span>
    </FilterBar>

    <!-- Selection bar -->
    {#if canManage}
      <SelectionBar
        selectedCount={selectedIds.size}
        totalCount={products.length}
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
    {#if products.length === 0}
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
                    checked={selectedIds.size > 0 && selectedIds.size === products.length}
                    indeterminate={selectedIds.size > 0 && selectedIds.size < products.length}
                    onchange={() => selectedIds.size === products.length ? clearSelection() : selectAll()}
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
            {#each products as p (p.id)}
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

      {#if pagination.pages > 1}
        <div class="mt-4 flex items-center justify-between">
          <span class="text-2xs text-text-tertiary">
            Page {pagination.page} of {pagination.pages} ({pagination.total} total)
          </span>
          <Pagination
            page={currentPage}
            totalPages={pagination.pages}
            onPageChange={(p) => { currentPage = p; }}
          />
        </div>
      {/if}
    {/if}
  {/if}
</div>
