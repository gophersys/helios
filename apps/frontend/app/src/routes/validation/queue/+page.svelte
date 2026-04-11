<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    ChevronLeft,
    ChevronRight,
    ChevronsLeft,
    ChevronsRight,
    ArrowUpCircle,
    XCircle,
    Clock,
    RefreshCw,
    ListOrdered,
    BarChart3,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import type { ValidationQueueEntry, QueueStats, QueueEntryStatus } from '$lib/types/queue';
  import type { Pagination } from '$lib/types/models';
  import { STAGE_NAMES } from '$lib/types/stages';
  import { listQueue, cancelQueueEntry, promoteQueueEntry, getQueueStats } from '$lib/services/queue';
  import { formatTimeAgo, formatDateTime, formatDuration } from '$lib/utils/formatting';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import EmptyState from '$lib/components/ui/empty-state.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';
  import FilterBar from '$lib/components/ui/filter-bar.svelte';
  import FilterSelect from '$lib/components/ui/filter-select.svelte';
  import FilterSearch from '$lib/components/ui/filter-search.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('validation:manage'));

  const STATUS_OPTIONS = [
    { value: 'QUEUED', label: 'Queued' },
    { value: 'ASSIGNED', label: 'Assigned' },
    { value: 'RUNNING', label: 'Running' },
    { value: 'COMPLETED', label: 'Completed' },
    { value: 'FAILED', label: 'Failed' },
    { value: 'CANCELLED', label: 'Cancelled' },
  ];

  const STAGE_OPTIONS = [
    { value: '1', label: 'Stage 1 — Smoke' },
    { value: '2', label: 'Stage 2 — Driver' },
    { value: '3', label: 'Stage 3 — Integration' },
    { value: '4', label: 'Stage 4 — Regression' },
    { value: '5', label: 'Stage 5 — Gate' },
  ];

  // State
  let entries = $state<ValidationQueueEntry[]>([]);
  let stats = $state<QueueStats | null>(null);
  let pagination = $state<Pagination>({ page: 1, limit: 25, total: 0, pages: 0 });
  let loading = $state(true);
  let error = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let statusFilter = $state('');
  let stageFilter = $state('');
  let searchQuery = $state('');
  let page = $state(1);
  let refreshTimer: ReturnType<typeof setInterval> | null = null;

  // Filtered entries (client-side search on top of server filters)
  const filteredEntries = $derived.by(() => {
    if (!searchQuery.trim()) return entries;
    const q = searchQuery.toLowerCase().trim();
    return entries.filter((entry) => {
      const pipelineName = entry.buildRun?.name?.toLowerCase() ?? '';
      const product = entry.buildRun?.product?.toLowerCase() ?? '';
      const branch = entry.buildRun?.branch?.toLowerCase() ?? '';
      const fixtureName = entry.fixture?.name?.toLowerCase() ?? '';
      const reason = entry.reason?.toLowerCase() ?? '';
      return (
        pipelineName.includes(q) ||
        product.includes(q) ||
        branch.includes(q) ||
        fixtureName.includes(q) ||
        reason.includes(q) ||
        entry.id.toLowerCase().includes(q)
      );
    });
  });

  function formatWaitTime(entry: ValidationQueueEntry): string {
    const start = new Date(entry.requestedAt).getTime();
    const end = entry.completedAt ? new Date(entry.completedAt).getTime() : Date.now();
    return formatDuration(end - start);
  }

  function priorityColorClass(priority: number): string {
    if (priority >= 80) return 'text-error';
    if (priority >= 50) return 'text-warning';
    if (priority >= 20) return 'text-accent';
    return 'text-text-secondary';
  }

  async function loadQueue(): Promise<void> {
    loading = entries.length === 0;
    error = null;
    try {
      const params: { status?: string; stage?: number; page?: number; limit?: number } = {
        page,
        limit: 25,
      };
      if (statusFilter) params.status = statusFilter;
      if (stageFilter) params.stage = Number(stageFilter);
      const res = await listQueue(params);
      entries = res.data;
      pagination = res.pagination;
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : 'Failed to load queue';
    } finally {
      loading = false;
    }
  }

  async function loadStats(): Promise<void> {
    try {
      stats = await getQueueStats();
    } catch {
      // Stats are non-critical
    }
  }

  async function refresh(): Promise<void> {
    await Promise.all([loadQueue(), loadStats()]);
  }

  async function handleCancel(id: string): Promise<void> {
    actionError = null;
    try {
      await cancelQueueEntry(id);
      await refresh();
    } catch (e: unknown) {
      actionError = e instanceof Error ? e.message : 'Failed to cancel entry';
    }
  }

  async function handlePromote(id: string): Promise<void> {
    actionError = null;
    try {
      await promoteQueueEntry(id);
      await refresh();
    } catch (e: unknown) {
      actionError = e instanceof Error ? e.message : 'Failed to promote entry';
    }
  }

  function startAutoRefresh(): void {
    stopAutoRefresh();
    refreshTimer = setInterval(() => {
      refresh();
    }, 10_000);
  }

  function stopAutoRefresh(): void {
    if (refreshTimer) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('validation:view')) {
      goto('/');
      return;
    }
    refresh();
    startAutoRefresh();
  });

  onDestroy(() => {
    stopAutoRefresh();
  });

  // Re-fetch when filters change
  $effect(() => {
    const _s = statusFilter;
    const _st = stageFilter;
    page = 1;
  });

  $effect(() => {
    const _p = page;
    const _s = statusFilter;
    const _st = stageFilter;
    loadQueue();
  });
