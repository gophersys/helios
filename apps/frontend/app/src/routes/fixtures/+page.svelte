<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { Plus, Trash2, Wrench, Search, Loader2, Wifi, WifiOff, AlertTriangle, Lock, Settings as SettingsIcon, List, LayoutGrid, Box } from 'lucide-svelte';
  import LinkChip from '$lib/components/ui/link-chip.svelte';
  import FixtureGridCard from '$lib/components/fixtures/fixture-grid-card.svelte';
  import FixtureCreateWizard from '$lib/components/fixtures/fixture-create-wizard.svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import { PageHeader, ErrorAlert, LoadingState, EmptyState } from '$lib/components/ui';
  import FilterBar from '$lib/components/ui/filter-bar.svelte';
  import FilterSelect from '$lib/components/ui/filter-select.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import FilterSearch from '$lib/components/ui/filter-search.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import Pagination from '$lib/components/ui/pagination.svelte';
  import SelectionBar from '$lib/components/ui/selection-bar.svelte';
  import type { Fixture, Product, Board, FixtureDesign } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import { actionable } from '$lib/actions/actionable';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('fixtures:manage'));

  type PaginationData = { page: number; limit: number; total: number; pages: number };

  // Data
  let fixtures = $state<Fixture[]>([]);
  let products = $state<Product[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Pagination
  let currentPage = $state(1);
  let pagination = $state<PaginationData>({ page: 1, limit: 25, total: 0, pages: 0 });

  // Filters
  let filterProduct = $state('');
  let filterType = $state('');
  let searchQuery = $state('');
  let searchTimeout: ReturnType<typeof setTimeout> | undefined;
  let debouncedSearch = $state('');

  // View mode
  let viewMode = $state<'table' | 'grid'>('table');

  $effect(() => {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('concord-fixtures-view', viewMode);
    }
  });

  // Selection + batch
  let selectedIds = $state<Set<string>>(new Set());
  let batchLoading = $state(false);
  let confirmBatchDelete = $state(false);

  function toggleItem(id: string) {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    selectedIds = next;
  }
  function selectAll() { selectedIds = new Set(fixtures.map(f => f.id)); }
  function clearSelection() { selectedIds = new Set(); confirmBatchDelete = false; }

  async function batchAction(action: 'delete') {
    if (selectedIds.size === 0) return;
    if (action === 'delete' && !confirmBatchDelete) { confirmBatchDelete = true; return; }
    confirmBatchDelete = false;
    batchLoading = true;
    error = null;
    try {
      const res = await api.post<ApiResponse<any>>('/v2/fixtures/batch', {
        action, ids: [...selectedIds],
      });
      const result = res.data;
      if (result.failed?.length > 0) {
        error = `${result.succeeded.length} deleted, ${result.failed.length} failed: ${result.failed[0].reason}`;
      }
      selectedIds = new Set();
      fetchFixtures();
    } catch (err: any) {
      error = err instanceof Error ? err.message : 'Batch delete failed';
    } finally { batchLoading = false; }
  }

  // Create form
  let showCreate = $state(false);
  let boards = $state<Board[]>([]);
  let availableDesigns = $state<FixtureDesign[]>([]);
  let formName = $state('');
  let formProductId = $state('');
  let formBoardRevisionId = $state('');
  let formDesignId = $state('');
  let formType = $state('VALIDATION');
  let formDescription = $state('');
  let submitting = $state(false);

  const boardRevisions = $derived.by(() => {
    const revs: { id: string; label: string }[] = [];
    for (const board of boards) {
      for (const rev of board.revisions ?? []) {
        revs.push({ id: rev.id, label: `${rev.version} (${rev.ckBoardsName || board.name})` });
      }
    }
    return revs;
  });

  const designOptions = $derived(
    availableDesigns.map(d => ({ value: d.id, label: `${d.name} (${d.revision})` }))
  );

  $effect(() => {
    clearTimeout(searchTimeout);
    const q = searchQuery;
    searchTimeout = setTimeout(() => { debouncedSearch = q; }, 300);
  });

  $effect(() => {
    filterProduct;
    filterType;
    debouncedSearch;
    currentPage = 1;
  });

  $effect(() => {
    const _page = currentPage;
    const _product = filterProduct;
    const _type = filterType;
    const _search = debouncedSearch;
    fetchFixtures();
  });

  async function fetchFixtures() {
    try {
      const params = new URLSearchParams();
      params.set('page', String(currentPage));
      params.set('limit', '25');
      if (filterProduct) params.set('productId', filterProduct);
      if (filterType) params.set('type', filterType);
      if (debouncedSearch) params.set('search', debouncedSearch);

      const res = await apiFetch<{ data: Fixture[]; pagination: PaginationData }>(
        '/v2/fixtures?' + params.toString()
      );
      fixtures = res.data;
      pagination = res.pagination;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load fixtures';
    } finally {
      loading = false;
    }
  }

  async function fetchProducts() {
    try {
      const res = await apiFetch<ApiResponse<{ data: Product[] }>>('/v2/products');
      const payload = res.data;
      products = Array.isArray(payload) ? payload : (payload as any)?.data || [];
    } catch { /* non-critical */ }
  }

  async function fetchBoardsForProduct(pid: string) {
    if (!pid) { boards = []; return; }
    try {
      const res = await apiFetch<ApiResponse<Product>>(`/v2/products/${pid}`);
      boards = res.data.boards ?? [];
    } catch { boards = []; }
  }

  async function fetchDesignsForRevision(revId: string) {
    if (!revId) { availableDesigns = []; return; }
    try {
      const res = await apiFetch<ApiResponse<{ data: FixtureDesign[] }>>(`/v2/fixtures/designs?boardRevisionId=${revId}`);
      const payload = res.data;
      availableDesigns = Array.isArray(payload) ? payload : (payload as any)?.data || [];
    } catch { availableDesigns = []; }
  }

  $effect(() => { if (formProductId) fetchBoardsForProduct(formProductId); else boards = []; });
  $effect(() => { if (formBoardRevisionId) fetchDesignsForRevision(formBoardRevisionId); else { availableDesigns = []; formDesignId = ''; } });

  async function handleCreate(e: Event) {
    e.preventDefault();
    if (!formDesignId) { error = 'Fixture design is required'; return; }
    submitting = true;
    error = null;
    try {
      await api.post('/v2/fixtures', {
        name: formName,
        productId: formProductId,
        boardRevisionId: formBoardRevisionId || null,
        designId: formDesignId,
        type: formType,
        description: formDescription || null,
      });
      showCreate = false;
      formName = ''; formProductId = ''; formBoardRevisionId = ''; formDesignId = ''; formDescription = '';
      await fetchFixtures();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to create fixture';
    } finally {
      submitting = false;
    }
  }

  function slotSummary(f: Fixture): string {
    if (f.slots) {
      const assigned = f.slots.filter(s => s.nodeId).length;
      return `${assigned}/${f.slots.length}`;
    }
    if (f.assignedCount !== undefined && f.slotCount !== undefined) {
      return `${f.assignedCount}/${f.slotCount}`;
    }
    return `${f.slotCount ?? 0}`;
  }

  function healthIcon(f: Fixture) {
    const slots = f.slots || [];
    if (slots.length === 0 && !f.slotCount) return { icon: WifiOff, color: 'text-text-tertiary' };
    if (slots.length === 0) return { icon: WifiOff, color: 'text-text-tertiary' };
    const assigned = slots.filter(s => s.nodeId);
    if (assigned.length === 0) return { icon: WifiOff, color: 'text-text-tertiary' };
    const online = assigned.filter(s => s.node?.status === 'ONLINE').length;
    if (online === assigned.length) return { icon: Wifi, color: 'text-success' };
    if (online > 0) return { icon: AlertTriangle, color: 'text-warning' };
    return { icon: WifiOff, color: 'text-error' };
  }

  onMount(() => {
    if (!auth.hasPermission('fixtures:view') && !auth.hasPermission('manufacturing:view')) {
      goto('/');
      return;
    }

    if (typeof localStorage !== 'undefined') {
      const stored = localStorage.getItem('concord-fixtures-view');
      if (stored === 'grid') viewMode = 'grid';
    }

    fetchProducts();

    // Redirect to detail page if ?selected=<id> is in the URL (e.g. from dashboard)
    const selectedId = $page.url.searchParams.get('selected');
    if (selectedId) {
      goto(`/fixtures/${selectedId}`);
      return;
    }
  });
