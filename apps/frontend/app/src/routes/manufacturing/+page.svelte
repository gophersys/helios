<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    Search,
    RefreshCw,
    Factory,
    ClipboardList,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import {
    PageHeader,
    ErrorAlert,
    EmptyState,
    LoadingState,
    Tabs,
    StatusBadge,
  } from '$lib/components/ui';
  import FilterSelect from '$lib/components/ui/filter-select.svelte';
  import Pagination from '$lib/components/ui/pagination.svelte';
  import FixtureCard from '$lib/components/manufacturing/fixture-card.svelte';
  import SessionCard from '$lib/components/manufacturing/session-card.svelte';
  import type {
    ManufacturingFixture,
    ManufacturingSession,
    Pagination as PaginationType,
  } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  const auth = getAuth();
  const canRun = $derived(auth.hasPermission('manufacturing:run'));

  // Tab state
  let activeTab = $state('fixtures');
  const tabs = [
    { id: 'fixtures', label: 'Fixtures', icon: Factory },
    { id: 'sessions', label: 'Sessions', icon: ClipboardList },
  ];

  // Fixtures state
  let fixtures = $state<ManufacturingFixture[]>([]);
  let fixturesLoading = $state(true);
  let fixturesError = $state<string | null>(null);

  // Sessions state
  let sessions = $state<ManufacturingSession[]>([]);
  let sessionsLoading = $state(true);
  let sessionsError = $state<string | null>(null);
  let sessionsPagination = $state<PaginationType>({ page: 1, limit: 25, total: 0, pages: 0 });
  let sessionsPage = $state(1);
  let statusFilter = $state('');
  let searchQuery = $state('');
  let refreshing = $state(false);

  // Auto-refresh
  let refreshInterval: ReturnType<typeof setInterval> | null = null;

  // Filtered sessions (client-side search)
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

  async function fetchFixtures() {
    fixturesError = null;
    try {
      const res = await apiFetch<ApiResponse<{ data: ManufacturingFixture[] }>>(
        '/v2/manufacturing/fixtures'
      );
      const payload = res.data;
      fixtures = Array.isArray(payload) ? payload : (payload as { data: ManufacturingFixture[] }).data || [];
    } catch (err) {
      fixturesError = err instanceof Error ? err.message : 'Failed to load fixtures';
    } finally {
      fixturesLoading = false;
    }
  }

  async function fetchSessions() {
    sessionsError = null;
    try {
      const params = new URLSearchParams();
      params.set('page', String(sessionsPage));
      params.set('limit', '25');
      if (statusFilter) params.set('status', statusFilter);

      const res = await apiFetch<ApiResponse<{ data: ManufacturingSession[]; pagination: PaginationType }>>(
        '/v2/manufacturing/sessions?' + params.toString()
      );
      sessions = res.data.data;
      sessionsPagination = res.data.pagination;
    } catch (err) {
      sessionsError = err instanceof Error ? err.message : 'Failed to load sessions';
    } finally {
      sessionsLoading = false;
      refreshing = false;
    }
  }

  async function startSession(fixtureId: string) {
    fixturesError = null;
    try {
      const res = await api.post<ApiResponse<ManufacturingSession>>(
        '/v2/manufacturing/sessions',
        { fixtureId }
      );
      const session = (res as any).data;
      if (session?.id) {
        goto(`/manufacturing/session/${session.id}`);
      } else {
        await fetchFixtures();
      }
    } catch (err) {
      fixturesError = err instanceof Error ? err.message : 'Failed to start session';
    }
  }

  function refresh() {
    refreshing = true;
    if (activeTab === 'fixtures') {
      fetchFixtures();
    } else {
      fetchSessions();
    }
  }

  onMount(() => {
    if (!auth.hasPermission('manufacturing:view')) {
      goto('/');
      return;
    }
    fetchFixtures();
    fetchSessions();
    refreshInterval = setInterval(() => {
      fetchFixtures();
      fetchSessions();
    }, 15000);
  });

  onDestroy(() => {
    if (refreshInterval) clearInterval(refreshInterval);
  });

  // Re-fetch sessions on filter/page changes
  $effect(() => {
    const _p = sessionsPage;
    fetchSessions();
  });
  $effect(() => {
    const _s = statusFilter;
    sessionsPage = 1;
  });
</script>

<svelte:head>
  <title>Manufacturing — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6 flex items-start justify-between">
    <PageHeader
      title="Manufacturing"
      description="Track and manage manufacturing sessions across your products."
    />
    <button onclick={refresh} disabled={refreshing} class="rounded-lg p-2 text-text-secondary hover:bg-surface-2 transition-colors" title="Refresh">
      <RefreshCw size={16} class={refreshing ? 'animate-spin' : ''} />
    </button>
  </div>

  <div class="mb-4">
    <Tabs {tabs} bind:activeTab />
  </div>

  <!-- Fixtures Tab -->
  {#if activeTab === 'fixtures'}
    <ErrorAlert message={fixturesError} />

    {#if fixturesLoading}
      <LoadingState message="Loading fixtures..." />
    {:else if fixtures.length === 0}
      <EmptyState message="No manufacturing fixtures configured yet." />
    {:else}
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {#each fixtures as fixture (fixture.id)}
          <FixtureCard {fixture} {canRun} onStartSession={startSession} />
        {/each}
      </div>
    {/if}
  {/if}

  <!-- Sessions Tab -->
  {#if activeTab === 'sessions'}
    <ErrorAlert message={sessionsError} />

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
        {sessionsPagination.total} sessions
      </span>
    </div>

    {#if sessionsLoading}
      <LoadingState message="Loading sessions..." />
    {:else if filteredSessions.length === 0}
      <EmptyState message={searchQuery || statusFilter ? 'No sessions match your filters.' : 'No manufacturing sessions found.'} />
    {:else}
      <div class="divide-y divide-border-subtle rounded-lg border border-border bg-surface-0">
        {#each filteredSessions as session (session.id)}
          <SessionCard {session} />
        {/each}
      </div>

      {#if sessionsPagination.pages > 1}
        <div class="mt-4">
          <Pagination
            page={sessionsPage}
            totalPages={sessionsPagination.pages}
            onPageChange={(page) => { sessionsPage = page; }}
          />
        </div>
      {/if}
    {/if}
  {/if}
</div>