</script>

<svelte:head>
  <title>Validation Queue - Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="Validation Queue"
      description="Priority-ranked queue for test bench allocation and scheduling."
    >
      {#snippet actions()}
        <button
          onclick={() => refresh()}
          class="btn btn-sm flex items-center gap-1.5"
          title="Refresh now (auto-refreshes every 10s)"
        >
          <RefreshCw size={14} />
          Refresh
        </button>
      {/snippet}
    </PageHeader>
  </div>

  <!-- Stats cards -->
  {#if stats}
    <div class="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <div class="rounded-lg border border-border bg-surface-0 p-3">
        <div class="flex items-center gap-2">
          <BarChart3 size={14} class="text-text-tertiary" />
          <span class="text-2xs font-medium text-text-tertiary">Total</span>
        </div>
        <div class="mt-2 text-xl font-semibold tabular-nums text-text-primary">{stats.total}</div>
      </div>
      <div class="rounded-lg border border-border bg-surface-0 p-3">
        <div class="flex items-center gap-2">
          <ListOrdered size={14} class="text-text-tertiary" />
          <span class="text-2xs font-medium text-text-tertiary">Queued</span>
        </div>
        <div class="mt-2 text-xl font-semibold tabular-nums text-warning">{stats.byStatus?.QUEUED ?? 0}</div>
      </div>
      <div class="rounded-lg border border-border bg-surface-0 p-3">
        <div class="text-2xs font-medium text-text-tertiary">Assigned</div>
        <div class="mt-2 text-xl font-semibold tabular-nums text-info">{stats.byStatus?.ASSIGNED ?? 0}</div>
      </div>
      <div class="rounded-lg border border-border bg-surface-0 p-3">
        <div class="text-2xs font-medium text-text-tertiary">Running</div>
        <div class="mt-2 text-xl font-semibold tabular-nums text-success">{stats.byStatus?.RUNNING ?? 0}</div>
      </div>
      <div class="rounded-lg border border-border bg-surface-0 p-3">
        <div class="text-2xs font-medium text-text-tertiary">Completed</div>
        <div class="mt-2 text-xl font-semibold tabular-nums text-text-primary">{(stats.byStatus?.COMPLETED ?? 0) + (stats.byStatus?.FAILED ?? 0)}</div>
      </div>
      <div class="rounded-lg border border-border bg-surface-0 p-3">
        <div class="flex items-center gap-2">
          <Clock size={14} class="text-text-tertiary" />
          <span class="text-2xs font-medium text-text-tertiary">Avg Wait</span>
        </div>
        <div class="mt-2 text-xl font-semibold tabular-nums text-text-primary">
          {stats.avgWaitSeconds != null ? formatDuration(stats.avgWaitSeconds * 1000) : '---'}
        </div>
      </div>
    </div>
  {/if}

  <!-- Filter bar -->
  <FilterBar class="mb-4">
    {#snippet filters()}
      <FilterSelect label="Status" value={statusFilter} onchange={(v) => { statusFilter = v; }} options={STATUS_OPTIONS} />
      <FilterSelect label="Stage" value={stageFilter} onchange={(v) => { stageFilter = v; }} options={STAGE_OPTIONS} />
      <FilterSearch bind:value={searchQuery} placeholder="Search build run, product, branch..." class="w-64" />
    {/snippet}
    <span class="ml-auto text-2xs text-text-tertiary shrink-0">
      {filteredEntries.length} of {pagination.total} entries
      <span class="ml-1 opacity-60">| auto-refreshing</span>
    </span>
  </FilterBar>

  <ErrorAlert message={error} />
  <ErrorAlert message={actionError} />

  <!-- Table -->
  {#if loading}
    <LoadingState message="Loading queue entries..." />
  {:else if filteredEntries.length === 0}
    <EmptyState message={searchQuery ? 'No entries match your search.' : 'Queue is empty. Entries appear when build runs request validation.'} />
  {:else}
    <div class="overflow-hidden rounded-lg border border-border">
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-border bg-surface-2">
              <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Priority</th>
              <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Stage</th>
              <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Pipeline</th>
              <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Status</th>
              <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Bench</th>
              <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Requested</th>
              <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Wait Time</th>
              {#if canManage}
                <th class="px-4 py-2.5 text-right text-2xs font-medium uppercase tracking-wider text-text-tertiary">Actions</th>
              {/if}
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each filteredEntries as entry (entry.id)}
              <tr class="transition-colors hover:bg-surface-2">
                <!-- Priority -->
                <td class="px-4 py-3">
                  <span class="font-mono text-sm font-bold tabular-nums {priorityColorClass(entry.priority)}">
                    {entry.priority}
                  </span>
                </td>

                <!-- Stage -->
                <td class="px-4 py-3">
                  <div class="flex items-center gap-2">
                    <span class="flex h-5 w-5 items-center justify-center rounded bg-surface-2 text-2xs font-bold text-text-secondary">
                      {entry.stage}
                    </span>
                    <span class="text-sm text-text-primary">{STAGE_NAMES[entry.stage] ?? `Stage ${entry.stage}`}</span>
                  </div>
                </td>

                <!-- Pipeline -->
                <td class="px-4 py-3">
                  {#if entry.buildRun}
                    <a
                      href="/builds/runs/{entry.buildRunId}"
                      class="text-sm font-medium text-accent hover:underline"
                    >
                      {entry.buildRun.name ?? entry.buildRunId.slice(0, 8)}
                    </a>
                    <div class="mt-0.5 text-2xs text-text-tertiary">
                      {entry.buildRun.product} / {entry.buildRun.branch}
                    </div>
                  {:else}
                    <span class="font-mono text-sm text-text-tertiary">{entry.buildRunId.slice(0, 12)}</span>
                  {/if}
                </td>

                <!-- Status -->
                <td class="px-4 py-3">
                  <StatusBadge status={entry.status} />
                  {#if entry.errorMessage}
                    <div class="mt-1 max-w-[200px] truncate text-2xs text-error" title={entry.errorMessage}>
                      {entry.errorMessage}
                    </div>
                  {/if}
                </td>

                <!-- Fixture -->
                <td class="px-4 py-3">
                  {#if entry.fixture}
                    <span class="text-sm text-text-primary">{entry.fixture.name}</span>
                    {#if entry.fixture.stationId}
                      <div class="text-2xs text-text-tertiary">{entry.fixture.stationId}</div>
                    {/if}
                  {:else}
                    <span class="text-sm text-text-tertiary">---</span>
                  {/if}
                </td>

                <!-- Requested -->
                <td class="px-4 py-3">
                  <span class="text-sm text-text-secondary" title={formatDateTime(entry.requestedAt)}>
                    {formatTimeAgo(entry.requestedAt)}
                  </span>
                </td>

                <!-- Wait Time -->
                <td class="px-4 py-3">
                  <span class="font-mono text-sm tabular-nums text-text-tertiary">
                    {formatWaitTime(entry)}
                  </span>
                </td>

                <!-- Actions -->
                {#if canManage}
                  <td class="px-4 py-3 text-right">
                    {#if entry.status === 'QUEUED'}
                      <div class="flex items-center justify-end gap-1">
                        <button
                          onclick={() => handlePromote(entry.id)}
                          class="btn btn-sm btn-secondary gap-1"
                          title="Boost priority +50"
                        >
                          <ArrowUpCircle size={12} />
                          Promote
                        </button>
                        <button
                          onclick={() => handleCancel(entry.id)}
                          class="btn btn-sm btn-danger gap-1"
                          title="Cancel this queue entry"
                        >
                          <XCircle size={12} />
                          Cancel
                        </button>
                      </div>
                    {:else if entry.status === 'ASSIGNED'}
                      <div class="flex items-center justify-end gap-1">
                        <button
                          onclick={() => handleCancel(entry.id)}
                          class="btn btn-sm btn-danger gap-1"
                          title="Cancel this queue entry"
                        >
                          <XCircle size={12} />
                          Cancel
                        </button>
                      </div>
                    {/if}
                  </td>
                {/if}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Pagination -->
    {#if pagination.pages > 1}
      <div class="mt-4 flex items-center justify-between">
        <span class="text-2xs text-text-tertiary">
          Page {pagination.page} of {pagination.pages} ({pagination.total} total)
        </span>
        <div class="flex items-center gap-1">
          <button
            onclick={() => (page = 1)}
            disabled={page <= 1}
            aria-label="First page"
            class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
          >
            <ChevronsLeft size={16} />
          </button>
          <button
            onclick={() => (page = Math.max(1, page - 1))}
            disabled={page <= 1}
            aria-label="Previous page"
            class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            onclick={() => (page = Math.min(pagination.pages, page + 1))}
            disabled={page >= pagination.pages}
            aria-label="Next page"
            class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
          >
            <ChevronRight size={16} />
          </button>
          <button
            onclick={() => (page = pagination.pages)}
            disabled={page >= pagination.pages}
            aria-label="Last page"
            class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
          >
            <ChevronsRight size={16} />
          </button>
        </div>
      </div>
    {/if}
  {/if}
</div>
