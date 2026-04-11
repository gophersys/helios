<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    ChevronDown,
    ChevronRight,
    ChevronLeft,
    ChevronsLeft,
    ChevronsRight,
    Search,
    Calendar,
    X,
    ArrowRight,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch } from '$lib/api';
  import type { AuditEntry, Pagination } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import { formatTimeAgo, formatDateTime } from '$lib/utils/formatting';
  import EmptyState from '$lib/components/ui/empty-state.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';
  import FilterBar from '$lib/components/ui/filter-bar.svelte';
  import FilterSelect from '$lib/components/ui/filter-select.svelte';
  import FilterSearch from '$lib/components/ui/filter-search.svelte';

  const auth = getAuth();

  // Action verb → past tense for display
  function getVerbPastTense(verb: string): string {
    const map: Record<string, string> = {
      create: 'created',
      update: 'updated',
      delete: 'deleted',
      deactivate: 'deactivated',
      register: 'registered',
      unregister: 'unregistered',
      upload: 'uploaded',
      trigger: 'triggered',
      cancel: 'cancelled',
      complete: 'completed',
      assign: 'assigned',
      unassign: 'unassigned',
      deploy: 'deployed',
      undeploy: 'undeployed',
      lock: 'locked',
      unlock: 'unlocked',
      login: 'logged in',
      promote: 'promoted',
      schedule: 'scheduled',
      sync: 'synced',
      start: 'started',
      end: 'ended',
      rerun: 'reran',
      retrigger: 'retriggered',
      reset: 'reset',
      cleanup: 'cleaned up',
    };
    return map[verb] || verb;
  }

  function formatAction(action: string): { verb: string; entity: string } {
    const parts = action.split('.');
    if (parts.length >= 2) {
      const verb = parts[parts.length - 1];
      const entity = parts.slice(0, -1).join(' ');
      return { verb: getVerbPastTense(verb), entity };
    }
    return { verb: action, entity: '' };
  }

  // Color coding for action categories
  function getActionColor(action: string): string {
    if (action.includes('create') || action.includes('register')) return 'text-success';
    if (action.includes('delete') || action.includes('deactivate') || action.includes('cleanup')) return 'text-error';
    if (action.includes('login')) return 'text-accent';
    return 'text-text-primary';
  }

  let entries = $state<AuditEntry[]>([]);
  let pagination = $state<Pagination>({ page: 1, limit: 50, total: 0, pages: 0 });
  let entityTypes = $state<string[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let expandedId = $state<string | null>(null);

  // Filters
  let entityType = $state('');
  let actionSearch = $state('');
  let dateFrom = $state('');
  let dateTo = $state('');
  let page = $state(1);

  async function fetchEntityTypes(): Promise<void> {
    try {
      const res = await apiFetch<ApiResponse<string[]>>('/v2/system/history/entity-types');
      entityTypes = res.data;
    } catch {
      // Fallback silently — filter will still work with manual input
    }
  }

  async function fetchHistory(): Promise<void> {
    loading = true;
    error = null;
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('limit', '50');
      if (entityType) params.set('entityType', entityType);
      if (actionSearch) params.set('action', actionSearch);
      if (dateFrom) params.set('from', new Date(dateFrom).toISOString());
      if (dateTo) params.set('to', new Date(dateTo + 'T23:59:59').toISOString());

      const res = await apiFetch<ApiResponse<{ data: AuditEntry[]; pagination: Pagination }>>(
        '/v2/system/history?' + params.toString()
      );

      entries = res.data.data;
      pagination = res.data.pagination;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load history';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('system:view')) {
      goto('/');
      return;
    }
    fetchEntityTypes();
    fetchHistory();
  });

  // Refetch when page changes
  $effect(() => {
    const _p = page;
    fetchHistory();
  });

  // Reset to page 1 when filters change
  $effect(() => {
    const _et = entityType;
    const _as = actionSearch;
    const _df = dateFrom;
    const _dt = dateTo;
    page = 1;
  });

  function toggleExpand(id: string): void {
    expandedId = expandedId === id ? null : id;
  }

  function clearFilters(): void {
    entityType = '';
    actionSearch = '';
    dateFrom = '';
    dateTo = '';
    page = 1;
  }

  const hasActiveFilters = $derived(!!entityType || !!actionSearch || !!dateFrom || !!dateTo);
