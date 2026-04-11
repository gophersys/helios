<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { RefreshCw } from 'lucide-svelte';
  import FilterBar from '$lib/components/ui/filter-bar.svelte';
  import FilterSearch from '$lib/components/ui/filter-search.svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch } from '$lib/api';
  import {
    PageHeader,
    ErrorAlert,
    EmptyState,
    LoadingState,
  } from '$lib/components/ui';
  import FilterSelect from '$lib/components/ui/filter-select.svelte';
  import Pagination from '$lib/components/ui/pagination.svelte';
  import SessionCard from '$lib/components/manufacturing/session-card.svelte';
  import type {
    ManufacturingSession,
    Pagination as PaginationType,
  } from '$lib/types/models';

  const auth = getAuth();

  let sessions = $state<ManufacturingSession[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let pagination = $state<PaginationType>({ page: 1, limit: 25, total: 0, pages: 0 });
  let currentPage = $state(1);
  let statusFilter = $state('');
  let searchQuery = $state('');
  let refreshing = $state(false);

  let refreshInterval: ReturnType<typeof setInterval> | null = null;

  const filteredSessions = $derived.by(() => {
    let result = sessions;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (s) =>
          s.product?.name?.toLowerCase().includes(q) ||
          s.fixture?.name?.toLowerCase().includes(q) ||
          (s.operator?.name || s.operatorName || '').toLowerCase().includes(q)
      );
    }
    return result;
  });

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
    <button onclick={refresh} disabled={refreshing} class="btn btn-ghost btn-sm btn-icon" title="Refresh">
      <RefreshCw size={16} class={refreshing ? 'animate-spin' : ''} />
    </button>
  </div>

  <ErrorAlert message={error} />

  <!-- Filter bar -->
  <FilterBar class="mb-4">
    {#snippet filters()}
      <FilterSelect
        label="Status"
        value={statusFilter}
        onchange={(v) => { statusFilter = v; }}
        options={[
          { value: 'ACTIVE', label: 'Active' },
          { value: 'COMPLETED', label: 'Completed' },
          { value: 'CANCELLED', label: 'Cancelled' },
        ]}
      />
      <FilterSearch bind:value={searchQuery} placeholder="Search sessions..." class="w-48" />
    {/snippet}
    <span class="ml-auto text-2xs text-text-tertiary shrink-0">
      {pagination.total} sessions
    </span>
  </FilterBar>

  {#if loading}
    <LoadingState message="Loading sessions..." />
  {:else if filteredSessions.length === 0}
    {@const hasFilters = searchQuery || statusFilter}
    <EmptyState message={hasFilters ? 'No sessions match your filters.' : 'No manufacturing sessions yet.'}>
      {#if !hasFilters}
        <p class="text-2xs text-text-tertiary mt-1">Sessions are created when operators start manufacturing on a fixture. <a href="/products" class="text-accent hover:text-accent-hover">Configure manufacturing stages</a> in a product's Manufacturing tab.</p>
      {/if}
    </EmptyState>
  {:else}
    <div class="divide-y divide-border-subtle rounded-lg border border-border bg-surface-0">
      {#each filteredSessions as session (session.id)}
        <SessionCard {session} />
      {/each}
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
