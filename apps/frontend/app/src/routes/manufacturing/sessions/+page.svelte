<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { RefreshCw, Plus, Archive, Trash2, CheckCircle2, XCircle, Wrench, User, Package, Cpu } from 'lucide-svelte';
  import LinkChip from '$lib/components/ui/link-chip.svelte';
  import SessionCreateWizard from '$lib/components/manufacturing/session-create-wizard.svelte';
  import FilterBar from '$lib/components/ui/filter-bar.svelte';
  import FilterSearch from '$lib/components/ui/filter-search.svelte';
  import SelectionBar from '$lib/components/ui/selection-bar.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import {
    PageHeader,
    ErrorAlert,
    EmptyState,
    LoadingState,
  } from '$lib/components/ui';
  import FilterSelect from '$lib/components/ui/filter-select.svelte';
  import Pagination from '$lib/components/ui/pagination.svelte';
  import { formatTimeAgo, formatDuration, formatDateTime } from '$lib/utils/formatting';
  import type {
    ManufacturingSession,
    Product,
    Pagination as PaginationType,
  } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  const auth = getAuth();

  let sessions = $state<ManufacturingSession[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let pagination = $state<PaginationType>({ page: 1, limit: 25, total: 0, pages: 0 });
  let currentPage = $state(1);
  let statusFilter = $state('');
  let productFilter = $state('');
  let searchQuery = $state('');
  let refreshing = $state(false);
  let productOptions = $state<{ value: string; label: string }[]>([]);

  let refreshInterval: ReturnType<typeof setInterval> | null = null;
  let showCreateWizard = $state(false);
  const canRun = $derived(auth.hasPermission('manufacturing:run'));

  // Selection + batch
  let selectedIds = $state<Set<string>>(new Set());
  let batchLoading = $state(false);
  let confirmBatchDelete = $state(false);

  function toggleItem(id: string) {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    selectedIds = next;
  }
  function selectAll() { selectedIds = new Set(filteredSessions.map(s => s.id)); }
  function clearSelection() { selectedIds = new Set(); confirmBatchDelete = false; }

  async function batchAction(action: 'archive' | 'delete') {
    if (selectedIds.size === 0) return;
    if (action === 'delete' && !confirmBatchDelete) { confirmBatchDelete = true; return; }
    confirmBatchDelete = false;
    batchLoading = true;
    error = null;
    try {
      const res = await api.post<ApiResponse<any>>('/v2/manufacturing/sessions/batch', {
        action,
        sessionIds: [...selectedIds],
      });
      const result = res.data;
      if (result.failed?.length > 0) {
        error = `${result.succeeded.length} ${action}d, ${result.failed.length} failed: ${result.failed[0].reason}`;
      }
      selectedIds = new Set();
      fetchSessions();
    } catch (err: any) {
      error = err instanceof Error ? err.message : `Batch ${action} failed`;
    } finally {
      batchLoading = false;
    }
  }

  const filteredSessions = $derived.by(() => {
    let result = sessions;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (s) =>
          s.product?.name?.toLowerCase().includes(q) ||
          s.fixture?.name?.toLowerCase().includes(q) ||
          (s.operator?.name || '').toLowerCase().includes(q)
      );
    }
    if (productFilter) {
      result = result.filter(s => s.product?.name === productFilter);
    }
    return result;
  });

  function getRunCounts(session: ManufacturingSession) {
    const runs = session.runs || [];
    return {
      total: runs.length,
      passed: runs.reduce((sum, r) => sum + (r.passedCount || 0), 0),
      failed: runs.reduce((sum, r) => sum + (r.failedCount || 0), 0),
    };
  }

  function getDuration(session: ManufacturingSession): string | null {
    if (!session.startedAt) return null;
    const start = new Date(session.startedAt).getTime();
    const end = session.endedAt ? new Date(session.endedAt).getTime() : Date.now();
    return formatDuration(end - start);
  }

  async function fetchSessions() {
    error = null;
    try {
      const params = new URLSearchParams();
      params.set('page', String(currentPage));
      params.set('limit', '25');
      if (statusFilter) params.set('status', statusFilter);

      const res = await apiFetch<{ data: ManufacturingSession[]; pagination: PaginationType }>(
        '/v2/manufacturing/sessions?' + params.toString()
      );
      sessions = res.data;
      pagination = res.pagination;

      // Extract unique products for filter
      if (productOptions.length === 0 && sessions.length > 0) {
        const prods = new Set<string>();
        sessions.forEach(s => { if (s.product?.name) prods.add(s.product.name); });
        productOptions = Array.from(prods).sort().map(p => ({ value: p, label: p }));
      }
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load sessions';
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  function refresh() {
    refreshing = true;
    fetchSessions();
  }

  onMount(() => {
    if (!auth.hasPermission('manufacturing:view')) {
      goto('/');
      return;
    }
    fetchSessions();
    refreshInterval = setInterval(fetchSessions, 15000);
  });

  onDestroy(() => {
    if (refreshInterval) clearInterval(refreshInterval);
  });

  $effect(() => {
    const _p = currentPage;
    fetchSessions();
  });
  $effect(() => {
    const _s = statusFilter;
    currentPage = 1;
  });
</script>

<svelte:head>
  <title>Session History — Manufacturing — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6 flex items-start justify-between">
    <PageHeader
      title="Manufacturing Sessions"
      description="Complete history of manufacturing sessions."
    />
    <div class="flex items-center gap-2">
      <button onclick={refresh} disabled={refreshing} class="btn btn-ghost btn-sm btn-icon" title="Refresh">
        <RefreshCw size={16} class={refreshing ? 'animate-spin' : ''} />
      </button>
      {#if canRun}
        <button onclick={() => showCreateWizard = true} class="btn btn-sm btn-primary">
          <Plus size={16} /> New Session
        </button>
      {/if}
    </div>
  </div>

  <ErrorAlert message={error} />

  <!-- Filter bar -->
  <FilterBar class="mb-4">
    {#snippet filters()}
      <FilterSelect
        label="Product"
        value={productFilter}
        onchange={(v) => { productFilter = v; }}
        options={productOptions}
      />
      <FilterSelect
        label="Status"
        value={statusFilter}
        onchange={(v) => { statusFilter = v; }}
        options={[
          { value: 'ACTIVE', label: 'Active' },
          { value: 'COMPLETED', label: 'Completed' },
          { value: 'CANCELLED', label: 'Cancelled' },
          { value: 'ARCHIVED', label: 'Archived' },
        ]}
      />
      <FilterSearch bind:value={searchQuery} placeholder="Search sessions..." class="w-48" />
    {/snippet}
    <span class="ml-auto text-2xs text-text-tertiary shrink-0">
      {pagination.total} sessions
    </span>
  </FilterBar>

  <!-- Selection bar -->
  <SelectionBar
    selectedCount={selectedIds.size}
    totalCount={filteredSessions.length}
    onSelectAll={selectAll}
    onClearSelection={clearSelection}
    actions={[
      { label: 'Archive', icon: Archive, variant: 'ghost' as const, loading: batchLoading, onclick: () => batchAction('archive') },
      { label: 'Delete', icon: Trash2, variant: 'danger' as const, loading: batchLoading, onclick: () => batchAction('delete') },
    ]}
  />

  <!-- Delete confirmation panel -->
  {#if confirmBatchDelete}
    <div class="mb-3 rounded-lg border border-error/30 bg-error-muted px-4 py-3 flex items-center justify-between">
      <span class="text-sm text-text-primary">
        Permanently delete {selectedIds.size} session{selectedIds.size !== 1 ? 's' : ''}? This cannot be undone.
      </span>
      <div class="flex items-center gap-2">
        <button onclick={() => { confirmBatchDelete = false; }} class="btn btn-sm btn-ghost">Cancel</button>
        <button onclick={() => batchAction('delete')} class="btn btn-sm btn-danger" disabled={batchLoading}>
          {batchLoading ? 'Deleting...' : 'Confirm Delete'}
        </button>
      </div>
    </div>
  {/if}

  {#if loading}
    <LoadingState message="Loading sessions..." />
  {:else if filteredSessions.length === 0}
    {@const hasFilters = searchQuery || statusFilter || productFilter}
    <EmptyState message={hasFilters ? 'No sessions match your filters.' : 'No manufacturing sessions yet.'}>
      {#if !hasFilters}
        <p class="text-2xs text-text-tertiary mt-1">Sessions are created when operators start manufacturing on a fixture. <a href="/products" class="text-accent hover:text-accent-hover">Configure manufacturing stages</a> in a product's Manufacturing tab.</p>
      {/if}
    </EmptyState>
  {:else}
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr>
            <th class="table-header w-10">
              <input
                type="checkbox"
                checked={selectedIds.size > 0 && selectedIds.size === filteredSessions.length}
                indeterminate={selectedIds.size > 0 && selectedIds.size < filteredSessions.length}
                onchange={() => selectedIds.size === filteredSessions.length ? clearSelection() : selectAll()}
                class="h-4 w-4 rounded border-border text-accent focus:ring-accent"
              />
            </th>
            <th class="table-header">ID</th>
            <th class="table-header">Product</th>
            <th class="table-header">Fixture</th>
            <th class="table-header">Operator</th>
            <th class="table-header">Status</th>
            <th class="table-header">Runs</th>
            <th class="table-header">Started</th>
            <th class="table-header">Duration</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredSessions as session (session.id)}
            {@const counts = getRunCounts(session)}
            {@const duration = getDuration(session)}
            <tr
              class="table-row cursor-pointer"
              class:opacity-60={session.status === 'ARCHIVED'}
              onclick={() => goto(`/manufacturing/session/${session.id}`)}
            >
              <td class="table-cell" onclick={(e) => e.stopPropagation()}>
                <input
                  type="checkbox"
                  checked={selectedIds.has(session.id)}
                  onchange={() => toggleItem(session.id)}
                  class="h-4 w-4 rounded border-border text-accent focus:ring-accent"
                />
              </td>
              <td class="table-cell">
                <span class="font-mono text-2xs text-text-tertiary">{session.id.slice(0, 8)}</span>
              </td>
              <td class="table-cell">
                <span class="font-medium text-text-primary">{session.product?.name || 'Unknown'}</span>
                <div class="flex flex-wrap gap-1 mt-1">
                  {#if session.fixture}
                    <LinkChip icon={Wrench} href="/fixtures/{session.fixtureId}">{session.fixture.name}</LinkChip>
                  {/if}
                  {#if session.operator}
                    <LinkChip icon={User}>{session.operator.name}</LinkChip>
                  {/if}
                  {#if session.assetSet}
                    <LinkChip icon={Package}>{session.assetSet.version}</LinkChip>
                  {/if}
                  {#if session.status === 'ACTIVE' && session.runnerStatus}
                    <LinkChip icon={Cpu} variant={session.runnerStatus === 'READY' ? 'success' : session.runnerStatus === 'ERROR' ? 'error' : 'warning'}>{session.runnerStatus}</LinkChip>
                  {/if}
                </div>
              </td>
              <td class="table-cell text-text-secondary">
                {session.fixture?.name || '—'}
              </td>
              <td class="table-cell text-text-secondary">
                {session.operator?.name || '—'}
              </td>
              <td class="table-cell">
                <StatusBadge status={session.status} />
              </td>
              <td class="table-cell">
                <div class="flex items-center gap-2">
                  <span class="flex items-center gap-1">
                    <CheckCircle2 size={11} class="text-success" />
                    <span class="text-text-primary font-medium text-2xs">{counts.passed}</span>
                  </span>
                  {#if counts.failed > 0}
                    <span class="flex items-center gap-1 text-error">
                      <XCircle size={11} />
                      <span class="font-medium text-2xs">{counts.failed}</span>
                    </span>
                  {/if}
                  <span class="text-2xs text-text-tertiary">{counts.total} panels</span>
                </div>
              </td>
              <td class="table-cell text-2xs text-text-tertiary">
                {#if session.startedAt}
                  <span title={formatDateTime(session.startedAt)}>
                    {formatTimeAgo(session.startedAt)}
                  </span>
                {:else}
                  —
                {/if}
              </td>
              <td class="table-cell text-2xs text-text-tertiary tabular-nums">
                {duration || '—'}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    {#if pagination.pages > 1}
      <div class="mt-4">
        <Pagination
          page={currentPage}
          totalPages={pagination.pages}
          onPageChange={(page) => { currentPage = page; }}
        />
      </div>
    {/if}
  {/if}
</div>

<SessionCreateWizard
  open={showCreateWizard}
  onClose={() => showCreateWizard = false}
  onStarted={(id) => {
    showCreateWizard = false;
    goto(`/manufacturing/session/${id}`);
  }}
/>