</script>

{#snippet DiffValue(label: string, value: unknown)}
  <div>
    <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">{label}</div>
    <div class="mt-0.5 text-sm">
      {#if value === null || value === undefined}
        <span class="text-text-tertiary italic">null</span>
      {:else if typeof value === 'boolean'}
        <span class={value ? 'text-success' : 'text-error'}>{String(value)}</span>
      {:else if typeof value === 'object'}
        <pre class="mt-1 max-h-40 overflow-auto rounded bg-surface-0 p-2 text-2xs text-text-secondary">{JSON.stringify(value, null, 2)}</pre>
      {:else}
        <span class="text-text-primary">{String(value)}</span>
      {/if}
    </div>
  </div>
{/snippet}

{#snippet BeforeAfterDiff(details: Record<string, unknown>)}
  {#if details.before && details.after && typeof details.before === 'object' && typeof details.after === 'object'}
    <div class="grid grid-cols-2 gap-4">
      <div>
        <div class="mb-2 text-xs font-semibold text-error">Before</div>
        <div class="space-y-2">
          {#each Object.entries(details.before as Record<string, unknown>) as [key, value]}
            {@render DiffValue(key, value)}
          {/each}
        </div>
      </div>
      <div>
        <div class="mb-2 text-xs font-semibold text-success">After</div>
        <div class="space-y-2">
          {#each Object.entries(details.after as Record<string, unknown>) as [key, value]}
            {@render DiffValue(key, value)}
          {/each}
        </div>
      </div>
    </div>
  {:else}
    <div class="grid grid-cols-2 gap-x-8 gap-y-3">
      {#each Object.entries(details) as [key, value]}
        {@render DiffValue(key, value)}
      {/each}
    </div>
  {/if}
{/snippet}

<svelte:head>
  <title>History — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="History"
      description="System-wide audit log — every create, update, and delete across the platform."
    />
  </div>

  <ErrorAlert message={error} />

  <!-- Filters -->
  <FilterBar class="mb-4">
    {#snippet filters()}
      <FilterSearch bind:value={actionSearch} placeholder="Search actions..." class="w-48" />
      <FilterSelect label="Entity" value={entityType} onchange={(v) => { entityType = v; }} options={entityTypes.map(t => ({ value: t, label: t }))} />
      <div class="flex items-center gap-1.5">
        <div class="relative">
          <Calendar size={14} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-tertiary pointer-events-none" />
          <input
            type="date"
            bind:value={dateFrom}
            aria-label="From date"
            class="rounded-md border border-border bg-surface-0 py-1.5 pl-8 pr-2 text-xs text-text-primary transition-colors hover:border-text-tertiary focus:border-accent focus:outline-hidden"
          />
        </div>
        <ArrowRight size={14} class="text-text-tertiary" />
        <input
          type="date"
          bind:value={dateTo}
          aria-label="To date"
          class="rounded-md border border-border bg-surface-0 px-2 py-1.5 text-xs text-text-primary transition-colors hover:border-text-tertiary focus:border-accent focus:outline-hidden"
        />
      </div>
    {/snippet}
    <span class="ml-auto text-2xs text-text-tertiary shrink-0">
      {pagination.total.toLocaleString()} entries
    </span>
  </FilterBar>

  <!-- Table -->
  {#if loading}
    <LoadingState message="Loading history..." />
  {:else if entries.length === 0}
    <EmptyState message="No audit entries found." />
  {:else}
    <div class="overflow-hidden rounded-lg border border-border">
      <table class="w-full">
        <thead>
          <tr class="border-b border-border bg-surface-2">
            <th class="w-8 px-3 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary"></th>
            <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Action</th>
            <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Entity</th>
            <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">User</th>
            <th class="px-4 py-2.5 text-right text-2xs font-medium uppercase tracking-wider text-text-tertiary">When</th>
          </tr>
        </thead>
        <tbody>
          {#each entries as entry (entry.id)}
            {@const isExpanded = expandedId === entry.id}
            {@const { verb, entity } = formatAction(entry.action)}
            {@const hasDetails = entry.details && Object.keys(entry.details).length > 0}

            <tr class="border-b border-border-subtle last:border-0">
              <td colspan="5" class="p-0">
                <div>
                  <button
                    onclick={() => hasDetails && toggleExpand(entry.id)}
                    class="flex w-full items-center text-left transition-colors {hasDetails
                      ? 'cursor-pointer hover:bg-surface-2'
                      : 'cursor-default'}"
                  >
                    <div class="w-8 shrink-0 px-3 py-3 flex items-center">
                      {#if hasDetails}
                        {#if isExpanded}
                          <ChevronDown size={16} class="text-text-tertiary" />
                        {:else}
                          <ChevronRight size={16} class="text-text-tertiary" />
                        {/if}
                      {/if}
                    </div>
                    <div class="flex-1 px-4 py-3 flex items-center gap-1">
                      <span class="font-medium {getActionColor(entry.action)}">{verb}</span>
                      {#if entity}
                        <span class="text-text-secondary">{entity}</span>
                      {/if}
                    </div>
                    <div class="shrink-0 px-4 py-3 flex items-center gap-2">
                      <span class="inline-flex items-center rounded-full bg-surface-2 px-2 py-0.5 text-2xs font-medium text-text-secondary">
                        {entry.entityType}
                      </span>
                      {#if entry.entityId}
                        <span class="font-mono text-2xs text-text-tertiary">
                          {entry.entityId.length > 12
                            ? entry.entityId.slice(0, 12) + '…'
                            : entry.entityId}
                        </span>
                      {/if}
                    </div>
                    <div class="shrink-0 px-4 py-3 flex items-center">
                      {#if entry.user}
                        <span class="text-sm text-text-secondary">{entry.user.name}</span>
                      {:else}
                        <span class="text-sm text-text-tertiary italic">System</span>
                      {/if}
                    </div>
                    <div class="shrink-0 px-4 py-3 flex items-center justify-end">
                      <span class="text-sm text-text-tertiary" title={formatDateTime(entry.createdAt)}>
                        {formatTimeAgo(entry.createdAt)}
                      </span>
                    </div>
                  </button>

                  <!-- Expanded details -->
                  {#if isExpanded && hasDetails}
                    <div class="border-t border-border-subtle bg-surface-1 px-12 py-4">
                      {@render BeforeAfterDiff(entry.details!)}
                      <div class="mt-4 flex items-center gap-4 border-t border-border-subtle pt-3 text-2xs text-text-tertiary">
                        <span>{formatDateTime(entry.createdAt)}</span>
                        {#if entry.ipAddress}
                          <span>IP: {entry.ipAddress}</span>
                        {/if}
                        <span class="font-mono">{entry.id}</span>
                      </div>
                    </div>
                  {/if}
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  <!-- Pagination -->
  {#if pagination.pages > 1}
    <div class="mt-4 flex items-center justify-between">
      <span class="text-2xs text-text-tertiary">
        Page {pagination.page} of {pagination.pages}
      </span>
      <div class="flex items-center gap-1">
        <button
          onclick={() => (page = 1)}
          disabled={page <= 1}
          aria-label="First page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30"
        >
          <ChevronsLeft size={16} />
        </button>
        <button
          onclick={() => (page = Math.max(1, page - 1))}
          disabled={page <= 1}
          aria-label="Previous page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30"
        >
          <ChevronLeft size={16} />
        </button>
        <button
          onclick={() => (page = Math.min(pagination.pages, page + 1))}
          disabled={page >= pagination.pages}
          aria-label="Next page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30"
        >
          <ChevronRight size={16} />
        </button>
        <button
          onclick={() => (page = pagination.pages)}
          disabled={page >= pagination.pages}
          aria-label="Last page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30"
        >
          <ChevronsRight size={16} />
        </button>
      </div>
    </div>
  {/if}
</div>
