<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { Search, RefreshCw } from 'lucide-svelte';
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
  import type { ApiResponse } from '$lib/types';

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

      const res = await apiFetch<ApiResponse<{ data: ManufacturingSession[]; pagination: PaginationType }>>(
        '/v2/manufacturing/sessions?' + params.toString()
      );
      sessions = res.data.data;
      pagination = res.data.pagination;
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
    <button onclick={refresh} disabled={refreshing} class="rounded-lg p-2 text-text-secondary hover:bg-surface-2 transition-colors" title="Refresh">
      <RefreshCw size={16} class={refreshing ? 'animate-spin' : ''} />
    </button>
  </div>

  <ErrorAlert message={error} />

  <!-- Filter bar -->
  <div class="mb-4 flex flex-wrap items-center gap-3">
    <FilterSelect
      label="Status"
      value={statusFilter}
      onchange={(v) => { statusFilter = v; }}
      options={[
        { value: '', label: 'All Status' },
        { value: 'ACTIVE', label: 'Active' },
        { value: 'COMPLETED', label: 'Completed' },
        { value: 'CANCELLED', label: 'Cancelled' },
      ]}
    />
    <div class="relative">
      <Search size={14} class="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary" />
      <input
        type="text"
        bind:value={searchQuery}
        placeholder="Search..."
        class="pl-9 pr-3 py-1.5 w-48 text-sm rounded-lg border border-border bg-surface-0 text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
      />
    </div>
    <span class="ml-auto text-2xs text-text-tertiary">
      {pagination.total} sessions
    </span>
  </div>

  {#if loading}
    <LoadingState message="Loading sessions..." />
  {:else if filteredSessions.length === 0}
    <EmptyState message={searchQuery || statusFilter ? 'No sessions match your filters.' : 'No manufacturing sessions found.'} />
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