</script>

<svelte:head>
  <title>Fixtures — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6 flex items-start justify-between">
    <PageHeader title="Fixtures" description="Physical test stations and MTIB assignments." />
    {#if canManage}
      <button use:actionable={{ id: 'create-fixture', label: 'Create fixture' }} onclick={() => showCreate = true} class="btn btn-sm btn-primary">
        <Plus size={16} /> New Fixture
      </button>
    {/if}
  </div>

  <ErrorAlert message={error} />

  <!-- Create form -->
  <FixtureCreateWizard
    open={showCreate}
    onClose={() => showCreate = false}
    onCreated={() => { showCreate = false; fetchFixtures(); }}
  />

  <!-- Filters -->
  <FilterBar class="mb-4">
    {#snippet filters()}
      <FilterSelect label="Product" value={filterProduct} onchange={(v) => { filterProduct = v; }} options={products.map(p => ({ value: p.id, label: p.name }))} />
      <FilterSelect label="Type" value={filterType} onchange={(v) => { filterType = v; }} options={[{ value: 'VALIDATION', label: 'Validation' }, { value: 'MANUFACTURING', label: 'Manufacturing' }]} />
      <FilterSearch bind:value={searchQuery} placeholder="Search fixtures..." class="w-56" />
    {/snippet}
    <span class="ml-auto text-2xs text-text-tertiary shrink-0">
      {pagination.total} fixture{pagination.total !== 1 ? 's' : ''}
    </span>
    <div class="flex items-center rounded-md bg-surface-2 p-0.5">
      <button
        onclick={() => viewMode = 'table'}
        class="rounded px-1.5 py-1 transition-colors {viewMode === 'table' ? 'bg-surface-1 text-text-primary shadow-xs' : 'text-text-tertiary hover:text-text-secondary'}"
        title="Table view"
      >
        <List size={14} />
      </button>
      <button
        onclick={() => viewMode = 'grid'}
        class="rounded px-1.5 py-1 transition-colors {viewMode === 'grid' ? 'bg-surface-1 text-text-primary shadow-xs' : 'text-text-tertiary hover:text-text-secondary'}"
        title="Grid view"
      >
        <LayoutGrid size={14} />
      </button>
    </div>
  </FilterBar>

  <!-- Selection bar -->
  {#if canManage}
    <SelectionBar
      selectedCount={selectedIds.size}
      totalCount={fixtures.length}
      onSelectAll={selectAll}
      onClearSelection={clearSelection}
      actions={[
        { label: 'Delete', icon: Trash2, variant: 'danger' as const, loading: batchLoading, onclick: () => batchAction('delete') },
      ]}
    />
  {/if}

  <!-- Inline delete confirmation -->
  {#if confirmBatchDelete}
    <div class="mb-3 flex items-center gap-3 rounded-lg border border-error/30 bg-error-muted px-4 py-2.5">
      <span class="text-sm text-text-primary">
        Permanently delete {selectedIds.size} fixture{selectedIds.size !== 1 ? 's' : ''}? This cannot be undone.
      </span>
      <div class="ml-auto flex items-center gap-2">
        <button onclick={() => { confirmBatchDelete = false; }} class="btn btn-sm btn-ghost">Cancel</button>
        <button onclick={() => batchAction('delete')} class="btn btn-sm btn-danger">Confirm Delete</button>
      </div>
    </div>
  {/if}

  <!-- Fixture list -->
  {#if loading}
    <LoadingState message="Loading fixtures..." />
  {:else if fixtures.length === 0}
    <EmptyState
      message={filterProduct || filterType || debouncedSearch ? 'No fixtures match your filters' : 'No fixtures registered'}
      icon={Wrench}
    />
  {:else if viewMode === 'table'}
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr>
            {#if canManage}
              <th class="table-header w-10">
                <input
                  type="checkbox"
                  checked={selectedIds.size > 0 && selectedIds.size === fixtures.length}
                  indeterminate={selectedIds.size > 0 && selectedIds.size < fixtures.length}
                  onchange={() => selectedIds.size === fixtures.length ? clearSelection() : selectAll()}
                  class="h-4 w-4 rounded border-border text-accent focus:ring-accent"
                />
              </th>
            {/if}
            <th class="table-header">Name</th>
            <th class="table-header">Product</th>
            <th class="table-header">Type</th>
            <th class="table-header">Design</th>
            <th class="table-header">Slots</th>
            <th class="table-header">Status</th>
            <th class="table-header">Health</th>
          </tr>
        </thead>
        <tbody>
          {#each fixtures as fixture}
            {@const health = healthIcon(fixture)}
            {@const HealthIcon = health.icon}
            <tr
              class="table-row cursor-pointer"
              onclick={() => goto(`/fixtures/${fixture.id}`)}
            >
              {#if canManage}
                <td class="table-cell w-10" onclick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={selectedIds.has(fixture.id)}
                    onchange={() => toggleItem(fixture.id)}
                    class="h-4 w-4 rounded border-border text-accent focus:ring-accent"
                  />
                </td>
              {/if}
              <td class="table-cell">
                <span class="font-medium text-text-primary">{fixture.name}</span>
                <div class="flex flex-wrap gap-1 mt-1">
                  {#if fixture.productName}
                    <LinkChip icon={Box} href="/products/{fixture.productId}">{fixture.productName}</LinkChip>
                  {/if}
                  {#if fixture.design?.name}
                    <LinkChip icon={Wrench}>{fixture.design.name}</LinkChip>
                  {/if}
                  <LinkChip icon={LayoutGrid}>{fixture.panelRows}&times;{fixture.panelCols}</LinkChip>
                </div>
              </td>
              <td class="table-cell text-text-secondary">{fixture.productName || '—'}</td>
              <td class="table-cell">
                <StatusBadge status={fixture.type} />
              </td>
              <td class="table-cell text-2xs text-text-tertiary">
                {fixture.design?.name || '—'}
              </td>
              <td class="table-cell">
                <span class="font-mono text-text-secondary">{slotSummary(fixture)}</span>
                <span class="text-2xs text-text-tertiary ml-1">assigned</span>
              </td>
              <td class="table-cell">
                {#if fixture.status === 'LOCKED'}
                  <div class="flex items-center gap-1">
                    <Lock size={12} class="text-warning" />
                    <span class="text-2xs text-warning">Locked</span>
                  </div>
                {:else}
                  <span class="text-2xs text-text-tertiary">Available</span>
                {/if}
              </td>
              <td class="table-cell">
                <HealthIcon size={14} class={health.color} />
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {#each fixtures as fixture (fixture.id)}
        <FixtureGridCard {fixture} onclick={() => goto(`/fixtures/${fixture.id}`)} />
      {/each}
    </div>
  {/if}

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

</div>
